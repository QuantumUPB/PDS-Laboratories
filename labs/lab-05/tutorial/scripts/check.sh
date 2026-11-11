#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

mode="${1:-baseline}"
overlay='http://192.168.100.20:8080/report.txt'
underlay='http://172.28.66.13:8080/report.txt'

access() {
    docker compose --profile incident exec -T "$1" curl -fsS \
        --connect-timeout 2 --max-time 5 -o /dev/null "$2" >/dev/null 2>&1
}

allow() {
    if access "$1" "$2"; then
        printf 'PASS  %s can reach %s\n' "$1" "$2"
    else
        printf 'FAIL  %s cannot reach %s\n' "$1" "$2" >&2
        exit 1
    fi
}

deny() {
    if access "$1" "$2"; then
        printf 'FAIL  %s can reach %s (should be denied)\n' "$1" "$2" >&2
        exit 1
    else
        printf 'PASS  %s is denied access to %s\n' "$1" "$2"
    fi
}

# A failed request is not evidence of a firewall rule if the HTTP server
# itself is down. Test locally before checking remote access decisions.
ready=0
attempt=0
while [ "$attempt" -lt 12 ]; do
    if docker compose exec -T fileserver curl -fsS --max-time 2 \
        -o /dev/null "$overlay" >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo 'FAIL  file server is not running on its Nebula address; inspect docker compose logs fileserver' >&2
    exit 1
fi

case "$mode" in
    network)
        if docker compose exec -T employee ping -c 1 -W 2 192.168.100.20 >/dev/null 2>&1; then
            echo 'PASS  employee reaches the file server over Nebula (ICMP)'
        else
            echo 'FAIL  employee cannot ping the Nebula file server' >&2
            exit 1
        fi
        deny employee "$overlay"
        deny contractor "$overlay"
        ;;
    baseline|reissued)
        allow employee "$overlay"
        deny contractor "$overlay"
        deny employee "$underlay"
        if [ "$mode" = reissued ]; then
            # Check the actual certificate, not merely whether HTTP happens to fail.
            groups=$(docker compose run --rm -T --entrypoint sh certtool -c \
                "nebula-cert print -json -path /state/peers/contractor/host.crt | python3 -c 'import json,sys; c=json.load(sys.stdin); c=c[0] if isinstance(c,list) else c; print(\",\".join(sorted(c[\"details\"].get(\"groups\") or [])))'")
            if [ "$groups" != contractor ]; then
                printf 'FAIL  contractor certificate has the wrong groups: %s\n' "$groups" >&2
                exit 1
            fi
            echo 'PASS  contractor certificate has only the contractor group'
        fi
        ;;
    incident)
        allow employee "$overlay"
        allow contractor "$overlay"
        deny employee "$underlay"
        ;;
    stolen)
        allow employee "$overlay"
        allow attacker "$overlay"
        ;;
    revoked)
        allow employee "$overlay"
        deny attacker "$overlay"
        ;;
    *)
        echo 'Usage: sh scripts/check.sh {network|baseline|incident|reissued|stolen|revoked}' >&2
        exit 2
        ;;
esac
