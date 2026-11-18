import json
import shutil
import sqlite3

import pytest
from cognitive_core.selfmodel import SelfModel

AVAILABLE={'local_inference_available':True}


def test_own_outcomes_only_and_runtime_separation(tmp_path):
    m=SelfModel(tmp_path,'a','n')
    try:
        for i in range(6):
            f=m.forecast('classifier','context',AVAILABLE,{'version':1})
            m.resolve(f['id'],True,'fixture:self')
        external=m.forecast('classifier','context',AVAILABLE,{'version':1})
        m.resolve(external['id'],False,'fixture:external',actor='other')
        new=m.forecast('classifier','context',AVAILABLE,{'version':1})
        assert new['samples']==6 and new['probability']==7/8 and not new['calibrated']
        assert m.forecast('classifier','context',AVAILABLE,{'version':2})['samples']==0
        assert m.forecast('classifier','different-context',AVAILABLE,{'version':1})['samples']==0
    finally:m.close()


def test_simulation_is_not_observed_learning(tmp_path):
    m=SelfModel(tmp_path)
    try:
        f=m.forecast('tool','c',AVAILABLE,{},epistemic='SIMULATED');m.resolve(f['id'],True,'simulation')
        assert m.forecast('tool','c',AVAILABLE,{})['samples']==0
        assert m.forecast('tool','c',AVAILABLE,{},epistemic='SIMULATED')['samples']==1
    finally:m.close()


def test_no_outcome_leak_and_immutable_resolution(tmp_path):
    m=SelfModel(tmp_path)
    try:
        before=m.forecast('tool','c',AVAILABLE,{})
        assert before['samples']==0 and before['probability'] is None
        result=m.resolve(before['id'],True,'observed-process')
        assert result['brier']==.25
        assert m.resolve(before['id'],True,'observed-process')==result
        with pytest.raises(ValueError):m.resolve(before['id'],False,'rewritten')
        row=m.episodes()[0]
        assert row['forecast']['samples']==0 and row['before_at']<=row['outcome']['observed_at']
    finally:m.close()


def test_owner_scope_and_restart_portability(tmp_path):
    source=tmp_path/'source';m=SelfModel(source,'owner','space')
    f=m.forecast('tool','c',AVAILABLE,{});m.close()
    copy=tmp_path/'copy';shutil.copytree(source,copy)
    reopened=SelfModel(copy,'owner','space')
    try:
        assert reopened.episodes()[0]['id']==f['id']
        path=tmp_path/'episodes.json';reopened.export(path)
        assert json.loads(path.read_text())['format']=='cognitive-self-v1'
        with pytest.raises(FileExistsError):reopened.export(path)
    finally:reopened.close()
    foreign=SelfModel(copy,'other','space')
    try:
        assert foreign.episodes()==[]
        with pytest.raises(KeyError):foreign.resolve(f['id'],True,'foreign')
    finally:foreign.close()


def test_missing_capability_prevents_admission(tmp_path):
    m=SelfModel(tmp_path)
    try:
        p=m.forecast('tool','c',{'local_inference_available':False},{})
        assert p['admitted'] is False and p['probability']==0
        result=m.resolve(p['id'],None,'not_attempted')
        assert result['brier'] is None and result['successful'] is None
    finally:m.close()


@pytest.mark.parametrize('snapshot',[{}, {'local_inference_available':'yes'}, {'local_inference_available':1}])
def test_invalid_runtime_observation_rejected(tmp_path,snapshot):
    m=SelfModel(tmp_path)
    try:
        with pytest.raises(ValueError):m.forecast('tool','c',snapshot,{})
        assert not m.episodes()
    finally:m.close()


def test_disk_admission_does_not_prevent_export(tmp_path):
    m=SelfModel(tmp_path/'state')
    m.db.execute('CREATE TABLE pad(value BLOB)');m.db.execute('INSERT INTO pad VALUES(zeroblob(2000000))')
    try:
        with pytest.raises(ValueError):m.forecast('tool','c',AVAILABLE,{})
        assert m.export(tmp_path/'still-readable.json')
    finally:m.close()
