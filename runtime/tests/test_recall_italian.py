"""Richiamo della memoria in italiano (cuore v2). Scritti prima della modifica: con 1.4.0rc5 passano 5 casi su 8."""
import pytest

from worldcore.engine import WorldCore, WorldCoreError

FACTS = [("luca.ruolo", "Luca Verdi è un cliente e anche un amico", ["persone"]),
         ("preventivo.luca", "Preventivo per impianto fotovoltaico da 6 kW richiesto da Luca il 10 novembre", ["lavoro"]),
         ("pagamento.rossi", "Fattura Rossi Impianti da 4.200 euro, scadenza a 30 giorni", ["contabilità"]),
         ("preferenza.caffe", "Valerio beve il caffè senza zucchero", ["preferenze"]),
         ("auto.tagliando", "Il tagliando della Panda è a 30.000 km", ["casa"])]


@pytest.fixture()
def wc(tmp_path):
    w = WorldCore(str(tmp_path / "wc.db"))
    for k, v, t in FACTS:
        w.remember("owner", k, v, space="personal", tags=t)
    yield w
    w.close()


def first(w, q):
    r = w.recall("owner", q, space="personal", limit=3)
    return r[0]["fact_key"] if r else None


@pytest.mark.parametrize("query,expected", [
    ("preventivi di Luca", "preventivo.luca"),          # plurale → singolare
    ("chi è Luca?", "luca.ruolo"),                      # la persona prima dei documenti che la citano
    ("quanto devo a Rossi?", "pagamento.rossi"),
    ("come prende il caffè Valerio?", "preferenza.caffe"),
    ("fotovoltaico", "preventivo.luca"),
    ("quando scade la fattura", "pagamento.rossi"),
    ("il tagliando dell'auto", "auto.tagliando"),
    ("fatture", "pagamento.rossi"),
])
def test_italian_recall(wc, query, expected):
    assert first(wc, query) == expected


def test_only_stopwords_returns_nothing(wc):
    assert wc.recall("owner", "il", space="personal") == []
    assert wc.recall("owner", "di che cosa", space="personal") == []


def test_unicode_tags_but_strict_identifiers(tmp_path):
    w = WorldCore(str(tmp_path / "wc.db"))
    m = w.remember("owner", "nota.1", "valore", space="personal", tags=["contabilità", "perché"])
    assert m["tags"] == ["contabilità", "perché"]
    with pytest.raises(WorldCoreError):
        w.remember("owner", "nota con spazi", "valore", space="personal")  # le chiavi restano identificativi rigidi
    with pytest.raises(WorldCoreError):
        w.remember("owner", "nota.2", "valore", space="personal", tags=["due parole"])
    w.close()
