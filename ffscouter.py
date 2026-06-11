"""
FFScouter integration — fetches battle stat estimates for faction members.
API: GET https://ffscouter.com/api/v1/get-stats?key={key}&targets={ids}
Rate limit: 20 req/min. Up to 205 targets per request.
"""

import requests
import time
from datetime import datetime
import memory_db

FF_KEY = "yYZxOpSXBFaAUzdc"
FF_API = "https://ffscouter.com/api/v1/get-stats"
TORN_API = "https://api.torn.com/v2"


def _fmt_bs(value):
    """Format a raw battle stats integer for display."""
    if not value:
        return "?"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}b"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return str(value)


def get_stats(player_ids):
    """
    Batch query FFScouter. Splits into chunks of 205 automatically.
    Returns {player_id (int): {bs_estimate, bs_estimate_human, fair_fight, bss_public}}
    """
    results = {}
    player_ids = list(player_ids)

    for i in range(0, len(player_ids), 205):
        chunk = player_ids[i : i + 205]
        targets = ",".join(str(pid) for pid in chunk)
        try:
            r = requests.get(f"{FF_API}?key={FF_KEY}&targets={targets}", timeout=15)
            if r.status_code == 429:
                print("[FFScouter] Rate limited — sleeping 35s")
                time.sleep(35)
                r = requests.get(f"{FF_API}?key={FF_KEY}&targets={targets}", timeout=15)
            if r.status_code == 200:
                for entry in r.json():
                    pid = entry["player_id"]
                    results[pid] = {
                        "bs_estimate": entry.get("bs_estimate", 0),
                        "bs_estimate_human": entry.get("bs_estimate_human", "?"),
                        "fair_fight": entry.get("fair_fight", 0),
                        "bss_public": entry.get("bss_public", 0),
                        "last_updated": entry.get("last_updated", 0),
                    }
            else:
                print(f"[FFScouter] HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[FFScouter] Request error: {e}")

        if i + 205 < len(player_ids):
            time.sleep(3)  # stay under 20 req/min

    return results


def _get_faction_members(api_key, faction_id=None):
    """
    Returns ({player_id (int): name}, faction_name) for all members in a faction.
    faction_id=None uses the API key's own faction.

    v2 API: /v2/faction[/{id}]?selections=members  → {"members": [{id, name, ...}]}
    Faction name fetched separately via ?selections=basic → {"basic": {"name": ...}}
    """
    base = f"{TORN_API}/faction/{faction_id}" if faction_id else f"{TORN_API}/faction"

    try:
        members_res = requests.get(f"{base}?key={api_key}&selections=members", timeout=10).json()
        members_list = members_res.get("members", [])
        if isinstance(members_list, dict):
            # fallback for older API shapes
            id_to_name = {int(uid): m.get("name", str(uid)) for uid, m in members_list.items()}
        else:
            id_to_name = {int(m["id"]): m.get("name", str(m["id"])) for m in members_list if "id" in m}
    except Exception as e:
        print(f"[FFScouter] Failed to get members: {e}")
        return {}, ""

    try:
        basic_res = requests.get(f"{base}?key={api_key}&selections=basic", timeout=10).json()
        # v2 wraps in "basic" key
        faction_name = (
            basic_res.get("basic", {}).get("name")
            or basic_res.get("faction", {}).get("name")
            or f"Faction #{faction_id or '?'}"
        )
    except Exception:
        faction_name = f"Faction #{faction_id or '?'}"

    return id_to_name, faction_name


