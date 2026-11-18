"""Versione dello schema del Core: scritta alla creazione, mantenuta nei database già esistenti, rifiutata se troppo nuova."""
import sqlite3

import pytest

from worldcore import WorldCore
from worldcore.engine import CORE_SCHEMA_VERSION, WorldCoreError


def test_new_database_records_version(tmp_path):
    p = str(tmp_path / "w.sqlite3")
    with WorldCore(p) as w:
        assert w.schema_version() == CORE_SCHEMA_VERSION == 1


def test_existing_database_without_version_gets_it_and_keeps_facts(tmp_path):
    p = str(tmp_path / "w.sqlite3")
    with WorldCore(p) as w:
        w.remember("local", "persona.x.mestiere", "Fa il notaio", kind="fact", source="test", space="personal")
    c = sqlite3.connect(p)
    c.execute("DELETE FROM schema_meta WHERE key='schema_version'")
    c.commit()
    c.close()
    with WorldCore(p) as w:
        assert w.schema_version() == 1
        assert w.facts("local", "persona.x.", space="personal")[0]["value"] == "Fa il notaio"


def test_database_from_newer_engine_is_refused(tmp_path):
    p = str(tmp_path / "w.sqlite3")
    WorldCore(p).close()
    c = sqlite3.connect(p)
    c.execute("UPDATE schema_meta SET value='99' WHERE key='schema_version'")
    c.commit()
    c.close()
    with pytest.raises(WorldCoreError, match="newer"):
        WorldCore(p)
