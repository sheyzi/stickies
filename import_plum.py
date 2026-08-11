#!/usr/bin/env python3
"""One-time importer: migrates notes from plum.sqlite into notes.sqlite."""

import re
import sqlite3
from pathlib import Path

import stickydb

PLUM_DB = Path.home() / ".stickynote" / "plum.sqlite"

TOKEN_PATTERNS = [
    (re.compile(r"\\id=[0-9a-fA-F-]+"), ""),
    (re.compile(r"\\b0"), ""),
    (re.compile(r"\\b"), ""),
    (re.compile(r"\\l0"), ""),
    (re.compile(r"\\l"), "- "),
]


def decode_plum_text(text):
    if not text:
        return ""
    for pattern, replacement in TOKEN_PATTERNS:
        text = pattern.sub(replacement, text)
    lines = []
    blank = 0
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            blank += 1
            if blank <= 1:
                lines.append("")
        else:
            blank = 0
            lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def main():
    if not PLUM_DB.exists():
        print(f"Error: {PLUM_DB} not found.")
        return 1

    stickydb.init_db()

    con = sqlite3.connect(PLUM_DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT Id, Text, CreatedAt FROM Note WHERE DeletedAt IS NULL"
    ).fetchall()
    con.close()

    imported = 0
    for row in rows:
        text = decode_plum_text(row["Text"]) or "(empty note)"
        existing = stickydb.create_note(
            text=text, note_id=row["Id"], created_at=row["CreatedAt"]
        )
        if existing["Text"] == text:
            imported += 1

    print(f"Imported {imported} notes into {stickydb.DB_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
