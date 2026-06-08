import sys
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import date

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import FANGRAPHS_COOKIE, FANGRAPHS_COOKIE_NAME
from src.ingestion.init_db import get_connection

# ── Fangraphs column mappings to our scoring categories ──────────────────
HITTER_COLS = {
    'mlbamid': 'player_id',
    'firstname': 'name_first',
    'lastname':  'name_last',
    'PA':  'PA',
    'HR':  'HR',
    'SB':  'SB',
    'AVG': 'AVG',
    'OBP': 'OBP',
    'SLG': 'SLG',
    'R':   'R',
    'RBI': 'RBI',
    'K':   'KO',
    'G':   'G',
}

PITCHER_COLS = {
    'mlbamid':  'player_id',
    'firstname': 'name_first',
    'lastname':  'name_last',
    'IP':   'INNs',
    'ERA':  'ERA',
    'WHIP': 'WHIP',
    'K':    'K',
    'QS':   'QS',
    'SV':   'SV',
    'HR':   'HRA',
    'W':    'W',
    'GS':   'GS',
    'G':    'G',
}


def get_session():
    """Create authenticated Fangraphs session."""
    session = requests.Session()
    session.cookies.set(
        FANGRAPHS_COOKIE_NAME,
        FANGRAPHS_COOKIE,
        domain='www.fangraphs.com'
    )
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.fangraphs.com/projections',
    })
    return session


def fetch_steamer_hitters(season=2026):
    """Load Steamer ROS hitter projections from manually downloaded CSV."""
    path = (
        Path(__file__).parent.parent.parent
        / "data" / "raw" / str(season)
        / "steamer_ros_hitters.csv"
    )
    df = pd.read_csv(path)

    # Rename to our column names
    df = df.rename(columns={
        'MLBAMID': 'player_id',
        'Name':    'name_full',
        'PA':      'PA',
        'HR':      'HR',
        'SB':      'SB',
        'AVG':     'AVG',
        'OBP':     'OBP',
        'SLG':     'SLG',
        'R':       'R',
        'RBI':     'RBI',
        'SO':      'KO',
    })

    df['OPS'] = df['OBP'] + df['SLG']
    df['RP']  = df['R'] + df['RBI'] - df['HR']

    keep = ['player_id', 'name_full', 'PA', 'HR', 'SB',
            'AVG', 'OPS', 'RP', 'KO']
    df = df[keep].copy()
    df['player_id']   = pd.to_numeric(df['player_id'], errors='coerce')
    df = df[df['player_id'].notna()].copy()
    df['player_id']   = df['player_id'].astype(int)
    df['fetched_date'] = date.today().isoformat()

    print(f"Steamer ROS hitters loaded: {len(df)}")
    return df


def fetch_steamer_pitchers(season=2026):
    """Load Steamer ROS pitcher projections from manually downloaded CSV."""
    path = (
        Path(__file__).parent.parent.parent
        / "data" / "raw" / str(season)
        / "steamer_ros_pitchers.csv"
    )
    df = pd.read_csv(path)

    df = df.rename(columns={
        'MLBAMID': 'player_id',
        'Name':    'name_full',
        'IP':      'INNs',
        'ERA':     'ERA',
        'WHIP':    'WHIP',
        'SO':      'K',
        'QS':      'QS',
        'SV':      'SV',
        'HR':      'HRA',
        'W':       'W',
        'GS':      'GS',
        'G':       'G',
    })

    keep = ['player_id', 'name_full', 'INNs', 'ERA', 'WHIP',
            'K', 'QS', 'SV', 'HRA', 'W', 'GS', 'G']
    df = df[keep].copy()
    df['player_id']   = pd.to_numeric(df['player_id'], errors='coerce')
    df = df[df['player_id'].notna()].copy()
    df['player_id']   = df['player_id'].astype(int)
    df['fetched_date'] = date.today().isoformat()

    print(f"Steamer ROS pitchers loaded: {len(df)}")
    return df


def save_steamer_to_db(hitters, pitchers):
    """Save Steamer ROS projections to DuckDB."""
    con = get_connection()

    con.execute("DROP TABLE IF EXISTS steamer_ros_hitters")
    con.execute("DROP TABLE IF EXISTS steamer_ros_pitchers")

    con.execute("""
        CREATE TABLE steamer_ros_hitters (
            player_id    INTEGER,
            name_full    VARCHAR,
            PA           FLOAT,
            HR           FLOAT,
            SB           FLOAT,
            AVG          FLOAT,
            OPS          FLOAT,
            RP           FLOAT,
            KO           FLOAT,
            fetched_date VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE steamer_ros_pitchers (
            player_id    INTEGER,
            name_full    VARCHAR,
            INNs         FLOAT,
            ERA          FLOAT,
            WHIP         FLOAT,
            K            FLOAT,
            QS           FLOAT,
            SV           FLOAT,
            HRA          FLOAT,
            W            FLOAT,
            GS           FLOAT,
            G            FLOAT,
            fetched_date VARCHAR
        )
    """)

    con.execute("INSERT INTO steamer_ros_hitters SELECT * FROM hitters")
    con.execute("INSERT INTO steamer_ros_pitchers SELECT * FROM pitchers")

    con.commit()
    con.close()
    print("Steamer projections saved to database.")


if __name__ == "__main__":
    import sys
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    hitters  = fetch_steamer_hitters(season=season)
    pitchers = fetch_steamer_pitchers(season=season)
    print(hitters.head())
    print(pitchers.head())
    save_steamer_to_db(hitters, pitchers)