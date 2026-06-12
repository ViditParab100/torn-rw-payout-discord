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


def fetch_player_by_id(torn_id, api_key):
    """
    Fetch a specific player's public profile using any available API key.
    Returns the raw v1 profile dict, or None on error.
    Useful for looking up level/title/gender of any player by their Torn ID.
    """
    try:
        r = requests.get(
            f"{TORN_V1}/user/{torn_id}",
            params={"selections": "profile", "key": api_key},
            timeout=8
        )
        data = r.json()
        if "error" in data:
            print(f"[PlayerIntel] fetch_player_by_id({torn_id}) error: {data['error']}")
            return None
        return data
    except Exception as e:
        print(f"[PlayerIntel] fetch_player_by_id({torn_id}): {e}")
        return None


def fetch_faction_genders(api_key):
    """
    Bulk-fetch genders for all current faction members.
    1. Gets member list via /v2/faction?selections=members
    2. For each member, fetches v1 profile (gender, level, title)
    3. Stores results in MongoDB faction_members_col

    Runs synchronously — call from a background executor for non-blocking use.
    Rate: ~1 profile/sec, safe under Torn's default limit.
    Returns count of members processed.
    """
    import time as _time

    # Step 1: Get faction member list
    try:
        r = requests.get(
            f"{TORN_V2}/faction",
            params={"key": api_key, "selections": "members"},
            timeout=10
        )
        data = r.json()
        members_raw = data.get("members", [])
        if isinstance(members_raw, dict):
            members_raw = list(members_raw.values())
        if not members_raw:
            print("[PlayerIntel] fetch_faction_genders: no members returned")
            return 0
    except Exception as e:
        print(f"[PlayerIntel] fetch_faction_genders member list error: {e}")
        return 0

    count = 0
    for member in members_raw:
        torn_id = member.get("id")
        torn_name = member.get("name", str(torn_id))
        if not torn_id:
            continue

        profile = fetch_player_by_id(torn_id, api_key)
        gender = profile.get("gender") if profile else None
        level = profile.get("level") if profile else None
        title = profile.get("title") if profile else None

        memory_db.save_faction_member(torn_id, torn_name, gender=gender, extra={
            "level": level,
            "title": title,
        })

        # Update in-memory gender dict if ai_engine is loaded
        if gender:
            try:
                import ai_engine as _ae
                _ae.PLAYER_GENDERS[torn_name] = gender
            except Exception:
                pass

        count += 1
        _time.sleep(0.7)  # stay safely under Torn rate limit

    print(f"[PlayerIntel] fetch_faction_genders: processed {count} members")
    return count


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
        torn_id = profile.get("player_id")
        level = profile.get("level")
        title = profile.get("title")
        rank = profile.get("rank")
        age_days = profile.get("age")
        donator = profile.get("donator")
        gender = profile.get("gender")
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
            "torn_id": torn_id,
            "torn_name": name,
            "level": level,
            "title": title,
            "rank": rank,
            "age_days": age_days,
            "donator": donator,
            "gender": gender,
            "status": status,
            "faction_position": faction_pos,
            "company_id": company_id,
            "company_name": company_name,
            "job_position": job_pos,
            "company": company_data,
            "fetched_at": datetime.now(),
        })

        # Register in faction_members for gender + torn_id lookups
        if torn_id:
            memory_db.save_faction_member(torn_id, name, gender=gender, extra={
                "level": level, "title": title
            })

        # Update in-memory gender dict
        if gender:
            try:
                import ai_engine as _ae
                _ae.PLAYER_GENDERS[name] = gender
            except Exception:
                pass

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


def _fmt_last_seen(last_action):
    """Returns a natural last-seen string from a Torn last_action dict, or None."""
    if not last_action or not isinstance(last_action, dict):
        return None
    online_status = last_action.get("status", "")
    relative = last_action.get("relative", "")
    if online_status.lower() == "online":
        return "Online RIGHT NOW"
    if relative:
        return f"{relative} ({online_status})"
    return None


def _company_health_note(stars):
    """Returns a short health commentary string for a company's star rating."""
    if stars is None:
        return ""
    if stars >= 5:
        return "top rated, business is booming"
    if stars == 4:
        return "doing pretty well"
    if stars == 3:
        return "solid, mid-tier"
    return "a bit of a struggle right now"


