import requests

base_uri = "https://api.torn.com/v2/"
faction_head = "faction/"

def get_key_info(api_key):
    url = f'{base_uri}key/info?key={api_key}'
    try:
        res = requests.get(url).json()
        if "error" in res:
            print(f"Torn API Error (Key Info): {res['error']}")
            return None
        data = res.get("info", {})
        user_data = data.get("user", {})
        return {"user_id": user_data.get("id"), "faction_id": user_data.get("faction_id")}
    except Exception as e:
        print(f"Error fetching key info: {e}")
        return None

def get_latest_war_id(api_key):
    """Fetches the last 2 wars and returns the one that ended most recently."""
    url = f'{base_uri}{faction_head}rankedwars?limit=2&sort=DESC&key={api_key}'
    try:
        response = requests.get(url)
        data = response.json()
        if "error" in data:
            print(f"Torn API Error (Ranked Wars): {data['error']}")
            return None
            
        wars = data.get("rankedwars", [])
        
        if not wars:
            return None
            
        # If there's only one war, return it
        if len(wars) == 1:
            return wars[0]
            
        # Return the war with the higher 'end' timestamp
        # This ignores upcoming wars (end = 0) and picks the most recently finished one
        latest_war = max(wars, key=lambda x: x.get('end', 0))
        return latest_war
        
    except Exception as e:
        print(f"Error fetching latest war: {e}")
        return None

def get_war_report_data(api_key, war_id, faction_id):
    url = f'{base_uri}{faction_head}{war_id}/rankedwarreport?key={api_key}'
    try:
        res = requests.get(url).json()
        if "error" in res:
            print(f"Torn API Error (War Report): {res['error']}")
            return None, None, None, None
            
        data = res.get("rankedwarreport", {})
        # Find opponent name for the title
        factions = data.get('factions', [])
        opponent = next((f['name'] for f in factions if f['id'] != faction_id), "Opponent")
        my_faction = next((f for f in factions if f['id'] == faction_id), None)
        return my_faction, opponent, data.get('start'), data.get('end')
    except Exception as e:
        print(f"Error fetching war report: {e}")
        return None, None, None, None

def get_chains_for_war(api_key, start, end):
    # If war is ongoing (end=0), use current time for the 'to' parameter
    to_ts = end if end and end > 0 else int(time.time())
    
    # Increase limit to 100 to ensure we don't miss chains in a long war
    url = f'{base_uri}{faction_head}chains?from={start}&to={to_ts}&limit=100&key={api_key}'
    try:
        res = requests.get(url).json()
        if "error" in res:
            print(f"Torn API Error (Chains): {res['error']}")
            return []
        return res.get("chains", [])
    except Exception as e:
        print(f"Error fetching chains: {e}")
        return []

def get_chain_report(api_key, chain_id):
    url = f'{base_uri}{faction_head}{chain_id}/chainreport?key={api_key}'
    try:
        res = requests.get(url).json()
        if "error" in res:
            print(f"Torn API Error (Chain Report {chain_id}): {res['error']}")
            return {}
        return res.get("chainreport", {})
    except Exception as e:
        print(f"Error fetching chain report {chain_id}: {e}")
        return {}

def get_faction_levels(api_key, faction_id):
    data = requests.get(f'{base_uri}faction/members?key={api_key}').json()
    return {m['id']: m['level'] for m in data.get('members', [])}