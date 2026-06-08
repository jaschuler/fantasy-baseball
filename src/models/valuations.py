import sys
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.ingestion.init_db import get_connection
from config.settings import (
    HIT_CATS, PITCH_CATS, INVERSE_CATS,
    LEAGUE_SIZE, REGULAR_SEASON_PERIODS
)

# ── League roster construction ─────────────────────────────────────────────
ROSTER_SPOTS = {
    'C':  1,
    '1B': 1,
    '2B': 1,
    '3B': 1,
    'SS': 1,
    'OF': 3,
    'SP': 5,
    'RP': 3,
    'P':  1,   # flex — split 5:3 between SP/RP
}

# Replacement level = LEAGUE_SIZE * spots
# P flex split proportionally: 5/8 SP, 3/8 RP
REPLACEMENT_LEVEL = {
    'C':  LEAGUE_SIZE * 1,
    '1B': LEAGUE_SIZE * 1,
    '2B': LEAGUE_SIZE * 1,
    '3B': LEAGUE_SIZE * 1,
    'SS': LEAGUE_SIZE * 1,
    'OF': LEAGUE_SIZE * 3,
    'SP': round(LEAGUE_SIZE * (5 + 5/8)),
    'RP': round(LEAGUE_SIZE * (3 + 3/8)),
}

# ── Playing time thresholds ────────────────────────────────────────────────
MIN_PA   = 30   # minimum PA to include unrostered hitters
MIN_INNs = 5.0  # minimum IP to include unrostered pitchers

# ── Scoring categories ─────────────────────────────────────────────────────
HIT_SCORING_CATS  = ['AVG', 'HR', 'KO', 'OPS', 'RP', 'SB']
PITCH_SCORING_CATS = ['ERA', 'HRA', 'K', 'QS', 'SV', 'WHIP']
INVERSE_CATS      = ['KO', 'ERA', 'HRA', 'WHIP']
RATE_CATS         = ['AVG', 'OPS', 'ERA', 'WHIP']  # need PA/INNs weighting


def get_eligible_pool(con, season, period_num=None):
    """
    Get the eligible player pool for z-score calculation.
    Includes rostered players + waiver adds + playing time threshold.
    
    If period_num is None, uses YTD cumulative stats.
    """
    if period_num:
        period_filter = "AND p.period_num = :period"
        params = {'season': season, 'period': period_num}
    else:
        period_filter = "AND p.period_num <= :max_period"
        max_period = con.execute("""
            SELECT MAX(period_num) FROM periods 
            WHERE season = ? AND period_type = 'regular'
        """, [season]).fetchone()[0]
        params = {'season': season, 'max_period': max_period}

    # Get rostered player IDs for this season
    rostered_ids = con.execute("""
        SELECT DISTINCT player_id
        FROM hitter_period_stats_scoring
        WHERE team_id IS NOT NULL
        AND player_id IS NOT NULL
        AND period_id IN (
            SELECT period_id FROM periods WHERE season = ?
        )
        UNION
        SELECT DISTINCT player_id
        FROM pitcher_period_stats_scoring
        WHERE team_id IS NOT NULL
        AND player_id IS NOT NULL
        AND period_id IN (
            SELECT period_id FROM periods WHERE season = ?
        )
    """, [season, season]).df()

    return rostered_ids['player_id'].tolist()

