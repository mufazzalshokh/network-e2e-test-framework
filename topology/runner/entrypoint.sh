#!/bin/sh
set -eu
ip route replace 10.20.0.0/24 via 10.10.0.254
exec setpriv --reuid=10001 --regid=10001 --clear-groups \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs "$@"
