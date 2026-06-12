"""
Battle Intelligence PDF Report
Per-player attack profiles for both factions using FFScouter battle stats.

Mechanics (Torn):
  Win zone   : attacker_bs >= 1.2 × defender_bs
  Sweet spot : defender_bs / attacker_bs ∈ [0.8, 1.1]  (max respect)
  Risky      : defender_bs >= 1.2 × attacker_bs
"""

from fpdf import FPDF
from datetime import datetime

# ── Page geometry ──────────────────────────────────────────────────────────────
ORIENT = "L"     # A4 landscape
FMT    = "A4"    # 297 × 210 mm
MARGIN = 10
USABLE = 277     # 297 - 2*10

# ── Column widths (sum = 277 mm) ───────────────────────────────────────────────
C_NAME  = 42
C_BS    = 20
C_SWEET = 72
C_WIN   = 72
C_COL4  = 71

COL_X = [
    MARGIN,
    MARGIN + C_NAME,
    MARGIN + C_NAME + C_BS,
    MARGIN + C_NAME + C_BS + C_SWEET,
    MARGIN + C_NAME + C_BS + C_SWEET + C_WIN,
]
COL_W = [C_NAME, C_BS, C_SWEET, C_WIN, C_COL4]

# ── Typography ─────────────────────────────────────────────────────────────────
ROW_FONT = 6.5
HDR_FONT = 7.0
LINE_H   = 3.8   # mm per line in data rows
MAX_SHOW = 5     # max targets per cell
ROW_PAD  = 1.5   # top/bottom padding inside each row

# ── Colours (R, G, B) ──────────────────────────────────────────────────────────
C_OUR_BG     = (44,  110,  44)   # dark green — our section banner
C_ENEMY_BG   = (150,  48,  48)   # dark red — enemy section banner
C_COL_HDR    = (50,   50,  50)   # column header strip
C_WHITE      = (255, 255, 255)
C_ODD        = (244, 248, 244)   # light green tint
C_EVEN       = (255, 255, 255)
C_TEXT       = (20,   20,  20)
C_DIM        = (120, 120, 120)
C_SWEET_INK  = (34,  139,  34)   # forest green
C_WIN_INK    = (30,   90, 190)   # blue
C_THREAT_INK = (190,  40,  40)   # red
C_GRID       = (210, 210, 210)


# ── Matchup computation ────────────────────────────────────────────────────────

def _fmt(name, bs_h, ratio):
    return f"{name[:18]} ({bs_h}, {ratio:.2f}x)"


def _compute_matchups(our_members, their_members):
    """
    Returns (our_profiles, their_profiles).

    our_profiles  — our members as attackers vs their roster.
      keys: name, bs_human, sweet, wins, threats

    their_profiles — enemy members; who from us targets them and who they threaten.
      keys: name, bs_human, sweet, wins, our_threats
    """
    def clean(lst):
        return sorted(
            [m for m in lst if isinstance(m, dict) and m.get("bs_estimate", 0) > 0],
            key=lambda m: m["bs_estimate"], reverse=True
        )

    ours   = clean(our_members)
    theirs = clean(their_members)

    our_profiles = []
    for om in ours:
        obs = om["bs_estimate"]
        sweet, wins, threats = [], [], []
        for tm in theirs:
            tbs = tm["bs_estimate"]
            ratio = tbs / obs
            e = (tm["name"], tm.get("bs_estimate_human", "?"), ratio)
            if 0.8 <= ratio <= 1.1:
                sweet.append(e)
            elif obs >= 1.2 * tbs:
                wins.append(e)
            elif tbs >= 1.2 * obs:
                threats.append(e)
        sweet.sort(key=lambda x: abs(x[2] - 1.0))
        wins.sort(key=lambda x: x[2], reverse=True)
        threats.sort(key=lambda x: x[2], reverse=True)
        our_profiles.append({
            "name":    om["name"],
            "bs_human": om.get("bs_estimate_human", "?"),
            "sweet":   sweet[:MAX_SHOW],
            "wins":    wins[:MAX_SHOW],
            "threats": threats[:MAX_SHOW],
        })

    their_profiles = []
    for tm in theirs:
        tbs = tm["bs_estimate"]
        sweet, wins, our_threats = [], [], []
        for om in ours:
            obs = om["bs_estimate"]
            ratio = obs / tbs   # our_bs as fraction of their_bs (enemy is the attacker)
            e = (om["name"], om.get("bs_estimate_human", "?"), ratio)
            if 0.8 <= ratio <= 1.1:
                sweet.append(e)       # our member is in enemy's sweet spot
            elif tbs >= 1.2 * obs:
                wins.append(e)        # enemy dominates our member
            elif obs >= 1.2 * tbs:
                our_threats.append(e) # our member dominates this enemy
        sweet.sort(key=lambda x: abs(x[2] - 1.0))
        wins.sort(key=lambda x: x[2], reverse=True)
        our_threats.sort(key=lambda x: x[2], reverse=True)
        their_profiles.append({
            "name":       tm["name"],
            "bs_human":   tm.get("bs_estimate_human", "?"),
            "sweet":      sweet[:MAX_SHOW],
            "wins":       wins[:MAX_SHOW],
            "our_threats": our_threats[:MAX_SHOW],
        })

    return our_profiles, their_profiles


