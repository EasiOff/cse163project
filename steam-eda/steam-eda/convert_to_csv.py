"""
Antony Feng Hao Chong
Section: AG
CSE 163

What this script does:

Converts raw JSON data from SteamSpy and Steam Store APIs into a single CSV file.
Combines data from both APIs for each game.
"""

import json
import os
import pandas as pd
from pathlib import Path

RAW_DIR = os.path.join('data', 'raw')
STEAMSPY_DIR = os.path.join(RAW_DIR, 'steamspy')
STORE_DIR = os.path.join(RAW_DIR, 'store')
OUTPUT_FILE = os.path.join('data', 'games.csv')

def load_steamspy_data(appid):
    """
    Load SteamSpy data for a game.
    
    Returns the parsed JSON data for a game from the SteamSpy cache,
    or an empty dict if the file doesn't exist.
    """
    path = os.path.join(STEAMSPY_DIR, f'{appid}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_store_data(appid):
    """
    Load Steam Store data for a game.
    
    Returns the parsed JSON data for a game from the Steam Store cache.
    Extracts the game data from the API response format.
    """
    path = os.path.join(STORE_DIR, f'{appid}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Steam Store API returns data under the appid key
            if isinstance(data, dict) and str(appid) in data:
                return data[str(appid)].get('data', {})
            return data
    return {}

def extract_game_data(appid):
    """
    Extract and combine game data from both API sources.
    
    Loads SteamSpy and Steam Store data for a game, extracts relevant
    fields, and returns a dictionary with combined information.
    Returns None if no data is available for the game.
    """
    spy = load_steamspy_data(appid)
    store = load_store_data(appid)
    
    if not spy and not store:
        return None
    
    # Build the row
    row = {'appid': appid}
    
    # From SteamSpy
    if spy:
        row['name'] = spy.get('name', '')
        row['price'] = spy.get('price', 0)
        row['owners'] = spy.get('owners', '')
        row['average_playtime'] = spy.get('average_playtime', 0)
        row['median_playtime'] = spy.get('median_playtime', 0)
        row['positive_reviews'] = spy.get('positive', 0)
        row['negative_reviews'] = spy.get('negative', 0)
        row['score_rank'] = spy.get('score_rank', '')
        row['developers'] = ','.join(spy.get('developer', []))
        row['publishers'] = ','.join(spy.get('publisher', []))
        row['genres'] = ','.join(spy.get('genre', []))
        row['tags'] = ','.join([tag for tag, count in spy.get('tags', {}).items()][:5])  # Top 5 tags
    
    # From Steam Store
    if store:
        row['release_date'] = store.get('release_date', {}).get('date', '')
        row['platforms'] = json.dumps(store.get('platforms', {}))
        store_genres = [g.get('description', '') for g in store.get('genres', [])]
        row['store_genres'] = ','.join(store_genres)
        row['website'] = store.get('website', '')
        row['supported_languages'] = len(store.get('supported_languages', '').split(','))
    
    return row

def main():
    """
    Convert raw JSON files to a single CSV dataset.
    
    Reads all cached API responses, extracts game data, combines them into
    a DataFrame, and saves the result as a CSV file.
    """
    
    # Get all app IDs from steamspy directory
    appids = []
    if os.path.exists(STEAMSPY_DIR):
        appids = [int(f[:-5]) for f in os.listdir(STEAMSPY_DIR) if f.endswith('.json')]
    
    print(f'Found {len(appids)} games')
    
    # Extract data for all games
    rows = []
    for i, appid in enumerate(appids, 1):
        row = extract_game_data(appid)
        if row:
            rows.append(row)
        if i % 500 == 0:
            print(f'  processed {i}/{len(appids)}')
    
    # Create DataFrame and save
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    
    print(f'Done! Saved {len(df)} games to {OUTPUT_FILE}')
    print(f'File size: {os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.2f} MB')

if __name__ == '__main__':
    main()
