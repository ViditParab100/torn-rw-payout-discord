"""
Player Intel — Torn API profile enrichment for CyberJeremy.

Uses the player's own stored Torn API key (from the vault) to fetch:
  - v1 profile: level, title, rank, age, status, donator, faction position, job/company
  - v2 /company: company name, type, days_old, rating (stars), employee count

Data is cached in MongoDB player_profiles_col with a 1-hour TTL.
Title changes are detected and automatically stored as lore facts.
"""

import requests
from datetime import datetime, timedelta
import memory_db

TORN_V1 = "https://api.torn.com/v1"
TORN_V2 = "https://api.torn.com/v2"
CACHE_TTL_HOURS = 1

# Rough title progression order (higher index = more advanced title)
_TITLE_ORDER = [
    "recruit", "private", "corporal", "sergeant", "staff sergeant",
    "master sergeant", "first sergeant", "sergeant major", "command sergeant major",
    "warrant officer", "senior warrant officer", "master warrant officer",
    "sub-lieutenant", "lieutenant", "captain", "major", "lieutenant colonel",
    "colonel", "brigadier", "general", "head general", "commander",
    "samaritan", "lifeguard", "guardian", "daredevil", "psycho",
    "maniac", "ruthless", "savage", "veteran", "elite", "pro",
    "expert", "legend", "master", "grandmaster",
    "duke", "duchess", "heir", "ruler", "overlord", "god", "avenger",
]


def _title_rank(title):
    """Returns progression index for a title. -1 if not in the list."""
    t = title.lower().strip() if title else ""
    try:
        return _TITLE_ORDER.index(t)
    except ValueError:
        return -1


def fetch_profile(api_key):
    """
    Fetch v1 user profile using the player's own key.
    v1 is used (not v2) because it includes the 'job' field with company info.
    Returns dict or None on error.
    """
    try:
        r = requests.get(
            f"{TORN_V1}/user",
            params={"selections": "profile", "key": api_key},
            timeout=8
        )
        data = r.json()
        if "error" in data:
            print(f"[PlayerIntel] Profile error code {data['error'].get('code')}: {data['error'].get('error')}")
            return None
        return data
    except Exception as e:
        print(f"[PlayerIntel] fetch_profile: {e}")
        return None


def fetch_company(api_key, company_id=None):
    """
    Fetch company details from v2 API.
    Without company_id: fetches the key owner's own company (director-level access).
    With company_id: fetches a specific company (limited public profile).
    Returns the 'profile' dict or None on error.
    """
    try:
        url = f"{TORN_V2}/company/{company_id}" if company_id else f"{TORN_V2}/company"
        r = requests.get(url, params={"key": api_key}, timeout=8)
        data = r.json()
        if "error" in data:
            return None
        return data.get("profile") if isinstance(data.get("profile"), dict) else None
    except Exception as e:
        print(f"[PlayerIntel] fetch_company: {e}")
        return None


