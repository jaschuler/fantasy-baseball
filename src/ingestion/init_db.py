import duckdb
import sys
from pathlib import Path

# ── Allow imports from project root ──────────────────────────────────────────
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import DB_PATH

def get_connection():
    """Return a DuckDB connection to the fantasy baseball database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))

def init_db():
    """Create all schema tables if they don't already exist."""
    con = get_connection()
    
    # ── Reference Tables ──────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id       INTEGER PRIMARY KEY,
            season        INTEGER,
            team_name     VARCHAR,
            manager_name  VARCHAR,
            last_name_key VARCHAR,
            division      VARCHAR,
            league_theme  VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS periods (
            period_id    INTEGER PRIMARY KEY,
            season       INTEGER,
            period_num   INTEGER,
            start_date   DATE,
            end_date     DATE,
            num_days     INTEGER,
            period_type  VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS scoring_categories (
            cat_id       INTEGER PRIMARY KEY,
            cat_code     VARCHAR,
            cat_display  VARCHAR,
            player_type  VARCHAR,
            is_inverse   BOOLEAN
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id       INTEGER PRIMARY KEY,
            name_first      VARCHAR,
            name_last       VARCHAR,
            name_full       VARCHAR,
            mlb_team        VARCHAR,
            position        VARCHAR,
            key_fangraphs   VARCHAR,
            key_bbref       VARCHAR,
            cbs_name_raw    VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS player_name_crosswalk (
            crosswalk_id     INTEGER PRIMARY KEY,
            cbs_name_raw     VARCHAR,
            player_id        INTEGER REFERENCES players(player_id),
            match_confidence FLOAT,
            match_method     VARCHAR,
            season           INTEGER
        )
    """)

    # ── Fact Tables ───────────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS hitter_period_stats_standard (
            id          INTEGER PRIMARY KEY,
            player_id   INTEGER REFERENCES players(player_id),
            period_id   INTEGER REFERENCES periods(period_id),
            team_id     INTEGER REFERENCES teams(team_id),
            mlb_team    VARCHAR,
            AB          INTEGER,
            R           INTEGER,
            H           INTEGER,
            doubles     INTEGER,
            triples     INTEGER,
            HR          INTEGER,
            RBI         INTEGER,
            BB          INTEGER,
            KO          INTEGER,
            SB          INTEGER,
            CS          INTEGER,
            AVG         FLOAT,
            OBP         FLOAT,
            SLG         FLOAT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS hitter_period_stats_scoring (
            id          INTEGER PRIMARY KEY,
            player_id   INTEGER REFERENCES players(player_id),
            period_id   INTEGER REFERENCES periods(period_id),
            team_id     INTEGER REFERENCES teams(team_id),
            AVG         FLOAT,
            HR          INTEGER,
            KO          INTEGER,
            OPS         FLOAT,
            RP          INTEGER,
            SB          INTEGER,
            PA          INTEGER
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS pitcher_period_stats_standard (
            id          INTEGER PRIMARY KEY,
            player_id   INTEGER REFERENCES players(player_id),
            period_id   INTEGER REFERENCES periods(period_id),
            team_id     INTEGER REFERENCES teams(team_id),
            mlb_team    VARCHAR,
            INNs        FLOAT,
            APP         INTEGER,
            GS          INTEGER,
            QS          INTEGER,
            CG          INTEGER,
            W           INTEGER,
            L           INTEGER,
            SV          INTEGER,
            BS          INTEGER,
            HD          INTEGER,
            K           INTEGER,
            BB          INTEGER,
            H           INTEGER,
            ERA         FLOAT,
            WHIP        FLOAT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS pitcher_period_stats_scoring (
            id          INTEGER PRIMARY KEY,
            player_id   INTEGER REFERENCES players(player_id),
            period_id   INTEGER REFERENCES periods(period_id),
            team_id     INTEGER REFERENCES teams(team_id),
            ERA         FLOAT,
            HRA         INTEGER,
            K           INTEGER,
            QS          INTEGER,
            SV          INTEGER,
            WHIP        FLOAT,
            INNs        FLOAT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS matchups (
            matchup_id    INTEGER PRIMARY KEY,
            period_id     INTEGER REFERENCES periods(period_id),
            team1_id      INTEGER REFERENCES teams(team_id),
            team2_id      INTEGER REFERENCES teams(team_id),
            team1_cat_w   INTEGER,
            team1_cat_l   INTEGER,
            team1_cat_t   INTEGER,
            team2_cat_w   INTEGER,
            team2_cat_l   INTEGER,
            team2_cat_t   INTEGER,
            team1_result  VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id   INTEGER PRIMARY KEY,
            season           INTEGER,
            transaction_date TIMESTAMP,
            effective_date   DATE,
            team_id          INTEGER REFERENCES teams(team_id),
            player_id        INTEGER REFERENCES players(player_id),
            tx_type          VARCHAR,
            acquisition_cost FLOAT,
            from_team_id     INTEGER REFERENCES teams(team_id)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS preseason_valuations (
            valuation_id      INTEGER PRIMARY KEY,
            season            INTEGER,
            player_id         INTEGER REFERENCES players(player_id),
            auction_price_paid FLOAT,
            projected_value   FLOAT,
            team_id           INTEGER REFERENCES teams(team_id),
            player_type       VARCHAR
        )
    """)

    con.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()