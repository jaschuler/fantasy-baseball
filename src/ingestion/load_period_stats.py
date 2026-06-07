import sys
import pandas as pd
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import RAW_DIR, CURRENT_SEASON
from src.ingestion.init_db import get_connection

def parse_player_info(player_str):
    """Extract name, position, and MLB team from CBS player string."""
    import re
    player_str = str(player_str).strip()
    
    # Extract MLB team — appears after |
    mlb_team = None
    team_match = re.search(r'\|\s*([A-Z]{2,3})\s*', player_str)
    if team_match:
        mlb_team = team_match.group(1).strip()
    
    # Extract position — appears before |
    pos_match = re.match(
        r'^(.+?)\s+((?:C|1B|2B|3B|SS|OF|DH|SP|RP|P)'
        r'(?:,(?:C|1B|2B|3B|SS|OF|DH|SP|RP|P))*)\s*\|',
        player_str
    )
    if pos_match:
        name = pos_match.group(1).strip()
        position = pos_match.group(2).strip()
    else:
        name = player_str.split('|')[0].strip()
        position = None
    
    # Clean name — remove trailing position artifacts
    name = re.sub(
        r'\s+(C|1B|2B|3B|SS|OF|DH|SP|RP|P)'
        r'(\s*,\s*(C|1B|2B|3B|SS|OF|DH|SP|RP|P))*\s*$',
        '', name
    ).strip().strip('"')
    
    return name, position, mlb_team


def get_period_id(con, season, period_num):
    """Look up period_id from periods table."""
    result = con.execute("""
        SELECT period_id FROM periods
        WHERE season = ? AND period_num = ?
    """, [season, period_num]).fetchone()
    return result[0] if result else None


def get_team_id(con, season, last_name_key):
    """Look up team_id from teams table."""
    result = con.execute("""
        SELECT team_id FROM teams
        WHERE season = ? AND last_name_key = ?
    """, [season, last_name_key]).fetchone()
    return result[0] if result else None


def load_hitter_score_period(con, season, period_num):
    """Load one period of hitter scoring stats into hitter_period_stats_scoring."""
    
    file_path = RAW_DIR / str(season) / f"p{period_num}_hit_score.csv"
    
    if not file_path.exists():
        print(f"  WARNING: {file_path.name} not found, skipping.")
        return 0
    
    period_id = get_period_id(con, season, period_num)
    if not period_id:
        print(f"  WARNING: period {period_num} not found in db, skipping.")
        return 0
    
    df = pd.read_csv(file_path, skiprows=1)
    df.columns = ['avail', 'player', 'AVG', 'HR', 'KO', 'OPS', 'RP', 'SB', 'rank', 'extra']
    
    # Drop header artifacts and empty rows
    df = df[df['avail'].notna()].copy()
    df = df[df['player'].notna()].copy()
    df = df[df['AVG'] != 'AVG'].copy()
    
    # Convert numeric columns
    for col in ['AVG', 'HR', 'KO', 'OPS', 'RP', 'SB']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    rows_loaded = 0
    
    for _, row in df.iterrows():
        name, position, mlb_team = parse_player_info(row['player'])
        
        # Get team_id — FA players get None
        avail = str(row['avail']).strip()
        if avail.startswith('FA') or avail == 'nan':
            team_id = None
        else:
            team_id = get_team_id(con, season, avail)
        
        con.execute("""
            INSERT INTO hitter_period_stats_scoring
                (player_id, period_id, team_id, AVG, HR, KO, OPS, RP, SB, PA)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            None,          # player_id — will resolve in MLBAM matching step
            period_id,
            team_id,
            row['AVG'],
            row['HR'],
            row['KO'],
            row['OPS'],
            row['RP'],
            row['SB'],
            None           # PA — not in score file, will come from standard file
        ])
        rows_loaded += 1
    
    return rows_loaded

def load_all_hitter_scores(season=2025):
    """Load hitter scoring stats for all periods in a season."""
    con = get_connection()
    
    # Clear existing data for this season to avoid duplicates
    con.execute("""
        DELETE FROM hitter_period_stats_scoring
        WHERE period_id IN (
            SELECT period_id FROM periods WHERE season = ?
        )
    """, [season])
    
    total = 0
    for period_num in range(1, 23):
        rows = load_hitter_score_period(con, season, period_num)
        print(f"  Period {period_num:>2}: {rows:>5} rows loaded")
        total += rows
    
    con.close()
    print(f"\nTotal hitter score rows loaded: {total}")


if __name__ == "__main__":
    print("Loading hitter scoring stats for 2025...")
    load_all_hitter_scores(season=2025)
