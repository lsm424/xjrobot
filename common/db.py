import sqlite3
from contextlib import contextmanager

conn = sqlite3.connect('robot.db')


@contextmanager
def get_db_context_session() -> sqlite3.Cursor:
    cursor = conn.cursor()
    yield cursor
    conn.commit()