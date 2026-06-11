import requests
from datetime import datetime
import memory_db

TORN_API = "https://api.torn.com/v2"

# Respect thresholds that warrant a milestone entry
RESPECT_THRESHOLDS = [
    100_000, 250_000, 500_000,
    1_000_000, 2_000_000, 5_000_000, 10_000_000
]

# ==========================================
# WAR-DATA MILESTONES (no API call needed)
# ==========================================

def detect_war_milestones(war_data):
    """
    Called after a war is fetched. Compares results against stored records
    and saves any new ones automatically.
    war_data: the dict returned by process_war_request (war_id, opponent_name, members)
    """
    members = war_data.get("members", [])
    war_id = war_data.get("war_id")
    today = datetime.now().strftime("%Y-%m-%d")
    found = []

    # 1. Personal hit records — check every member who hit >= 5
    for m in members:
        name = m.get("name", "")
        hits = m.get("war_hits", 0)
        if hits < 5:
            continue

        current_record = memory_db.get_milestone_record("member_hit_record", player=name)
        if current_record is None or hits > current_record:
            memory_db.add_faction_milestone(
                achievement=f"{name} — {hits} hits in a single war (personal best)",
                provided_date=today,
                milestone_type="member_hit_record",
                value=hits,
                war_id=war_id,
                player=name,
                auto=True
            )
            found.append(f"{name} personal record: {hits} hits")

    # 2. Faction-wide single-war top hitter record
    if members:
        top = max(members, key=lambda m: m.get("war_hits", 0))
        top_hits = top.get("war_hits", 0)
        if top_hits >= 10:
            current_record = memory_db.get_milestone_record("faction_top_single_war_hits")
            if current_record is None or top_hits > current_record:
                memory_db.add_faction_milestone(
                    achievement=f"Faction record: {top['name']} dropped {top_hits} hits in one war",
                    provided_date=today,
                    milestone_type="faction_top_single_war_hits",
                    value=top_hits,
                    war_id=war_id,
                    player=top["name"],
                    auto=True
                )
                found.append(f"Faction top hitter record: {top['name']} {top_hits} hits")

    # 3. Most total hits the faction dropped in a single war
    total_hits = sum(m.get("war_hits", 0) for m in members)
    if total_hits >= 20:
        current_record = memory_db.get_milestone_record("faction_total_war_hits")
        if current_record is None or total_hits > current_record:
            memory_db.add_faction_milestone(
                achievement=f"Faction dropped {total_hits} total hits in one war vs {war_data.get('opponent_name', 'opponent')}",
                provided_date=today,
                milestone_type="faction_total_war_hits",
                value=total_hits,
                war_id=war_id,
                auto=True
            )
            found.append(f"Total war hits record: {total_hits}")

    # 4. Win streak — check war results stored in MongoDB
    _check_win_streak(war_data, today)

    if found:
        print(f"[MilestoneDetector] {len(found)} new record(s): {found}")


def _check_win_streak(war_data, today):
    """
    Counts the current consecutive win streak using the result field on stored wars.
    If the new war was a loss, streak resets — no need to update the record.
    """
    recent_wars = list(memory_db.wars_collection.find().sort("war_id", -1).limit(20))
    if not recent_wars:
        return

    streak = 0
    for war in recent_wars:
        if war.get("result") == "win":
            streak += 1
        else:
            break

    current_record = memory_db.get_milestone_record("win_streak")
    if streak >= 3 and (current_record is None or streak > current_record):
        memory_db.add_faction_milestone(
            achievement=f"Win streak: {streak} wars in a row",
            provided_date=today,
            milestone_type="win_streak",
            value=streak,
            war_id=war_data.get("war_id"),
            auto=True
        )


# ==========================================
# FACTION API MILESTONES (one API call)
# ==========================================

