#!/usr/bin/env bash
set -euo pipefail
# Source-only upgrade. Never modify device records, firmware or existing database.
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${1:-$HOME/zkteco-m5-lab/ZKTeco_set_time}"
if [[ ! -d "$PROJECT/tools" ]]; then
  echo "Project tools/ directory not found: $PROJECT" >&2
  exit 1
fi
cd "$PROJECT"
mkdir -p local/source_backups
chmod 700 local/source_backups || true
STAMP="$(date +%Y%m%d_%H%M%S)"
FILES=(zkclock_manager.py zkclock_manager_reports.py test_zkclock_manager.py test_zkclock_manager_v2.py test_zkclock_manager_v3.py)
for file in "${FILES[@]}"; do
  if [[ ! -f "$SOURCE_DIR/$file" ]]; then
    echo "Missing package source: $file" >&2
    exit 1
  fi
done
if [[ "$SOURCE_DIR" != "$PWD/tools" ]]; then
  for file in "${FILES[@]}"; do
    if [[ -f "tools/$file" ]]; then
      cp -p "tools/$file" "local/source_backups/${file}.${STAMP}.bak"
    fi
    cp "$SOURCE_DIR/$file" "tools/$file"
  done
else
  echo "Code already lives in project tools/: running offline tests without copying."
fi
PYTHONPATH=tools python3 tools/test_zkclock_manager.py
PYTHONPATH=tools python3 tools/test_zkclock_manager_v2.py
PYTHONPATH=tools python3 tools/test_zkclock_manager_v3.py
printf '\nSUCCESS: ZK CLOCK Manager v0.3 installed. Existing local archive preserved.\n'
printf 'Stop old server with Control+C. Then run from repo root:\n'
printf '  python3 tools/zkclock_manager.py backup\n'
printf '  python3 tools/zkclock_manager.py serve --port 8768\n'
printf 'Optional foreground polling: python3 tools/zkclock_manager.py watch --interval-minutes 30\n'
