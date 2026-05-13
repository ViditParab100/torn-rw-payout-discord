import torn_api
import excel_generator
import pdf_convertor
import memory_db

def run_payout_logic(api_key, total_payout_cash, medical_cost, assist_pay, outside_hit_val, outside_hit_limit, manual_war_id=None):    # 1. Setup & Bulk Level Fetching
    key_info = torn_api.get_key_info(api_key)
    f_id = key_info['faction_id']
    
    member_levels = torn_api.get_faction_levels(api_key, f_id)
    
    war_info = torn_api.get_latest_war_id(api_key)
    war_id = manual_war_id if manual_war_id else war_info['id']
    
    my_faction_report, opponent_name, start_ts, end_ts = torn_api.get_war_report_data(api_key, war_id, f_id)
    
    # 2. Process All Chains in War Period
    chains = torn_api.get_chains_for_war(api_key, start_ts, end_ts)
    total_chain_attacks = {}
    total_chain_assists = {}
    bonus_table_data = []
    
    for c in chains:
        c_report = torn_api.get_chain_report(api_key, c['id'])
        
        # FIX: Access attackers[id] and attacks[total] per the JSON structure
        for a in c_report.get('attackers', []):
            u_id = a['id']
            # Using .get() chain to safely reach the nested 'total' hits
            hit_count = a.get('attacks', {}).get('total', 0)
            asst_count = a.get('attacks', {}).get('assists', 0)
            total_chain_attacks[u_id] = total_chain_attacks.get(u_id, 0) + hit_count
            total_chain_assists[u_id] = total_chain_assists.get(u_id, 0) + asst_count
            
        # FIX: Track Bonuses using defender_id (defender_name is not in chain reports)
        for b in c_report.get('bonuses', []):
            u_id = b['attacker_id']
            bonus_table_data.append({
                "u_id": u_id, 
                "defender": b.get('defender_id', 'Unknown'), # Use ID from the JSON
                "deduction": b['respect'], 
                "cid": c['id']
            })

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
        n_bonus = (capped_hits * outside_hit_val) if level <= 30 else 0
        total_newbie_bonus_pool += n_bonus
        
        members[u_id] = {
            "name": m['name'], 
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
            "Defender": b['defender'], # This will be the Defender ID
            "Deduction": b['deduction'], 
            "Avg rep in chain": round(p_avg, 2),
            "Net deduction": round(net_deduct, 2),
            "Chain link": f"https://www.torn.com/war.php?step=chainreport&chainID={b['cid']}"
        })

    # 5. Final Payout Calculation
    raw_total_rep = my_faction_report['score']
    net_total_rep = raw_total_rep - total_net_deductions
    
    total_assist_pay = sum(total_chain_assists.values()) * assist_pay
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
        "total_assists": sum(total_chain_assists.values()),
        "total_assists_pay": total_assist_pay,
        "total_rep_before": raw_total_rep,
        "total_rep_after": net_total_rep,
        "price_per_rep": price_per_rep,
        "members": list(members.values()),
        "bonuses": final_bonus_table
    }

def process_war_and_get_files(api_key, total_payout_money, medical_cost, assist_pay, outside_hit_val, outside_hit_limit):
    # 1. Get the data once
    data = run_payout_logic(api_key, total_payout_money, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    
    clean_opp_name = data['opponent_name'].replace(" ", "")
    base_name = f"War_Report_{clean_opp_name}_{data['war_id']}"
    
    # 2. Generate Excel (the master)
    xlsx_path = excel_generator.create_payout_excel(data, f"{base_name}.xlsx")
    
    # 3. Generate PDF (the visual mirror)
    pdf_path = pdf_convertor.create_payout_pdf(data, f"{base_name}.pdf")
    
    return [xlsx_path, pdf_path]


# --- NEW ADDITIONS FOR MEMORY & ANALYTICS ---

def recalculate_money(cached_data, new_payout, new_med, new_assist):
    """Updates cash payouts safely, handling both Full and Slim DB caches."""
    cached_data['initial_payout'] = new_payout
    cached_data['medical_cost'] = new_med
    cached_data['assist_pay'] = new_assist
    
    # 1. Safely get assists (Defaults to 0 if this is a slim AI cache)
    total_assists = cached_data.get('total_assists', 0)
    cached_data['total_assists_pay'] = total_assists * new_assist
    
    # 2. Safely get newbie bonus
    newbie_bonus = cached_data.get('newbie_bonus_total', 0)
    
    # 3. Safely get total respect. If it's a slim cache, we just add up the members' respect manually!
    if 'total_rep_after' in cached_data:
        total_rep = cached_data['total_rep_after']
    else:
        total_rep = sum(m.get('rep_gained', 0) for m in cached_data.get('members', []))
        
    cached_data['total_rep_after'] = total_rep
    
    # Recalculate price per rep pool
    pool = (new_payout * 0.9) - new_med - newbie_bonus - cached_data['total_assists_pay']
    cached_data['price_per_rep'] = pool / total_rep if total_rep > 0 else 0
    
    cached_data['_was_cached'] = True # Flag for the Ranger to know
    return cached_data

def process_war_request(api_key, total_payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit, force_update=False):
    """Smart router: Checks cache first, otherwise hits Torn API."""
    # Fast 1-page API call to get current War ID
    war_info = torn_api.get_latest_war_id(api_key)
    current_war_id = war_info['id'] if war_info else None
    
    cached_data = memory_db.get_cached_war(current_war_id) if current_war_id else None
    
    if cached_data and not force_update:
        print(f"🧠 Memory Hit: Loaded War {current_war_id} from DB.")
        # Only recalculate the flat cash amounts (avoids API calls)
        return recalculate_money(cached_data, total_payout, medical_cost, assist_pay)
    
    print("🌍 Memory Miss or Force Update. Fetching from Torn API...")
    # Run the original legacy logic
    final_data = run_payout_logic(api_key, total_payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    final_data['_was_cached'] = False
    
    # Save/Overwrite in the local SQLite memory
    # (In a real app, you might want to delete the old record if force updating, 
    # but sqlite's INSERT will fail peacefully if it exists, so we just let it be 
    # or handle overwriting. For now, it secures the first complete run).
    memory_db.save_war(final_data) 
    return final_data

def generate_files_from_data(data):
    """Generates Excel and PDF from a pre-calculated data dictionary."""
    clean_opp_name = data['opponent_name'].replace(" ", "")
    base_name = f"War_Report_{clean_opp_name}_{data['war_id']}"
    
    xlsx_path = excel_generator.create_payout_excel(data, f"{base_name}.xlsx")
    pdf_path = pdf_convertor.create_payout_pdf(data, f"{base_name}.pdf")
    
    return [xlsx_path, pdf_path]

# Keep your original process_war_and_get_files intact below this so legacy calls don't break!


# Example test
if __name__ == "__main__":
    test_key = "ArdyKEZzOKwSZ1xy"
    payout = 1975000000 # Your example number
    medical_cost = 10000000
    assist_pay = 500000
    outside_hit_val = 10000
    outside_hit_limit = 100
    saved_file = process_war_and_get_files(test_key, payout, medical_cost, assist_pay, outside_hit_val, outside_hit_limit)
    print(f"Excel report generated: {saved_file}")

# Example Usage
# if __name__ == "__main__":
#     test_key = ""
#     results = run_payout_logic(test_key)
#     print(f"Processed {len(results['member_table'])} members.")