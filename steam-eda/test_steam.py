"""
Antony Feng Hao Chong
Section: AG
CSE 163

What this script does:

Tests for collect_data.py and clean.py. Each parsing function is checked
on small hand-written inputs whose correct output is known, and the
whole cleaning pipeline is checked on a tiny fake data folder of six
games built to cover each special case (free, delisted, DLC, coming
soon, too few reviews).

Usage:
    python test_steam.py      (or: python -m pytest test_steam.py)
"""

import json
import math
import os
import tempfile

import requests

import clean
import collect_data


def test_parse_owners():
    """
    Test the parse_owners function with valid and invalid inputs.
    """
    assert clean.parse_owners('1,000,000 .. 2,000,000') == (1000000,
                                                            2000000)
    assert clean.parse_owners('0 .. 20,000') == (0, 20000)
    for bad in [None, '', 'unknown', '5 .. many']:
        low, high = clean.parse_owners(bad)
        assert math.isnan(low) and math.isnan(high)


def test_parse_release_year():
    """
    Test the parse_release_year function with various date formats.
    """
    assert clean.parse_release_year('Oct 21, 2020') == 2020
    assert clean.parse_release_year('21 Oct, 2020') == 2020
    assert clean.parse_release_year('Q1 2024') == 2024
    assert clean.parse_release_year('2019') == 2019
    assert clean.parse_release_year('Dec 1999') == 1999
    for bad in ['Coming soon', 'To be announced', '', None]:
        assert math.isnan(clean.parse_release_year(bad))


def test_count_languages():
    """
    Test the count_languages function with various HTML formats.
    """
    html = ('English<strong>*</strong>, French<strong>*</strong>, '
            'Simplified Chinese<br><strong>*</strong>languages with full '
            'audio support')
    assert clean.count_languages(html) == 3
    assert clean.count_languages('English') == 1
    assert clean.count_languages('English, German<br/>footnote') == 2
    assert clean.count_languages('') == 0
    assert math.isnan(clean.count_languages(None))


def test_tags_to_list():
    """
    Test the tags_to_list function with tag dictionaries and edge cases.
    """
    tags = {'Indie': 50, 'Roguelike': 300, 'Action': 120}
    assert clean.tags_to_list(tags) == ['Roguelike', 'Action', 'Indie']
    assert clean.tags_to_list([]) == []
    assert clean.tags_to_list(None) == []


def test_price_band():
    """
    Test the price_band function across different price thresholds.
    """
    assert clean.price_band(0, False) == 'Free'
    assert clean.price_band(19.99, True) == 'Free'
    assert clean.price_band(9.99, False) == 'Under $10'
    assert clean.price_band(10.00, False) == '$10-$29.99'
    assert clean.price_band(29.99, False) == '$10-$29.99'
    assert clean.price_band(30.00, False) == '$30+'
    assert math.isnan(clean.price_band(float('nan'), False))