def detect_faction_api_milestones(api_key):
    """
    Fetches live faction stats from Torn API and checks for:
    - Chain record (faction's all-time best chain)
    - Total respect milestones (100k, 500k, 1M, etc.)
    - Total wars won milestones

    Call this once per scout run, after war data is processed.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    found = []

    try:
        res = requests.get(f"{TORN_API}/faction?key={api_key}", timeout=10).json()
    except Exception as e:
        print(f"[MilestoneDetector] Faction API call failed: {e}")
        return

    if "error" in res:
        print(f"[MilestoneDetector] Torn API error: {res['error']}")
        return

    faction = res.get("faction", res)  # v2 wraps in "faction", fallback handles flat response

    # 1. Best chain record
    best_chain = (
        faction.get("best_chain")
        or faction.get("stats", {}).get("best_chain")
        or 0
    )
    if best_chain >= 10:
        current_record = memory_db.get_milestone_record("faction_chain_record")
        if current_record is None or best_chain > current_record:
            memory_db.add_faction_milestone(
                achievement=f"Faction chain record: {best_chain} hits",
                provided_date=today,
                milestone_type="faction_chain_record",
                value=best_chain,
                auto=True
            )
            found.append(f"Chain record: {best_chain}")

    # 2. Total respect milestones
    total_respect = (
        faction.get("respect")
        or faction.get("stats", {}).get("respect")
        or 0
    )
    if total_respect > 0:
        current_respect_record = memory_db.get_milestone_record("faction_respect_total") or 0
        for threshold in RESPECT_THRESHOLDS:
            if total_respect >= threshold and threshold > current_respect_record:
                label = _format_respect(threshold)
                memory_db.add_faction_milestone(
                    achievement=f"Faction crossed {label} total respect",
                    provided_date=today,
                    milestone_type="faction_respect_total",
                    value=threshold,
                    auto=True
                )
                found.append(f"Respect milestone: {label}")
                # Only record the highest threshold crossed
                break

    # 3. Wars won milestones (optional — add if field is present in response)
    wars_won = (
        faction.get("wars_won")
        or faction.get("stats", {}).get("wars_won")
        or 0
    )
    if wars_won > 0:
        _check_wars_won_milestone(wars_won, today, found)

    if found:
        print(f"[MilestoneDetector] API milestones found: {found}")


def _check_wars_won_milestone(wars_won, today, found):
    WAR_WIN_THRESHOLDS = [10, 25, 50, 100, 200]
    current = memory_db.get_milestone_record("faction_wars_won") or 0
    for threshold in sorted(WAR_WIN_THRESHOLDS, reverse=True):
        if wars_won >= threshold and threshold > current:
            memory_db.add_faction_milestone(
                achievement=f"Faction reached {threshold} ranked wars won",
                provided_date=today,
                milestone_type="faction_wars_won",
                value=threshold,
                auto=True
            )
            found.append(f"Wars won milestone: {threshold}")
            break


def _format_respect(value):
    if value >= 1_000_000:
        n = value // 1_000_000
        return f"{n}M"
    return f"{value // 1_000}K"


# ==========================================
# CHAIN HISTORY MILESTONES
# ==========================================

CHAIN_THRESHOLDS = [100, 250, 500, 1000, 2000, 2500]


def _fetch_all_chains(api_key):
    """
    Paginates through the full chain history by combining:
    - sort=asc (oldest 100) + paginating sort=desc backwards until overlap.
    Returns a time-sorted list of all unique chain dicts.
    """
    import time as _time

    all_chains = {}  # keyed by chain id for dedup

    # Oldest 100
    try:
        r = requests.get(
            f"{TORN_API}/faction/chains?key={api_key}&limit=100&sort=asc",
            timeout=10
        ).json()
        for c in r.get("chains", []):
            all_chains[c["id"]] = c
    except Exception as e:
        print(f"[ChainMilestone] ASC fetch error: {e}")
        return []

    oldest_known_ts = min((c["start"] for c in all_chains.values()), default=0)

    # Newest 100 + paginate backwards
    try:
        r2 = requests.get(
            f"{TORN_API}/faction/chains?key={api_key}&limit=100&sort=desc",
            timeout=10
        ).json()
        for c in r2.get("chains", []):
            all_chains[c["id"]] = c
        prev_link = r2.get("_metadata", {}).get("links", {}).get("prev")
    except Exception as e:
        print(f"[ChainMilestone] DESC fetch error: {e}")
        prev_link = None

    while prev_link:
        _time.sleep(1)
        try:
            r3 = requests.get(f"{prev_link}&key={api_key}", timeout=10).json()
            batch = r3.get("chains", [])
            if not batch:
                break
            for c in batch:
                all_chains[c["id"]] = c
            prev_link = r3.get("_metadata", {}).get("links", {}).get("prev")
            oldest_in_batch = min(c["start"] for c in batch)
            if oldest_in_batch <= oldest_known_ts:
                break  # overlapped with the asc batch
        except Exception as e:
            print(f"[ChainMilestone] Pagination error: {e}")
            break

    return sorted(all_chains.values(), key=lambda c: c["start"])


def detect_chain_milestones(api_key):
    """
    Fetches the full chain history (all pages) and stores a milestone for the
    first time each CHAIN_THRESHOLD was hit. Uses chain_first_{N} type —
    idempotent on repeated calls.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Skip entirely if all thresholds already recorded
    if all(memory_db.get_milestone_record(f"chain_first_{t}") is not None
           for t in CHAIN_THRESHOLDS):
        print("[ChainMilestone] All thresholds already stored — skipping.")
        return

    chains = _fetch_all_chains(api_key)
    if not chains:
        print("[ChainMilestone] No chains fetched.")
        return

    print(f"[ChainMilestone] Scanning {len(chains)} chains for threshold milestones...")
    stored = 0

    for threshold in CHAIN_THRESHOLDS:
        if memory_db.get_milestone_record(f"chain_first_{threshold}") is not None:
            continue
        for chain in chains:
            if chain.get("chain", 0) >= threshold:
                start_ts = chain.get("start", 0)
                date_str = (
                    datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
                    if start_ts else today
                )
                label = f"{threshold:,}"
                memory_db.add_faction_milestone(
                    achievement=f"First faction chain to reach {label} hits",
                    provided_date=date_str,
                    milestone_type=f"chain_first_{threshold}",
                    value=threshold,
                    auto=True
                )
                stored += 1
                break

    print(f"[ChainMilestone] Stored {stored} new chain milestone(s).")


