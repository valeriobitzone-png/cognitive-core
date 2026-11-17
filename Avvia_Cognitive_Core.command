#!/bin/sh
# Optional Mac launcher; Core and its data remain ordinary portable Python/files.
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
PYTHON_BIN=
for candidate in "${COGNITIVE_CORE_PYTHON:-}" python3.12 python3.11 python3; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys;sys.exit(sys.version_info<(3,11))' 2>/dev/null; then
        PYTHON_BIN=$candidate
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo 'Serve Python 3.11 o successivo. Imposta COGNITIVE_CORE_PYTHON al suo percorso.'
    exit 1
fi
CORE_HOME=${COGNITIVE_CORE_HOME:-"$APP_DIR/../dati-programma"}
export PYTHONPATH="$APP_DIR/runtime/src"
exec "$PYTHON_BIN" -B -m cognitive_core --home "$CORE_HOME" --namespace unified console
