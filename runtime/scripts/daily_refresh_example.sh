#!/usr/bin/env bash
# ESEMPIO DISABILITATO FINCHÉ L'UTENTE NON LO SCHEDULA ESPLICITAMENTE.
set -euo pipefail
: "${WORLDCORE_DB:?Impostare WORLDCORE_DB con il database esistente}"
cd "$(dirname "$0")/.."
# Richiede un accesso Internet funzionante e rispetto dei termini API.
python scripts/update_sources.py --provider gdelt --topic news --db "$WORLDCORE_DB" --max-items 20 --allow-network
python scripts/update_sources.py --provider gdelt --topic crypto --db "$WORLDCORE_DB" --max-items 20 --allow-network
python scripts/update_sources.py --provider crossref --topic medicine --db "$WORLDCORE_DB" --max-items 20 --allow-network
python scripts/update_sources.py --provider openalex --topic science --db "$WORLDCORE_DB" --max-items 20 --allow-network
python scripts/update_sources.py --provider github --topic 3d_printing --db "$WORLDCORE_DB" --max-items 20 --allow-network