# ── PDF class ──────────────────────────────────────────────────────────────────

class _PDF(FPDF):

    def __init__(self, our_name, their_name):
        super().__init__(orientation=ORIENT, unit="mm", format=FMT)
        self._our   = our_name
        self._their = their_name
        self._date  = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.set_auto_page_break(auto=True, margin=14)
        self.set_margins(MARGIN, 10, MARGIN)

    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*C_DIM)
        self.cell(0, 5,
                  f"BATTLE INTEL  |  {self._our} vs {self._their}  |  {self._date}",
                  ln=True, align="C")
        self.set_draw_color(*C_GRID)
        self.line(MARGIN, self.get_y(), MARGIN + USABLE, self.get_y())
        self.ln(1)

    def footer(self):
        self.set_y(-8)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*C_DIM)
        self.cell(0, 4, f"Page {self.page_no()}  |  CyberJeremy Battle Intelligence", align="C")

    def section_banner(self, text, color):
        self.set_fill_color(*color)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 11)
        self.cell(USABLE, 8, text, ln=True, fill=True, align="C")
        self.ln(1)

    def col_headers(self, col4_label):
        labels = [
            "Player", "BS",
            "Sweet Spot Targets  (0.8-1.1x)",
            "Domination Targets  (1.2x+)",
            col4_label,
        ]
        self.set_fill_color(*C_COL_HDR)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", HDR_FONT)
        for i, label in enumerate(labels):
            self.set_x(COL_X[i])
            self.cell(COL_W[i], 5, label, border=0, fill=True, align="C")
        self.ln()

    def player_row(self, profile, col4_key, row_idx=0):
        """
        Draws one player row. Returns True if a page break is needed (row was
        not drawn); the caller should then add_page + col_headers and retry.
        """
        sweet_lines = [_fmt(*e) for e in profile["sweet"]]
        win_lines   = [_fmt(*e) for e in profile["wins"]]
        col4_lines  = [_fmt(*e) for e in profile.get(col4_key, [])]

        n = max(len(sweet_lines), len(win_lines), len(col4_lines), 1)
        row_h = n * LINE_H + ROW_PAD * 2

        if self.will_page_break(row_h):
            return True

        y0 = self.get_y()
        bg = C_ODD if row_idx % 2 == 0 else C_EVEN
        self.set_fill_color(*bg)
        self.rect(MARGIN, y0, USABLE, row_h, style="F")

        # Player name
        self.set_xy(COL_X[0], y0 + ROW_PAD)
        self.set_font("Helvetica", "B", ROW_FONT)
        self.set_text_color(*C_TEXT)
        self.cell(COL_W[0], LINE_H, profile["name"][:22], border=0)

        # BS
        self.set_xy(COL_X[1], y0 + ROW_PAD)
        self.set_font("Helvetica", "", ROW_FONT)
        self.set_text_color(*C_DIM)
        self.cell(COL_W[1], LINE_H, profile["bs_human"], border=0, align="C")

        # Sweet / Win / Col4
        self._col_lines(COL_X[2], y0 + ROW_PAD, COL_W[2], sweet_lines, C_SWEET_INK)
        self._col_lines(COL_X[3], y0 + ROW_PAD, COL_W[3], win_lines,   C_WIN_INK)
        self._col_lines(COL_X[4], y0 + ROW_PAD, COL_W[4], col4_lines,  C_THREAT_INK)

        self.set_draw_color(*C_GRID)
        self.line(MARGIN, y0 + row_h, MARGIN + USABLE, y0 + row_h)
        self.set_xy(MARGIN, y0 + row_h)
        return False

    def _col_lines(self, x, y, w, lines, color):
        self.set_text_color(*color)
        self.set_font("Helvetica", "", ROW_FONT)
        for line in lines:
            self.set_xy(x, y)
            self.cell(w, LINE_H, line[:40], border=0)
            y += LINE_H


