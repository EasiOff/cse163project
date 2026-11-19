"""
Antony Feng Hao Chong
Section: AG
CSE 163

What this script does:

Exploratory data analysis for the Steam project. Reads the tables made
by clean.py and, for each dataset (SteamSpy, Steam Store, and the merged
games table), reports its size, missing data, a summary of every
variable of interest, and plots.

Outputs:
* results/eda_summary.txt: every number used in the EDA report
* results/tag_counts.csv:  number of games carrying each SteamSpy tag
* figures/*.png:           the EDA plots

Usage:
    python eda.py
"""

import os
import matplotlib
import pandas as pd
import seaborn as sns
import clean

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator 

FIG_DIR = 'figures'
RESULTS_DIR = 'results'
MIN_GAMES_PER_TAG = 100   # tags on fewer games are left out of RQ2 plots (there are ridiculous tags)


def size_summary(df, name, row_meaning):
    """
    Returns lines giving the number of rows and columns of df, what a row
    represents, and the column names.
    """
    rows, cols = df.shape
    return [f'## {name}: size',
            f'{rows} rows x {cols} columns. Each row is {row_meaning}.',
            'Columns: ' + ', '.join(df.columns), '']


def missing_summary(df, name):
    """
    Generate a summary of missing data in a DataFrame.
    
    Returns a list of formatted lines describing missing values in each
    column and the total number of rows with any missing data.
    """
    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    lines = [f'## {name}: missing data']
    if missing.empty:
        lines.append('df.isna().sum().sum() == 0: no missing values.')
    else:
        pct = (missing / len(df) * 100).round(1)
        table = pd.DataFrame({'missing': missing, 'percent': pct})
        lines.append(table.to_string())
        rows_with_missing = df.isna().any(axis=1).sum()
        lines.append(f'Rows with at least one missing value: '
                     f'{rows_with_missing} of {len(df)} '
                     f'({rows_with_missing / len(df) * 100:.1f}%)')
    lines.append('')
    return lines


def quantitative_summary(df, columns, name):
    """
    Generate statistical summaries for numeric columns.
    
    Returns lines with descriptive statistics (mean, std, min, quartiles,
    median, max, and count) for each specified column.
    """
    table = df[columns].describe().T.round(3)
    return [f'## {name}: quantitative variables', table.to_string(), '']


def categorical_summary(df, columns, name, max_values=30):
    """
    Generate value counts for categorical columns.
    
    Returns lines showing the count of each unique value in the specified
    columns. Shows up to max_values most common values per column.
    """
    lines = [f'## {name}: categorical variables']
    for column in columns:
        counts = df[column].value_counts(dropna=False)
        lines.append(f'{column} ({len(counts)} unique values):')
        lines.append(counts.head(max_values).to_string())
        if len(counts) > max_values:
            lines.append(f'... {len(counts) - max_values} more values')
        lines.append('')
    return lines


def save_figure(fig, filename):
    """
    Save a matplotlib figure to file and close it.
    
    Saves the figure to the figures directory at 200 DPI and closes it.
    """
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, filename), dpi=200)
    plt.close(fig)


def tag_counts(games):
    """
    Count the frequency of each user tag across games.
    
    Returns a Series with the number of games for each tag, sorted
    in descending order by frequency.
    """
    tags = games['tags'].fillna('').str.split(clean.SEP).explode()
    return tags[tags != ''].value_counts()


