"""
Battle Intelligence PDF Report - cross-faction matchup analysis.

Two categories per player, both use the 0.7-1.1x range (Score 3 / max-respect zone):

  Attack targets  : enemy_bs / our_bs in [0.7, 1.1]
                    --> WE get max respect attacking them
                    --> sorted closest-to-1.0x first

  Fair-fight threats : our_bs / enemy_bs in [0.7, 1.1]
                    --> THEY get max respect attacking us (Score 3 zone)
                    --> NOT the biggest enemy, but the closest-stat ones
                    --> sorted closest-to-1.0x first (most dangerous first)

Public API:
  generate_battle_report(our_data, their_data, output_path)
  _compute_matchups(our_members, their_members)   [kept for Layer 6 tests]
  MAX_SHOW                                        [kept for Layer 6 tests]
"""

from fpdf import FPDF
from datetime import datetime

# ── Page layout (A4 landscape 297 x 210 mm) ───────────────────────────────────
ORIENT = "L"
FMT    = "A4"
MARGIN = 10
USABLE = 277          # 297 - 2*10

# ── Column widths (sum = 277 mm) ──────────────────────────────────────────────
C_NAME   = 40
C_BS     = 18
C_ATTACK = 109         # top-5 attack targets column
C_THREAT = 110         # top-5 fair-fight threats column

COL_X = [
    MARGIN,
    MARGIN + C_NAME,
    MARGIN + C_NAME + C_BS,
    MARGIN + C_NAME + C_BS + C_ATTACK,
]
COL_W = [C_NAME, C_BS, C_ATTACK, C_THREAT]

# ── Typography ────────────────────────────────────────────────────────────────
ROW_FONT = 6.5
HDR_FONT = 7.0
LINE_H   = 3.8         # mm per entry line
ROW_PAD  = 1.2         # top/bottom padding inside a data row
SHOW     = 5           # entries per cell

# ── Colours ───────────────────────────────────────────────────────────────────
C_OUR_BG      = (44,  110,  44)
C_ENEMY_BG    = (150,  48,  48)
C_COL_HDR     = (50,   50,  50)
C_WHITE       = (255, 255, 255)
C_ODD         = (244, 250, 244)
C_EVEN        = (255, 255, 255)
C_TEXT        = (20,   20,  20)
C_DIM         = (120, 120, 120)
C_ATTACK_INK  = (20,  130,  20)    # green -- attack targets
C_THREAT_INK  = (190,  40,  40)   # red   -- fair-fight threats
C_GRID        = (210, 210, 210)

# ── Battle mechanics ──────────────────────────────────────────────────────────
PREF_LOW  = 0.7        # lower bound of max-respect zone
PREF_HIGH = 1.1        # upper bound
WIN_RATIO = 1.2        # domination threshold (kept for legacy compute)

# Kept for Layer 6 tests
MAX_SHOW = 5


# ── Legacy compute (kept for Layer 6 tests + ffscouter.player_matchup_report) ─

def _fmt(name, bs_h, ratio):
    return f"{name[:18]} ({bs_h}, {ratio:.2f}x)"