# ── Summary page ───────────────────────────────────────────────────────────────

def _draw_summary(pdf, our_data, their_data, our_profiles, their_profiles):
    our_name   = our_data.get("faction_name", "KO WeightRoom")
    their_name = their_data.get("faction_name", "Enemy")

    # Title
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 10, "BATTLE INTELLIGENCE REPORT", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*C_DIM)
    pdf.cell(0, 6, f"{our_name}  vs  {their_name}", ln=True, align="C")
    pdf.ln(6)

    # Side-by-side faction boxes
    BOX_W = (USABLE - 8) / 2
    BOX_X = [MARGIN, MARGIN + BOX_W + 8]

    def faction_box(x, data, hdr_color):
        name = data.get("faction_name", "?")
        y = pdf.get_y()
        pdf.set_xy(x, y)
        pdf.set_fill_color(*hdr_color)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(BOX_W, 7, f"  {name}", fill=True, align="L")
        rows = [
            ("Members",  str(data.get("member_count", "?"))),
            ("Avg BS",   data.get("avg_bs_human", "?")),
            ("Total BS", f"{data.get('total_bs', 0) / 1_000_000_000:.2f}b"
                         if data.get("total_bs", 0) >= 1e9
                         else f"{data.get('total_bs', 0) / 1_000_000:.1f}m"),
            ("Top Gun",  f"{data.get('top_fighter', {}).get('name', '?')} "
                         f"({data.get('top_fighter', {}).get('bs_human', '?')})"),
        ]
        y += 7
        for key, val in rows:
            pdf.set_xy(x, y)
            pdf.set_fill_color(246, 251, 246)
            pdf.set_text_color(*C_DIM)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(BOX_W / 2, 6, f"  {key}:", fill=True)
            pdf.set_xy(x + BOX_W / 2, y)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*C_TEXT)
            pdf.cell(BOX_W / 2, 6, val, fill=True)
            y += 6
        return y  # bottom y of this box

    y_start = pdf.get_y()
    bot_l = faction_box(BOX_X[0], our_data,   C_OUR_BG)
    pdf.set_y(y_start)
    bot_r = faction_box(BOX_X[1], their_data, C_ENEMY_BG)
    pdf.set_y(max(bot_l, bot_r) + 5)

    # Verdict
    our_avg   = our_data.get("avg_bs", 1) or 1
    their_avg = their_data.get("avg_bs", 1) or 1
    ratio     = our_avg / their_avg
    if ratio >= 1.3:
        verdict, vc = "WE OUTCLASS THEM", C_OUR_BG
    elif ratio >= 0.85:
        verdict, vc = "EVEN MATCHUP", (150, 120, 20)
    else:
        verdict, vc = "THEY OUTGUN US", C_ENEMY_BG

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*vc)
    pdf.cell(0, 7, f"Verdict: {verdict}  (avg BS ratio: {ratio:.2f}x)", ln=True, align="C")
    pdf.ln(4)

    # Mechanics legend
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 5, "Battle Mechanics:", ln=True)
    for color, label, desc in [
        (C_SWEET_INK,  "Sweet Spot (0.8-1.1x)",  "Target's BS is 80-110% of your BS -> max respect"),
        (C_WIN_INK,    "Domination  (>= 1.2x)",  "Your BS >= 1.2x target's -> you win cleanly"),
        (C_THREAT_INK, "Threat  (enemy >= 1.2x)", "Their BS >= 1.2x yours -> risky, avoid if possible"),
    ]:
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(54, 4.5, f"  >  {label}:")
        pdf.set_text_color(*C_DIM)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(0, 4.5, desc, ln=True)
    pdf.ln(4)

    # Counts
    n_sweet  = sum(len(p["sweet"])   for p in our_profiles)
    n_wins   = sum(len(p["wins"])    for p in our_profiles)
    n_threat = sum(len(p["threats"]) for p in our_profiles)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 5, "Matchup Totals:", ln=True)
    for color, text in [
        (C_SWEET_INK,  f"Sweet-spot pairs: {n_sweet}"),
        (C_WIN_INK,    f"Domination pairs: {n_wins}"),
        (C_THREAT_INK, f"Threat pairs (their members who beat ours): {n_threat}"),
    ]:
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(0, 4, f"  {text}", ln=True)
    pdf.ln(4)

    # Top 10 sweet-spot pairs (closest ratio to 1.0)
    all_sweet = []
    for p in our_profiles:
        for name, bs_h, r in p["sweet"]:
            all_sweet.append((p["name"], p["bs_human"], name, bs_h, r))
    all_sweet.sort(key=lambda x: abs(x[4] - 1.0))

    if all_sweet:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_TEXT)
        pdf.cell(0, 5, "Top 10 Sweet-Spot Matchups (closest to 1:1):", ln=True)
        for our_n, our_bs, their_n, their_bs, r in all_sweet[:10]:
            pdf.set_text_color(*C_SWEET_INK)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(
                0, 4,
                f"  {our_n} ({our_bs})  ->  {their_n} ({their_bs})   [{r:.2f}x]",
                ln=True
            )


