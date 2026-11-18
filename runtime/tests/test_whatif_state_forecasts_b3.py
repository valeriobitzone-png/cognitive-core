"""B3: WHAT IF su stato fornito dal chiamante (con salvataggio) e elenco delle previsioni."""
from datetime import datetime, timedelta, timezone

import pytest

from worldcore.engine import WorldCore, WorldCoreError

SC = [{"id": "a", "kind": "state", "actions": [{"op": "add", "key": "costo", "value": -50}]},
      {"id": "b", "kind": "state", "actions": [{"op": "add", "key": "costo", "value": 20}]}]
OBJ = [{"key": "costo", "direction": "minimize", "scale": 100, "weight": 1}]


@pytest.fixture()
def db(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    yield w
    w.close()


def due(days=1):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_state_override_persists_run_without_touching_stored_state(db):
    db.set_state("u", "costo", 999, space="s")                                 # lo stato del Core resta com'è
    r = db.compare_futures("u", "meglio A o B?", SC, space="s", objectives=OBJ, persist=True, state={"costo": 300})
    assert r["ranking"] == ["a", "b"] and "run_id" in r
    assert r["scenarios"][0]["projected_state"]["costo"] == 250 and r["scenarios"][1]["projected_state"]["costo"] == 320
    assert db.state("u", space="s")["costo"] == 999
    h = db.whatif_history("u", space="s")
    assert len(h) == 1 and h[0]["question"] == "meglio A o B?" and h[0]["status"] == "unresolved"
    v = db.verify_whatif("u", r["run_id"], "a", {"costo": 260}, space="s")
    assert v["status"] == "verified" and v["absolute_errors"]["costo"] == 10
    assert db.whatif_history("u", space="s")[0]["status"] == "verified"


def test_state_override_default_behaviour_unchanged(db):
    db.set_state("u", "costo", 300, space="s")
    r = db.compare_futures("u", "q", SC, space="s", objectives=OBJ, persist=False)
    assert r["scenarios"][0]["projected_state"]["costo"] == 250 and "run_id" not in r


def test_state_override_rejects_bad_state(db):
    with pytest.raises(WorldCoreError):
        db.compare_futures("u", "q", SC, space="s", objectives=OBJ, persist=False, state=[1, 2])
    with pytest.raises(WorldCoreError):
        db.compare_futures("u", "q", SC, space="s", objectives=OBJ, persist=False, state={f"k{i}": i for i in range(201)})


def test_list_forecasts_and_brier(db):
    f1 = db.forecast("u", "arriva il preventivo", True, 0.8, due(1), space="s")
    f2 = db.forecast("u", "chiude il bando", True, 0.6, due(3), space="s")
    db.forecast("u", "altro spazio", True, 0.5, due(1), space="t")
    assert [f["id"] for f in db.list_forecasts("u", space="s", status="pending")] == [f1["id"], f2["id"]]
    db.resolve_forecast("u", f1["id"], True, space="s", allow_early=True)
    assert [f["id"] for f in db.list_forecasts("u", space="s", status="pending")] == [f2["id"]]
    res = db.list_forecasts("u", space="s", status="resolved")
    assert len(res) == 1 and abs(res[0]["brier"] - 0.04) < 1e-9
    assert abs(db.forecast_stats("u", space="s")["mean_brier"] - 0.04) < 1e-9
    assert len(db.list_forecasts("u", space="s")) == 2
    with pytest.raises(WorldCoreError):
        db.list_forecasts("u", space="s", status="boh")
