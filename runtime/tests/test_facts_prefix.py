import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pytest
from worldcore.engine import WorldCore, WorldCoreError


def _k(f):
    return f.get("key") or f.get("fact_key")


def test_facts_by_prefix(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    w.remember("o", "persona.anna.profilo", "Anna, collega", space="s")
    w.remember("o", "persona.anna.relazione", "collega di lavoro", space="s")
    w.remember("o", "persona.annalisa.profilo", "altra persona", space="s")
    w.remember("o", "persona.anna.relazione", "amica", space="s")  # sostituisce la versione precedente
    got = w.facts("o", "persona.anna.", space="s")
    assert [_k(f) for f in got] == ["persona.anna.profilo", "persona.anna.relazione"]
    assert got[1]["value"] == "amica"
    assert w.facts("o", "persona.anna.", space="altro") == []


def test_prefix_is_literal(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    w.remember("o", "persona.anna_b.profilo", "con trattino basso", space="s")
    w.remember("o", "persona.annaxb.profilo", "senza", space="s")
    assert [_k(f) for f in w.facts("o", "persona.anna_", space="s")] == ["persona.anna_b.profilo"]
    assert w.facts("o", "persona.anna%", space="s") == []
    with pytest.raises(WorldCoreError):
        w.facts("o", "", space="s")
