"""Letture e scritture insieme sulla stessa connessione: prima davano sqlite3.InterfaceError, ora nessun errore e nessuna scrittura persa."""
import threading

from worldcore import WorldCore


def test_parallel_reads_and_writes_share_one_connection(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    errors, N = [], 150

    def writer(k):
        for i in range(N):
            try:
                w.remember("local", f"w{k}.fatto{i}", f"Fatto {i} del writer {k}", kind="fact", source="test", space="s")
            except Exception as e:
                errors.append(repr(e))

    def reader():
        for i in range(N * 2):
            try:
                w.facts("local", "w", space="s", limit=50)
                w.recall("local", "fatto writer", space="s", limit=5)
                w.history("local", "w0.fatto0", space="s")
            except Exception as e:
                errors.append(repr(e))

    threads = [threading.Thread(target=writer, args=(k,)) for k in range(2)] + [threading.Thread(target=reader) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []
    assert len(w.facts("local", "w0.", space="s", limit=1000)) == N and len(w.facts("local", "w1.", space="s", limit=1000)) == N


def test_rows_behave_like_a_cursor(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    w.db.execute("CREATE TABLE t(a INTEGER)")
    cur = w.db.execute("INSERT INTO t VALUES(1)")
    assert cur.rowcount == 1
    w.db.executemany("INSERT INTO t VALUES(?)", [(2,), (3,)])
    rows = w.db.execute("SELECT a FROM t ORDER BY a")
    assert rows.fetchone()["a"] == 1 and [r["a"] for r in rows.fetchmany(1)] == [2] and [r["a"] for r in rows] == [3] and rows.fetchone() is None
    assert w.db.execute("SELECT count(*) FROM t").fetchone()[0] == 3
