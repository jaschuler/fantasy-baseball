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

con.close()