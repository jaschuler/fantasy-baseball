import sys
import duckdb
from pathlib import Path
from datetime import date

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import DB_PATH, LEAGUE_THEME, HIT_CATS, PITCH_CATS, INVERSE_CATS, CAT_DISPLAY
from src.ingestion.init_db import get_connection

def load_teams():
    """Populate the teams reference table for all seasons."""
    con = get_connection()

    teams = [
        # season, team_name, manager_name, last_name_key, division
        (2025, "Sexual and Violent",                          "Joe Schuler",      "Schuler",  "Shooter",      "Happy Gilmore"),
        (2025, "Team Tummy Sticks",                           "Troy Curl",        "Curl",     "Shooter",      "Happy Gilmore"),
        (2025, "Lock It Up",                                  "Chris Easom",      "Easom",    "Chubbs",       "Happy Gilmore"),
        (2025, "Motor Boatin' SOB",                           "Mike Hyland",      "Hyland",   "Shooter",      "Happy Gilmore"),
        (2025, "Pimps from Oakland or Cowboys From Arizona",  "Andrew Smith",     "Smith",    "Shooter",      "Happy Gilmore"),
        (2025, "Ma, the meatloaf!",                           "Jairo Rubio",      "Rubio",    "Shooter",      "Happy Gilmore"),
        (2025, "Make me a cycle, clown!",                     "Brett Stang",      "Stang",    "Chubbs",       "Happy Gilmore"),
        (2025, "Chazz Reinhold",                              "Blake Englert",    "Englert",  "Shooter",      "Happy Gilmore"),
        (2025, "Just The Tip",                                "Tony Vicencio",    "Vicencio", "Chubbs",       "Happy Gilmore"),
        (2025, "Stage 5 Clingers",                            "Elliott Sweitzer", "Sweitzer", "Chubbs",       "Happy Gilmore"),
        (2025, "Nature Always Wins",                          "Ryan Bevans",      "Bevans",   "Chubbs",       "Happy Gilmore"),
        (2025, "10,000 Days O'Toole",                         "John Knight",      "Knight",   "Chubbs",       "Happy Gilmore"),
        # 2026 season
        (2026, "Sexual and Violent",                          "Joe Schuler",      "Schuler",  "Ice My Balls", "Wedding Crashers"),
        (2026, "Team Tummy Sticks",                           "Troy Curl",        "Curl",     "Ice My Balls", "Wedding Crashers"),
        (2026, "Lock It Up",                                  "Chris Easom",      "Easom",    "Spit Up Blood","Wedding Crashers"),
        (2026, "Motor Boatin' SOB",                           "Mike Hyland",      "Hyland",   "Ice My Balls", "Wedding Crashers"),
        (2026, "Pimps from Oakland or Cowboys From Arizona",  "Andrew Smith",     "Smith",    "Ice My Balls", "Wedding Crashers"),
        (2026, "Ma, the meatloaf!",                           "Jairo Rubio",      "Rubio",    "Ice My Balls", "Wedding Crashers"),
        (2026, "Make me a cycle, clown!",                     "Brett Stang",      "Stang",    "Spit Up Blood","Wedding Crashers"),
        (2026, "Chazz Reinhold",                              "Blake Englert",    "Englert",  "Ice My Balls", "Wedding Crashers"),
        (2026, "Just The Tip",                                "Tony Vicencio",    "Vicencio", "Spit Up Blood","Wedding Crashers"),
        (2026, "Stage 5 Clingers",                            "Elliott Sweitzer", "Sweitzer", "Spit Up Blood","Wedding Crashers"),
        (2026, "Nature Always Wins",                          "Ryan Bevans",      "Bevans",   "Spit Up Blood","Wedding Crashers"),
        (2026, "10,000 Days O'Toole",                         "John Knight",      "Knight",   "Spit Up Blood","Wedding Crashers"),
    ]

    con.execute("DELETE FROM teams")

    con.executemany("""
        INSERT INTO teams (season, team_name, manager_name, last_name_key, division, league_theme)
        VALUES (?, ?, ?, ?, ?, ?)
    """, teams)

    print(f"Loaded {len(teams)} teams.")
    con.close()

