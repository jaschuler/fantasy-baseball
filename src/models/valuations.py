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

def get_full_season_estimates(con, season, period_num=None):
    """
    Combine YTD actuals with Steamer ROS projections.
    Full season estimate = YTD + Steamer ROS.
    Rate stats weighted by PA/INNs.
    Returns hitter and pitcher DataFrames.
    """
    # Get YTD actuals
    hitters_ytd  = get_hitter_stats(con, season, period_num)
    pitchers_ytd = get_pitcher_stats(con, season, period_num)

    # Get Steamer ROS
    steamer_h = con.execute("""
        SELECT * FROM steamer_ros_hitters
    """).df()

    steamer_p = con.execute("""
        SELECT * FROM steamer_ros_pitchers
    """).df()

    # ── Hitters ───────────────────────────────────────────────────────────
    h = hitters_ytd.merge(
        steamer_h[['player_id','PA','HR','SB','AVG','OPS','RP','KO']],
        on='player_id',
        how='left',
        suffixes=('_ytd', '_ros')
    )

    # Counting stats — add directly
    h['HR_proj'] = h['HR_ytd'].fillna(0) + h['HR_ros'].fillna(0)
    h['SB_proj'] = h['SB_ytd'].fillna(0) + h['SB_ros'].fillna(0)
    h['RP_proj'] = h['RP_ytd'].fillna(0) + h['RP_ros'].fillna(0)
    h['KO_proj'] = h['KO_ytd'].fillna(0) + h['KO_ros'].fillna(0)

    # Rate stats — weighted average by PA
    pa_ytd = h['PA_ytd'].fillna(0)
    pa_ros = h['PA_ros'].fillna(0)
    pa_tot = pa_ytd + pa_ros

    h['AVG_proj'] = (
        (h['AVG_ytd'].fillna(0) * pa_ytd +
         h['AVG_ros'].fillna(0) * pa_ros) /
        pa_tot.replace(0, float('nan'))
    )
    h['OPS_proj'] = (
        (h['OPS_ytd'].fillna(0) * pa_ytd +
         h['OPS_ros'].fillna(0) * pa_ros) /
        pa_tot.replace(0, float('nan'))
    )

    # Rename YTD columns cleanly
    h = h.rename(columns={
        'HR_ytd': 'HR', 'SB_ytd': 'SB', 'RP_ytd': 'RP',
        'KO_ytd': 'KO', 'AVG_ytd': 'AVG', 'OPS_ytd': 'OPS',
    })

    # ── Pitchers ──────────────────────────────────────────────────────────
    p = pitchers_ytd.merge(
        steamer_p[['player_id','INNs','ERA','WHIP','K','QS','SV','HRA']],
        on='player_id',
        how='left',
        suffixes=('_ytd', '_ros')
    )

    # Counting stats
    p['K_proj']   = p['K_ytd'].fillna(0)   + p['K_ros'].fillna(0)
    p['QS_proj']  = p['QS_ytd'].fillna(0)  + p['QS_ros'].fillna(0)
    p['SV_proj']  = p['SV_ytd'].fillna(0)  + p['SV_ros'].fillna(0)
    p['HRA_proj'] = p['HRA_ytd'].fillna(0) + p['HRA_ros'].fillna(0)

    # Rate stats weighted by INNs
    inns_ytd = p['INNs_ytd'].fillna(0)
    inns_ros = p['INNs_ros'].fillna(0)
    inns_tot = inns_ytd + inns_ros

    p['ERA_proj'] = (
        (p['ERA_ytd'].fillna(0) * inns_ytd +
         p['ERA_ros'].fillna(0) * inns_ros) /
        inns_tot.replace(0, float('nan'))
    )
    p['WHIP_proj'] = (
        (p['WHIP_ytd'].fillna(0) * inns_ytd +
         p['WHIP_ros'].fillna(0) * inns_ros) /
        inns_tot.replace(0, float('nan'))
    )

    p = p.rename(columns={
        'K_ytd': 'K', 'QS_ytd': 'QS', 'SV_ytd': 'SV',
        'HRA_ytd': 'HRA', 'ERA_ytd': 'ERA', 'WHIP_ytd': 'WHIP',
        'INNs_ytd': 'INNs',
    })

    return h, p

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
    Produces three dollar value outputs:
    - YTD: what the player has earned so far
    - Pace: full season if current pace continues
    - Projected: YTD actuals + Steamer ROS
    """
    con = get_connection()

    period_label = f"Period {period_num}" if period_num else "YTD"
    print(f"\nRunning valuations — {season} {period_label}")

    # ── Get season metadata for pace calculation ───────────────────────────
    total_season_days = con.execute("""
        SELECT SUM(num_days) FROM periods
        WHERE season = ? AND period_type = 'regular'
    """, [season]).fetchone()[0]

    if period_num:
        days_played = con.execute("""
            SELECT SUM(num_days) FROM periods
            WHERE season = ? AND period_num <= ? AND period_type = 'regular'
        """, [season, period_num]).fetchone()[0]
    else:
        max_period = con.execute("""
            SELECT MAX(period_num) FROM periods
            WHERE season = ? AND period_type = 'regular'
        """, [season]).fetchone()[0]
        days_played = con.execute("""
            SELECT SUM(num_days) FROM periods
            WHERE season = ? AND period_num <= ? AND period_type = 'regular'
        """, [season, max_period]).fetchone()[0]

    pace_factor = total_season_days / days_played if days_played else 1.0
    print(f"  Days played: {days_played} / {total_season_days} — pace factor: {pace_factor:.3f}")

    # ── YTD stats ─────────────────────────────────────────────────────────
    print("  Aggregating YTD stats...")
    hitters_ytd  = get_hitter_stats(con, season, period_num)
    pitchers_ytd = get_pitcher_stats(con, season, period_num)
    print(f"  Hitter pool: {len(hitters_ytd)} | Pitcher pool: {len(pitchers_ytd)}")

    # ── Pace projections ──────────────────────────────────────────────────
    hitters_pace  = hitters_ytd.copy()
    pitchers_pace = pitchers_ytd.copy()

    for cat in ['HR', 'SB', 'RP', 'KO']:
        hitters_pace[cat] = hitters_pace[cat] * pace_factor
    for cat in ['K', 'QS', 'SV', 'HRA']:
        pitchers_pace[cat] = pitchers_pace[cat] * pace_factor

    # ── Steamer projected ─────────────────────────────────────────────────
    print("  Blending with Steamer ROS...")
    hitters_proj, pitchers_proj = get_full_season_estimates(con, season, period_num)

    # Use projected columns for z-score calculation
    for cat in ['HR', 'SB', 'RP', 'KO']:
        hitters_proj[cat] = hitters_proj[f'{cat}_proj']
    for cat in ['K', 'QS', 'SV', 'HRA']:
        pitchers_proj[cat] = pitchers_proj[f'{cat}_proj']
    hitters_proj['AVG'] = hitters_proj['AVG_proj']
    hitters_proj['OPS'] = hitters_proj['OPS_proj']
    pitchers_proj['ERA']  = pitchers_proj['ERA_proj']
    pitchers_proj['WHIP'] = pitchers_proj['WHIP_proj']

    # ── Z-scores and dollar values ────────────────────────────────────────
    hitters_ytd,  h_z = calculate_z_scores(hitters_ytd,  HIT_SCORING_CATS, INVERSE_CATS)
    hitters_pace, _   = calculate_z_scores(hitters_pace, HIT_SCORING_CATS, INVERSE_CATS)
    hitters_proj, _   = calculate_z_scores(hitters_proj, HIT_SCORING_CATS, INVERSE_CATS)

    pitchers_ytd,  p_z = calculate_z_scores(pitchers_ytd,  PITCH_SCORING_CATS, INVERSE_CATS)
    pitchers_pace, _   = calculate_z_scores(pitchers_pace, PITCH_SCORING_CATS, INVERSE_CATS)
    pitchers_proj, _   = calculate_z_scores(pitchers_proj, PITCH_SCORING_CATS, INVERSE_CATS)

    hitters_ytd   = calculate_dollar_values(hitters_ytd,   'hitter')
    hitters_pace  = calculate_dollar_values(hitters_pace,  'hitter')
    hitters_proj  = calculate_dollar_values(hitters_proj,  'hitter')

    pitchers_ytd  = calculate_dollar_values(pitchers_ytd,  'pitcher')
    pitchers_pace = calculate_dollar_values(pitchers_pace, 'pitcher')
    pitchers_proj = calculate_dollar_values(pitchers_proj, 'pitcher')

    con.close()

    # ── Summary output ────────────────────────────────────────────────────
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.float_format', '{:.2f}'.format)

    print(f"\n  === TOP 10 HITTERS — YTD ===")
    print(hitters_ytd.sort_values('dollar_value', ascending=False)[
        ['name_full', 'primary_pos', 'PA', 'HR', 'SB', 'AVG',
         'OPS', 'RP', 'KO', 'z_total', 'dollar_value']
    ].head(10).to_string(index=False))

    print(f"\n  === TOP 10 HITTERS — PACE ===")
    print(hitters_pace.sort_values('dollar_value', ascending=False)[
        ['name_full', 'primary_pos', 'HR', 'SB', 'AVG',
         'OPS', 'RP', 'KO', 'z_total', 'dollar_value']
    ].head(10).to_string(index=False))

    print(f"\n  === TOP 10 HITTERS — PROJECTED (YTD + STEAMER) ===")
    print(hitters_proj.sort_values('dollar_value', ascending=False)[
        ['name_full', 'primary_pos', 'HR', 'SB', 'AVG_proj',
         'OPS_proj', 'RP_proj', 'KO_proj', 'z_total', 'dollar_value']
    ].head(10).to_string(index=False))

    print(f"\n  === TOP 10 PITCHERS — YTD ===")
    print(pitchers_ytd.sort_values('dollar_value', ascending=False)[
        ['name_full', 'pitcher_role', 'INNs', 'ERA', 'WHIP',
         'K', 'QS', 'SV', 'HRA', 'z_total', 'dollar_value']
    ].head(10).to_string(index=False))

    print(f"\n  === TOP 10 PITCHERS — PACE ===")
    print(pitchers_pace.sort_values('dollar_value', ascending=False)[
        ['name_full', 'pitcher_role', 'ERA', 'WHIP',
         'K', 'QS', 'SV', 'HRA', 'z_total', 'dollar_value']
    ].head(10).to_string(index=False))

    print(f"\n  === TOP 10 PITCHERS — PROJECTED (YTD + STEAMER) ===")
    print(pitchers_proj.sort_values('dollar_value', ascending=False)[
        ['name_full', 'pitcher_role', 'ERA_proj', 'WHIP_proj',
         'K_proj', 'QS_proj', 'SV_proj', 'HRA_proj', 'z_total', 'dollar_value']
    ].head(10).to_string(index=False))

    return hitters_ytd, hitters_pace, hitters_proj, pitchers_ytd, pitchers_pace, pitchers_proj


if __name__ == "__main__":
    import sys
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    run_valuations(season=season)