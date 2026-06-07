import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.ingestion.init_db import get_connection

con = get_connection()

print("=== TEAMS ===")
print(con.execute("SELECT * FROM teams ORDER BY season, team_id").df())

print("\n=== PERIODS ===")
print(con.execute("SELECT * FROM periods ORDER BY season, period_num").df())

print("\n=== SCORING CATEGORIES ===")
print(con.execute("SELECT * FROM scoring_categories ORDER BY cat_id").df())

# Add this temporarily to notebooks/quick_check.py

print("=== HITTER SCORE SAMPLE ===")
print(con.execute("""
    SELECT 
        h.period_id,
        p.period_num,
        h.team_id,
        t.last_name_key,
        h.AVG,
        h.HR,
        h.KO,
        h.OPS,
        h.RP,
        h.SB
    FROM hitter_period_stats_scoring h
    LEFT JOIN periods p ON h.period_id = p.period_id
    LEFT JOIN teams t ON h.team_id = t.team_id
    WHERE h.team_id IS NOT NULL
    AND p.period_num = 1
    LIMIT 10
""").df())

print("\n=== FA vs ROSTERED BREAKDOWN (Period 1) ===")
print(con.execute("""
    SELECT 
        CASE WHEN team_id IS NULL THEN 'FA' ELSE 'Rostered' END as status,
        COUNT(*) as count
    FROM hitter_period_stats_scoring h
    JOIN periods p ON h.period_id = p.period_id
    WHERE p.period_num = 1
    GROUP BY 1
""").df())

# con.close()