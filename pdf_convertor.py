from fpdf import FPDF

class WarPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        # Lime Green Background for Header
        self.set_fill_color(146, 208, 80) 
        self.cell(0, 12, 'TORN WAR PAYOUT REPORT', border=1, ln=1, align='C', fill=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_payout_pdf(data, filename):
    pdf = WarPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # --- 1. TOP SUMMARY SECTION (Matches Excel A1:B10) ---
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_fill_color(146, 208, 80)
    
    # helper to draw summary rows
    def draw_summary_row(label, value, is_money=True):
        pdf.cell(60, 7, label, border=1, fill=True)
        val_str = f"${value:,.0f}" if is_money else f"{value:,.2f}"
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(60, 7, val_str, border=1, ln=1)
        pdf.set_font('Helvetica', 'B', 10)

    pdf.cell(60, 7, "Title", border=1, fill=True)
    pdf.cell(120, 7, data['title'], border=1, ln=1)
    
    draw_summary_row("RW Payout (Initial)", data['initial_payout'])
    draw_summary_row("Medical Costs (Deducted)", data['medical_cost'])
    draw_summary_row("Newbie Bonus Pool", data['newbie_bonus_total'])
    draw_summary_row("Pay Per Assist", data['assist_pay'])
    draw_summary_row("Total Assists Pay", data['total_assists_pay'])
    
    pool_for_rep = (data['initial_payout'] * 0.9) - data['medical_cost'] - data['newbie_bonus_total'] - data['total_assists_pay']
    draw_summary_row("Final Respect Pool", pool_for_rep)
    draw_summary_row("Total Rep (After Ded.)", data['total_rep_after'], False)
    draw_summary_row("Pay per Rep", data['price_per_rep'], False)
    
    pdf.ln(10)

    # --- 2. MAIN MEMBER TABLE (Row 12+) ---
    pdf.set_font('Helvetica', 'B', 8)
    cols = [45, 18, 18, 18, 22, 25, 22, 28, 28, 30] # Fits 277mm Landscape
    headers = ['Member name', 'War Hits', 'Out Hits', 'Assists', 'Rep', 'Chain Ded', 'Net Rep', 'Newbie $', 'Asst $', 'Final $']
    
    for i, h in enumerate(headers):
        pdf.cell(cols[i], 8, h, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    # Mirroring your Excel sorting
    sorted_members = sorted(data['members'], 
                            key=lambda x: ((x['rep_gained'] - x['net_deduction_sum'] if x['rep_gained'] - x['net_deduction_sum'] >0 else 0) * data['price_per_rep']) + x['newbie_bonus'] + x['war_assists'] * data['assist_pay'], 
                            reverse=True)

    for m in sorted_members:
        net_rep = m['rep_gained'] - m['net_deduction_sum'] if m['rep_gained'] - m['net_deduction_sum'] > 0 else 0
        resp_share = net_rep * data['price_per_rep']
        asst_pay = m['war_assists'] * data['assist_pay']
        final = resp_share + m['newbie_bonus'] + asst_pay

        pdf.cell(cols[0], 7, m['name'], border=1)
        pdf.cell(cols[1], 7, str(m['war_hits']), border=1, align='C')
        pdf.cell(cols[2], 7, str(m['outside_hits']), border=1, align='C')
        pdf.cell(cols[3], 7, str(m['war_assists']), border=1, align='C')
        pdf.cell(cols[4], 7, f"{m['rep_gained']:.1f}", border=1, align='R')
        pdf.cell(cols[5], 7, f"{m['net_deduction_sum']:.1f}", border=1, align='R')
        pdf.cell(cols[6], 7, f"{net_rep:.1f}", border=1, align='R')
        pdf.cell(cols[7], 7, f"${m['newbie_bonus']:,.0f}", border=1, align='R')
        pdf.cell(cols[8], 7, f"${asst_pay:,.0f}", border=1, align='R')
        pdf.cell(cols[9], 7, f"${final:,.0f}", border=1, align='R')
        pdf.ln()

    # --- 3. CHAIN BONUS TABLE ---
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 8, "Chain Bonus Correction", border=1, ln=1, fill=True)
    
    pdf.set_font('Helvetica', 'B', 8)
    b_cols = [45, 30, 30, 35, 35, 60]
    b_headers = ['Attacker', 'Defender ID', 'Bonus Val', 'Avg Rep', 'Net Ded', 'Link']
    for i, h in enumerate(b_headers):
        pdf.cell(b_cols[i], 8, h, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font('Helvetica', '', 7)
    for b in data['bonuses']:
        pdf.cell(b_cols[0], 7, b.get('Attacker', 'Unknown'), border=1)
        pdf.cell(b_cols[1], 7, str(b.get('Defender', 'N/A')), border=1)
        pdf.cell(b_cols[2], 7, f"{b.get('Deduction', 0):.2f}", border=1)
        pdf.cell(b_cols[3], 7, f"{b.get('Avg rep in chain', 0):.2f}", border=1)
        pdf.cell(b_cols[4], 7, f"{b.get('Net deduction', 0):.2f}", border=1)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(b_cols[5], 7, "View Chain Link", border=1, link=b.get('Chain link', ''))
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    pdf.output(filename)
    return filename