#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if [ ! -f state/authority/ca.crt ]; then
    echo "Run 'sh scripts/setup.sh' first." >&2
    exit 1
fi
if [ -f state/incident/stolen/host.crt ]; then
    echo "Incident already introduced. To start over use 'sh scripts/reset.sh'." >&2
    exit 1
fi

# Replace the contractor identity for the lab incident.
# The authority remains offline; VPN peers receive only host credentials.
docker compose run --rm -T --entrypoint sh certtool -c '
    set -eu
    cp /state/peers/contractor/host.crt /state/backup/contractor/host.crt
    cp /state/peers/contractor/host.key /state/backup/contractor/host.key
    rm /state/peers/contractor/host.crt /state/peers/contractor/host.key
'
docker compose run --rm -T certtool sign \
    -ca-crt /state/authority/ca.crt -ca-key /state/authority/ca.key \
    -name contractor -ip 192.168.100.30/24 -groups contractor,employee \
    -out-crt /state/peers/contractor/host.crt \
    -out-key /state/peers/contractor/host.key

# Keep a copy of the credential used in the incident for the final task.
docker compose run --rm -T --entrypoint sh certtool -c '
    set -eu
    cp /state/peers/contractor/host.crt /state/incident/stolen/host.crt
    cp /state/peers/contractor/host.key /state/incident/stolen/host.key
    cp /state/authority/ca.crt /state/incident/stolen/ca.crt
    chmod 600 /state/incident/stolen/host.key
'
docker compose restart contractor

echo 'Incident active: contractor has received a new, signed certificate.'
echo 'Investigate the certificate and the protected service behavior.'
