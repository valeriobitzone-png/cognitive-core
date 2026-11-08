"""Supervised decision-example collection for future LoRA/classifiers.

No unattended learning of model weights from unverified web content.
"""
import hashlib
import json
from pathlib import Path

ALLOWED_LABELS={'WAIT','STORE_ONLY','PREPARE_SILENTLY','SUGGEST','ASK_FOR_CONTEXT'}


def add_reviewed_example(output_dir, *, event, label, rationale, reviewed_by):
    if label not in ALLOWED_LABELS:
        raise ValueError('invalid label')
    if not reviewed_by.strip():
        raise ValueError('human review required for training examples')
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    record={'input':event,'output':{'action':label,'rationale':rationale[:500]},
            'reviewed_by':reviewed_by,'status':'human_reviewed'}
    blob=json.dumps(record,sort_keys=True,ensure_ascii=False)
    digest=hashlib.sha256(blob.encode()).hexdigest()
    file=output_dir/(digest+'.json')
    file.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return file


def export_supervised_jsonl(output_dir, target_file):
    output_dir=Path(output_dir)
    target_file=Path(target_file)
    count=0
    with target_file.open('w',encoding='utf-8') as out:
        for path in sorted(output_dir.glob('*.json')):
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('status')!='human_reviewed':
                continue
            pair={'messages':[{'role':'user','content':json.dumps(data['input'],ensure_ascii=False)},
                              {'role':'assistant','content':json.dumps(data['output'],ensure_ascii=False)}]}
            out.write(json.dumps(pair,ensure_ascii=False)+'\n');count+=1
    return count