def eda_steamspy(spy):
    """
    Analyze the SteamSpy dataset.
    
    Generates summary statistics, missing data analysis, and plots showing
    the distribution of positive review percentages and the 20 most
    common user tags.
    """
    spy = spy.copy()
    spy['total_reviews'] = spy['positive'] + spy['negative']
    spy['pct_positive'] = spy['positive'] / spy['total_reviews'].where(
        spy['total_reviews'] > 0)
    spy['price'] = spy['price_cents'] / 100
    spy['owners_range'] = (spy['owners_low'].map('{:,.0f}'.format) + ' .. '
                           + spy['owners_high'].map('{:,.0f}'.format))

    lines = size_summary(spy.drop(columns=['total_reviews', 'pct_positive',
                                           'price', 'owners_range']),
                         'SteamSpy', 'one game')
    lines += missing_summary(spy, 'SteamSpy')
    lines += quantitative_summary(
        spy, ['positive', 'negative', 'total_reviews', 'pct_positive',
              'price', 'average_forever', 'ccu'], 'SteamSpy')
    lines += categorical_summary(spy, ['owners_range'], 'SteamSpy')

    counts = tag_counts(spy)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    counts.rename('num_games').to_csv(
        os.path.join(RESULTS_DIR, 'tag_counts.csv'), index_label='tag')
    lines += ['## SteamSpy: tags (full list in results/tag_counts.csv)',
              f'{len(counts)} unique tags. Games with no tags: '
              f'{spy["tags"].isna().sum()}',
              counts.head(30).to_string(), '']

    # Plot 1: distribution of pct_positive among games with enough reviews
    reviewed = spy[spy['total_reviews'] >= clean.MIN_REVIEWS]
    share_vp = (reviewed['pct_positive'] >= clean.VERY_POSITIVE_PCT).mean()
    lines += [f'Games with >= {clean.MIN_REVIEWS} reviews: {len(reviewed)}; '
              f'share with pct_positive >= 0.80: {share_vp:.3f}', '']
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.histplot(reviewed['pct_positive'] * 100, bins=40, ax=ax,
                 color='#4C72B0')
    ax.axvline(80, color='#C44E52', linestyle='--',
               label='80% ("Very Positive" threshold)')
    ax.set_title('Share of positive reviews per game')
    ax.set_xlabel('Positive reviews (%)')
    ax.set_ylabel('Number of games')
    ax.legend()
    save_figure(fig, 'fig1_spy_pct_positive.png')

    # Plot 2: most common tags
    fig, ax = plt.subplots(figsize=(7, 5))
    top = counts.head(20)
    sns.barplot(x=top.values, y=top.index, ax=ax, color='#4C72B0')
    ax.set_title('20 most common SteamSpy user tags')
    ax.set_xlabel('Number of games with the tag')
    ax.set_ylabel('')
    save_figure(fig, 'fig2_spy_top_tags.png')
    return lines


def eda_store(store):
    """
    Analyze the Steam Store dataset.
    
    Generates summary statistics, missing data analysis, and plots showing
    game releases by year (indie vs non-indie) and the distribution of
    supported languages.
    """
    lines = size_summary(store, 'Steam Store', 'one Steam app')
    lines += missing_summary(store, 'Steam Store')
    ok = store[store['store_success']]
    lines += [f'Store returned success: false for '
              f'{(~store["store_success"]).sum()} apps (delisted or '
              f'region-locked); the summaries below use the other '
              f'{len(ok)}.', '']
    lines += quantitative_summary(
        ok, ['release_year', 'num_languages', 'num_platforms',
             'required_age', 'metacritic'], 'Steam Store')
    lines += categorical_summary(
        ok, ['type', 'coming_soon', 'is_free', 'is_indie',
             'is_early_access', 'windows', 'mac', 'linux', 'required_age'],
        'Steam Store')
    genres = ok['genres'].fillna('').str.split(clean.SEP).explode()
    lines += ['## Steam Store: genres', genres[genres != ''].value_counts()
              .to_string(), '']

    games_only = ok[(ok['type'] == 'game')
                    & ok['release_year'].between(2006, 2025)].copy()
    games_only['Indie'] = games_only['is_indie'].map(
        {True: 'Indie', False: 'Not indie'})

    # Plot 3: releases per year, indie vs not
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(data=games_only, x='release_year', hue='Indie',
                 multiple='stack', discrete=True, ax=ax,
                 hue_order=['Not indie', 'Indie'],
                 palette=['#4C72B0', '#DD8452'])
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title('Games in the sample by release year')
    ax.set_xlabel('Release year')
    ax.set_ylabel('Number of games')
    save_figure(fig, 'fig3_store_release_years.png')

    # Plot 4: number of supported languages
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.histplot(games_only['num_languages'].dropna(), discrete=True, ax=ax,
                 color='#4C72B0')
    ax.set_title('Number of languages each game supports')
    ax.set_xlabel('Supported languages')
    ax.set_ylabel('Number of games')
    save_figure(fig, 'fig4_store_languages.png')
    return lines