# ── Section renderer ───────────────────────────────────────────────────────────

def _render_section(pdf, profiles, col4_key, banner_text, banner_color, col4_label):
    pdf.add_page()
    pdf.section_banner(banner_text, banner_color)
    pdf.col_headers(col4_label)
    for i, profile in enumerate(profiles):
        if pdf.player_row(profile, col4_key, row_idx=i):
            pdf.add_page()
            pdf.section_banner(f"{banner_text} (cont.)", banner_color)
            pdf.col_headers(col4_label)
            pdf.player_row(profile, col4_key, row_idx=i)


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_battle_report(our_data, their_data, output_path):
    """
    Generate the battle intelligence PDF and write it to output_path.
    our_data / their_data: dicts from ffscouter.scout_faction().
    Returns output_path on success.
    """
    our_name   = our_data.get("faction_name", "KO WeightRoom")
    their_name = their_data.get("faction_name", "Enemy")

    our_members   = list(our_data.get("members", {}).values())
    their_members = list(their_data.get("members", {}).values())

    our_profiles, their_profiles = _compute_matchups(our_members, their_members)

    pdf = _PDF(our_name, their_name)

    # Page 1: summary
    pdf.add_page()
    _draw_summary(pdf, our_data, their_data, our_profiles, their_profiles)

    # Section: our faction attacking
    _render_section(
        pdf, our_profiles,
        col4_key="threats",
        banner_text=f"OUR ATTACK PROFILES  --  {our_name}",
        banner_color=C_OUR_BG,
        col4_label="Threats to Them (avoid)",
    )

    # Section: enemy faction profiles
    _render_section(
        pdf, their_profiles,
        col4_key="our_threats",
        banner_text=f"ENEMY PROFILES  --  {their_name}",
        banner_color=C_ENEMY_BG,
        col4_label="Our Players Who Beat Them",
    )

    pdf.output(output_path)
    return output_path