def scout_faction(torn_api_key, faction_id=None, faction_name=None):
    """
    Full pipeline: Torn member list → FFScouter stats → enriched summary dict.

    Returns:
    {
        faction_id, faction_name, member_count,
        members: {player_id: {name, bs_estimate, bs_estimate_human, fair_fight}},
        total_bs, avg_bs, avg_bs_human,
        top_fighter: {name, bs_human},
        fetched_at: ISO string
    }
    Returns None on failure.
    """
    members_map, torn_name = _get_faction_members(torn_api_key, faction_id)
    if not members_map:
        return None

    resolved_name = faction_name or torn_name
    stats = get_stats(list(members_map.keys()))

    enriched = {}
    total_bs = 0
    top_fighter = {"name": "?", "bs": 0, "bs_human": "?"}

    for pid, name in members_map.items():
        ff = stats.get(pid, {})
        bs = ff.get("bs_estimate") or 0
        enriched[pid] = {
            "name": name,
            "bs_estimate": bs,
            "bs_estimate_human": ff.get("bs_estimate_human") or _fmt_bs(bs),
            "fair_fight": ff.get("fair_fight", 0),
        }
        total_bs += bs
        if bs > top_fighter["bs"]:
            top_fighter = {
                "name": name,
                "bs": bs,
                "bs_human": ff.get("bs_estimate_human") or _fmt_bs(bs),
            }

    member_count = len(enriched)
    avg_bs = total_bs // member_count if member_count else 0

    result = {
        "faction_id": faction_id or 0,
        "faction_name": resolved_name,
        "member_count": member_count,
        "members": enriched,
        "total_bs": total_bs,
        "avg_bs": avg_bs,
        "avg_bs_human": _fmt_bs(avg_bs),
        "top_fighter": top_fighter,
        "fetched_at": datetime.now().isoformat(),
    }

    # Cache in MongoDB (convert dict keys to strings for BSON)
    serializable = dict(result)
    serializable["members"] = {str(k): v for k, v in enriched.items()}
    memory_db.save_faction_intel(faction_id or 0, resolved_name, serializable)

    return result


def compare_factions(our_data, their_data):
    """
    Builds a structured comparison string for Jeremy to present.
    """
    if not our_data or not their_data:
        return "Data incomplete — couldn't build comparison."

    our_total = our_data["total_bs"]
    their_total = their_data["total_bs"]
    ratio = our_total / their_total if their_total else 0

    if ratio >= 1.3:
        verdict = "WE OUTCLASS THEM"
        verdict_emoji = "✅"
    elif ratio >= 0.85:
        verdict = "EVEN MATCHUP"
        verdict_emoji = "⚖️"
    else:
        verdict = "THEY OUTGUN US"
        verdict_emoji = "⚠️"

    our_avg = our_data["avg_bs"]

    # Their members who are significantly stronger than our average
    threats = sorted(
        [m for m in their_data["members"].values() if m.get("bs_estimate", 0) > our_avg * 1.5],
        key=lambda m: m.get("bs_estimate", 0),
        reverse=True
    )

    lines = [
        f"{'─'*42}",
        f"  BATTLE INTEL — {their_data['faction_name']}",
        f"{'─'*42}",
        f"  Verdict  {verdict_emoji}  {verdict}  (ratio: {ratio:.2f}x)",
        f"{'─'*42}",
        f"{'':>12}{'KO WeightRoom':>18}{'':>2}{'Them':>12}",
        f"  Members  {'':>3}{our_data['member_count']:>14}    {their_data['member_count']:>10}",
        f"  Avg BS   {'':>3}{our_data['avg_bs_human']:>14}    {their_data['avg_bs_human']:>10}",
        f"  Total BS {'':>3}{_fmt_bs(our_total):>14}    {_fmt_bs(their_total):>10}",
        f"  Top gun  {'':>3}{our_data['top_fighter']['name'][:12]:>14}    {their_data['top_fighter']['name'][:10]:>10}",
        f"           {'':>3}{our_data['top_fighter']['bs_human']:>14}    {their_data['top_fighter']['bs_human']:>10}",
        f"{'─'*42}",
    ]

    if threats:
        threat_strs = [f"{m['name']} ({m['bs_estimate_human']})" for m in threats[:5]]
        lines.append(f"  Threats  {', '.join(threat_strs)}")
        lines.append(f"{'─'*42}")

    return "\n".join(lines)
