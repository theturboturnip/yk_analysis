import sqlite3

class ReadOnlyDb:
    conn: sqlite3.Connection
    cur: sqlite3.Cursor
    version: int
    def __init__(self, path, expected_version):
        self.conn = sqlite3.Connection(f"file:{path}?mode=ro", uri=True)
        self.cur = self.conn.cursor()
        self.version = self.cur.execute("SELECT user_version FROM pragma_user_version").fetchone()[0]
        if self.version != expected_version:
            raise RuntimeError(f"DB user_version {self.version} doesn't match requested version {expected_version}")