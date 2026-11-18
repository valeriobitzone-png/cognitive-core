"""Cuore v2 · richiamo per significato con embedder dell'host. Embedder finto e deterministico: il test non dipende da un modello."""
import pytest

np = pytest.importorskip("numpy")
from worldcore.engine import WorldCore  # noqa: E402

# «significati» finti: ogni concetto è un asse; una parola attiva il suo asse
AXES = {"auto": 0, "macchina": 0, "panda": 0, "tagliando": 1, "manutenzione": 1, "revisione": 1,
        "caffe": 2, "caffè": 2, "colazione": 2, "fattura": 3, "pagare": 3, "bolletta": 3}


def fake_embed(texts, kind):
    out = []
    for t in texts:
        v = np.full(8, 0.05, dtype=np.float32)
        for w in t.lower().replace(":", " ").replace(".", " ").split():
            if w in AXES:
                v[AXES[w]] += 1
        out.append(v / np.linalg.norm(v))
    return out


@pytest.fixture()
def wc(tmp_path):
    w = WorldCore(str(tmp_path / "wc.db"))
    w.remember("owner", "auto.tagliando", "Il tagliando della Panda è a 30.000 km", space="p")    # scritto prima dell'embedder
    w.set_embedder(fake_embed, "fake-v1", min_similarity=0.6)
    assert w.embed_missing() == 1 and w.embed_missing() == 0
    w.remember("owner", "preferenza.caffe", "Valerio beve il caffè senza zucchero", space="p")
    w.remember("owner", "fattura.luce", "Bolletta della luce da pagare il 20", space="p")
    yield w
    w.close()


def test_paraphrase_found_by_meaning(wc):
    r = wc.recall("owner", "manutenzione della macchina", space="p", limit=3)
    assert r and r[0]["fact_key"] == "auto.tagliando"          # nessuna parola in comune: solo il significato


def test_lexical_still_works_and_unrelated_stays_out(wc):
    assert wc.recall("owner", "zucchero", space="p")[0]["fact_key"] == "preferenza.caffe"
    keys = [m["fact_key"] for m in wc.recall("owner", "manutenzione", space="p")]
    assert "preferenza.caffe" not in keys                       # sotto soglia e senza parole in comune


def test_scope_and_updates_respected(wc):
    assert wc.recall("owner", "manutenzione della macchina", space="altro") == []
    wc.remember("owner", "auto.tagliando", "Il tagliando della Panda è stato fatto a ottobre", space="p")
    r = wc.recall("owner", "manutenzione della macchina", space="p")
    assert len([m for m in r if m["fact_key"] == "auto.tagliando"]) == 1 and "ottobre" in r[0]["value"]


def test_broken_embedder_never_blocks_memory(tmp_path):
    w = WorldCore(str(tmp_path / "wc.db"))

    def broken(texts, kind):
        raise RuntimeError("modello spento")

    w.set_embedder(broken, "broken-v1")
    m = w.remember("owner", "nota.1", "fattura del fornitore", space="p")
    assert m["fact_key"] == "nota.1"
    assert w.recall("owner", "fattura", space="p")[0]["fact_key"] == "nota.1"   # ripiego lessicale
    w.close()
