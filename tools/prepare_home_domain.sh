#!/usr/bin/env bash
# Prepare a hostname-based HTTPS certificate. Never silently overwrite trust.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST="$(scutil --get LocalHostName 2>/dev/null || true)"
[[ "$HOST" =~ ^[A-Za-z0-9-]+$ ]] || {
  echo "STOP: Mac Bonjour hostname unavailable"; exit 2;
}
URL="https://$HOST.local:8766/"
IP="$(ipconfig getifaddr en0 || true)"
echo "Stable local URL: $URL"
echo "Current IP: $IP"
echo "Only works while iPhone can reach Mac over local Bonjour/mDNS."
if [[ -f .secrets/mac.crt ]]; then
  SAN="$(openssl x509 -in .secrets/mac.crt -noout -ext subjectAltName 2>/dev/null)"
  if printf '%s' "$SAN" | grep -Fq "DNS:$HOST.local"; then
    echo "HTTPS certificate already includes hostname; NO CHANGE NEEDED."
    exit 0
  fi
fi
if [[ "\${1:-}" != "--rotate" ]]; then
  echo
  echo "EXISTING certificate does not include the hostname."
  echo "No changes made. To rotate certificates deliberately:"
  echo "  bash tools/prepare_home_domain.sh --rotate"
  echo "After rotation, AirDrop the NEW CA certificate and trust it on iPhone."
  echo "Stop the old gateway first, and remove trust of the OLD temporary CA."
  exit 3
fi
[[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "No current Wi-Fi IP; cannot generate complete cert"; exit 4;
}
mkdir -p .secrets
umask 077
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP=".secrets/tls-backups/$STAMP"
mkdir -p "$BACKUP"
for FILE in ca.cnf ca.crt mac.crt mac.key mac.csr mac.srl \
  ca.srl server.ext ZKTeco_Local_CA.cer; do
  if [[ -f ".secrets/$FILE" ]]; then
    mv ".secrets/$FILE" "$BACKUP/"
  fi
done
echo "Previous trust materials preserved inside $BACKUP"
bash tools/create_local_tls.sh "$IP"
echo
echo "Replace the old temporary CA profile on the iPhone with:"
echo "  .secrets/ZKTeco_Local_CA.cer"
echo "Do not transfer any private .key files. Validate HTTPS without warnings."
