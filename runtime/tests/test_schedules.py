import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pytest
from worldcore.engine import WorldCore, WorldCoreError

T0 = 1_800_000_000.0


def test_one_shot_and_recurring(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    a = w.schedule("o", "reminder", "chiama Marco", T0 + 60, space="s")
    b = w.schedule("o", "check", "posta", T0 + 30, space="s", every_seconds=120, spec={"x": 1})
    assert w.lease_due("o", space="s", now=T0) == []
    due = w.lease_due("o", space="s", now=T0 + 61)
    assert [d["id"] for d in due] == [b["id"], a["id"]] and due[1]["spec"] == {}
    assert w.lease_due("o", space="s", now=T0 + 62) == []           # già in carico: nessuna doppia consegna
    done = w.complete_schedule("o", a["id"], due[1]["lease_token"], space="s", now=T0 + 62)
    assert done["status"] == "done" and done["runs"] == 1
    rec = w.complete_schedule("o", b["id"], due[0]["lease_token"], space="s", now=T0 + 400)
    assert rec["status"] == "active" and rec["next_run"] == T0 + 30 + 4 * 120 and rec["spec"] == {"x": 1}
    assert [x["id"] for x in w.schedules("o", space="s")] == [b["id"]]


def test_expired_lease_is_released_and_bad_token_refused(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    a = w.schedule("o", "reminder", "x", T0, space="s")
    first = w.lease_due("o", space="s", now=T0 + 1, lease_seconds=60)[0]
    with pytest.raises(WorldCoreError):
        w.complete_schedule("o", a["id"], "falso", space="s", now=T0 + 2)
    again = w.lease_due("o", space="s", now=T0 + 120)[0]               # l'host era caduto: si riprende
    assert again["lease_token"] != first["lease_token"]
    with pytest.raises(WorldCoreError):                                 # il lease vecchio non vale più
        w.complete_schedule("o", a["id"], first["lease_token"], space="s", now=T0 + 121)
    assert w.complete_schedule("o", a["id"], again["lease_token"], space="s", now=T0 + 121)["status"] == "done"


def test_cancel_spaces_and_validation(tmp_path):
    w = WorldCore(str(tmp_path / "w.sqlite3"))
    a = w.schedule("o", "reminder", "x", T0, space="s1")
    assert w.lease_due("o", space="s2", now=T0 + 1) == []
    assert w.cancel_schedule("o", a["id"], space="s1") and not w.cancel_schedule("o", a["id"], space="s1")
    assert w.lease_due("o", space="s1", now=T0 + 1) == []
    with pytest.raises(WorldCoreError):
        w.schedule("o", "reminder", "x", T0, space="s1", every_seconds=5)
    with pytest.raises(WorldCoreError):
        w.schedule("o", "reminder", "x", float("nan"), space="s1")
