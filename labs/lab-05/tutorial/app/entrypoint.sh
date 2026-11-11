#!/bin/sh
set -eu

if [ "${1:-nebula}" = "fileserver" ]; then
    nebula -config /etc/nebula/config.yml &
    nebula_pid=$!
    # The service binds to the VPN address, NOT 0.0.0.0. Underlay access
    # must not bypass Nebula's identity-aware firewall.
    count=0
    until ip -4 addr show dev nebula1 2>/dev/null | grep -q '192.168.100.20/24'; do
        if ! kill -0 "$nebula_pid" 2>/dev/null; then
            echo "Nebula exited before the overlay interface was ready" >&2
            exit 1
        fi
        count=$((count + 1))
        if [ "$count" -ge 30 ]; then
            echo "Timed out waiting for the Nebula overlay interface" >&2
            exit 1
        fi
        sleep 1
    done
    exec python3 -m http.server 8080 --bind 192.168.100.20 --directory /srv/files
fi

exec nebula -config /etc/nebula/config.yml
