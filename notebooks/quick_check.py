import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.ingestion.init_db import get_connection

con = get_connection()

# print("=== TEAMS ===")
# print(con.execute("SELECT * FROM teams ORDER BY season, team_id").df())

# print("\n=== PERIODS ===")
# print(con.execute("SELECT * FROM periods ORDER BY season, period_num").df())

# print("\n=== SCORING CATEGORIES ===")
# print(con.execute("SELECT * FROM scoring_categories ORDER BY cat_id").df())

# # Add this temporarily to notebooks/quick_check.py

# print("=== HITTER SCORE SAMPLE ===")
# print(con.execute("""
#     SELECT 
#         h.period_id,
#         p.period_num,
#         h.team_id,
#         t.last_name_key,
#         h.AVG,
#         h.HR,
#         h.KO,
#         h.OPS,
#         h.RP,
#         h.SB
#     FROM hitter_period_stats_scoring h
#     LEFT JOIN periods p ON h.period_id = p.period_id
#     LEFT JOIN teams t ON h.team_id = t.team_id
#     WHERE h.team_id IS NOT NULL
#     AND p.period_num = 1
#     LIMIT 10
# """).df())

# print("\n=== FA vs ROSTERED BREAKDOWN (Period 1) ===")
# print(con.execute("""
#     SELECT 
#         CASE WHEN team_id IS NULL THEN 'FA' ELSE 'Rostered' END as status,
#         COUNT(*) as count
#     FROM hitter_period_stats_scoring h
#     JOIN periods p ON h.period_id = p.period_id
#     WHERE p.period_num = 1
#     GROUP BY 1
# """).df())

# print("=== PITCHER SCORE SAMPLE ===")
# print(con.execute("""
#     SELECT 
#         p.period_num,
#         t.last_name_key,
#         h.ERA,
#         h.HRA,
#         h.K,
#         h.QS,
#         h.SV,
#         h.WHIP
#     FROM pitcher_period_stats_scoring h
#     LEFT JOIN periods p ON h.period_id = p.period_id
#     LEFT JOIN teams t ON h.team_id = t.team_id
#     WHERE h.team_id IS NOT NULL
#     AND p.period_num = 1
# """).df().head(10))


# print("=== MATCHUPS SAMPLE ===")
# print(con.execute("""
#     SELECT 
#         p.period_num,
#         t1.last_name_key  AS team1,
#         m.team1_result,
#         m.team1_cat_w,
#         m.team1_cat_l,
#         m.team1_cat_t,
#         t2.last_name_key  AS team2,
#         m.team2_cat_w,
#         m.team2_cat_l,
#         m.team2_cat_t
#     FROM matchups m
#     JOIN periods p  ON m.period_id  = p.period_id
#     JOIN teams t1   ON m.team1_id   = t1.team_id
#     JOIN teams t2   ON m.team2_id   = t2.team_id
#     WHERE p.period_num = 1
#     ORDER BY p.period_num
# """).df())

print("=== TRANSACTION TYPE BREAKDOWN ===")
print(con.execute("""
    SELECT 
        tx_type,
        COUNT(*)              AS count,
        ROUND(AVG(acquisition_cost), 2) AS avg_cost
    FROM transactions
    GROUP BY tx_type
    ORDER BY count DESC
""").df())

print("\n=== EARLIEST TRANSACTIONS ===")
print(con.execute("""
    SELECT 
        transaction_date,
        tm.last_name_key,
        tx_type,
        acquisition_cost
    FROM transactions t
    JOIN teams tm ON t.team_id = tm.team_id
    ORDER BY transaction_date
""").df().head(10))

# con.close()