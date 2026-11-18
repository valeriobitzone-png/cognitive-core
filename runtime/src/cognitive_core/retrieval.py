"""Lexical retrieval with freshness labels (clean-room rewrite of well-known techniques).

Ideas, not code, taken from MIT-licensed Hermes plugins: Okapi BM25 ranking (neural-mesh),
CURRENT / UNVERIFIED / HISTORICAL provenance labels (grounded-recall), reversible
suppression that is distinct from forgetting (scope-recall). Labels describe provenance,
never truth.
"""

import json
import math
import re
from collections import Counter

K1 = 1.5
B = 0.75
CURRENT, UNVERIFIED, HISTORICAL = 'CURRENT', 'UNVERIFIED', 'HISTORICAL'
RANK = {HISTORICAL: 0, UNVERIFIED: 1, CURRENT: 2}
_HIST = re.compile(r'\b(history|historical|archived?|obsolete|deprecated|superseded|changelog|legacy|storico|obsoleto|archiviato|superato)\b', re.I)
_TOK = re.compile(r'[a-z0-9àèéìòù]+')


def tokenize(text):
    return [t for t in _TOK.findall(text.lower()) if len(t) > 1]


def idf(n, df):
    return math.log(1.0 + (n - df + 0.5) / (df + 0.5))


class BM25:
    def __init__(self, docs, k1=K1, b=B):
        self.k1 = k1
        self.b = b
        self.corpus = [tokenize(d) for d in docs]
        self.n = len(self.corpus)
        self.df = Counter()
        for d in self.corpus:
            self.df.update(set(d))
        self.avgdl = (sum(map(len, self.corpus)) / self.n) if self.n else 1.0

    def score(self, i, query):
        doc = self.corpus[i]
        if not doc:
            return 0.0
        tf = Counter(doc)
        norm = 1 - self.b + self.b * len(doc) / self.avgdl if self.avgdl else 1.0
        s = 0.0
        for t in set(tokenize(query)):
            f = tf.get(t, 0)
            if f:
                s += idf(self.n, self.df[t]) * f * (self.k1 + 1) / (f + self.k1 * norm)
        return s

    def rank(self, query, limit=5):
        scored = [(self.score(i, query), i) for i in range(self.n)]
        return [(s, i) for s, i in sorted(scored, key=lambda x: -x[0])[:limit] if s > 0]


def freshness(text, valid_to, recorded, now, max_age_days=90):
    """HISTORICAL if the fact was closed or text says so; CURRENT if recent; else UNVERIFIED."""
    if valid_to is not None or _HIST.search(text):
        return HISTORICAL
    return CURRENT if (now - recorded) <= max_age_days * 86400 else UNVERIFIED
