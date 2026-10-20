#!/bin/sh
# BusyBox udhcpc invokes this file for deconfig, bound and renew events.
# This is a deliberately small script for the fixed /24 laboratory network.
set -eu

case "$1" in
    deconfig)
        ip -4 address flush dev "$interface"
        ip link set dev "$interface" up
        ;;
    bound|renew)
        ip -4 address flush dev "$interface"
        ip -4 address add "$ip/24" dev "$interface"
        ip link set dev "$interface" up

        if [ -n "${router:-}" ]; then
            set -- $router
            ip -4 route replace default via "$1" dev "$interface"
        fi

        printf '%s\n' "${dns:-}" > /tmp/dhcp-dns-servers
        if [ -n "${dns:-}" ]; then
            : > /etc/resolv.conf
            for nameserver in $dns; do
                printf 'nameserver %s\n' "$nameserver" >> /etc/resolv.conf
            done
        fi

        printf 'DHCP: address=%s subnet=%s router=%s dns=%s\n' \
            "$ip" "${subnet:-unknown}" "${router:-none}" "${dns:-none}"
        ;;
esac