def get_hitter_stats(con, season, period_num=None):
    """
    Aggregate hitter scoring stats for the eligible pool.
    Returns one row per player with cumulative or period stats.
    """
    if period_num:
        period_filter = "AND p.period_num = :period"
    else:
        max_period = con.execute("""
            SELECT MAX(period_num) FROM periods
            WHERE season = ? AND period_type = 'regular'
        """, [season]).fetchone()[0]
        period_filter = f"AND p.period_num <= {max_period}"

    # Get rostered player IDs
    rostered_ids = get_eligible_pool(con, season, period_num)

    query = f"""
        SELECT
            h.player_id,
            pl.name_full,
            pl.position,
            MAX(h.cbs_name_raw)               AS cbs_name_raw,
            MAX(h.team_id)                    AS team_id,
            SUM(h.PA)                         AS PA,
            SUM(h.HR)                         AS HR,
            SUM(h.KO)                         AS KO,
            SUM(h.RP)                         AS RP,
            SUM(h.SB)                         AS SB,
            SUM(h.AVG * COALESCE(h.PA, 0))    AS AVG_weighted,
            SUM(h.OPS * COALESCE(h.PA, 0))    AS OPS_weighted,
            SUM(COALESCE(h.PA, 0))            AS PA_total
        FROM hitter_period_stats_scoring h
        JOIN periods p      ON h.period_id  = p.period_id
        JOIN players pl     ON h.player_id  = pl.player_id
        WHERE p.season = {season}
        {period_filter}
        AND h.player_id IS NOT NULL
        GROUP BY h.player_id, pl.name_full, pl.position
        HAVING (
            {f"h.player_id IN ({','.join(str(x) for x in rostered_ids)})" 
             if rostered_ids else "1=0"}
            OR SUM(COALESCE(h.PA, 0)) >= {MIN_PA}
        )
    """

    df = con.execute(query).df()

    # Extract position from CBS name string directly
    from src.ingestion.load_period_stats import parse_player_info
    df['cbs_position'] = df['cbs_name_raw'].apply(
        lambda x: parse_player_info(x)[1] if x else None
    )

    # Calculate rate stats from weighted sums
    df['AVG'] = df['AVG_weighted'] / df['PA_total'].replace(0, np.nan)
    df['OPS'] = df['OPS_weighted'] / df['PA_total'].replace(0, np.nan)

    # Drop intermediate columns
    df = df.drop(columns=['AVG_weighted', 'OPS_weighted', 'PA_total'])

    return df

def get_pitcher_stats(con, season, period_num=None):
    """
    Aggregate pitcher scoring stats for the eligible pool.
    Returns one row per player with cumulative or period stats.
    """
    if period_num:
        period_filter = "AND p.period_num = :period"
    else:
        max_period = con.execute("""
            SELECT MAX(period_num) FROM periods
            WHERE season = ? AND period_type = 'regular'
        """, [season]).fetchone()[0]
        period_filter = f"AND p.period_num <= {max_period}"

    # Get rostered player IDs
    rostered_ids = get_eligible_pool(con, season, period_num)

    query = f"""
        SELECT
            h.player_id,
            pl.name_full,
            pl.position,
            MAX(h.cbs_name_raw)                AS cbs_name_raw,
            SUM(h.INNs)                        AS INNs,
            SUM(h.K)                           AS K,
            SUM(h.QS)                          AS QS,
            SUM(h.SV)                          AS SV,
            SUM(h.HRA)                         AS HRA,
            SUM(h.ERA * COALESCE(h.INNs, 0))   AS ERA_weighted,
            SUM(h.WHIP * COALESCE(h.INNs, 0))  AS WHIP_weighted,
            SUM(COALESCE(h.INNs, 0))           AS INNs_total
        FROM pitcher_period_stats_scoring h
        JOIN periods p   ON h.period_id = p.period_id
        JOIN players pl  ON h.player_id = pl.player_id
        WHERE p.season = {season}
        {period_filter}
        AND h.player_id IS NOT NULL
        GROUP BY h.player_id, pl.name_full, pl.position
        HAVING (
            {f"h.player_id IN ({','.join(str(x) for x in rostered_ids)})" 
             if rostered_ids else "1=0"}
            OR SUM(COALESCE(h.INNs, 0)) >= {MIN_INNs}
        )
    """

    df = con.execute(query).df()

    # Extract position from CBS name string directly
    from src.ingestion.load_period_stats import parse_player_info
    df['cbs_position'] = df['cbs_name_raw'].apply(
        lambda x: parse_player_info(x)[1] if x else None
    )

    # Calculate rate stats from weighted sums
    df['ERA']  = df['ERA_weighted']  / df['INNs_total'].replace(0, np.nan)
    df['WHIP'] = df['WHIP_weighted'] / df['INNs_total'].replace(0, np.nan)

    # Drop intermediate columns
    df = df.drop(columns=['ERA_weighted', 'WHIP_weighted', 'INNs_total'])

    return df