def enrich_player(api_key, discord_id, display_name):
    """
    Fetch Torn profile + company data for this player, cache in MongoDB,
    and fire lore/milestone updates for notable changes (title promotions, etc).
    Safe to call from a background thread — never raises.
    """
    try:
        profile = fetch_profile(api_key)
        if not profile:
            return

        name = profile.get("name") or display_name
        level = profile.get("level")
        title = profile.get("title")
        rank = profile.get("rank")
        age_days = profile.get("age")
        donator = profile.get("donator")
        status_obj = profile.get("status") or {}
        status = status_obj.get("state", "Okay") if isinstance(status_obj, dict) else str(status_obj)
        faction_obj = profile.get("faction") or {}
        faction_pos = faction_obj.get("position") if isinstance(faction_obj, dict) else None
        job_obj = profile.get("job") or {}
        company_id = job_obj.get("company_id")
        company_name = job_obj.get("company_name") or job_obj.get("company")
        job_pos = job_obj.get("position") or job_obj.get("job")

        # Detailed company info (works when player is director or for public profiles)
        company_data = {}
        if company_id:
            raw = fetch_company(api_key, company_id)
            if raw:
                type_field = raw.get("type") or {}
                type_name = type_field.get("name") if isinstance(type_field, dict) else str(type_field or "?")
                dir_field = raw.get("director") or {}
                dir_name = dir_field.get("name") if isinstance(dir_field, dict) else None
                emps = raw.get("employees") or []
                company_data = {
                    "id": raw.get("id", company_id),
                    "name": raw.get("name") or company_name,
                    "type": type_name,
                    "days_old": raw.get("days_old"),
                    "rating": raw.get("rating"),
                    "employee_count": len(emps) if isinstance(emps, list) else 0,
                    "director_name": dir_name,
                }

        # Detect title change vs last cached
        old = memory_db.get_player_profile(str(discord_id))
        old_title = old.get("title") if old else None

        # Save updated cache
        memory_db.save_player_profile(str(discord_id), {
            "discord_id": str(discord_id),
            "torn_name": name,
            "level": level,
            "title": title,
            "rank": rank,
            "age_days": age_days,
            "donator": donator,
            "status": status,
            "faction_position": faction_pos,
            "company_id": company_id,
            "company_name": company_name,
            "job_position": job_pos,
            "company": company_data,
            "fetched_at": datetime.now(),
        })

        # Auto-lore: title fact
        if title and level:
            memory_db.update_player_lore(name, f"Torn title '{title}' at level {level}")

        # Auto-lore: company fact
        if company_data:
            cd = company_data
            role = job_pos if job_pos else "employee"
            memory_db.update_player_lore(
                name,
                f"{role} of {cd['name']} ({cd['type']}), "
                f"{cd.get('days_old', '?')} days old, "
                f"{cd.get('rating', '?')} stars, "
                f"{cd.get('employee_count', '?')} employees"
            )
        elif company_name and job_pos:
            memory_db.update_player_lore(name, f"Works at {company_name} as {job_pos}")

        # Title promotion detection — stores lore + milestone
        if old_title and title and old_title != title:
            old_rank = _title_rank(old_title)
            new_rank = _title_rank(title)
            if new_rank > old_rank or old_rank == -1:
                memory_db.update_player_lore(
                    name, f"Title upgraded from '{old_title}' to '{title}'"
                )
                memory_db.add_faction_milestone(
                    f"{name} earned the Torn title '{title}'",
                    datetime.now().strftime("%Y-%m-%d"),
                    milestone_type="general"
                )
                print(f"[PlayerIntel] Title promotion: {name} '{old_title}' → '{title}'")

    except Exception as e:
        print(f"[PlayerIntel] enrich_player error (discord_id={discord_id}): {e}")


def get_player_context(discord_id):
    """
    Returns a compact formatted string from the last cached Torn profile.
    Returns empty string if no profile or if cache is stale (> 1h).
    """
    profile = memory_db.get_player_profile(str(discord_id))
    if not profile:
        return ""

    fetched_at = profile.get("fetched_at")
    if fetched_at and datetime.now() - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
        return ""

    parts = []
    level = profile.get("level")
    title = profile.get("title", "")
    status = profile.get("status", "Okay")
    donator = profile.get("donator")
    age_days = profile.get("age_days")
    faction_pos = profile.get("faction_position")

    if level:
        parts.append(f"Level {level}" + (f" ({title})" if title else ""))
    if status and status.lower() not in ("okay", "ok"):
        parts.append(f"Status: {status}")
    if donator:
        parts.append("Donator")
    if faction_pos:
        parts.append(f"Faction: {faction_pos}")
    if age_days:
        years = age_days // 365
        parts.append(f"Age: ~{years}yr" if years else f"Age: {age_days}d")

    cd = profile.get("company")
    if cd:
        parts.append(
            f"Company: {cd.get('name', '?')} ({cd.get('type', '?')}) | "
            f"{cd.get('rating', '?')} stars | "
            f"{cd.get('days_old', '?')} days old | "
            f"{cd.get('employee_count', '?')} staff | "
            f"{profile.get('job_position', '?')}"
        )
    elif profile.get("company_name"):
        parts.append(
            f"Company: {profile['company_name']} "
            f"({profile.get('job_position', 'employee')})"
        )

    name = profile.get("torn_name", "?")
    return f"[Torn Profile — {name}] " + " | ".join(parts) if parts else ""