# ==========================================
# FACTION UPGRADE MILESTONES
# ==========================================

def detect_upgrade_milestones(api_key):
    """
    Fetches faction upgrades and stores each unlocked upgrade as a dated milestone.
    Uses upgrade_{upgrade_id} as the type — idempotent, updates if level increased.

    Handles the v2 structure:
      upgrades.core.upgrades  → list of upgrade objects
      upgrades.war            → list of branch dicts, each with .upgrades list
      upgrades.peace          → same as war
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        res = requests.get(
            f"{TORN_API}/faction?selections=upgrades&key={api_key}",
            timeout=10
        ).json()
    except Exception as e:
        print(f"[UpgradeMilestone] Upgrades API error: {e}")
        return

    upgrades = res.get("upgrades", {})
    if not upgrades:
        print("[UpgradeMilestone] No upgrades data returned.")
        return

    stored = 0

    def _process_list(upgrade_list):
        nonlocal stored
        if not isinstance(upgrade_list, list):
            return
        for obj in upgrade_list:
            if not isinstance(obj, dict):
                continue
            uid = obj.get("id")
            level = obj.get("level", 0)
            unlocked_at = obj.get("unlocked_at", 0)
            name = obj.get("name", f"Upgrade #{uid}")
            if not uid or not unlocked_at:
                continue
            date_str = datetime.fromtimestamp(unlocked_at).strftime("%Y-%m-%d")
            mtype = f"upgrade_{uid}"
            current = memory_db.get_milestone_record(mtype)
            if current is None or level > current:
                memory_db.add_faction_milestone(
                    achievement=f"Faction upgrade unlocked: {name} (level {level})",
                    provided_date=date_str,
                    milestone_type=mtype,
                    value=level,
                    auto=True
                )
                stored += 1

    # core branch: {upgrades: [...]}
    core = upgrades.get("core", {})
    if isinstance(core, dict):
        _process_list(core.get("upgrades", []))

    # war + peace branches: [{name, upgrades: [...]}, ...]
    for section_key in ("war", "peace"):
        section = upgrades.get(section_key, [])
        if isinstance(section, list):
            for branch in section:
                if isinstance(branch, dict):
                    _process_list(branch.get("upgrades", []))

    print(f"[UpgradeMilestone] Stored {stored} upgrade milestone(s).")