def calculate_z_scores(df, cats, inverse_cats):
    """
    Calculate z-scores for each scoring category.
    Inverse categories are sign-flipped so higher z = better always.
    Returns df with z-score columns added and a composite z_total.
    """
    z_cols = []

    for cat in cats:
        if cat not in df.columns:
            continue

        col_data = df[cat].copy()

        # Skip if no variance
        if col_data.std() == 0:
            df[f'z_{cat}'] = 0.0
            z_cols.append(f'z_{cat}')
            continue

        z = (col_data - col_data.mean()) / col_data.std()

        # Flip sign for inverse categories
        if cat in inverse_cats:
            z = z * -1

        df[f'z_{cat}'] = z
        z_cols.append(f'z_{cat}')

    # Composite z-score — sum of all category z-scores
    df['z_total'] = df[z_cols].sum(axis=1)

    return df, z_cols


def assign_primary_position(position_str):
    """
    Assign a player's primary position for replacement level calculation.
    Uses scarcest eligible position to maximize value.
    Scarcity order: C > SS > 2B > 3B > 1B > OF
    """
    if not position_str:
        return 'OF'

    positions = [p.strip() for p in str(position_str).split(',')]

    scarcity_order = ['C', 'SS', '2B', '3B', '1B', 'OF', 'DH']
    for pos in scarcity_order:
        if pos in positions:
            return pos

    return positions[0] if positions else 'OF'


def assign_pitcher_role(position_str):
    """
    Assign pitcher role — SP or RP — for replacement level.
    """
    if not position_str:
        return 'RP'
    positions = [p.strip() for p in str(position_str).split(',')]
    if 'SP' in positions:
        return 'SP'
    return 'RP'


def calculate_dollar_values(df, player_type, z_col='z_total'):
    """
    Convert z-scores to dollar values using replacement level.
    
    Method:
    1. Identify replacement level player for each position
    2. Calculate z-score above replacement (z_total - replacement_z)
    3. Scale to auction dollar values
    
    Total auction dollars available across all teams:
    $270 budget * 12 teams = $3,240
    Minus $1 per roster spot (minimum bid) * 18 spots * 12 teams = $216
    Leaves $3,024 to distribute among above-replacement players
    """
    TOTAL_BUDGET    = 270 * LEAGUE_SIZE           # $3,240
    MIN_BID         = 1
    ACTIVE_SPOTS    = 18
    DOLLARS_TO_DIST = TOTAL_BUDGET - (MIN_BID * ACTIVE_SPOTS * LEAGUE_SIZE)

    # Split dollars between hitters and pitchers (roughly 67/33)
    if player_type == 'hitter':
        available_dollars = DOLLARS_TO_DIST * 0.67
        pos_col = 'primary_pos'
        repl_levels = {k: v for k, v in REPLACEMENT_LEVEL.items()
                      if k not in ('SP', 'RP')}
    else:
        available_dollars = DOLLARS_TO_DIST * 0.33
        pos_col = 'pitcher_role'
        repl_levels = {'SP': REPLACEMENT_LEVEL['SP'],
                       'RP': REPLACEMENT_LEVEL['RP']}

    # Assign positions
    if player_type == 'hitter':
        pos_col_to_use = 'cbs_position' if 'cbs_position' in df.columns else 'position'
        df['primary_pos'] = df[pos_col_to_use].apply(assign_primary_position)
    else:
        pos_col_to_use = 'cbs_position' if 'cbs_position' in df.columns else 'position'
        df['pitcher_role'] = df[pos_col_to_use].apply(assign_pitcher_role)

    # Find replacement level z-score for each position
    df_sorted = df.sort_values(z_col, ascending=False).copy()

    replacement_z = {}
    for pos, repl_rank in repl_levels.items():
        pos_players = df_sorted[df_sorted[pos_col] == pos]
        if len(pos_players) >= repl_rank:
            replacement_z[pos] = pos_players.iloc[repl_rank - 1][z_col]
        elif len(pos_players) > 0:
            replacement_z[pos] = pos_players.iloc[-1][z_col]
        else:
            replacement_z[pos] = 0.0

    # Calculate z above replacement
    df['repl_z'] = df[pos_col].map(replacement_z)
    df['z_above_repl'] = df[z_col] - df['repl_z']

    # Only above-replacement players get positive dollar values
    above_repl = df[df['z_above_repl'] > 0].copy()

    # Scale z_above_repl to dollar values
    total_z = above_repl['z_above_repl'].sum()
    if total_z > 0:
        df['dollar_value'] = (
            df['z_above_repl'].clip(lower=0) / total_z * available_dollars
        ).round(2)
    else:
        df['dollar_value'] = 0.0

    # Below replacement = $1 minimum
    df.loc[df['dollar_value'] < 1, 'dollar_value'] = 1.0

    return df

