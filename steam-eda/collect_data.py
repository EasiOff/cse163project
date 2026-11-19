"""
Antony Feng Hao Chong
Section: AG
CSE 163

What this script does:

Downloads data about the most-owned Steam games from two public APIs:

* SteamSpy (https://steamspy.com/api.php): review counts, owner
  estimates, price, playtime, and user tags.
* Steam Store (https://store.steampowered.com/api/appdetails): release
  date, genres, platforms, supported languages, and more.

Every response is cached as a JSON file under data/raw/, so the script
can be stopped and restarted without repeating finished requests.

Usage:
    python collect_data.py            # top 5,000 games (about 3 hours)
    python collect_data.py --pages 1  # top 1,000 games only
    python collect_data.py --limit 50 # quick test on 50 games
"""

import argparse
import json
import os
import time
import requests

STEAMSPY_URL = 'https://steamspy.com/api.php'
STORE_URL = 'https://store.steampowered.com/api/appdetails'
RAW_DIR = os.path.join('data', 'raw')

# Pauses between requests, in seconds, chosen to respect each API's
# published or observed rate limit.
STEAMSPY_ALL_DELAY = 61     # "all" requests: 1 per minute
STEAMSPY_APP_DELAY = 1.0    # "appdetails" requests: 1 per second
STORE_DELAY = 1.5           # Store API allows about 200 requests / 5 min

MAX_RETRIES = 5
HEADERS = {'User-Agent': 'CSE163-student-project (steam-eda)'}


def fetch_json(url, params, cache_path, delay=0.0, max_retries=MAX_RETRIES,
               session=None):
    """
    Fetch JSON data from a URL with caching and retry logic.
    
    Returns the parsed JSON response for url with the given query params.
    If cache_path already exists, its contents are returned and no request
    is made. Otherwise the request is sent, retrying with exponential
    backoff on errors, rate limits (HTTP 429), and empty responses. A
    successful response is saved to cache_path, and the function then
    sleeps for delay seconds so the next request respects the rate limit.
    Raises RuntimeError if every attempt fails.
    """
    if os.path.exists(cache_path):
        with open(cache_path, encoding='utf-8') as f:
            return json.load(f)

    getter = session if session is not None else requests
    wait = 5
    for attempt in range(1, max_retries + 1):
        try:
            response = getter.get(url, params=params, headers=HEADERS,
                                  timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data is not None:
                    _save_json(data, cache_path)
                    time.sleep(delay)
                    return data
                reason = 'empty response'
            else:
                reason = f'HTTP {response.status_code}'
        except (requests.RequestException, ValueError) as error:
            reason = type(error).__name__
        print(f'  attempt {attempt} failed ({reason}); waiting {wait}s')
        time.sleep(wait)
        wait *= 2
    raise RuntimeError(f'Gave up on {url} {params}')


def _save_json(data, path):
    """
    Save JSON data to a file with atomic writes.
    
    Writes data to path as JSON, creating parent folders as needed. Writes
    to a temporary file first so an interrupted run never leaves a
    half-written cache file behind.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(temp_path, path)


def get_top_appids(num_pages, raw_dir=RAW_DIR, session=None):
    """
    Retrieve Steam app IDs for the most-owned games from SteamSpy.
    
    Returns a list of Steam appids for the most-owned games, in the order
    SteamSpy ranks them (most owners first). Each SteamSpy "all" page
    holds 1,000 games, so num_pages=5 gives the top 5,000.
    """
    appids = []
    for page in range(num_pages):
        cache_path = os.path.join(raw_dir, 'steamspy_all',
                                  f'page_{page}.json')
        cached = os.path.exists(cache_path)
        if not cached:
            print(f'Downloading SteamSpy list page {page} ...')
        data = fetch_json(STEAMSPY_URL, {'request': 'all', 'page': page},
                          cache_path, delay=0, session=session)
        appids.extend(int(appid) for appid in data)
        # Only wait when we actually hit the API and another page follows.
        if not cached and page < num_pages - 1:
            time.sleep(STEAMSPY_ALL_DELAY)
    return appids


def collect_game_details(appids, raw_dir=RAW_DIR, session=None):
    """
    Download game data from SteamSpy and Steam Store APIs.
    
    Downloads (or loads from cache) the SteamSpy appdetails and Steam Store
    appdetails responses for every appid, printing progress as it goes.
    Games whose requests fail after every retry are skipped and listed at
    the end, so one bad game does not stop a multi-hour run.
    """
    failed = []
    total = len(appids)
    for i, appid in enumerate(appids, start=1):
        spy_path = os.path.join(raw_dir, 'steamspy', f'{appid}.json')
        store_path = os.path.join(raw_dir, 'store', f'{appid}.json')
        try:
            fetch_json(STEAMSPY_URL,
                       {'request': 'appdetails', 'appid': appid},
                       spy_path, delay=STEAMSPY_APP_DELAY, session=session)
            fetch_json(STORE_URL,
                       {'appids': appid, 'cc': 'us', 'l': 'en'},
                       store_path, delay=STORE_DELAY, session=session)
        except RuntimeError as error:
            print(f'  skipping {appid}: {error}')
            failed.append(appid)
        if i % 100 == 0 or i == total:
            print(f'{i}/{total} games done')
    if failed:
        print(f'{len(failed)} games failed; rerun to retry them: {failed}')
    return failed


def main():
    """
    Run the data collection pipeline with command-line options.
    
    Collects Steam game data by fetching the top games list and downloading
    details for each game from both SteamSpy and Steam Store APIs.
    Supports --pages, --limit flags for controlling dataset size.
    """
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    parser.add_argument('--pages', type=int, default=5,
                        help='SteamSpy pages of 1,000 games (default 5)')
    parser.add_argument('--limit', type=int, default=None,
                        help='only collect the first N games (for testing)')
    args = parser.parse_args()

    with requests.Session() as session:
        appids = get_top_appids(args.pages, session=session)
        if args.limit is not None:
            appids = appids[:args.limit]
        print(f'Collecting details for {len(appids)} games ...')
        collect_game_details(appids, session=session)
    print('Done. Raw responses are in', RAW_DIR)


if __name__ == '__main__':
    main()