def _compute_matchups(our_members, their_members):
    """
    Original MAX_SHOW-capped computation with 0.8-1.1x sweet spot.
    Kept for Layer 6 tests; not used by generate_battle_report.
    """
    def clean(lst):
        return sorted(
            [m for m in lst if isinstance(m, dict) and m.get("bs_estimate", 0) > 0],
            key=lambda m: m["bs_estimate"], reverse=True,
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
            ratio = obs / tbs
            e = (om["name"], om.get("bs_estimate_human", "?"), ratio)
            if 0.8 <= ratio <= 1.1:
                sweet.append(e)
            elif tbs >= 1.2 * obs:
                wins.append(e)
            elif obs >= 1.2 * tbs:
                our_threats.append(e)
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


# ── Full compute for the PDF report ───────────────────────────────────────────

def _compute_report_matchups(our_members, their_members):
    """
    Compute top-5 attack targets and top-5 fair-fight threats per player.

    Attack targets  : enemy_bs / our_bs in [0.7, 1.1] -- we attack, we get max respect
    Fair-fight threats : our_bs / enemy_bs in [0.7, 1.1] -- they attack us, they get Score 3
    Both sorted by |ratio - 1.0| (closest to 1:1 = best matchup first).
    """
    def clean(lst):
        return sorted(
            [m for m in lst if isinstance(m, dict) and m.get("bs_estimate", 0) > 0],
            key=lambda m: m["bs_estimate"], reverse=True,
        )

    ours   = clean(our_members)
    theirs = clean(their_members)

    def _entry(name, bs_h, ratio):
        return (name, bs_h, ratio)

    our_profiles = []
    for om in ours:
        obs = om["bs_estimate"]
        attack_targets, ff_threats = [], []
        for tm in theirs:
            tbs = tm["bs_estimate"]
            r_attack  = tbs / obs       # from our perspective as attacker
            r_defense = obs / tbs       # from their perspective as attacker (us as defender)
            if PREF_LOW <= r_attack  <= PREF_HIGH:
                attack_targets.append(_entry(tm["name"], tm.get("bs_estimate_human", "?"), r_attack))
            if PREF_LOW <= r_defense <= PREF_HIGH:
                ff_threats.append(_entry(tm["name"], tm.get("bs_estimate_human", "?"), r_defense))
        attack_targets.sort(key=lambda x: abs(x[2] - 1.0))
        ff_threats.sort(key=lambda x: abs(x[2] - 1.0))
        our_profiles.append({
            "name":     om["name"],
            "bs_human": om.get("bs_estimate_human", "?"),
            "targets":  attack_targets[:SHOW],
            "threats":  ff_threats[:SHOW],
        })

    their_profiles = []
    for tm in theirs:
        tbs = tm["bs_estimate"]
        attack_targets, our_counters = [], []
        for om in ours:
            obs = om["bs_estimate"]
            r_attack  = obs / tbs       # enemy attacks our member (enemy gets respect)
            r_defense = tbs / obs       # we attack enemy (we get respect = our counters)
            if PREF_LOW <= r_attack  <= PREF_HIGH:
                attack_targets.append(_entry(om["name"], om.get("bs_estimate_human", "?"), r_attack))
            if PREF_LOW <= r_defense <= PREF_HIGH:
                our_counters.append(_entry(om["name"], om.get("bs_estimate_human", "?"), r_defense))
        attack_targets.sort(key=lambda x: abs(x[2] - 1.0))
        our_counters.sort(key=lambda x: abs(x[2] - 1.0))
        their_profiles.append({
            "name":        tm["name"],
            "bs_human":    tm.get("bs_estimate_human", "?"),
            "targets":     attack_targets[:SHOW],   # our members they prefer to hit
            "our_counters": our_counters[:SHOW],    # our members who counter them
        })

    return our_profiles, their_profiles


# ── PDF class ─────────────────────────────────────────────────────────────────

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
        self.cell(0, 4, f"Page {self.page_no()}  |  CyberJeremy Battle Intelligence",
                  align="C")

    def section_banner(self, text, color):
        self.set_fill_color(*color)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 11)
        self.cell(USABLE, 8, text, ln=True, fill=True, align="C")
        self.ln(1)

    def col_headers(self, attack_label, threat_label):
        labels = ["Player", "BS", attack_label, threat_label]
        self.set_fill_color(*C_COL_HDR)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", HDR_FONT)
        for i, label in enumerate(labels):
            self.set_x(COL_X[i])
            self.cell(COL_W[i], 5, label, border=0, fill=True, align="C")
        self.ln()

    def _col_lines(self, x, y, w, entries, color):
        """Render up to SHOW entries in a column, each on its own line."""
        self.set_font("Helvetica", "", ROW_FONT)
        self.set_text_color(*color)
        for name, bs_h, ratio in entries:
            label = f"{name[:20]} ({ratio:.2f}x)"
            self.set_xy(x, y)
            self.cell(w, LINE_H, label[:38], border=0)
            y += LINE_H

    def player_row(self, profile, row_idx=0, enemy_side=False):
        """
        Draw one player row (up to SHOW entries per column).
        Returns True if the row needs a page break before drawing.
        """
        targets  = profile.get("targets",  [])
        threats  = profile.get("threats",  profile.get("our_counters", []))

        n    = max(len(targets), len(threats), 1)
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

        # Attack targets column (green)
        self._col_lines(COL_X[2], y0 + ROW_PAD, COL_W[2], targets,  C_ATTACK_INK)

        # Fair-fight threats / counters column (red)
        self._col_lines(COL_X[3], y0 + ROW_PAD, COL_W[3], threats,  C_THREAT_INK)

        # Bottom separator
        self.set_draw_color(*C_GRID)
        self.line(MARGIN, y0 + row_h, MARGIN + USABLE, y0 + row_h)
        self.set_xy(MARGIN, y0 + row_h)
        return False


# ── Summary page ──────────────────────────────────────────────────────────────

