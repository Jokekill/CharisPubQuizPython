"""SQLite vrstva — schéma a pomocné funkce.

Používáme přímo modul sqlite3 (žádné ORM): schéma je malé a takhle je
aplikace bez závislostí navíc a bez překvapení na PythonAnywhere.
"""
import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    token       TEXT NOT NULL UNIQUE,          -- identita zařízení (localStorage)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS question_sets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id      INTEGER NOT NULL REFERENCES question_sets(id) ON DELETE CASCADE,
    poradi      INTEGER NOT NULL,              -- pořadí v sadě (od 0)
    typ         TEXT NOT NULL,                 -- abcd | pravdanepravda | text | cislo
    otazka      TEXT NOT NULL,
    obrazek     TEXT,                          -- název souboru v media/, nebo NULL
    moznost_a   TEXT, moznost_b TEXT, moznost_c TEXT, moznost_d TEXT,
    spravna     TEXT NOT NULL,
    alt_odpovedi TEXT,                         -- alternativy pro typ text, oddělené |
    tolerance   REAL,                          -- jen pro typ cislo (absolutní ±)
    body        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS answers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id  INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    team_id      INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    odpoved      TEXT NOT NULL,
    auto_spravne INTEGER,                      -- automatické vyhodnocení 0/1, NULL = zatím ne
    override     INTEGER,                      -- ruční rozhodnutí admina 0/1, NULL = bez zásahu
    bonus        INTEGER NOT NULL DEFAULT 0,   -- bonusový bod za nejbližší číselný odhad
    body         INTEGER NOT NULL DEFAULT 0,   -- celkem udělené body za tuto odpověď
    updated_at   TEXT,
    UNIQUE (question_id, team_id)
);

-- Stav hry: vždy jediný řádek s id=1, autoritativní na serveru.
CREATE TABLE IF NOT EXISTS game_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    phase           TEXT NOT NULL DEFAULT 'lobby',
        -- lobby | question | results_set | results_total | review | finished
    set_queue       TEXT NOT NULL DEFAULT '[]',  -- JSON pole id sad v pořadí hraní
    set_index       INTEGER NOT NULL DEFAULT -1, -- index do set_queue
    question_index  INTEGER NOT NULL DEFAULT -1, -- index otázky v aktuální sadě
    q_state         TEXT NOT NULL DEFAULT 'hidden',
        -- shown | open | countdown | locked | revealed
    countdown_ends  REAL,                        -- unix timestamp konce odpočtu
    countdown_secs  INTEGER,                     -- délka aktuálního odpočtu
    review_index    INTEGER NOT NULL DEFAULT -1, -- index otázky v review módu
    version         INTEGER NOT NULL DEFAULT 0   -- roste při každé změně stavu
);

INSERT OR IGNORE INTO game_state (id) VALUES (1);
"""


def get_db() -> sqlite3.Connection:
    """Vrátí spojení do DB pro aktuální request (jedno na request)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Vytvoří schéma, pokud neexistuje. Volá se při startu aplikace."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def bump_version(db):
    """Zvýší čítač verze stavu — klienti podle něj poznají změnu."""
    db.execute("UPDATE game_state SET version = version + 1 WHERE id = 1")
