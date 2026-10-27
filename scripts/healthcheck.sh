#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
failed=0
for unit in cups avahi-daemon smbd wsdd; do
    if ! systemctl is-active "$unit.service"; then failed=1; fi
done
# A completed oneshot must be inactive so that the next USB event can run it again.
systemctl is-active scpprint-usb-heal.service || true
if [[ $(systemctl show scpprint-usb-heal.service -p Result --value) != success ]] ||
   [[ $(systemctl show scpprint-usb-heal.service -p ExecMainStatus --value) != 0 ]]; then
    failed=1
fi
for unit in scpprint-agent scpprint-raw; do
    if systemctl is-enabled --quiet "$unit.service" 2>/dev/null; then
        if ! systemctl is-active "$unit.service"; then failed=1; fi
    fi
done
if systemctl is-enabled --quiet scpprint-agent.service 2>/dev/null; then
    if ! systemctl is-active scpprint-queue-control.socket; then failed=1; fi
fi
if ! lpstat -h localhost -r; then failed=1; fi
lpstat -h localhost -p -d || true
exit "$failed"
