from pydantic import EncodedBytes
import torn_api
import excel_generator
import pdf_convertor
import memory_db
import requests
import time

def run_payout_logic(api_key, total_payout_cash, medical_cost, assist_pay, outside_hit_val, outside_hit_limit, manual_war_id=None):
    # 1. Setup & Bulk Level Fetching
    key_info = torn_api.get_key_info(api_key)
    if not key_info:
        raise ValueError("Invalid API Key or Torn API is down.")
    f_id = key_info['faction_id']
    
    member_levels = torn_api.get_faction_levels(api_key, f_id)
    
    war_info = torn_api.get_latest_war_id(api_key)
    war_id = manual_war_id if manual_war_id else (war_info['id'] if war_info else None)
    
    if not war_id:
        raise ValueError("No ranked war found for this faction.")
    
    my_faction_report, opponent_name, start_ts, end_ts = torn_api.get_war_report_data(api_key, war_id, f_id)
    
    if not my_faction_report:
        raise ValueError(f"Could not fetch war report for War ID {war_id}.")
    
    # Create a set of our actual faction member IDs as strings for quick filtering
    faction_member_ids = {str(m['id']) for m in my_faction_report['members']}
    
    # NESTED HELPER: Fetches raw individual attacks for the post-war overflow interval
    def get_post_war_attacks(start_time, end_time):
        attacks = [] 
        current_to = end_time
        base_uri = "https://api.torn.com/v2/"
        while True:
            url = f"{base_uri}faction/attacks?from={start_time}&to={current_to}&key={api_key}"
            try:
                res = requests.get(url).json()
                if "error" in res:
                    break
                batch = res.get("attacks", []) 
                if not batch:
                    break
                
                added = 0
                oldest_ts = current_to
                for atk_data in batch: 
                    attacks.append(atk_data)
                    ts = atk_data.get("timestamp_ended", atk_data.get("timestamp_started", current_to))
                    if ts < oldest_ts:
                        oldest_ts = ts
                    added += 1
                
                if added < 100:
                    break
                current_to = oldest_ts - 1
                if current_to < start_time:
                    break
            except:
                break
        return attacks

    # 2. Process All Chains in War Period
    chains = torn_api.get_chains_for_war(api_key, start_ts, end_ts)
    print(f"📊 Found {len(chains)} chains within the war window.")
    
    total_chain_attacks = {}
    total_chain_assists = {}
    bonus_table_data = []
    
    # Sort chains by ID ascending to process them chronologically
    sorted_chains = sorted(chains, key=lambda x: x['id'])
    
    for c in sorted_chains:
        c_report = torn_api.get_chain_report(api_key, c['id'])
        if not c_report:
            continue
            
        print(f"  🔗 Processing Chain {c['id']} ({c_report.get('details', {}).get('chain', 0)} hits)...")
            
        # Extract details
        chain_start = c_report.get('start', 0)
        chain_end = c_report.get('end', 0)
        is_ongoing = (chain_end == 0)
        
        # SAFETY SKIP: If an entirely new chain was started after the war ended, skip it completely
        if end_ts > 0 and chain_start > end_ts:
            print(f"    ⚠️ Skipping Chain {c['id']}: Started after war ended.")
            continue
            
        post_war_hits = {}
        post_war_assists = {}
        post_war_attacks_list = []
        
        # Identify post-war hits if this chain overflows the war window
        if end_ts > 0 and (chain_end > end_ts or is_ongoing):
            print(f"    📍 Chain {c['id']} detected as Overflow Chain. Calculating post-war deductions...")
            fetch_end = chain_end if not is_ongoing else int(time.time())
            post_war_attacks_list = get_post_war_attacks(end_ts + 1, fetch_end)
            
            for atk in post_war_attacks_list:
                if atk.get("attacker") == None:
                    continue
                attacker_id = atk.get("attacker").get("id")
                if attacker_id:
                    u_str = str(attacker_id)
                    if u_str not in faction_member_ids: continue
                        
                    res_str = atk.get("result", "")
                    # FILTER: Only count successful hits/assists done by faction mates
                    if res_str == "Assist":
                        post_war_assists[u_str] = post_war_assists.get(u_str, 0) + 1
                    elif res_str in ["Attacked", "Hospitalized", "Mugged", "Arrested", "Looted"] or atk.get("respect_gain", 0) > 0:
                        post_war_hits[u_str] = post_war_hits.get(u_str, 0) + 1

        # Aggregate hits/assists for this chain, deducting any post-war actions
        for a in c_report.get('attackers', []):
            u_id = a['id']
            u_str = str(u_id)
            
            hit_count = max(0, a.get('attacks', {}).get('total', 0) - post_war_hits.get(u_str, 0))
            asst_count = max(0, a.get('attacks', {}).get('assists', 0) - post_war_assists.get(u_str, 0))
            
            total_chain_attacks[u_id] = total_chain_attacks.get(u_id, 0) + hit_count
            total_chain_assists[u_id] = total_chain_assists.get(u_id, 0) + asst_count
            
        # Track Bonuses, filtering out those that occurred after the war ended
        bonus_count = 0
        for b in c_report.get('bonuses', []):
            # If this is the overflow chain, find the corresponding attack to check its timing
            if post_war_attacks_list:
                is_post_war_bonus = False
                for atk in post_war_attacks_list:
                    # Match by Attacker, Defender, and ensure the attack respect encompasses the bonus
                    if (atk.get('attacker')!= None and 
                        atk.get('attacker').get('id') == b['attacker_id'] and 
                        atk.get('defender').get('id') == b['defender_id'] and
                        atk.get('ended') > end_ts and
                        atk.get('respect_gain', 0) >= b['respect']):
                        is_post_war_bonus = True
                        break
                
                if is_post_war_bonus:
                    continue
                
            u_id = b['attacker_id']
            bonus_table_data.append({
                "u_id": u_id, 
                "defender": b.get('defender_id', 'Unknown'), 
                "deduction": b['respect'], 
                "cid": c['id']
            })
            bonus_count += 1
        print(f"    ✅ Added {bonus_count} valid bonuses from Chain {c['id']}.")

    # 3. Build Member Base Stats with Newbie Logic
    members = {}
    total_newbie_bonus_pool = 0
    
    for m in my_faction_report['members']:
        u_id = m['id']
        war_hits = m['attacks'] 
        chain_hits = total_chain_attacks.get(u_id, 0)
        chain_asst = total_chain_assists.get(u_id, 0)
        outside_hits = max(0, chain_hits - war_hits)
        
        # APPLY LIMIT: Cap the hits at the user-defined limit
        capped_hits = min(outside_hits, outside_hit_limit)
        
        level = member_levels.get(u_id, 100)
        # Bonus is only paid on the capped amount
        n_bonus = (capped_hits * outside_hit_val) if level <= 20 else 0
        total_newbie_bonus_pool += n_bonus
        
        members[u_id] = {
            "name": m['name'], 
            "level": level, # Saved for cache recalculations
            "war_hits": war_hits, 
            "war_assists": chain_asst,
            "outside_hits": outside_hits, # We still show total outside hits in Excel
            "rep_gained": m['score'],
            "newbie_bonus": n_bonus,      # But payout is based on capped_hits
            "total_bonus_val": 0, 
            "net_deduction_sum": 0
        }

    # 4. Calculate Player Averages & Net Deductions (Smoothing)
    for b in bonus_table_data:
        if b['u_id'] in members:
            members[b['u_id']]['total_bonus_val'] += b['deduction']

    for u_id, m in members.items():
        # Player Avg = (Total Rep - All Bonuses) / War Hits
        m['player_avg'] = (m['rep_gained'] - m['total_bonus_val']) / max(1, m['war_hits']) if (m['rep_gained'] - m['total_bonus_val']) / max(1, m['war_hits']) > 0 else 5

    final_bonus_table = []
    total_net_deductions = 0
    for b in bonus_table_data:
        if b['u_id'] not in members: continue
        
        u_id = b['u_id']
        p_avg = members[u_id]['player_avg']
        net_deduct = b['deduction'] - p_avg
        members[u_id]['net_deduction_sum'] += net_deduct
        total_net_deductions += net_deduct
        
        final_bonus_table.append({
            "Attacker": members[u_id]['name'], 
            "Defender": b['defender'], 
            "Deduction": b['deduction'], 
            "Avg rep in chain": round(p_avg, 2),
            "Net deduction": round(net_deduct, 2),
            "Chain link": f"https://www.torn.com/war.php?step=chainreport&chainID={b['cid']}"
        })

    # 5. Final Payout Calculation
    raw_total_rep = my_faction_report['score']
    net_total_rep = raw_total_rep - total_net_deductions
    
    total_assists_count = sum(total_chain_assists.values())
    total_assist_pay = total_assists_count * assist_pay
    payout_pool = (total_payout_cash * 0.9) - medical_cost - total_newbie_bonus_pool - total_assist_pay
    price_per_rep = payout_pool / net_total_rep if net_total_rep > 0 else 0

    return {
        "title": f"WAR :- {my_faction_report['name']} vs {opponent_name}",
        "war_id": war_id,
        "opponent_name": opponent_name,
        "initial_payout": total_payout_cash,
        "medical_cost": medical_cost,
        "newbie_bonus_total": total_newbie_bonus_pool,
        "assist_pay": assist_pay,
        "total_assists": total_assists_count,
        "total_assists_pay": total_assist_pay,
        "total_rep_before": raw_total_rep,
        "total_rep_after": net_total_rep,
        "price_per_rep": price_per_rep,
        "members": list(members.values()),
        "bonuses": final_bonus_table,
        "outside_hit_val": outside_hit_val,
        "outside_hit_limit": outside_hit_limit
    }

