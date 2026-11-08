"""Cold-start and legacy-index backfill must serialize across connections."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from worldcore import WorldCore


@pytest.mark.parametrize('trial',range(5))
def test_parallel_legacy_intelligence_index_backfill(tmp_path,trial):
    path=tmp_path/f'legacy{trial}.db'
    with WorldCore(path) as w:
        w.db.execute('INSERT INTO intel_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
          ('a','default','fixture','one',1,'news','Fixture','Test observation','https://example.org','CC0',
           '2024-01-01T00:00:00Z','2024-01-01T00:00:01Z','[]','[]',1.0,'a'*64))
        w.db.execute('DROP TABLE intel_index')
    def initialize(_):
        with WorldCore(path) as w:
            return w.db.execute('SELECT COUNT(*) FROM intel_index').fetchone()[0]
    with ThreadPoolExecutor(max_workers=6) as pool:
        counts=list(pool.map(initialize,range(12)))
    assert counts==[1]*12
