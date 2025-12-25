import torn_api 
import excel_generator

def run_payout_logic(api_key, manual_war_id=None):
    # 1. Identify User/Faction
    info = torn_api.get_key_info(api_key)
    f_id = info['faction_id']

    # 2. Identify the War
    if manual_war_id:
        war_id = manual_war_id
        # We still need the timestamps, so we fetch details
        war_data = torn_api.get_latest_war_id(api_key) # Simple fallback
    else:
        war_data = torn_api.get_latest_war_id(api_key)
        war_id = war_data['id']

    # 3. Get Base Member Stats
    report = torn_api.get_war_report_data(api_key, war_id, f_id)
    members = {m['id']: {"name": m['name'], "attacks": m['attacks'], "raw_rep": m['score'], "deductions": 0} 
               for m in report['members']}

    # 4. Process Chain Deductions
    chains = torn_api.get_chains_for_war(api_key, war_data['start'], war_data['end'])
    bonus_table = []

    for c in chains:
        c_report = torn_api.get_chain_report(api_key, c['id'])
        details = c_report.get('details', {})
        
        # Logic: Avg Rep = Total Respect / Total Hits (fallback to 5)
        avg_rep = (details.get('respect', 0) / details.get('targets', 1)) if details.get('targets', 0) > 0 else 5
        
        for b in c_report.get('bonuses', []):
            attacker_id = b['attacker_id']
            net_deduction = b['respect'] - avg_rep
            
            # Apply deduction to member total
            if attacker_id in members:
                members[attacker_id]['deductions'] += net_deduction

            # Prep data for the Bonus Table UI
            bonus_table.append({
                "name": members.get(attacker_id, {}).get("name", "Unknown"),
                "bonus_hit": b['chain'],
                "net_deduction": round(net_deduction, 2),
                "link": f"https://www.torn.com/war.php?step=chainreport&chainID={c['id']}"
            })

    # 5. Final Calculation
    final_member_stats = []
    for m_id, data in members.items():
        data['final_rep'] = max(0, data['raw_rep'] - data['deductions'])
        final_member_stats.append(data)

    return {
        "member_table": final_member_stats,
        "bonus_table": bonus_table,
        "total_rep_earned": report['rewards']['respect']
    }

def process_war_and_get_file(api_key, total_payout_money, manual_war_id=None):
    # 1. Run the existing logic to get data
    data = run_payout_logic(api_key, manual_war_id)
    
    # 2. Generate the Excel file
    file_path = excel_generator.create_payout_excel(data, total_payout_money)
    
    return file_path

# Example test
if __name__ == "__main__":
    test_key = ""
    payout = 1074411000 # Your example number
    saved_file = process_war_and_get_file(test_key, payout)
    print(f"Excel report generated: {saved_file}")

# Example Usage
# if __name__ == "__main__":
#     test_key = ""
#     results = run_payout_logic(test_key)
#     print(f"Processed {len(results['member_table'])} members.")