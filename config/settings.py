from pathlib import Path

# ── Project Root ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent

# ── Data Paths ────────────────────────────────────────────────────────────────
DATA_DIR        = ROOT_DIR / "data"
RAW_DIR         = DATA_DIR / "raw"
PROCESSED_DIR   = DATA_DIR / "processed"

# ── Database ──────────────────────────────────────────────────────────────────
DB_DIR  =   ROOT_DIR / "db"
DB_PATH =   DB_DIR / "fantasy_baseball.duckdb"

# ── Seasons ───────────────────────────────────────────────────────────────────
CURRENT_SEASON  = 2026
HISTORICAL_SEASONS = [2025]

# ── League Settings ───────────────────────────────────────────────────────────
LEAGUE_SIZE     = 12
REGULAR_SEASON_PERIODS = 16
LEAGUE_THEME    = {2025: "Happy Gilmore", 2026: "Wedding Crashers"}

# ── Scoring Categories ────────────────────────────────────────────────────────
HIT_CATS        = ["AVG", "HR", "KO", "OPS", "RP", "SB"]
PITCH_CATS      = ["ERA", "HRA", "K", "QS", "SV", "WHIP"]
INVERSE_CATS    = ["KO", "ERA", "HRA", "WHIP"]  # lower is better

CAT_DISPLAY = {
    "AVG":  "Batting Average",
    "HR":   "Home Runs",
    "KO":   "Strikeouts",
    "OPS":  "OPS",
    "RP":   "Runs Produced",
    "SB":   "Stolen Bases",
    "ERA":  "ERA",
    "HRA":  "Home Runs Allowed",
    "K":    "Strikeouts",
    "QS":   "Quality Starts",
    "SV":   "Saves",
    "WHIP": "WHIP",
}