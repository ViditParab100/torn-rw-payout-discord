import pandas as pd

def create_payout_excel(data, filename="War_Payout.xlsx"):
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        workbook = writer.book
        sheet = workbook.add_worksheet('Payout')
        
        # --- STYLING ---
        # Lime Green Header Style
        header_fmt = workbook.add_format({
            'bold': True, 
            'bg_color': '#92D050', 
            'border': 1, 
            'align': 'center',
            'valign': 'vcenter'
        })
        money_fmt = workbook.add_format({'num_format': '$#,##0', 'border': 1, 'align': 'center'})
        num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'align': 'center'})
        
        # Set Column Widths (A to H is now 8 columns total)
        sheet.set_column('A:H', 22) 

        # --- Top Summary Section ---
        sheet.write('A1', 'Title', header_fmt); sheet.merge_range('B1:E1', data['title'], header_fmt)
        sheet.write('A2', 'RW Payout (Initial)', header_fmt); sheet.write('B2', data['initial_payout'], money_fmt)
        sheet.write('A3', 'Medical Costs (Deducted)', header_fmt); sheet.write('B3', data['medical_cost'], money_fmt)
        
        # New Summary Row for Newbie Bonus Pool
        sheet.write('A4', 'Newbie Bonus Pool', header_fmt); sheet.write('B4', data['newbie_bonus_total'], money_fmt)
        
        # Pool for Respect calculation
        pool_for_rep = (data['initial_payout'] * 0.9) - data['medical_cost'] - data['newbie_bonus_total']
        sheet.write('A5', 'Final Respect Pool', header_fmt); sheet.write('B5', pool_for_rep, money_fmt)
        
        sheet.write('A6', 'Total Rep (After Ded.)', header_fmt); sheet.write('B6', data['total_rep_after'], num_fmt)
        sheet.write('A7', 'Price per rep', header_fmt); sheet.write('B7', data['price_per_rep'], num_fmt)

        # --- Main Member Table ---
        # Added 'War Hits', 'Outside Hits', and 'Newbie Bonus'
        m_headers = [
            'Member name', 'War Hits', 'Outside Hits', 'Rep gained', 
            'Chain deduction', 'Net Rep', 'Newbie Bonus', 'Final Payout'
        ]
        for c, h in enumerate(m_headers): 
            sheet.write(9, c, h, header_fmt)
        
        row = 10
        # Sort by total payout (Respect share + Newbie Bonus)
        sorted_members = sorted(data['members'], 
                                key=lambda x: ((x['rep_gained'] - x['net_deduction_sum']) * data['price_per_rep']) + x['newbie_bonus'], 
                                reverse=True)
        
        for m in sorted_members:
            net_rep = m['rep_gained'] - m['net_deduction_sum']
            respect_share = net_rep * data['price_per_rep']
            final_total = respect_share + m['newbie_bonus']

            sheet.write(row, 0, m['name'])
            sheet.write(row, 1, m['war_hits'])       # RW target hits
            sheet.write(row, 2, m['outside_hits'])   # Total Chain Hits - War Hits
            sheet.write(row, 3, m['rep_gained'], num_fmt)
            sheet.write(row, 4, m['net_deduction_sum'], num_fmt)
            sheet.write(row, 5, net_rep, num_fmt)
            sheet.write(row, 6, m['newbie_bonus'], money_fmt)
            sheet.write(row, 7, final_total, money_fmt)
            row += 1

        # --- Chain Bonus Table ---
        b_row = row + 3
        sheet.write(b_row, 0, 'Chain Bonus Smoothing Details', header_fmt)
        b_headers = ['Attacker', 'Defender ID', 'Bonus Value', 'Avg Rep (Member)', 'Net Deduction', 'Link']
        for i, h in enumerate(b_headers): 
            sheet.write(b_row + 1, i, h, header_fmt)
        
        row = b_row + 2
        for b in data['bonuses']:
            sheet.write(row, 0, b.get('Attacker', 'Unknown'))
            sheet.write(row, 1, b.get('Defender', 'N/A')) # Changed to Defender ID
            sheet.write(row, 2, b.get('Deduction', 0), num_fmt)
            sheet.write(row, 3, b.get('Avg rep in chain', 0), num_fmt)
            sheet.write(row, 4, b.get('Net deduction', 0), num_fmt)
            # Correct link format for Faction Chain Reports
            c_link = b.get('Chain link', '')
            sheet.write_url(row, 5, c_link, string="View Chain")
            row += 1
            
    return filename