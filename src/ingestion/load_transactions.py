import sys
import csv
import re
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.ingestion.init_db import get_connection

def get_team_id_by_name(con, season, team_name):
    """Look up team_id by full team name."""
    result = con.execute("""
        SELECT team_id FROM teams
        WHERE season = ? AND team_name = ?
    """, [season, team_name]).fetchone()
    return result[0] if result else None

def parse_transaction_file(season=2025):
    """Parse CBS transaction report and load into transactions table."""
    
    file_path = (
        Path(__file__).parent.parent.parent
        / "data" / "raw" / str(season)
        / "2025_Full_Year_Transaction_Report.csv"
    )
    
    if not file_path.exists():
        print(f"WARNING: {file_path.name} not found.")
        return 0

    # Season date boundaries
    early_start  = datetime(2025, 3, 17)  # include pre-season adds/trades
    season_start = datetime(2025, 3, 27)  # actual season start
    season_end   = datetime(2025, 9, 30)

    con = get_connection()
    con.execute("DELETE FROM transactions WHERE season = ?", [season])

    with open(file_path, 'r') as f:
        content = f.read()

    rows = list(csv.reader(content.splitlines()))
    rows_loaded = 0
    skipped = 0

    for row in rows[1:]:
        if not row or not row[0].strip():
            continue

        # Parse date
        try:
            tx_date = datetime.strptime(row[0].strip(), '%m/%d/%y %I:%M %p ET')
        except:
            continue

        # Hard filter — outside all bounds
        if tx_date < early_start or tx_date > season_end:
            skipped += 1
            continue

        team_name    = row[1].strip() if len(row) > 1 else ''
        players_raw  = row[2].strip() if len(row) > 2 else ''
        effective    = row[3].strip() if len(row) > 3 else ''

        team_id = get_team_id_by_name(con, season, team_name)

        # Parse effective date
        try:
            effective_date = datetime.strptime(effective, '%m/%d/%y').date()
        except:
            effective_date = tx_date.date()

        # Each row can have multiple player transactions
        player_lines = [p.strip() for p in players_raw.split('\n') if p.strip()]

        for player_line in player_lines:
            # Determine transaction type
            if ' - Dropped' in player_line:
                tx_type     = 'drop'
                player_info = player_line.replace(' - Dropped', '').strip()
                cost        = None
                from_team   = None

            elif 'Signed for $' in player_line:
                tx_type     = 'add'
                cost_match  = re.search(r'Signed for \$(\d+\.\d+)', player_line)
                cost        = float(cost_match.group(1)) if cost_match else None
                player_info = re.sub(r'\s*-\s*Signed for \$[\d.]+', '', player_line).strip()
                from_team   = None

            elif ' - Activated' in player_line:
                tx_type     = 'activate'
                player_info = player_line.replace(' - Activated', '').strip()
                cost        = None
                from_team   = None

            elif ' - Traded from ' in player_line:
                tx_type     = 'trade'
                t_match     = re.match(r'^(.+?)\s+-\s+Traded from (.+)$', player_line)
                player_info = t_match.group(1).strip() if t_match else player_line
                from_name   = t_match.group(2).strip() if t_match else None
                from_team   = get_team_id_by_name(con, season, from_name) if from_name else None
                cost        = None

            else:
                continue

            # Filter pre-season drops
            if tx_date < season_start and tx_type == 'drop':
                skipped += 1
                continue

            # Clean player name
            name_match = re.match(
                r'^(.+?)\s+(?:C|1B|2B|3B|SS|OF|DH|SP|RP|P)[\s,|]',
                player_info
            )
            player_name = name_match.group(1).strip() if name_match else player_info.split('|')[0].strip()
            player_name = re.sub(
                r'\s+(C|1B|2B|3B|SS|OF|DH|SP|RP|P)'
                r'(\s*,\s*(C|1B|2B|3B|SS|OF|DH|SP|RP|P))*\s*$',
                '', player_name
            ).strip().strip('"')

            con.execute("""
                INSERT INTO transactions
                    (season, transaction_date, effective_date,
                     team_id, player_id, tx_type,
                     acquisition_cost, from_team_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                season,
                tx_date,
                effective_date,
                team_id,
                None,
                tx_type,
                cost,
                from_team,
            ])
            rows_loaded += 1

    con.close()
    print(f"Skipped {skipped} out-of-season or pre-season drops.")
    print(f"Total transactions loaded: {rows_loaded}")
    return rows_loaded


if __name__ == "__main__":
    parse_transaction_file(season=2025)