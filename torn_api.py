import requests
base_uri = "https://api.torn.com/v2/"
faction_head = "faction/"

def get_key_info(api_key):
    # Returns Faction ID and User ID from the key.
    url = f'{base_uri}key/info?key={api_key}'
    response = requests.get(url)
    data = response.json().get("info", {})
    return {
        "user_id": data.get("user", {}).get("id"),
        "faction_id": data.get("user", {}).get("faction_id")
    }

def get_latest_war_id(api_key):
    # Gets the most recent Ranked War ID if none is specified.
    url = f'{base_uri}{faction_head}rankedwars?limit=1&sort=DESC&key={api_key}'
    data = requests.get(url).json()
    wars = data.get("rankedwars", [])
    return wars[0] if wars else None

def get_war_report_data(api_key, war_id, faction_id):
    # Fetches base member stats (attacks and raw respect).
    url = f'{base_uri}{faction_head}{war_id}/rankedwarreport?key={api_key}'
    data = requests.get(url).json().get("rankedwarreport", {})
    
    # Find our specific faction's data
    faction_stats = next((f for f in data['factions'] if f['id'] == faction_id), None)
    return faction_stats

def get_chains_for_war(api_key, start_ts, end_ts):
    # Finds all chains that occurred during the war period.
    url = f'{base_uri}{faction_head}chains?from={start_ts}&to={end_ts}&key={api_key}'
    return requests.get(url).json().get("chains", [])

def get_chain_report(api_key, chain_id):
    # Fetches details and bonuses for a specific chain.
    url = f'{base_uri}{faction_head}{chain_id}/chainreport?key={api_key}'
    return requests.get(url).json().get("chainreport", {})