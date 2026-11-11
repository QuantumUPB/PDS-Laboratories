#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Students decide which certificate group is appropriate.
groups="${1:-}"
if [ -z "$groups" ] || [ "$#" -ne 1 ]; then
    echo 'Usage: sh scripts/reissue-contractor.sh GROUP_NAME' >&2
    exit 2
fi
if [ ! -f state/incident/stolen/host.crt ]; then
    echo "First run 'sh scripts/introduce-incident.sh'." >&2
    exit 1
fi

# Generate a fresh keypair and certificate. The old, stolen credential is
# deliberately left valid for the revocation exercise.
docker compose run --rm -T --entrypoint sh certtool -c '
    rm -f /state/peers/contractor/host.crt /state/peers/contractor/host.key
'
docker compose run --rm -T certtool sign \
    -ca-crt /state/authority/ca.crt -ca-key /state/authority/ca.key \
    -name contractor -ip 192.168.100.30/24 -groups "$groups" \
    -out-crt /state/peers/contractor/host.crt \
    -out-key /state/peers/contractor/host.key
docker compose restart contractor

echo 'New contractor identity issued. Check its group membership and access.'
