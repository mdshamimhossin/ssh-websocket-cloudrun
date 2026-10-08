#!/bin/bash
set -euo pipefail
: "${SSH_PASSWORD:?Set SSH_PASSWORD using Secret Manager}"
: "${SSH_HOST_KEY:?Set SSH_HOST_KEY using Secret Manager}"
printf 'tunneluser:%s\n' "$SSH_PASSWORD" | chpasswd
umask 077
printf '%s\n' "$SSH_HOST_KEY" > /run/ssh_host_ed25519_key
unset SSH_PASSWORD SSH_HOST_KEY
mkdir -p /run/sshd
/usr/sbin/sshd -t -f /app/sshd_config
/usr/sbin/sshd -D -e -f /app/sshd_config &
sshd_pid=$!
python /app/server.py &
bridge_pid=$!
cleanup() { kill "$bridge_pid" "$sshd_pid" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 0' TERM INT
set +e
wait -n "$sshd_pid" "$bridge_pid"
exit 1