def process_war_and_get_files(api_key, total_payout_money, medical_cost, assist_pay, outside_hit_val, outside_hit_limit):
    # 1. Get the data once (Uses cache-friendly router)
    data = process_war_request(api_key, total_payout_money, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    
    clean_opp_name = data['opponent_name'].replace(" ", "")
    base_name = f"War_Report_{clean_opp_name}_{data['war_id']}"
    
    # 2. Generate Excel (the master)
    xlsx_path = excel_generator.create_payout_excel(data, f"{base_name}.xlsx")
    
    # 3. Generate PDF (the visual mirror)
    pdf_path = pdf_convertor.create_payout_pdf(data, f"{base_name}.pdf")
    
    return [xlsx_path, pdf_path]


# --- ADDITIONS FOR MEMORY & ANALYTICS ---

def recalculate_money(cached_data, new_payout, new_med, new_assist, new_outside_val, new_outside_limit):
    """Updates cash payouts safely, handling both Full and Slim DB caches."""
    cached_data['initial_payout'] = new_payout
    cached_data['medical_cost'] = new_med
    cached_data['assist_pay'] = new_assist
    cached_data['outside_hit_val'] = new_outside_val
    cached_data['outside_hit_limit'] = new_outside_limit
    
    # 1. Recalculate Newbie Bonus and Total Assists Pay
    total_newbie_bonus = 0
    total_assists_count = 0
    
    for m in cached_data.get('members', []):
        # Recalculate Newbie Bonus if we have the level and outside hits
        if 'level' in m and 'outside_hits' in m:
            capped_hits = min(m['outside_hits'], new_outside_limit)
            m['newbie_bonus'] = (capped_hits * new_outside_val) if m['level'] <= 30 else 0
        
        total_newbie_bonus += m.get('newbie_bonus', 0)
        total_assists_count += m.get('war_assists', 0)
    
    cached_data['newbie_bonus_total'] = total_newbie_bonus
    cached_data['total_assists'] = total_assists_count
    cached_data['total_assists_pay'] = total_assists_count * new_assist
    
    # 2. Safely get total respect. If it's a slim cache, we just add up the members' respect manually!
    if 'total_rep_after' in cached_data:
        total_rep = cached_data['total_rep_after']
    else:
        total_rep = sum(m.get('rep_gained', 0) for m in cached_data.get('members', []))
        
    cached_data['total_rep_after'] = total_rep
    
    # Recalculate price per rep pool
    pool = (new_payout * 0.9) - new_med - total_newbie_bonus - cached_data['total_assists_pay']
    cached_data['price_per_rep'] = pool / total_rep if total_rep > 0 else 0
    
    cached_data['_was_cached'] = True
    return cached_data

def process_war_request(api_key, total_payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit, force_update=True):
    """Smart router: Checks cache first, otherwise hits Torn API."""
    war_info = torn_api.get_latest_war_id(api_key)
    current_war_id = war_info['id'] if war_info else None
    
    cached_data = memory_db.get_cached_war(current_war_id) if current_war_id else None
    
    if cached_data and not force_update:
        print(f"🧠 Memory Hit: Loaded War {current_war_id} from DB.")
        return recalculate_money(cached_data, total_payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    
    print("🌍 Memory Miss or Force Update. Fetching from Torn API...")
    final_data = run_payout_logic(api_key, total_payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    final_data['_was_cached'] = False
    
    memory_db.save_war(final_data) 
    return final_data

def generate_files_from_data(data):
    """Generates Excel and PDF from a pre-calculated data dictionary."""
    clean_opp_name = data['opponent_name'].replace(" ", "")
    base_name = f"War_Report_{clean_opp_name}_{data['war_id']}"
    
    xlsx_path = excel_generator.create_payout_excel(data, f"{base_name}.xlsx")
    pdf_path = pdf_convertor.create_payout_pdf(data, f"{base_name}.pdf")
    
    return [xlsx_path, pdf_path]


if __name__ == "__main__":
    test_key = "ArdyKEZzOKwSZ1xy"
    payout = 1950000000 
    medical_cost = 208019200
    assist_pay = 350000

    outside_hit_val = 200000
    outside_hit_limit = 10
    
    # Remember to pass force_update=True when triggering your wrapper to override cached DB entries.
    saved_file = process_war_and_get_files(test_key, payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    print(f"Excel report generated: {saved_file}")