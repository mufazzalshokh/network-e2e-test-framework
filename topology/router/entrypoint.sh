#!/bin/sh
set -eu
iptables -w 5 -P FORWARD DROP
iptables -w 5 -F FORWARD
iptables -w 5 -A FORWARD -m conntrack --ctstate INVALID -j DROP
iptables -w 5 -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -w 5 -A FORWARD -s 10.10.0.0/24 -d 10.20.0.10 -p tcp --dport 9090 -j DROP
case "${LAB_POLICY:-normal}" in
    normal)
        iptables -w 5 -A FORWARD -s 10.10.0.0/24 -d 10.20.0.10 -p tcp --dport 9000 -j ACCEPT
        ;;
    block-allowed)
        iptables -w 5 -A FORWARD -s 10.10.0.0/24 -d 10.20.0.10 -p tcp --dport 9000 -j DROP
        ;;
    *) echo 'Unknown LAB_POLICY' >&2; exit 2 ;;
esac
iptables -w 5 -A FORWARD -s 10.10.0.0/24 -d 10.20.0.10 -p tcp --dport 8080 -j ACCEPT
echo "Forwarding policy installed: ${LAB_POLICY:-normal}"
exec python -c 'import signal; signal.pause()'