def run_valuations(season, period_num=None):
    """
    Run full valuation pipeline for a given season and period.
    If period_num is None, runs YTD cumulative.
    Returns hitter and pitcher DataFrames with z-scores and dollar values.
    """
    con = get_connection()

    period_label = f"Period {period_num}" if period_num else "YTD"
    print(f"\nRunning valuations — {season} {period_label}")

    # ── Hitters ───────────────────────────────────────────────────────────
    print("  Aggregating hitter stats...")
    hitters = get_hitter_stats(con, season, period_num)
    print(f"  Hitter pool: {len(hitters)} players")

    hitters, h_z_cols = calculate_z_scores(
        hitters, HIT_SCORING_CATS, INVERSE_CATS
    )
    hitters = calculate_dollar_values(hitters, 'hitter')

    # ── Pitchers ──────────────────────────────────────────────────────────
    print("  Aggregating pitcher stats...")
    pitchers = get_pitcher_stats(con, season, period_num)
    print(f"  Pitcher pool: {len(pitchers)} players")

    pitchers, p_z_cols = calculate_z_scores(
        pitchers, PITCH_SCORING_CATS, INVERSE_CATS
    )
    pitchers = calculate_dollar_values(pitchers, 'pitcher')

    con.close()

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n  Top 10 Hitters ({period_label}):")
    h_display = hitters.sort_values('dollar_value', ascending=False)[
        ['name_full', 'primary_pos', 'PA', 'HR', 'SB', 'AVG', 'OPS',
         'RP', 'KO', 'z_AVG', 'z_HR', 'z_KO', 'z_OPS', 'z_RP', 'z_SB',
         'z_total', 'dollar_value']
    ].head(10)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.float_format', '{:.2f}'.format)
    print(h_display.to_string(index=False))

    print(f"\n  Top 10 Pitchers ({period_label}):")
    p_display = pitchers.sort_values('dollar_value', ascending=False)[
        ['name_full', 'pitcher_role', 'INNs', 'ERA', 'WHIP', 'HRA', 'K',
         'QS', 'SV', 'z_ERA', 'z_WHIP', 'z_HRA', 'z_K', 'z_QS', 'z_SV',
         'z_total', 'dollar_value']
    ].head(10)
    print(p_display.to_string(index=False))

    return hitters, pitchers


if __name__ == "__main__":
    import sys
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

    # Run YTD valuations
    hitters, pitchers = run_valuations(season=season)