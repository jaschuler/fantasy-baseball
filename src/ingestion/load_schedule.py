import sys
import re
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.ingestion.init_db import get_connection

def get_team_id_by_key(con, season, last_name_key):
    """Look up team_id from teams table by last name key."""
    result = con.execute("""
        SELECT team_id FROM teams
        WHERE season = ? AND last_name_key = ?
    """, [season, last_name_key]).fetchone()
    return result[0] if result else None

def get_period_id(con, season, period_num):
    """Look up period_id from periods table."""
    result = con.execute("""
        SELECT period_id FROM periods
        WHERE season = ? AND period_num = ?
    """, [season, period_num]).fetchone()
    return result[0] if result else None

def load_schedule(season=2025):
    """Parse schedule docx and load matchups into matchups table."""
    from docx import Document

    doc_path = (
        Path(__file__).parent.parent.parent
        / "data" / "raw" / str(season)
        / "schedule_and_results.docx"
        )
    
    if not doc_path.exists():
        doc_path = (
            Path(__file__).parent.parent.parent
            / "data" / "raw" / str(season)
            / f"{season}_schedule_results_ytd.docx"
        )
    

    if not doc_path.exists():
        print(f"WARNING: {doc_path.name} not found.")
        return 0

    doc = Document(doc_path)
    con = get_connection()

    con.execute("""
        DELETE FROM matchups
        WHERE period_id IN (
            SELECT period_id FROM periods WHERE season = ?
        )
    """, [season])

    rows_loaded = 0

    for table in doc.tables:
        header = table.rows[0].cells[0].text.strip()
        period_match = re.match(
            r'Period (\d+): (\d+/\d+/\d+) - (\d+/\d+/\d+)',
            header
        )
        if not period_match:
            continue

        period_num = int(period_match.group(1))
        period_id = get_period_id(con, season, period_num)
        if not period_id:
            continue

        for row in table.rows[1:]:
            cells = [c.text.strip().replace('\xa0', ' ') for c in row.cells]
            if not cells[0]:
                continue

            t1_match = re.match(r'(.+?)\s+\(([WL])\)', cells[0])
            t2_match = re.match(r'(.+?)\s+\(([WL])\)', cells[1])
            if not t1_match or not t2_match:
                continue

            team1_key    = t1_match.group(1).strip()
            team1_result = t1_match.group(2)
            team2_key    = t2_match.group(1).strip()

            team1_id = get_team_id_by_key(con, season, team1_key)
            team2_id = get_team_id_by_key(con, season, team2_key)

            score_match = re.match(
                r'(\d+)-(\d+)-(\d+)\s+(\d+)-(\d+)-(\d+)',
                cells[2]
            )
            if score_match:
                t1_w = int(score_match.group(1))
                t1_l = int(score_match.group(2))
                t1_t = int(score_match.group(3))
                t2_w = int(score_match.group(4))
                t2_l = int(score_match.group(5))
                t2_t = int(score_match.group(6))
            else:
                t1_w = t1_l = t1_t = t2_w = t2_l = t2_t = None

            con.execute("""
                INSERT INTO matchups
                    (period_id, team1_id, team2_id,
                     team1_cat_w, team1_cat_l, team1_cat_t,
                     team2_cat_w, team2_cat_l, team2_cat_t,
                     team1_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                period_id,
                team1_id,
                team2_id,
                t1_w, t1_l, t1_t,
                t2_w, t2_l, t2_t,
                team1_result
            ])
            rows_loaded += 1

    con.close()
    print(f"Total matchups loaded: {rows_loaded}")
    return rows_loaded


if __name__ == "__main__":
    import sys
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    load_schedule(season=season)