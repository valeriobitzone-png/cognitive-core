# Cognitive Core — documentazione su AMBRO

Questo è il punto di ingresso per rapporti, studi, test e atlante delle capacità. I documenti storici conservano contenuti e riferimenti originali.

## Rapporti

- [Correzioni più recenti e test](correzioni-audit-20261112/REPORT_CORREZIONI_IT.md)
- [Atlante delle capacità](atlante-capacita-20261112/LEGGIMI_IT.md)
- [Audit della memoria e del ciclo](audit-core-20261112/AUDIT_IT.md)
- [Unificazione operativa](unificazione-2026-11-10/REPORT_UNIFICAZIONE_IT.md)
- [Modelli locali: ricerca fase 2](ricerca-decisionale-fase2-20261111/REPORT_FASE2_IT.md)
- [Esperimenti](esperimenti-2026-11-11/REPORT_ESPERIMENTI_IT.md)
- [Correzioni iniziali](correzioni-2026-11-10/CORREZIONI_COMPLETATE_IT.md)
- [Audit iniziale](audit-2026-11-10/AUDIT_TECNICO_COGNITIVE_CORE_IT.md)

## Organizzazione

| Cartella | Funzione |
|---|---|
| `../cognitive-core/` | Repository operativo canonico; sviluppare qui |
| `../realtest/` | Dati sperimentali originali e runner; non modificati dall’accorpamento |
| `../evidence/` | Archivio evidenze preesistente |
| Questa cartella | Rapporti, risultati e snapshot dei lavori |
| `../cognitive-core/validation/` | Tracce delle installazioni, backup e rollback; conservate |

Le sottocartelle `runtime/` dentro gli studi sono copie storiche per riprodurre le prove, non altri repository operativi da sviluppare. I pesi archiviati non vengono caricati automaticamente.

## Stato del trasferimento

- `atlante-capacita-20261112`: archived_verified_and_linked; 51 file.
- `audit-2026-11-10`: archived_verified_and_linked; 57 file.
- `audit-core-20261112`: archived_verified_and_linked; 495 file.
- `correzioni-2026-11-10`: archived_verified_and_linked; 400 file.
- `correzioni-audit-20261112`: archived_verified_and_linked; 555 file.
- `curiosita-integrazione-20261111`: archived_verified_and_linked; 359 file.
- `decisionale-locale-2026-11-10`: archived_verified_and_linked; 602 file.
- `esperimenti-2026-11-11`: archived_verified_and_linked; 106 file.
- `ricerca-decisionale-fase2-20261111`: archived_verified_and_linked; 551 file.
- `unificazione-2026-11-10`: archived_verified_and_linked; 892 file.

I vecchi percorsi locali delle cartelle completate puntano a questo archivio e richiedono AMBRO montato. Backup locale conservato: `/Users/ambrogio/Documents/ChatGPT/COGNITIVE CORE/.backup-accorpamento-20261113`. Nessuna cancellazione automatica.

Manifest e verifiche: [stato](consolidamento-20261113.json), [inventario iniziale con hash](consolidamento-20261112.json). Per recuperare la versione locale precedente, conservare prima eventuali modifiche successive su AMBRO, rimuovere solo il collegamento interessato e riportare la cartella dal backup alla posizione iniziale.

Accorpamento completato: **10 cartelle, 4068 file verificati**. Anche fase 2 e unificazione sono presenti integralmente su AMBRO, inclusi i pesi prima disponibili soltanto su iCloud. [Rapporto di completamento](REPORT_ACCORPAMENTO_20261113_IT.md).

## Apporto cognitivo dal pacchetto Assistente Personale

- [Contenuti cognitivi recuperati e riconciliazione](apporto-cognitivo-assistente-20261113/LEGGIMI_IT.md)
- [Pacchetto senza grafica](apporto-cognitivo-assistente-20261113/APPORTO_COGNITIVO_SENZA_GRAFICA.zip)

Prototipi di riferimento non attivati; integrazione tramite il bridge esistente provata su database temporanei. Nessuna sostituzione del Core operativo.
