#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if [ -e state/authority/ca.crt ] || [ -e state/authority/ca.key ]; then
    echo "Existing lab PKI detected. Use 'sh scripts/reset.sh' to start over (deletes all lab keys)." >&2
    exit 1
fi

mkdir -p state/authority state/configs state/peers/lighthouse \
    state/peers/employee state/peers/contractor state/peers/fileserver \
    state/backup/contractor state/incident/stolen
cp configs/*.yml state/configs/

echo "Building the local Nebula tooling image..."
docker compose build certtool

echo "Generating a NEW local CA (its private key is never mounted in a VPN peer)..."
docker compose run --rm -T certtool ca \
    -name 'PDS Lab 05 CA' \
    -out-crt /state/authority/ca.crt \
    -out-key /state/authority/ca.key

sign_host() {
    node="$1"
    address="$2"
    groups="$3"
    docker compose run --rm -T certtool sign \
        -ca-crt /state/authority/ca.crt \
        -ca-key /state/authority/ca.key \
        -name "$node" -ip "$address/24" -groups "$groups" \
        -out-crt "/state/peers/$node/host.crt" \
        -out-key "/state/peers/$node/host.key"
}

sign_host lighthouse 192.168.100.1 infrastructure
sign_host employee   192.168.100.10 employee
sign_host contractor 192.168.100.30 contractor
sign_host fileserver 192.168.100.20 fileserver

docker compose run --rm -T --entrypoint sh certtool -c '
    set -eu
    for node in lighthouse employee contractor fileserver; do
        cp /state/authority/ca.crt "/state/peers/$node/ca.crt"
        chmod 600 "/state/peers/$node/host.key"
    done
    chmod 600 /state/authority/ca.key
'

echo "Starting the four normal peers..."
docker compose up -d lighthouse employee contractor fileserver
cat <<'INFO'

Ready for the lab. Allow a few seconds for the overlay to form, then run:
  sh scripts/check.sh baseline

The generated CA private key is in state/authority/ca.key (never commit state/).
INFO
