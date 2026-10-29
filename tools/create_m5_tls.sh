#!/usr/bin/env bash
# Creates a per-device TLS CA and trusted zkclock.local server leaf.
# Never commits keys. Existing files are never silently overwritten.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .secrets
if [ -e .secrets/m5-ca.key ] || [ -e .secrets/m5-server.key ] || [ -e include/m5_tls_local.h ]; then
  echo "STOP: existing M5 TLS material; refusing silent overwrite."
  echo "Back up old materials and revoke old CA trust before rotating deliberately."
  exit 3
fi
umask 077
openssl req -new -x509 -nodes -newkey rsa:2048 -sha256 -days 1825 \
  -subj "/CN=ZK Clock Local Root" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -keyout .secrets/m5-ca.key -out .secrets/m5-ca.crt
openssl req -new -nodes -newkey rsa:2048 \
  -subj "/CN=zkclock.local" \
  -keyout .secrets/m5-server.key -out .secrets/m5-server.csr
cat > .secrets/m5-ext.cnf <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:zkclock.local,IP:192.168.4.1
EOF
openssl x509 -req -sha256 -days 365 \
  -in .secrets/m5-server.csr -CA .secrets/m5-ca.crt \
  -CAkey .secrets/m5-ca.key -CAcreateserial \
  -extfile .secrets/m5-ext.cnf -out .secrets/m5-server.crt
openssl rsa -in .secrets/m5-server.key -outform DER -out .secrets/m5-server-key.der >/dev/null 2>&1
openssl x509 -in .secrets/m5-server.crt -outform DER -out .secrets/m5-server-cert.der
openssl x509 -in .secrets/m5-ca.crt -outform DER -out .secrets/m5-ca.cer
openssl verify -CAfile .secrets/m5-ca.crt .secrets/m5-server.crt
openssl x509 -in .secrets/m5-server.crt -noout -ext subjectAltName
python3 - <<'PY'
from pathlib import Path
def array(name, data):
    parts = [",".join("0x%02x"%v for v in data[i:i+16]) for i in range(0,len(data),16)]
    return "static const uint8_t %s[] = {\n%s\n};\n" % (name, ",\n".join(parts))
path=Path("include/m5_tls_local.h")
body = ("#pragma once\n#include <stdint.h>\n// LOCAL PRIVATE KEY: ignore in Git, never share this generated header.\n"
       + array("kM5TlsServerKey",Path(".secrets/m5-server-key.der").read_bytes())
       + array("kM5TlsServerCert",Path(".secrets/m5-server-cert.der").read_bytes()))
path.write_text(body)
path.chmod(0o600)
print("TLS header written locally; bytes:",len(body))
PY
echo "Install ONLY .secrets/m5-ca.cer onto the iPhone; never send .key or m5_tls_local.h."
echo "iPhone: Settings > General > About > Certificate Trust Settings > enable trust."
echo "Final address: https://zkclock.local/"
