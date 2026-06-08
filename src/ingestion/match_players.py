import sys
import re
import pandas as pd
import numpy as np
from pathlib import Path
from rapidfuzz import process, fuzz

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.ingestion.init_db import get_connection
from src.ingestion.load_period_stats import parse_player_info

# ── Constants ─────────────────────────────────────────────────────────────────
MATCH_THRESHOLD  = 88.0   # minimum confidence for auto-match
CHADWICK_PATH    = Path(__file__).parent.parent.parent / "data" / "raw" / "chadwick_people.csv"

# Ohtani special case — same MLBAM ID, two CBS entries
MANUAL_OVERRIDES = {
    # Ohtani two-way
    ("Shohei Ohtani (Batter)",  "hitter"):  660271,
    ("Shohei Ohtani (Pitcher)", "pitcher"): 660271,
    ("Shohei Ohtani",           "pitcher"): 660271,

    # Name format mismatches
    ("Matthew Boyd",            "pitcher"): 571510,
    ("Zachary Neto",            "hitter"):  687263,
    ("J.T. Realmuto",           "hitter"):  592663,
    ("Jesus Made",              "hitter"):  815908,
    ("Michael King",            "pitcher"): 650633,
    ("Cameron Schlittler",      "pitcher"): 693645,

    # Prospects below fuzzy threshold
    ("Ethan Holliday",          "hitter"):  815787,
    ("Leo De Vries",            "hitter"):  815888,
    ("Xavier Isaac",            "hitter"):  800060,
    ("Sebastian Walcott",       "hitter"):  806964,
    ("Walker Jenkins",          "hitter"):  805805,
    ("Druw Jones",              "hitter"):  702258,
    ("Ethan Conrad",            "hitter"):  828255,
    ("Max Clark",               "hitter"):  703601,
    ("Luis Pena",               "hitter"):  821270,
}

def load_chadwick():
    """Load and filter Chadwick register to active MLB players."""
    df = pd.read_csv(CHADWICK_PATH, low_memory=False)

    # Filter to players with MLBAM IDs who played recently
    df = df[df['key_mlbam'].notna()].copy()
    df = df[(df['mlb_played_last'] >= 2020) | (df['mlb_played_last'].isna())].copy()

    # Build full name for matching — lowercase for comparison
    df['name_full'] = (
        df['name_first'].fillna('') + ' ' +
        df['name_last'].fillna('')
    ).str.strip().str.lower()

    df['key_mlbam']      = df['key_mlbam'].astype(int)
    df['key_fangraphs']  = pd.to_numeric(df['key_fangraphs'], errors='coerce')

    df = df[[
        'key_mlbam', 'key_fangraphs', 'key_bbref',
        'name_first', 'name_last', 'name_full',
        'mlb_played_first', 'mlb_played_last'
    ]].copy()

    print(f"Chadwick filtered to {len(df)} players (MLB since 2020)")
    return df


def extract_unique_cbs_names(season=2025):
    """
    Extract unique player name strings directly from stat tables.
    """
    con = get_connection()

    hitters = con.execute("""
        SELECT DISTINCT cbs_name_raw, 'hitter' AS player_type
        FROM hitter_period_stats_scoring
        WHERE cbs_name_raw IS NOT NULL
    """).df()

    pitchers = con.execute("""
        SELECT DISTINCT cbs_name_raw, 'pitcher' AS player_type
        FROM pitcher_period_stats_scoring
        WHERE cbs_name_raw IS NOT NULL
    """).df()

    con.close()

    df = pd.concat([hitters, pitchers]).drop_duplicates(
        subset=['cbs_name_raw', 'player_type']
    )
    print(f"Unique CBS player strings from stat tables: {len(df)}")
    return df


def normalize_name(name):
    """Normalize a name for comparison."""
    name = name.lower().strip()
    name = re.sub(r'\s+jr\.?$', '', name)
    name = re.sub(r'\s+sr\.?$', '', name)
    name = re.sub(r'\s+ii$',    '', name)
    name = re.sub(r'\s+iii$',   '', name)
    # Remove accents
    replacements = {
        'á':'a','é':'e','í':'i','ó':'o','ú':'u',
        'ñ':'n','ü':'u','à':'a','è':'e','ì':'i',
        'ò':'o','ù':'u','â':'a','ê':'e','î':'i',
        'ô':'o','û':'u','ä':'a','ë':'e','ï':'i',
        'ö':'o',
    }
    for accented, plain in replacements.items():
        name = name.replace(accented, plain)
    return name.strip()


