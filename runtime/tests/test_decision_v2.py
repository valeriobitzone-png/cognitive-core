"""Cuore v2 · riflesso decisionale sui messaggi. Scritti prima della modifica.
Con 1.4.0rc5 «paga la bolletta domani» → WAIT e ogni altro messaggio → STORE_ONLY."""
import pytest

from cognitive_core.decision import Reflex

R = Reflex()


def act(text, kind="message"):
    return R.classify({"kind": kind, "text": text})


@pytest.mark.parametrize("text,expected", [
    # saluti e conferme: nessun lavoro (invariato)
    ("ciao", "WAIT"), ("Grazie!", "WAIT"), ("ok", "WAIT"), ("va bene", "WAIT"),
    # impegni e scadenze: non vanno mai persi
    ("paga la bolletta domani", "SUGGEST"),
    ("devo chiamare il commercialista entro venerdì", "SUGGEST"),
    ("ricordami di rinnovare il passaporto", "SUGGEST"),
    ("la fattura di Rossi scade il 20", "SUGGEST"),
    ("dobbiamo consegnare il preventivo a Luca lunedì alle 10", "SUGGEST"),
    ("I need to renew the car insurance by Friday", "SUGGEST"),
    # problemi e discrepanze da seguire
    ("il cliente Ferri lamenta crepe nel pavimento", "SUGGEST"),
    ("la consegna dei pannelli è in ritardo di quattro giorni", "SUGGEST"),
    ("la caldaia non funziona", "SUGGEST"),
    # azioni esterne chieste all'agente: sempre approvazione
    ("manda una mail a Luca con il preventivo", "REQUEST_APPROVAL"),
    ("puoi prenotare il ristorante per sabato?", "REQUEST_APPROVAL"),
    ("pubblica il post su Instagram", "REQUEST_APPROVAL"),
    ("cancella tutti i file della cartella fatture", "REQUEST_APPROVAL"),
    # domande e note
    ("quanto ho speso di luce quest'anno?", "STORE_ONLY"),
    ("Luca preferisce essere chiamato di mattina", "STORE_ONLY"),
    ("bella giornata", "WAIT"),
])
def test_message_reflex(text, expected):
    assert act(text).action == expected, text


def test_priorities_follow_urgency_and_kind():
    assert act("paga la bolletta domani").priority > act("ricordami di rinnovare il passaporto").priority
    assert act("la caldaia non funziona").priority >= 0.6
    assert act("Luca mi propone uno sconto del 10% sull'ordine").priority < act("paga la bolletta domani").priority


def test_owner_task_with_deadline_is_not_an_agent_action():
    d = act("paga la bolletta domani")
    assert d.action == "SUGGEST" and not d.requires_approval and "promemoria" in d.rationale


def test_external_action_requires_approval_flag():
    d = act("manda una mail a Luca")
    assert d.requires_approval is True


def test_structured_kinds_unchanged():
    assert act("x", kind="session_end").action == "PREPARE_SILENTLY"
    assert act("spend money", kind="external_action").action == "REQUEST_APPROVAL"