def _draw_summary(pdf, our_data, their_data, our_profiles, their_profiles):
    our_name   = our_data.get("faction_name", "KO WeightRoom")
    their_name = their_data.get("faction_name", "Enemy")

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 10, "BATTLE INTELLIGENCE REPORT", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*C_DIM)
    pdf.cell(0, 6, f"{our_name}  vs  {their_name}", ln=True, align="C")
    pdf.ln(6)

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
            ("Total BS", (
                f"{data.get('total_bs', 0) / 1_000_000_000:.2f}b"
                if data.get("total_bs", 0) >= 1e9
                else f"{data.get('total_bs', 0) / 1_000_000:.1f}m"
            )),
            ("Top Gun",  (
                f"{data.get('top_fighter', {}).get('name', '?')} "
                f"({data.get('top_fighter', {}).get('bs_human', '?')})"
            )),
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
        return y

    y_start = pdf.get_y()
    bot_l = faction_box(BOX_X[0], our_data,   C_OUR_BG)
    pdf.set_y(y_start)
    bot_r = faction_box(BOX_X[1], their_data, C_ENEMY_BG)
    pdf.set_y(max(bot_l, bot_r) + 5)

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
    pdf.cell(0, 5, "Battle Mechanics (Score 3 / max-respect zone):", ln=True)
    for color, label, desc in [
        (C_ATTACK_INK, "Attack Targets (0.7-1.1x)",
         "enemy_bs / our_bs in this range -> WE get Score 3 / max respect"),
        (C_THREAT_INK, "Fair-Fight Threats (0.7-1.1x)",
         "our_bs / their_bs in this range -> THEY get Score 3 attacking us"),
    ]:
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(62, 4.5, f"  >  {label}:")
        pdf.set_text_color(*C_DIM)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(0, 4.5, desc, ln=True)
    pdf.ln(4)

    # Aggregate counts
    n_atk = sum(len(p["targets"])  for p in our_profiles)
    n_thr = sum(len(p["threats"])  for p in our_profiles)
    n_etg = sum(len(p["targets"])  for p in their_profiles)
    n_ecn = sum(len(p.get("our_counters", [])) for p in their_profiles)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 5, "Matchup Summary (top 5 per player shown in report):", ln=True)
    for color, text in [
        (C_ATTACK_INK, f"Our attack target pairs (0.7-1.1x, we get max respect): {n_atk}"),
        (C_THREAT_INK, f"Fair-fight threat pairs (Score 3 zone for them attacking us): {n_thr}"),
        (C_THREAT_INK, f"Enemy attack target pairs (Score 3 for them in our roster): {n_etg}"),
        (C_ATTACK_INK, f"Our counter pairs (we get max respect hitting them): {n_ecn}"),
    ]:
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(0, 4, f"  {text}", ln=True)
    pdf.ln(4)

    # Top 15 best mutual matchups (closest to 1:1 from our attack perspective)
    all_targets = []
    for p in our_profiles:
        for name, bs_h, r in p["targets"]:
            all_targets.append((p["name"], p["bs_human"], name, bs_h, r))
    all_targets.sort(key=lambda x: abs(x[4] - 1.0))

    if all_targets:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_TEXT)
        pdf.cell(0, 5, "Top 15 Best Matchups (closest to 1:1 ratio -- best respect):", ln=True)
        for our_n, our_bs, their_n, their_bs, r in all_targets[:15]:
            pdf.set_text_color(*C_ATTACK_INK)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(
                0, 4,
                f"  {our_n} ({our_bs})  ->  {their_n} ({their_bs})  [{r:.2f}x]",
                ln=True,
            )


# ── Section renderer ──────────────────────────────────────────────────────────

def _render_section(pdf, profiles, banner_text, banner_color,
                    attack_label, threat_label, enemy_side=False):
    pdf.add_page()
    pdf.section_banner(banner_text, banner_color)
    pdf.col_headers(attack_label, threat_label)
    for i, profile in enumerate(profiles):
        if pdf.player_row(profile, row_idx=i, enemy_side=enemy_side):
            pdf.add_page()
            pdf.section_banner(f"{banner_text} (cont.)", banner_color)
            pdf.col_headers(attack_label, threat_label)
            pdf.player_row(profile, row_idx=i, enemy_side=enemy_side)


# ── Public API ────────────────────────────────────────────────────────────────

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

    our_profiles, their_profiles = _compute_report_matchups(our_members, their_members)

    pdf = _PDF(our_name, their_name)

    # Page 1: summary
    pdf.add_page()
    _draw_summary(pdf, our_data, their_data, our_profiles, their_profiles)

    # Section A: our members attacking — who to hit, who threatens us
    _render_section(
        pdf, our_profiles,
        banner_text=f"OUR ATTACK PROFILES  --  {our_name}",
        banner_color=C_OUR_BG,
        attack_label=f"Top 5 Attack Targets  (0.7-1.1x -- max respect from {their_name})",
        threat_label="Top 5 Fair-Fight Threats  (Score 3 zone -- they get max respect hitting us)",
        enemy_side=False,
    )

    # Section B: enemy members attacking — who they target, who counters them
    _render_section(
        pdf, their_profiles,
        banner_text=f"ENEMY ATTACK PROFILES  --  {their_name}",
        banner_color=C_ENEMY_BG,
        attack_label=f"Top 5 of Our Members They Target  (Score 3 for them)",
        threat_label=f"Top 5 of Our Members Who Counter Them  (max respect for us)",
        enemy_side=True,
    )

    pdf.output(output_path)
    return output_path