class FakeResponse:
    """
    Mock for requests.Response with status code and JSON body.
    """

    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    """
    Mock for requests.Session that returns canned responses in order.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _no_sleep(seconds):
    """
    Stub for time.sleep to make tests run instantly.
    """


def test_fetch_json_uses_cache():
    """
    Test that fetch_json uses cached files and skips network requests.
    """
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, 'cached.json')
        with open(path, 'w') as f:
            json.dump({'cached': True}, f)
        session = FakeSession([])
        result = collect_data.fetch_json('http://unused', {}, path,
                                         session=session)
        assert result == {'cached': True}
        assert session.calls == 0


def test_fetch_json_retries_then_saves():
    """
    Test that fetch_json retries on errors and saves successful responses.
    """
    original_sleep = collect_data.time.sleep
    collect_data.time.sleep = _no_sleep
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'sub', 'out.json')
            session = FakeSession([FakeResponse(429, None),
                                   requests.ConnectionError(),
                                   FakeResponse(200, None),
                                   FakeResponse(200, {'ok': 1})])
            result = collect_data.fetch_json('http://x', {}, path,
                                             session=session)
            assert result == {'ok': 1}
            assert session.calls == 4
            with open(path) as f:
                assert json.load(f) == {'ok': 1}
    finally:
        collect_data.time.sleep = original_sleep


def test_fetch_json_gives_up():
    """
    Test that fetch_json gives up after max retries and raises RuntimeError.
    """
    original_sleep = collect_data.time.sleep
    collect_data.time.sleep = _no_sleep
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'out.json')
            session = FakeSession([FakeResponse(500, None)] * 3)
            try:
                collect_data.fetch_json('http://x', {}, path,
                                        max_retries=3, session=session)
                assert False, 'expected RuntimeError'
            except RuntimeError:
                pass
            assert not os.path.exists(path)
    finally:
        collect_data.time.sleep = original_sleep


def _spy(appid, positive, negative, price_cents, tags):
    """
    Create a mock SteamSpy API response for a game.
    """
    return {'appid': appid, 'name': f'Game {appid}', 'developer': 'Dev',
            'publisher': 'Pub', 'positive': positive, 'negative': negative,
            'owners': '20,000 .. 50,000', 'price': str(price_cents),
            'initialprice': str(price_cents), 'average_forever': 100,
            'median_forever': 50, 'ccu': 10, 'tags': tags}


def _store(appid, success=True, app_type='game', is_free=False,
           date='Oct 21, 2020', coming_soon=False, genres=('Action',)):
    """
    Create a mock Steam Store API response for a game.
    """
    if not success:
        return {str(appid): {'success': False}}
    return {str(appid): {'success': True, 'data': {
        'type': app_type, 'is_free': is_free, 'required_age': '0',
        'release_date': {'coming_soon': coming_soon, 'date': date},
        'platforms': {'windows': True, 'mac': True, 'linux': False},
        'supported_languages': 'English<strong>*</strong>, French'
                               '<br><strong>*</strong>languages with '
                               'full audio support',
        'genres': [{'id': '1', 'description': g} for g in genres],
        'categories': [{'id': 2, 'description': 'Single-player'}]}}}


def _write_fake_raw(folder):
    """Write mock API responses for six test games to simulate data collection.
    
    Creates games with various edge cases: indie hit, free game, delisted,
    DLC, coming soon, and game with low review count.
    """
    spy = {1: _spy(1, 900, 100, 1999, {'Indie': 10, 'Roguelike': 30}),
           2: _spy(2, 300, 300, 0, []),
           3: _spy(3, 80, 20, 499, {'Action': 5}),
           4: _spy(4, 80, 20, 299, {'Action': 5}),
           5: _spy(5, 0, 0, 1499, {'Action': 5}),
           6: _spy(6, 9, 1, 3999, {'Roguelike': 2})}
    store = {1: _store(1, genres=('Indie', 'Early Access')),
             2: _store(2, is_free=True, date='21 Mar, 2015'),
             3: _store(3, success=False),
             4: _store(4, app_type='dlc'),
             5: _store(5, coming_soon=True, date='Coming soon'),
             6: _store(6, date='Q1 2024')}
    for name, responses in [('steamspy', spy), ('store', store)]:
        os.makedirs(os.path.join(folder, name))
        for appid, body in responses.items():
            with open(os.path.join(folder, name, f'{appid}.json'), 'w') as f:
                json.dump(body, f)


def test_pipeline():
    """Test the full data loading and cleaning pipeline on mock data.
    
    Verifies that the pipeline correctly loads SteamSpy and Steam Store
    data, merges them, filters based on review counts and validity,
    and creates tag indicators.
    """
    with tempfile.TemporaryDirectory() as folder:
        _write_fake_raw(folder)
        spy = clean.load_steamspy(folder)
        store = clean.load_store(folder)
        assert spy.shape[0] == 6 and store.shape[0] == 6
        assert spy.loc[spy['appid'] == 1, 'tags'].item() == 'Roguelike|Indie'
        assert spy['tags'].isna().sum() == 1
        assert store['store_success'].sum() == 5
        assert store.loc[store['appid'] == 1, 'num_languages'].item() == 2

        games = clean.merge_tables(spy, store)
        assert sorted(games['appid']) == [1, 2, 6]
        game1 = games[games['appid'] == 1].iloc[0]
        assert game1['pct_positive'] == 0.9
        assert game1['price'] == 19.99
        assert game1['price_band'] == '$10-$29.99'
        assert game1['very_positive'] == 1
        assert bool(game1['is_indie']) and bool(game1['is_early_access'])
        assert game1['release_year'] == 2020
        game2 = games[games['appid'] == 2].iloc[0]
        assert game2['price_band'] == 'Free'
        assert game2['very_positive'] == 0
        assert not game2['is_indie']

        analysis = clean.filter_min_reviews(games)
        assert sorted(analysis['appid']) == [1, 2]

        tags = clean.tag_indicators(games, n=2)
        assert list(tags.columns) == ['tag_Roguelike', 'tag_Indie']
        assert tags['tag_Roguelike'].tolist() == [1, 0, 1]


def main():
    """
    Run all test functions and report results.
    """
    tests = [value for name, value in globals().items()
             if name.startswith('test_') and callable(value)]
    for test in tests:
        test()
        print(f'passed {test.__name__}')
    print(f'All {len(tests)} tests passed.')


if __name__ == '__main__':
    main()
