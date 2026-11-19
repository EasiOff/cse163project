"""
Antony Feng Hao Chong
Section: AG
CSE 163

What this script does:

Turns the raw JSON responses saved by collect_data.py into three tables:

* data/clean/steamspy.csv: one row per game from SteamSpy
* data/clean/store.csv:    one row per game from the Steam Store API
* data/clean/games.csv:    the two joined on appid, keeping only released
  games, with derived columns used by the research questions

Usage:
    python clean.py
"""

import glob
import json
import os
import re

import numpy as np
import pandas as pd

RAW_DIR = os.path.join('data', 'raw')
CLEAN_DIR = os.path.join('data', 'clean')

# Multi-valued fields (tags, genres, categories) are stored in one CSV
# cell joined by this character, which never appears in Steam's names.
SEP = '|'

MIN_REVIEWS = 50          # games with fewer reviews are excluded
VERY_POSITIVE_PCT = 0.80  # Steam's "Very Positive" threshold ...
VERY_POSITIVE_MIN = 500   # ... as we define it for RQ4

PRICE_BANDS = ['Free', 'Under $10', '$10-$29.99', '$30+']



def parse_owners(owners):
    """
    Parse SteamSpy owner range into low and high estimates.
    
    Converts a SteamSpy owners range such as "1,000,000 .. 2,000,000"
    into a (low, high) tuple of ints. Returns (nan, nan) if the value is
    missing or not in that format.
    """
    if not isinstance(owners, str) or '..' not in owners:
        return (np.nan, np.nan)
    low, high = owners.split('..')
    try:
        return (int(low.replace(',', '').strip()),
                int(high.replace(',', '').strip()))
    except ValueError:
        return (np.nan, np.nan)


def parse_release_year(date_text):
    """
    Extract year from Steam release date string.
    
    Returns the four-digit year in a Steam release date string, which can
    look like "Oct 21, 2020", "21 Oct, 2020", "Q1 2024", or "2019".
    Returns nan for strings with no year, such as "Coming soon" or "To be
    announced", and for missing values.
    """
    if not isinstance(date_text, str):
        return np.nan
    match = re.search(r'\b(19|20)\d{2}\b', date_text)
    return int(match.group(0)) if match else np.nan


def count_languages(html):
    """
    Count languages from Steam Store supported languages HTML.
    
    Counts the languages in a Steam Store supported_languages string, e.g.
    'English<strong>*</strong>, French<br><strong>*</strong>languages with
    full audio support' has 2 languages. The footnote after <br> is
    ignored, HTML tags and asterisks are stripped, and the remaining
    comma-separated names are counted. Returns nan if html is missing.
    """
    if not isinstance(html, str):
        return np.nan
    text = re.split(r'<br\s*/?>', html)[0]
    text = re.sub(r'<[^>]+>', '', text)
    names = [name.replace('*', '').strip() for name in text.split(',')]
    return len([name for name in names if name])


def tags_to_list(tags):
    """
    Convert SteamSpy tags dictionary to sorted list.
    
    Returns SteamSpy's tags as a list of tag names, most votes first.
    SteamSpy sends a dict of {tag: votes} normally but an empty list when
    a game has no tags, so both shapes are accepted.
    """
    if isinstance(tags, dict):
        return [tag for tag, _ in sorted(tags.items(),
                                         key=lambda item: -item[1])]
    return []


def price_band(price, is_free):
    """
    Categorize price into discrete bands.
    
    Returns the price band label for a price in US dollars: "Free",
    "Under $10", "$10-$29.99", or "$30+". Returns nan if price is missing
    and the game is not marked free.
    """
    if is_free is True or price == 0:
        return 'Free'
    if price is None or pd.isna(price):
        return np.nan
    if price < 10:
        return 'Under $10'
    if price < 30:
        return '$10-$29.99'
    return '$30+'



def _load_json_files(folder):
    """
    Load all JSON files from a directory into a dictionary.
    
    Returns a dict mapping appid (int) to the parsed JSON of every
    <appid>.json file in folder.
    """
    results = {}
    for path in glob.glob(os.path.join(folder, '*.json')):
        appid = int(os.path.splitext(os.path.basename(path))[0])
        with open(path, encoding='utf-8') as f:
            results[appid] = json.load(f)
    return results


def load_steamspy(raw_dir=RAW_DIR):
    """
    Load and parse SteamSpy raw data into a DataFrame.
    
    Returns a DataFrame with one row per game in raw_dir/steamspy/,
    holding the SteamSpy fields used in this project.
    """
    rows = []
    for appid, data in _load_json_files(os.path.join(raw_dir,
                                                     'steamspy')).items():
        low, high = parse_owners(data.get('owners'))
        rows.append({
            'appid': appid,
            'name': data.get('name'),
            'developer': data.get('developer'),
            'publisher': data.get('publisher'),
            'positive': data.get('positive'),
            'negative': data.get('negative'),
            'owners_low': low,
            'owners_high': high,
            # initialprice is the full price; price can be a sale price.
            'price_cents': data.get('initialprice'),
            'average_forever': data.get('average_forever'),
            'median_forever': data.get('median_forever'),
            'ccu': data.get('ccu'),
            'tags': SEP.join(tags_to_list(data.get('tags'))),
        })
    df = pd.DataFrame(rows)
    numeric = ['positive', 'negative', 'price_cents', 'average_forever',
               'median_forever', 'ccu']
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors='coerce')
    # SteamSpy uses empty strings for unknown names; treat them as missing.
    for column in ['name', 'developer', 'publisher', 'tags']:
        df[column] = df[column].replace('', np.nan)
    return df.sort_values('appid').reset_index(drop=True)


