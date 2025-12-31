import requests

base_uri = "https://api.torn.com/v2/"
faction_head = "faction/"

def get_key_info(api_key):
    url = f'{base_uri}key/info?key={api_key}'
    try:
        data = requests.get(url).json().get("info", {})
        user_data = data.get("user", {})
        return {"user_id": user_data.get("id"), "faction_id": user_data.get("faction_id")}
    except: return None

def get_latest_war_id(api_key):
    url = f'{base_uri}{faction_head}rankedwars?limit=1&sort=DESC&key={api_key}'
    try:
        wars = requests.get(url).json().get("rankedwars", [])
        return wars[0] if wars else None
    except: return None

def get_war_report_data(api_key, war_id, faction_id):
    url = f'{base_uri}{faction_head}{war_id}/rankedwarreport?key={api_key}'
    try:
        data = requests.get(url).json().get("rankedwarreport", {})
        # Find opponent name for the title
        factions = data.get('factions', [])
        opponent = next((f['name'] for f in factions if f['id'] != faction_id), "Opponent")
        my_faction = next((f for f in factions if f['id'] == faction_id), None)
        return my_faction, opponent, data['start'], data['end']
    except: return None, None, None, None

def get_chains_for_war(api_key, start, end):
    url = f'{base_uri}{faction_head}chains?from={start}&to={end}&key={api_key}'
    return requests.get(url).json().get("chains", [])

def get_chain_report(api_key, chain_id):
    url = f'{base_uri}{faction_head}{chain_id}/chainreport?key={api_key}'
    return requests.get(url).json().get("chainreport", {})