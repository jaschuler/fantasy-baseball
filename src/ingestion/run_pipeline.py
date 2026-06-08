import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.ingestion.init_db import get_connection
from src.ingestion.load_period_stats import (
    load_hitter_score_period,
    load_hitter_standard_period,
    load_pitcher_score_period,
    load_pitcher_standard_period,
    get_period_id,
)


def run_full_pipeline(season):
    """Load all stat tables for a given season in a single connection."""
    con = get_connection()

    # Get max period for this season
    max_period = con.execute("""
        SELECT MAX(period_num) FROM periods WHERE season = ?
    """, [season]).fetchone()[0]

    print(f"\n=== Loading {season} data ({max_period} periods) ===")

    # Clear all four tables for this season
    for table in [
        'hitter_period_stats_scoring',
        'hitter_period_stats_standard',
        'pitcher_period_stats_scoring',
        'pitcher_period_stats_standard',
    ]:
        con.execute(f"""
            DELETE FROM {table}
            WHERE period_id IN (
                SELECT period_id FROM periods WHERE season = ?
            )
        """, [season])
    print("Cleared existing data.")

    # Load all four tables period by period
    totals = {
        'hitter_score':    0,
        'hitter_standard': 0,
        'pitcher_score':   0,
        'pitcher_standard':0,
    }

    for period_num in range(1, max_period + 1):
        hs = load_hitter_score_period(con, season, period_num)
        hst = load_hitter_standard_period(con, season, period_num)
        ps = load_pitcher_score_period(con, season, period_num)
        pst = load_pitcher_standard_period(con, season, period_num)

        totals['hitter_score']    += hs
        totals['hitter_standard'] += hst
        totals['pitcher_score']   += ps
        totals['pitcher_standard']+= pst

        print(f"  Period {period_num:>2}: "
              f"hit_score={hs:>5} "
              f"hit_std={hst:>5} "
              f"pit_score={ps:>5} "
              f"pit_std={pst:>5}")

    con.commit()
    con.close()

    print(f"\nTotals for {season}:")
    for key, val in totals.items():
        print(f"  {key:<20}: {val:,}")


if __name__ == "__main__":
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    run_full_pipeline(season)