def _names(items):
    """
    Extract names from Store API list of items.
    
    Joins the "description" of each item in a Store API list of
    {id, description} dicts. Returns nan if items is missing.
    """
    if not isinstance(items, list):
        return np.nan
    return SEP.join(item.get('description', '') for item in items)


def load_store(raw_dir=RAW_DIR):
    """
    Load and parse Steam Store raw data into a DataFrame.
    
    Returns a DataFrame with one row per game in raw_dir/store/. Games the
    Store API returned "success": false for (delisted or region-locked)
    are kept with store_success False and missing values elsewhere.
    """
    rows = []
    for appid, response in _load_json_files(os.path.join(raw_dir,
                                                         'store')).items():
        entry = response.get(str(appid), {}) if response else {}
        success = bool(entry.get('success'))
        data = entry.get('data', {}) if success else {}
        release = data.get('release_date', {})
        platforms = data.get('platforms', {})
        genres = _names(data.get('genres'))
        rows.append({
            'appid': appid,
            'store_success': success,
            'type': data.get('type'),
            'is_free': data.get('is_free'),
            'required_age': data.get('required_age'),
            'release_date': release.get('date'),
            'coming_soon': release.get('coming_soon'),
            'release_year': parse_release_year(release.get('date')),
            'windows': platforms.get('windows'),
            'mac': platforms.get('mac'),
            'linux': platforms.get('linux'),
            'num_languages': count_languages(
                data.get('supported_languages')),
            'metacritic': data.get('metacritic', {}).get('score'),
            'genres': genres,
            'categories': _names(data.get('categories')),
        })
    df = pd.DataFrame(rows)
    df['required_age'] = pd.to_numeric(df['required_age'], errors='coerce')
    df['metacritic'] = pd.to_numeric(df['metacritic'], errors='coerce')
    has_genres = df['genres'].notna()
    genre_lists = df['genres'].fillna('').str.split(SEP)
    # Unknown (missing) when the Store gave no genres at all.
    for column, genre in [('is_indie', 'Indie'),
                          ('is_early_access', 'Early Access')]:
        df[column] = genre_lists.apply(lambda g: genre in g).astype(
            object).where(has_genres, np.nan)
    platform_cols = ['windows', 'mac', 'linux']
    num_platforms = df[platform_cols].fillna(False).astype(int).sum(axis=1)
    df['num_platforms'] = num_platforms.where(df['store_success'])
    return df.sort_values('appid').reset_index(drop=True)


def merge_tables(steamspy, store):
    """
    Join SteamSpy and Steam Store data with derived features.
    
    Joins the SteamSpy and Store tables on appid (inner join), keeps only
    released games (Store type "game", not "coming soon"), and adds the
    derived columns used by the research questions: total_reviews,
    pct_positive, price, price_band, owners_mid, and very_positive.
    """
    games = steamspy.merge(store, on='appid', how='inner')
    coming_soon = games['coming_soon'].fillna(False).astype(bool)
    released = (games['store_success'] & (games['type'] == 'game')
                & ~coming_soon)
    games = games[released].copy()

    games['total_reviews'] = games['positive'] + games['negative']
    games['pct_positive'] = (games['positive']
                             / games['total_reviews'].replace(0, np.nan))
    games['price'] = games['price_cents'] / 100
    games['price_band'] = [price_band(p, f) for p, f
                           in zip(games['price'], games['is_free'])]
    games['owners_mid'] = (games['owners_low'] + games['owners_high']) / 2
    games['very_positive'] = ((games['pct_positive'] >= VERY_POSITIVE_PCT)
                              & (games['total_reviews']
                                 >= VERY_POSITIVE_MIN)).astype(int)
    return games.reset_index(drop=True)


def filter_min_reviews(games, min_reviews=MIN_REVIEWS):
    """
    Filter games to those with minimum review threshold.
    
    Returns only the games with at least min_reviews reviews, so that
    pct_positive is not based on a handful of votes.
    """
    return games[games['total_reviews'] >= min_reviews].reset_index(
        drop=True)


def tag_indicators(games, n=100):
    """
    Create binary indicator columns for the top n tags.
    
    Returns a DataFrame of 0/1 columns named tag_<Tag>, one for each of
    the n most common SteamSpy tags, aligned with games' index.
    """
    tag_lists = games['tags'].fillna('').str.split(SEP)
    counts = tag_lists.explode().loc[lambda s: s != ''].value_counts()
    top = counts.index[:n]
    return pd.DataFrame({f'tag_{tag}': tag_lists.apply(lambda t: int(tag in t))
                         for tag in top}, index=games.index)


def main():
    """
    Run the data cleaning pipeline.
    
    Loads raw API responses, parses them into DataFrames, merges the tables,
    and saves the cleaned data to CSV files.
    """
    steamspy = load_steamspy()
    store = load_store()
    games = merge_tables(steamspy, store)
    steamspy.to_csv(os.path.join(CLEAN_DIR, 'steamspy.csv'), index=False)
    store.to_csv(os.path.join(CLEAN_DIR, 'store.csv'), index=False)
    games.to_csv(os.path.join(CLEAN_DIR, 'games.csv'), index=False)
    print(f'SteamSpy: {len(steamspy)} rows, Store: {len(store)} rows, '
          f'merged released games: {len(games)} rows')
    print('Saved to', CLEAN_DIR)


if __name__ == '__main__':
    main()
