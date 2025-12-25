import pandas as pd

def create_payout_excel(data, total_money, filename="War_Payout.xlsx"):
    # --- 1. DATA PREP ---
    payout_90 = total_money * 0.90
    member_list = data['member_table']
    bonus_list = data['bonus_table']
    
    # Calculate Price Per Rep
    total_rep_after_deductions = sum(m['final_rep'] for m in member_list)
    price_per_rep = payout_90 / total_rep_after_deductions if total_rep_after_deductions > 0 else 0

    # Convert to DataFrames
    df_members = pd.DataFrame(member_list)
    # Calculate individual payouts
    df_members['payout'] = df_members['final_rep'] * price_per_rep
    
    # Select and rename columns for the Excel sheet
    df_members = df_members[['name', 'attacks', 'raw_rep', 'deductions', 'final_rep', 'payout']]
    df_members.columns = ['Member Name', 'Attacks', 'Rep Gained', 'Chain Deduction', 'Rep after Deductions', 'RW Payout']
    df_members = df_members.sort_values(by='RW Payout', ascending=False)

    df_bonuses = pd.DataFrame(bonus_list)

    # --- 2. EXCEL FORMATTING ---
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        workbook = writer.book
        sheet = workbook.add_worksheet('Payout Report')

        # Formats
        money_fmt = workbook.add_format({'num_format': '$#,##0', 'align': 'center'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        num_fmt = workbook.add_format({'num_format': '#,##0.00', 'align': 'center'})

        # Header Info
        sheet.write('A1', 'RW Payout (Initial)', header_fmt)
        sheet.write('B1', total_money, money_fmt)
        sheet.write('A2', 'RW Payout (90%)', header_fmt)
        sheet.write('B2', payout_90, money_fmt)
        sheet.write('A3', 'Price per Rep', header_fmt)
        sheet.write('B3', price_per_rep, num_fmt)

        # Main Table
        start_row = 5
        for col_num, value in enumerate(df_members.columns.values):
            sheet.write(start_row, col_num, value, header_fmt)

        for row_num, row_data in enumerate(df_members.values):
            sheet.write_row(start_row + 1 + row_num, 0, row_data)
            # Format the money column specifically
            sheet.write(start_row + 1 + row_num, 5, row_data[5], money_fmt)

        # Chain Bonus Table (Lower down)
        bonus_start = start_row + len(df_members) + 4
        sheet.write(bonus_start, 0, "Chain Bonuses & Deductions", header_fmt)
        
        if not df_bonuses.empty:
            for col_num, value in enumerate(df_bonuses.columns.values):
                sheet.write(bonus_start + 1, col_num, value, header_fmt)
            for row_num, row_data in enumerate(df_bonuses.values):
                sheet.write_row(bonus_start + 2 + row_num, 0, row_data)

    return filename