def get_player_name_context(player_name, api_key):
    """
    Looks up a player by display name -> torn_id in faction_members, then fetches
    their public Torn v1 profile. Returns a formatted multi-line context string or "".
    Includes: level/title, donator status, last seen, company role + health.
    Used when Jeremy is asked about a specific member (not the speaker).
    """
    torn_id = memory_db.get_member_torn_id(player_name)
    if not torn_id:
        return ""
    profile = fetch_player_by_id(torn_id, api_key)
    if not profile:
        return ""

    name = profile.get("name", player_name)
    level = profile.get("level")
    title = profile.get("title", "")
    donator = profile.get("donator")
    gender = profile.get("gender")
    age_days = profile.get("age")
    status_obj = profile.get("status") or {}
    status_state = status_obj.get("state", "Okay") if isinstance(status_obj, dict) else "Okay"
    status_desc = status_obj.get("description", "") if isinstance(status_obj, dict) else ""
    faction_obj = profile.get("faction") or {}
    faction_pos = faction_obj.get("position") if isinstance(faction_obj, dict) else None
    job_obj = profile.get("job") or {}
    company_id = job_obj.get("company_id") if isinstance(job_obj, dict) else None
    company_name = (job_obj.get("company_name") or job_obj.get("company")) if isinstance(job_obj, dict) else None
    job_pos = job_obj.get("position") if isinstance(job_obj, dict) else None
    last_action = profile.get("last_action") or {}

    lines = [f"[Live Profile - {name}]"]

    if level:
        lines.append(f"Level: {level}" + (f" ({title})" if title else ""))

    meta = []
    if gender:
        meta.append(f"Gender: {gender}")
    if age_days:
        years = age_days // 365
        meta.append(f"Age: ~{years}yr in Torn" if years else f"Age: {age_days}d in Torn")
    if meta:
        lines.append(" | ".join(meta))

    if faction_pos:
        lines.append(f"Faction role: {faction_pos}")

    # Non-donator is highlighted more than donator — good convo hook for Jeremy
    if donator is not None:
        if donator:
            lines.append("Donator: YES")
        else:
            lines.append("Donator: NO -- never bought a donator pack (worth asking if they're planning to!)")

    if status_state and status_state.lower() not in ("okay", "ok"):
        s = f"Status: {status_state}"
        if status_desc:
            s += f" -- {status_desc}"
        lines.append(s)

    last_seen = _fmt_last_seen(last_action)
    if last_seen:
        lines.append(f"Last seen: {last_seen}")

    # Company — director vs employee phrasing; fetch health details if possible
    if company_name and job_pos:
        is_director = job_pos.lower() in ("director", "co-director", "owner")
        role_phrase = "Director/Owner at" if is_director else f"{job_pos} at"
        cline = f'Company: {role_phrase} "{company_name}"'
        if company_id:
            cdata = fetch_company(api_key, company_id)
            if cdata:
                type_field = cdata.get("type") or {}
                ctype = type_field.get("name") if isinstance(type_field, dict) else None
                stars = cdata.get("rating")
                emps = cdata.get("employees") or []
                emp_count = len(emps) if isinstance(emps, list) else None
                if ctype:
                    cline += f" ({ctype})"
                if stars is not None:
                    cline += f", {stars} stars -- {_company_health_note(stars)}"
                if emp_count:
                    cline += f", {emp_count} employees"
        lines.append(cline)
    elif company_name:
        lines.append(f'Company: Works at "{company_name}"')

    return "\n".join(lines) if len(lines) > 1 else ""


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
    gender = profile.get("gender")
    job_pos = profile.get("job_position", "")

    if level:
        parts.append(f"Level {level}" + (f" ({title})" if title else ""))
    if gender:
        parts.append(f"Gender: {gender}")
    if status and status.lower() not in ("okay", "ok"):
        parts.append(f"Status: {status}")
    if donator is not None:
        if donator:
            parts.append("Donator: YES")
        else:
            parts.append("Donator: NO -- never bought a pack")
    if faction_pos:
        parts.append(f"Faction: {faction_pos}")
    if age_days:
        years = age_days // 365
        parts.append(f"Age: ~{years}yr" if years else f"Age: {age_days}d")

    cd = profile.get("company")
    if cd:
        is_director = str(job_pos).lower() in ("director", "co-director", "owner")
        role_phrase = "Director/Owner at" if is_director else f"{job_pos or 'Employee'} at"
        stars = cd.get("rating")
        health = f", {stars} stars -- {_company_health_note(stars)}" if stars is not None else ""
        emp = cd.get("employee_count")
        emp_str = f", {emp} staff" if emp else ""
        parts.append(
            f"Company: {role_phrase} \"{cd.get('name', '?')}\" "
            f"({cd.get('type', '?')}){health}{emp_str}"
        )
    elif profile.get("company_name"):
        parts.append(
            f"Company: {profile['company_name']} "
            f"({job_pos or 'employee'})"
        )

    name = profile.get("torn_name", "?")
    return f"[Torn Profile - {name}] " + " | ".join(parts) if parts else ""
