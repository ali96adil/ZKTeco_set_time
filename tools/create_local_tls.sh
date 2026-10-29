#!/usr/bin/env bash
# Short-lived private CA and HTTPS server certificate for an authorized
# isolated/offline Mac control gateway. NEVER publish .secrets or private keys.
set -euo pipefail
cd "$(dirname "$0")/.."
MAC_IP="${1:-}"
if [[ -z "$MAC_IP" ]]; then
  MAC_IP="$(ipconfig getifaddr en0 || true)"
fi
if [[ ! "$MAC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: bash tools/create_local_tls.sh 10.1.x.x"
  exit 2
fi
if [[ -e .secrets/ca.key || -e .secrets/mac.key ]]; then
  echo "STOP: Existing private keys found. Inspect .secrets or rotate them manually."
  exit 2
fi

umask 077
mkdir -p .secrets
cat >.secrets/ca.cnf <<'EOF'
[ req ]
prompt = no
default_bits = 3072
distinguished_name = dn
x509_extensions = v3_ca
[ dn ]
CN = ZKTeco Local Admin CA (short lived)
[ v3_ca ]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
EOF
openssl req -new -x509 -sha256 -nodes -days 7 \
  -newkey rsa:3072 -config .secrets/ca.cnf \
  -keyout .secrets/ca.key -out .secrets/ca.crt
openssl req -new -sha256 -nodes -newkey rsa:3072 \
  -keyout .secrets/mac.key -out .secrets/mac.csr \
  -subj "/CN=$MAC_IP"

# Local Bonjour hostname survives DHCP IP changes; requires local mDNS routing.
BONJOUR_HOST=""
if command -v scutil >/dev/null 2>&1; then
  LOCAL_NAME="$(scutil --get LocalHostName 2>/dev/null || true)"
  if [[ "$LOCAL_NAME" =~ ^[A-Za-z0-9-]+$ ]]; then
    BONJOUR_HOST=",$(printf 'DNS:%s.local' "$LOCAL_NAME")"
  fi
fi
cat >.secrets/server.ext <<EOF
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = IP:$MAC_IP,IP:127.0.0.1,DNS:localhost$BONJOUR_HOST
EOF
openssl x509 -req -sha256 -days 7 \
  -in .secrets/mac.csr \
  -CA .secrets/ca.crt -CAkey .secrets/ca.key -CAcreateserial \
  -extfile .secrets/server.ext -out .secrets/mac.crt
chmod 600 .secrets/*.key
# CA is not needed again after signing the one server certificate. Delete the
# powerful CA private key to reduce the risk if the Mac is later compromised.
rm -f .secrets/ca.key .secrets/mac.csr .secrets/ca.srl
cp .secrets/ca.crt .secrets/ZKTeco_Local_CA.cer

echo
echo "Certificate bundle created for HTTPS IP: $MAC_IP"
if [[ -n "$BONJOUR_HOST" ]]; then echo "Stable Bonjour hostname: https://$LOCAL_NAME.local:8766/"; fi
echo "CA certificate to transfer to iPhone via AirDrop (public certificate only):"
echo "  .secrets/ZKTeco_Local_CA.cer"
echo "CA SHA256 fingerprint (verify before installing/trusting):"
openssl x509 -in .secrets/ca.crt -noout -fingerprint -sha256
echo "Server hostname/IP:"
openssl x509 -in .secrets/mac.crt -noout -ext subjectAltName
echo "The CA private key was deleted after signing. Never share .secrets/mac.key."
echo "IMPORTANT: Trusting any root CA on iPhone is powerful. Remove after test."
