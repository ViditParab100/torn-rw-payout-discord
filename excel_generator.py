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
            'align': 'center'
        })
        money_fmt = workbook.add_format({'num_format': '$#,##0', 'border': 1})
        num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        
        # Set Column Widths (Spaced out)
        sheet.set_column('A:F', 20) 

        # --- Top Summary Section ---
        sheet.write('A1', 'Title', header_fmt); sheet.merge_range('B1:E1', data['title'], header_fmt)
        sheet.write('A2', 'RW Payout (Initial)', header_fmt); sheet.write('B2', data['initial_payout'], money_fmt)
        sheet.write('A3', 'Medical Costs (Deducted)', header_fmt); sheet.write('B3', data['medical_cost'], money_fmt)
        sheet.write('A4', 'RW Payout (Final Pool)', header_fmt); sheet.write('B4', (data['initial_payout']*0.9) - data['medical_cost'], money_fmt)
        sheet.write('A5', 'Total Rep (Before)', header_fmt); sheet.write('B5', data['total_rep_before'], num_fmt)
        sheet.write('A6', 'Total Rep (After)', header_fmt); sheet.write('B6', data['total_rep_after'], num_fmt)
        sheet.write('A7', 'Price per rep', header_fmt); sheet.write('B7', data['price_per_rep'], num_fmt)

        # --- Main Member Table ---
        m_headers = ['Member name', 'Attacks', 'Rep gained', 'Chain deduction', 'Rep after deductions', 'RW payout']
        for c, h in enumerate(m_headers): 
            sheet.write(9, c, h, header_fmt)
        
        row = 10
        sorted_members = sorted(data['members'], key=lambda x: x['rep_gained'] - x['net_deduction_sum'], reverse=True)
        for m in sorted_members:
            net_rep = m['rep_gained'] - m['net_deduction_sum']
            sheet.write(row, 0, m['name'])
            sheet.write(row, 1, m['attacks'])
            sheet.write(row, 2, m['rep_gained'], num_fmt)
            sheet.write(row, 3, m['net_deduction_sum'], num_fmt)
            sheet.write(row, 4, net_rep, num_fmt)
            sheet.write(row, 5, net_rep * data['price_per_rep'], money_fmt)
            row += 1

        # --- Chain Bonus Table ---
        b_row = row + 3
        sheet.write(b_row, 0, 'Chain bonuses', header_fmt)
        b_headers = ['Attacker', 'Defender', 'Deduction', 'Avg rep in war', 'Net deduction', 'Chain link']
        for c, h in enumerate(b_headers): 
            sheet.write(b_row + 1, c, h, header_fmt)
        
        row = b_row + 2
        for b in data['bonuses']:
            sheet.write(row, 0, b['Attacker'])
            sheet.write(row, 1, b['Defender'])
            sheet.write(row, 2, b['Deduction'], num_fmt)
            sheet.write(row, 3, b['Avg rep in war'], num_fmt)
            sheet.write(row, 4, b['Net deduction'], num_fmt)
            sheet.write_url(row, 5, b['Chain link'], string="Chain Link")
            row += 1
            
    return filename