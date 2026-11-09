#!/usr/bin/env bash
set -euo pipefail
# Generate a private root CA and a Mac-LAN IP certificate for the optional iPhone UI.
# This script does NOT read or write to a ZKTeco device.
cd "${ZK_CLOCK_ROOT:-$HOME/zkteco-m5-lab/ZKTeco_set_time}"
LAN_IP="${1:-$(ipconfig getifaddr en0 2>/dev/null || true)}"
if [[ -z "$LAN_IP" ]]; then
  echo "LAN IP not found. Run: bash setup_phone_https.sh 192.168.x.x" >&2
  exit 1
fi
python3 - "$LAN_IP" <<'PY'
import ipaddress,sys
ip = ipaddress.ip_address(sys.argv[1])
lan = [ipaddress.ip_network(c) for c in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
if ip.version != 4 or not any(ip in block for block in lan):
    raise SystemExit('Use your private Mac LAN IPv4 address only.')
PY
umask 077
mkdir -p .secrets
if [[ -e .secrets/zkmanager-ca.crt || -e .secrets/zkmanager-ca.key || -e .secrets/zkmanager-server.key ]]; then
  echo "Existing certificates found: no overwrite. Check the IP in your certificate or archive old certificates intentionally." >&2
  exit 2
fi
CA_CONFIG="$(mktemp)"
trap 'rm -f "$CA_CONFIG"' EXIT
cat > "$CA_CONFIG" <<'EOF'
[req]
prompt = no
distinguished_name = dn
x509_extensions = v3_ca
[dn]
CN = ZK CLOCK Manager Private CA
[v3_ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
EOF
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 730 \
  -keyout .secrets/zkmanager-ca.key -out .secrets/zkmanager-ca.crt \
  -config "$CA_CONFIG" -extensions v3_ca >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout .secrets/zkmanager-server.key \
  -out .secrets/zkmanager-server.csr -subj "/CN=$LAN_IP" >/dev/null 2>&1
EXTFILE="$(mktemp)"
trap 'rm -f "$EXTFILE" "$CA_CONFIG"' EXIT
cat > "$EXTFILE" <<EOF
subjectAltName=IP:$LAN_IP
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -in .secrets/zkmanager-server.csr \
  -CA .secrets/zkmanager-ca.crt -CAkey .secrets/zkmanager-ca.key -CAcreateserial \
  -out .secrets/zkmanager-server.crt -days 365 -sha256 -extfile "$EXTFILE" >/dev/null 2>&1
rm -f .secrets/zkmanager-server.csr
chmod 600 .secrets/zkmanager-ca.key .secrets/zkmanager-server.key
chmod 644 .secrets/zkmanager-ca.crt .secrets/zkmanager-server.crt
printf '\nREADY — Mac LAN IP: %s\n' "$LAN_IP"
printf 'Transfer ONLY .secrets/zkmanager-ca.crt to iPhone and trust it there.\n'
printf 'Never send .key files or upload .secrets to GitHub.\n'
printf 'iPhone URL after starting serve-phone: https://%s:8769/\n' "$LAN_IP"