def match_players(season=2025):
    """
    Match CBS player strings to MLBAM IDs via Chadwick register.
    Writes results to player_name_crosswalk table.
    """
    chadwick  = load_chadwick()
    cbs_names = extract_unique_cbs_names(season)

    # Build normalized name list for fuzzy matching
    chad_names     = chadwick['name_full'].tolist()
    chad_names_norm = [normalize_name(n) for n in chad_names]

    con = get_connection()
    con.execute("DELETE FROM player_name_crosswalk WHERE season = ?", [season])

    auto_matched  = 0
    manual_matched = 0
    low_confidence = []

    for _, row in cbs_names.iterrows():
        cbs_raw   = row['cbs_name_raw']
        p_type    = row['player_type']

        name, position, mlb_team = parse_player_info(cbs_raw)
        name_norm = normalize_name(name)

        # Check manual overrides first
        override_key = (name, p_type)
        if override_key in MANUAL_OVERRIDES:
            mlbam_id   = MANUAL_OVERRIDES[override_key]
            confidence = 100.0
            method     = 'manual'
            manual_matched += 1

            # Ensure player exists in players table
            chad_row = chadwick[chadwick['key_mlbam'] == mlbam_id]
            if len(chad_row) > 0:
                cr = chad_row.iloc[0]
                con.execute("""
                    INSERT OR IGNORE INTO players
                        (player_id, name_first, name_last, name_full,
                        key_fangraphs, key_bbref, cbs_name_raw)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    mlbam_id,
                    cr['name_first'],
                    cr['name_last'],
                    f"{cr['name_first']} {cr['name_last']}",
                    int(cr['key_fangraphs']) if not pd.isna(cr['key_fangraphs']) else None,
                    cr['key_bbref'] if cr['key_bbref'] else None,
                    cbs_raw
                ])

        else:
            # Fuzzy match against normalized Chadwick names
            result = process.extractOne(
                name_norm,
                chad_names_norm,
                scorer=fuzz.token_sort_ratio
            )

            if result is None:
                low_confidence.append({
                    'cbs_name_raw': cbs_raw,
                    'parsed_name':  name,
                    'player_type':  p_type,
                    'confidence':   0.0,
                    'best_match':   None
                })
                continue

            best_match, confidence, idx = result

            if confidence >= MATCH_THRESHOLD:
                mlbam_id  = int(chadwick.iloc[idx]['key_mlbam'])
                method    = 'auto'
                auto_matched += 1
            else:
                low_confidence.append({
                    'cbs_name_raw': cbs_raw,
                    'parsed_name':  name,
                    'player_type':  p_type,
                    'confidence':   confidence,
                    'best_match':   chadwick.iloc[idx]['name_full']
                })
                continue

        # Insert into players table if not exists
        chad_row = chadwick[chadwick['key_mlbam'] == mlbam_id]
        if len(chad_row) > 0:
            cr = chad_row.iloc[0]
            con.execute("""
                INSERT OR IGNORE INTO players
                    (player_id, name_first, name_last, name_full,
                     key_fangraphs, key_bbref, cbs_name_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                mlbam_id,
                cr['name_first'],
                cr['name_last'],
                f"{cr['name_first']} {cr['name_last']}",
                int(cr['key_fangraphs']) if not pd.isna(cr['key_fangraphs']) else None,
                cr['key_bbref'] if cr['key_bbref'] else None,
                cbs_raw
            ])

        # Insert into crosswalk
        con.execute("""
            INSERT INTO player_name_crosswalk
                (cbs_name_raw, player_id, player_type,
                 match_confidence, match_method, season)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [cbs_raw, mlbam_id, p_type, confidence, method, season])

    con.close()

    print(f"\n=== MATCHING RESULTS ===")
    print(f"Auto matched:    {auto_matched}")
    print(f"Manual matched:  {manual_matched}")
    print(f"Low confidence:  {len(low_confidence)}")
    print(f"Total processed: {auto_matched + manual_matched + len(low_confidence)}")

    if low_confidence:
        lc_df = pd.DataFrame(low_confidence).sort_values('confidence', ascending=False)
        print(f"\nTop low confidence matches:")
        print(lc_df.head(20).to_string())
        lc_df.to_csv('data/processed/low_confidence_matches.csv', index=False)
        print(f"\nFull list saved to data/processed/low_confidence_matches.csv")

    return low_confidence

def update_player_ids(season=2025):
    """
    Update player_id in all four stat tables by joining
    through player_name_crosswalk on cbs_name_raw.
    """
    con = get_connection()

    updates = [
        ('hitter_period_stats_scoring',   'hitter'),
        ('hitter_period_stats_standard',  'hitter'),
        ('pitcher_period_stats_scoring',  'pitcher'),
        ('pitcher_period_stats_standard', 'pitcher'),
    ]

    for table, player_type in updates:
        con.execute(f"""
            UPDATE {table}
            SET player_id = (
                SELECT c.player_id
                FROM player_name_crosswalk c
                WHERE c.cbs_name_raw = {table}.cbs_name_raw
                AND   c.player_type  = '{player_type}'
                AND   c.season       = 2025
                LIMIT 1
            )
            WHERE player_id IS NULL
        """)

        total   = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        
        matched = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE player_id IS NOT NULL"
        ).fetchone()[0]

        print(f"{table}:")
        print(f"  Matched: {matched:>7} / {total} ({matched/total*100:.1f}%)")

    con.close()

if __name__ == "__main__":
    match_players(season=2025)
    print("\nUpdating player_id in stat tables...")
    update_player_ids(season=2025)