def load_periods():
    """Populate the periods reference table for 2025 season."""
    con = get_connection()

    periods = [
        # season, period_num, start_date, end_date, num_days, period_type
        (2025,  1, date(2025, 3, 27), date(2025, 4,  6), 11, "regular"),
        (2025,  2, date(2025, 4,  7), date(2025, 4, 13),  7, "regular"),
        (2025,  3, date(2025, 4, 14), date(2025, 4, 20),  7, "regular"),
        (2025,  4, date(2025, 4, 21), date(2025, 4, 27),  7, "regular"),
        (2025,  5, date(2025, 4, 28), date(2025, 5,  4),  7, "regular"),
        (2025,  6, date(2025, 5,  5), date(2025, 5, 11),  7, "regular"),
        (2025,  7, date(2025, 5, 12), date(2025, 5, 18),  7, "regular"),
        (2025,  8, date(2025, 5, 19), date(2025, 5, 25),  7, "regular"),
        (2025,  9, date(2025, 5, 26), date(2025, 6,  1),  7, "regular"),
        (2025, 10, date(2025, 6,  2), date(2025, 6,  8),  7, "regular"),
        (2025, 11, date(2025, 6,  9), date(2025, 6, 15),  7, "regular"),
        (2025, 12, date(2025, 6, 16), date(2025, 6, 22),  7, "regular"),
        (2025, 13, date(2025, 6, 23), date(2025, 6, 29),  7, "regular"),
        (2025, 14, date(2025, 6, 30), date(2025, 7,  6),  7, "regular"),
        (2025, 15, date(2025, 7,  7), date(2025, 7, 13),  7, "regular"),
        (2025, 16, date(2025, 7, 14), date(2025, 7, 27), 14, "regular"),
        (2025, 17, date(2025, 7, 28), date(2025, 8,  3),  7, "playoff"),
        (2025, 18, date(2025, 8,  4), date(2025, 8, 10),  7, "playoff"),
        (2025, 19, date(2025, 8, 11), date(2025, 8, 17),  7, "playoff"),
        (2025, 20, date(2025, 8, 18), date(2025, 8, 24),  7, "playoff"),
        (2025, 21, date(2025, 8, 25), date(2025, 8, 31),  7, "playoff"),
        (2025, 22, date(2025, 9,  1), date(2025, 9,  7),  7, "playoff"),
    ]

    con.execute("DELETE FROM periods")

    con.executemany("""
        INSERT INTO periods 
            (season, period_num, start_date, end_date, num_days, period_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, periods)

    print(f"Loaded {len(periods)} periods.")
    con.close()

def load_scoring_categories():
    """Populate the scoring categories reference table."""
    con = get_connection()

    categories = [
        # cat_code, cat_display, player_type, is_inverse
        ("AVG",  "Batting Average",        "hitter",  False),
        ("HR",   "Home Runs",              "hitter",  False),
        ("KO",   "Strikeouts",             "hitter",  True),
        ("OPS",  "OPS",                    "hitter",  False),
        ("RP",   "Runs Produced",          "hitter",  False),
        ("SB",   "Stolen Bases",           "hitter",  False),
        ("ERA",  "ERA",                    "pitcher", True),
        ("HRA",  "Home Runs Allowed",      "pitcher", True),
        ("K",    "Strikeouts",             "pitcher", False),
        ("QS",   "Quality Starts",         "pitcher", False),
        ("SV",   "Saves",                  "pitcher", False),
        ("WHIP", "WHIP",                   "pitcher", True),
    ]

    con.execute("DELETE FROM scoring_categories")

    con.executemany("""
        INSERT INTO scoring_categories 
            (cat_code, cat_display, player_type, is_inverse)
        VALUES (?, ?, ?, ?)
    """, categories)

    print(f"Loaded {len(categories)} scoring categories.")
    con.close()

if __name__ == "__main__":
    load_teams()
    load_periods()
    load_scoring_categories()