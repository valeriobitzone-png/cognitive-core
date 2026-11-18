"""Set separato per il riflesso v2: scritto dopo le regole e misurato UNA volta, senza ritoccare le regole.
Uso: PYTHONPATH=<core>/runtime/src python scripts/heldout_decision_v2.py"""
from cognitive_core.decision import Reflex

CASES = [
    ("buonanotte", "WAIT"), ("perfetto, grazie mille", "WAIT"),
    ("venerdì scade l'assicurazione della moto", "SUGGEST"),
    ("mi serve il certificato medico per la palestra entro fine mese", "SUGGEST"),
    ("ho promesso a Giulia di passare sabato", "SUGGEST"),
    ("domani compra il latte", "SUGGEST"),
    ("il condominio aspetta il pagamento della rata entro il 5", "SUGGEST"),
    ("il fornitore ha consegnato metà della merce", "SUGGEST"),
    ("l'app di fatturazione mi dà errore all'invio", "SUGGEST"),
    ("c'è una perdita d'acqua sotto il lavello", "SUGGEST"),
    ("Marco ci offre il 15% se ordiniamo entro il mese", "SUGGEST"),
    ("scrivi una mail al commercialista per fissare l'appuntamento", "REQUEST_APPROVAL"),
    ("rispondi a Luca che va bene", "REQUEST_APPROVAL"),
    ("ordina altre 10 cartucce per la stampante", "REQUEST_APPROVAL"),
    ("potresti cancellare l'abbonamento a Netflix?", "REQUEST_APPROVAL"),
    ("quanto costa il tagliando della Panda?", "STORE_ONLY"),
    ("chi è il referente di Rossi Impianti?", "STORE_ONLY"),
    ("Luca ha due figli e vive a Frascati", "STORE_ONLY"),
    ("mah", "WAIT"),
    ("oggi il mercato delle criptovalute è salito parecchio dopo la notizia", "STORE_ONLY"),
]
r = Reflex()
ok = 0
for text, want in CASES:
    got = r.classify({"kind": "message", "text": text}).action
    ok += got == want
    print(f"{'OK' if got == want else 'NO'}  {want:16s} {got:16s} {text}")
print(f"== {ok}/{len(CASES)}")
