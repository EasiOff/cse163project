# What Makes a Steam Game Loved?

CSE 163 final project: price, genre, and player reviews across the top
5,000 Steam games, using data from the SteamSpy API and the Steam Store
API.

## Setup

Requires Python 3.10 or newer.

```
pip install -r requirements.txt
```

## Running the project

Run the scripts in this order from the project folder:

1. `python collect_data.py` downloads raw API responses into `data/raw/`.
   It takes about 4–5 hours for 5,000 games because of the APIs' rate
   limits. You can stop it with Ctrl+C at any time; running it again
   picks up where it stopped. For a quick trial, use
   `python collect_data.py --limit 50`.
2. `python clean.py` parses the raw responses into `data/clean/`
   (`steamspy.csv`, `store.csv`, and the merged `games.csv`).
3. `python eda.py` writes the plots to `figures/` and every summary
   number to `results/eda_summary.txt`.

## Tests

```
python test_steam.py
```

The tests use small hand-written inputs and fake API responses, so they
need no internet connection.

## Data

* SteamSpy API: https://steamspy.com/api.php
* Steam Store API: https://store.steampowered.com/api/appdetails?appids=730&cc=us&l=en

Neither API needs an account or key. The raw responses are not stored in
this repository because they are large; a copy is available on Google
Drive: LINK TO BE ADDED.
