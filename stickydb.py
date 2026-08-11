import sqlite3
import time
import uuid
from pathlib import Path

DATA_DIR = Path.home() / ".stickynote"
DB_PATH = DATA_DIR / "notes.sqlite"

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS Note (
    Id        TEXT PRIMARY KEY,
    Text      TEXT NOT NULL DEFAULT '',
    Title     TEXT NOT NULL DEFAULT '',
    Color     TEXT NOT NULL DEFAULT 'yellow',
    IsOpen    INTEGER NOT NULL DEFAULT 0,
    X         INTEGER,
    Y         INTEGER,
    Width     INTEGER,
    Height    INTEGER,
    CreatedAt INTEGER,
    UpdatedAt INTEGER
);
"""

DEFAULT_COLOR = "yellow"


def _now_ms():
    return int(time.time() * 1000)


def _connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _column_names(con):
    return {row["name"] for row in con.execute("PRAGMA table_info(Note)").fetchall()}


def _migrate(con):
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    if version < 2:
        cols = _column_names(con)
        if "Title" not in cols:
            con.execute("ALTER TABLE Note ADD COLUMN Title TEXT NOT NULL DEFAULT ''")
        if "IsOpen" not in cols:
            con.execute("ALTER TABLE Note ADD COLUMN IsOpen INTEGER NOT NULL DEFAULT 0")
    con.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
    con.commit()


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = _connect()
    con.execute(SCHEMA)
    _migrate(con)
    con.close()


def _to_dict(row):
    return dict(row) if row is not None else None


def load_notes():
    con = _connect()
    rows = con.execute("SELECT * FROM Note ORDER BY CreatedAt").fetchall()
    con.close()
    return [_to_dict(r) for r in rows]


def get_note(note_id):
    con = _connect()
    row = con.execute("SELECT * FROM Note WHERE Id=?", (note_id,)).fetchone()
    con.close()
    return _to_dict(row)


def create_note(
    text="",
    title="",
    color=DEFAULT_COLOR,
    is_open=False,
    note_id=None,
    created_at=None,
):
    now = _now_ms()
    note_id = note_id or str(uuid.uuid4())
    created_at = created_at if created_at is not None else now
    con = _connect()
    con.execute(
        "INSERT OR IGNORE INTO Note "
        "(Id, Text, Title, Color, IsOpen, X, Y, Width, Height, CreatedAt, UpdatedAt) "
        "VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)",
        (note_id, text, title, color, 1 if is_open else 0, created_at, now),
    )
    con.commit()
    con.close()
    return {
        "Id": note_id,
        "Text": text,
        "Title": title,
        "Color": color,
        "IsOpen": 1 if is_open else 0,
        "X": None,
        "Y": None,
        "Width": None,
        "Height": None,
        "CreatedAt": created_at,
        "UpdatedAt": now,
    }


def update_note(note):
    note["UpdatedAt"] = _now_ms()
    con = _connect()
    con.execute(
        "UPDATE Note SET Text=?, Title=?, Color=?, IsOpen=?, X=?, Y=?, Width=?, "
        "Height=?, UpdatedAt=? WHERE Id=?",
        (
            note["Text"],
            note.get("Title", ""),
            note["Color"],
            1 if note.get("IsOpen") else 0,
            note["X"],
            note["Y"],
            note["Width"],
            note["Height"],
            note["UpdatedAt"],
            note["Id"],
        ),
    )
    con.commit()
    con.close()


def set_open(note_id, is_open):
    con = _connect()
    con.execute(
        "UPDATE Note SET IsOpen=?, UpdatedAt=? WHERE Id=?",
        (1 if is_open else 0, _now_ms(), note_id),
    )
    con.commit()
    con.close()


def delete_note(note_id):
    con = _connect()
    con.execute("DELETE FROM Note WHERE Id=?", (note_id,))
    con.commit()
    con.close()