def eda_games(games):
    """
    Analyze the merged games dataset.
    
    Generates summary statistics and plots for research questions: RQ1
    (price band effect on reviews), RQ2 (tag effect on reviews), and RQ3
    (indie game trends over time).
    """
    analysis = clean.filter_min_reviews(games)
    lines = size_summary(games, 'Merged games', 'one released game found '
                         'in both SteamSpy and the Store')
    lines += [f'After keeping games with >= {clean.MIN_REVIEWS} reviews: '
              f'{len(analysis)} rows (dropped '
              f'{len(games) - len(analysis)}).', '']
    lines += missing_summary(analysis, 'Merged games (analysis set)')
    lines += quantitative_summary(
        analysis, ['pct_positive', 'total_reviews', 'price',
                   'num_languages', 'release_year'], 'Merged games')
    lines += categorical_summary(
        analysis, ['price_band', 'very_positive', 'is_indie',
                   'is_early_access'], 'Merged games')

    # RQ1: price band
    band_medians = analysis.groupby('price_band')['pct_positive'].agg(
        ['count', 'median']).reindex(clean.PRICE_BANDS)
    lines += ['## RQ1 preview: pct_positive by price band',
              band_medians.round(3).to_string(), '']
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.boxplot(data=analysis, x='price_band', y=analysis['pct_positive']
                * 100, order=clean.PRICE_BANDS, ax=ax, color='#8DA0CB',
                fliersize=2)
    # Escape "$" so matplotlib does not read the labels as math text.
    ax.set_xticks(range(len(clean.PRICE_BANDS)))
    ax.set_xticklabels([band.replace('$', r'\$')
                        for band in clean.PRICE_BANDS])
    ax.set_title('Positive-review share by price band')
    ax.set_xlabel('Price band (full price, USD)')
    ax.set_ylabel('Positive reviews (%)')
    save_figure(fig, 'fig5_games_price_band.png')

    # RQ2: tags ranked by median pct_positive
    exploded = analysis[['tags', 'pct_positive']].assign(
        tag=analysis['tags'].fillna('').str.split(clean.SEP)).explode('tag')
    exploded = exploded[exploded['tag'] != '']
    by_tag = exploded.groupby('tag')['pct_positive'].agg(['count',
                                                         'median'])
    by_tag = by_tag[by_tag['count'] >= MIN_GAMES_PER_TAG].sort_values(
        'median')
    ea = analysis.groupby('is_early_access')['pct_positive'].agg(
        ['count', 'median'])
    lines += [f'## RQ2 preview: {len(by_tag)} tags on >= '
              f'{MIN_GAMES_PER_TAG} games', 'Lowest 10:',
              by_tag.head(10).round(3).to_string(), 'Highest 10:',
              by_tag.tail(10).round(3).to_string(),
              'Early Access vs released:', ea.round(3).to_string(), '']
    if len(by_tag) >= 2:
        n = min(10, len(by_tag) // 2)
        ends = pd.concat([by_tag.head(n), by_tag.tail(n)])
        colors = ['#C44E52'] * n + ['#55A868'] * n
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.barh(ends.index, ends['median'] * 100, color=colors)
        ax.set_title(f'Tags with the lowest (red) and highest (green)\n'
                     f'median positive-review share (tags on >= '
                     f'{MIN_GAMES_PER_TAG} games)')
        ax.set_xlabel('Median positive reviews (%)')
        ax.set_xlim(left=max(0, ends['median'].min() * 100 - 10))
        save_figure(fig, 'fig6_games_tags.png')

    # RQ3: indie trend
    recent = analysis[analysis['release_year'].between(2010, 2025)
                      & analysis['is_indie'].notna()].copy()
    recent['Indie'] = recent['is_indie'].map({True: 'Indie',
                                              False: 'Not indie'})
    trend = recent.groupby(['release_year', 'Indie'])['pct_positive'].agg(
        ['count', 'median']).unstack('Indie')
    lines += ['## RQ3 preview: median pct_positive by year and indie',
              trend.round(3).to_string(), '']
    fig, ax = plt.subplots(figsize=(8, 4))
    medians = recent.groupby(['release_year', 'Indie'],
                             as_index=False)['pct_positive'].median()
    sns.lineplot(data=medians, x='release_year',
                 y=medians['pct_positive'] * 100, hue='Indie', marker='o',
                 ax=ax, hue_order=['Not indie', 'Indie'],
                 palette=['#4C72B0', '#DD8452'])
    ax.set_title('Median positive-review share by release year')
    ax.set_xlabel('Release year')
    ax.set_ylabel('Median positive reviews (%)')
    ax.legend(title='')
    save_figure(fig, 'fig7_games_indie_trend.png')

    # RQ4: class balance
    balance = analysis['very_positive'].value_counts(normalize=True)
    lines += ['## RQ4 preview: class balance of very_positive',
              balance.round(3).to_string(), '']
    return lines


def main():
    """
    Run the full exploratory data analysis pipeline.
    
    Loads cleaned datasets, performs EDA on each one, generates plots and
    summary statistics, then saves results to file.
    """
    spy = pd.read_csv(os.path.join(clean.CLEAN_DIR, 'steamspy.csv'))
    store = pd.read_csv(os.path.join(clean.CLEAN_DIR, 'store.csv'))
    games = pd.read_csv(os.path.join(clean.CLEAN_DIR, 'games.csv'))
    
    for df in (store, games):
        for column in ['is_indie', 'is_early_access']:
            df[column] = df[column].map({True: True, False: False,
                                         'True': True, 'False': False})

    lines = ['# Steam EDA summary', '']
    lines += eda_steamspy(spy)
    lines += eda_store(store)
    lines += eda_games(games)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, 'eda_summary.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {path} and {len(os.listdir(FIG_DIR))} figures in '
          f'{FIG_DIR}/')


if __name__ == '__main__':
    main()
