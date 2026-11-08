"""Tiny multilingual intent router learned from explicit labels, not a general NLP model.

No model weights, private corpus or external API calls. Unknown/ambiguous requests
are passed to the hosting LLM without attempting an authoritative classification.
"""
from __future__ import annotations
import json, math,re
from collections import Counter,defaultdict
from .worldmodel import _valid_atom

INTENTS={'memory','planning','news','markets','health_info','sports','maps','3d','social','coding','general'}

def _tokens(txt):
    from .engine import WorldCoreError
    if not isinstance(txt,str) or not txt.strip() or len(txt)>500 or '\x00' in txt:
        raise WorldCoreError('invalid natural-language example')
    words=re.findall(r'[^\W_]+',txt.casefold())[:100]
    return words + ['__'.join(words[i:i+2]) for i in range(len(words)-1)]

class LanguageMixin:
    def _init_language_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS labeled_utterances(
          owner TEXT,space TEXT,id TEXT,utterance TEXT,intent TEXT,source TEXT,
          PRIMARY KEY(owner,space,id));
        CREATE INDEX IF NOT EXISTS utterance_scope ON labeled_utterances(owner,space,intent);
        ''')

    def label_utterance(self,owner,id,text,intent,*,space='default',source='explicit'):
        from .engine import WorldCoreError
        owner,space,id,source=map(lambda x:_valid_atom(x,'identifier'),(owner,space,id,source))
        if intent not in INTENTS:raise WorldCoreError('unknown intent label')
        _tokens(text)
        with self._transaction():
            row=self.db.execute('SELECT utterance,intent,source FROM labeled_utterances WHERE owner=? AND space=? AND id=?',(owner,space,id)).fetchone()
            if row:
                if tuple(row)==(text,intent,source):return {'status':'unchanged'}
                raise WorldCoreError('conflicting immutable utterance label')
            self.db.execute('INSERT INTO labeled_utterances VALUES (?,?,?,?,?,?)',(owner,space,id,text,intent,source))
        return {'status':'learned','intent':intent}

    def classify_intent(self,owner,text,*,space='default',min_examples_per_intent=3,
                        min_probability=.52,min_margin=.10):
        """Train-on-read smoothed Naive Bayes; low-quality predictions abstain.

        Confidence is a heuristic posterior under model assumptions, not calibrated.
        Not suitable for medical or psychological diagnosis or profiling.
        """
        from .engine import WorldCoreError
        owner,space=map(lambda x:_valid_atom(x,'identifier'),(owner,space))
        features=_tokens(text)
        if not 1<=min_examples_per_intent<=1000 or not 0<=min_probability<=1 or not 0<=min_margin<=1:
            raise WorldCoreError('invalid classification thresholds')
        with self.lock:
            rows=self.db.execute('SELECT utterance,intent FROM labeled_utterances WHERE owner=? AND space=?',(owner,space)).fetchall()
        totals=Counter(r['intent'] for r in rows)
        ready=[k for k,v in totals.items() if v>=min_examples_per_intent]
        if len(ready)<2:
            return {'status':'abstain','reason':'needs_two_trained_intents','sample_count':len(rows)}
        counts=defaultdict(Counter);vocab=set()
        for r in rows:
            if r['intent'] not in ready:continue
            xs=_tokens(r['utterance']);counts[r['intent']].update(xs);vocab.update(xs)
        size=len(vocab)+1
        scores={}
        relevant=[x for x in features if x in vocab]
        if not relevant:return {'status':'abstain','reason':'no_known_vocabulary','sample_count':len(rows)}
        for intent in ready:
            prior=totals[intent]/sum(totals[k] for k in ready)
            denom=sum(counts[intent].values())+size
            scores[intent]=math.log(prior)+sum(math.log((counts[intent][tok]+1)/denom) for tok in relevant)
        top=max(scores.values());probs={k:math.exp(v-top) for k,v in scores.items()};z=sum(probs.values())
        probs={k:v/z for k,v in probs.items()}
        top2=sorted(probs.items(),key=lambda x:-x[1]);intent,p=top2[0]
        if p<min_probability or p-top2[1][1]<min_margin:
            return {'status':'abstain','reason':'low_margin_or_uncertainty','candidate':intent,
                    'estimated_probability':round(p,4),'confidence_calibrated':False}
        return {'status':'classified','intent':intent,'estimated_probability':round(p,4),
                'confidence_calibrated':False,'sample_count':len(rows),
                'notice':'lightweight lexicon classifier; complex language requires an external LLM'}
