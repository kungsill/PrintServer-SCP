#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C
export NEEDRESTART_MODE=a
export APT_LISTCHANGES_FRONTEND=none
export UCF_FORCE_CONFFOLD=1

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
API=1
UPGRADE=1
RAW_QUEUE=''
LISTEN=0.0.0.0
ADMIN_USER=${SUDO_USER:-}
PRINTER_NAME=''
DEVICE_URI=''
DRIVER=''
usage() {
    cat <<'HELP'
Usage: sudo bash setup-scpprint-armbian.sh [options]
  --admin-user USER     Linux account for CUPS administration (default: SUDO_USER)
  --listen IPv4        Agent/RAW bind address (default: 0.0.0.0)
  --raw-queue QUEUE    Also enable TCP 9100 for an existing/provisioned queue
  --printer-name NAME --device-uri URI --driver MODEL
                      Provision one queue without using the CUPS UI
  --skip-upgrade       Skip apt-get upgrade, still update index/install dependencies
  --without-agent     Install printing services without Dashboard/API
  --with-api          Compatibility option; Agent is enabled by default
HELP
}
while (($#)); do
    case "$1" in
        --with-api) API=1; shift ;;
        --without-agent) API=0; shift ;;
        --skip-upgrade) UPGRADE=0; shift ;;
        --raw-queue|--listen|--admin-user|--printer-name|--device-uri|--driver)
            (($# >= 2)) || { usage; exit 2; }
            case "$1" in
                --raw-queue) RAW_QUEUE=$2 ;;
                --listen) LISTEN=$2 ;;
                --admin-user) ADMIN_USER=$2 ;;
                --printer-name) PRINTER_NAME=$2 ;;
                --device-uri) DEVICE_URI=$2 ;;
                --driver) DRIVER=$2 ;;
            esac
            shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage; exit 2 ;;
    esac
done
[[ $EUID -eq 0 ]] || { echo 'Run with sudo or as root.' >&2; exit 1; }
# ป้องกันการติดตั้งซ้อนกัน เก็บ log โดยไม่พิมพ์ token และไม่ reboot เอง
umask 077
exec 9>/run/lock/scpprint-setup.lock
flock -n 9 || { echo 'Another SCPPrint setup is running.' >&2; exit 1; }
touch /var/log/scpprint-setup.log
chmod 600 /var/log/scpprint-setup.log
exec > >(tee -a /var/log/scpprint-setup.log) 2>&1
trap 'echo "Setup failed at line $LINENO. Check /var/log/scpprint-setup.log; no automatic reboot was performed." >&2' ERR
# ต้องคัดลอกโปรเจกต์ทั้งโฟลเดอร์มาด้วย ตรวจไฟล์ก่อนเปลี่ยนระบบ
for source_file in scripts/configure_cups.py scripts/usb_heal.py scripts/healthcheck.sh config/smb.conf config/99-scpprint-usb.rules config/scpprint-tmpfiles.conf systemd/scpprint-usb-heal.service; do
    [[ -f $ROOT_DIR/$source_file ]] || { echo "Missing project file: $source_file" >&2; exit 1; }
done
if ((API)); then
    for source_file in agent/common.py agent/api.py agent/queue_control.py agent/static/index.html agent/static/dashboard.css agent/static/dashboard.js systemd/scpprint-agent.service systemd/scpprint-queue-control.socket systemd/scpprint-queue-control@.service; do
        [[ -f $ROOT_DIR/$source_file ]] || { echo "Missing project file: $source_file" >&2; exit 1; }
    done
fi
if [[ -n $RAW_QUEUE ]]; then
    for source_file in agent/common.py agent/raw.py systemd/scpprint-raw.service; do
        [[ -f $ROOT_DIR/$source_file ]] || exit 1
    done
fi
[[ -r /etc/os-release ]] || { echo 'Linux with systemd required.' >&2; exit 1; }
source /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
    debian:12|ubuntu:24.04) ;;
    *) echo 'Supported targets: Armbian Debian 12 / Ubuntu 24.04.' >&2; exit 1 ;;
esac
[[ $(dpkg --print-architecture) == arm64 ]] || { echo 'ARM64 target required.' >&2; exit 1; }
[[ -d /run/systemd/system ]] || { echo 'systemd must be running.' >&2; exit 1; }
if [[ -z $ADMIN_USER ]]; then
    echo 'Specify --admin-user USER when running directly as root.' >&2; exit 2
fi
id -- "$ADMIN_USER" >/dev/null
[[ $ADMIN_USER != root ]] || { echo 'Use a non-root admin account.' >&2; exit 2; }
[[ -z $RAW_QUEUE || $RAW_QUEUE =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,126}$ ]] || exit 2
if [[ -n $PRINTER_NAME || -n $DEVICE_URI || -n $DRIVER ]]; then
    [[ $PRINTER_NAME =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,126}$ && -n $DEVICE_URI && -n $DRIVER ]] || { echo 'Supply all three printer provisioning options.' >&2; exit 2; }
    [[ $DEVICE_URI =~ ^(usb://|hp:/usb/|ipp://|ipps://|socket://|lpd://) ]] || { echo 'Unsupported printer URI.' >&2; exit 2; }
    [[ $DRIVER != -* ]] || exit 2
    if [[ $DRIVER == everywhere && ! $DEVICE_URI =~ ^ipps?:// ]]; then
        echo 'The everywhere driver requires an IPP/IPPS URI.' >&2; exit 2
    fi
fi
# ตรวจ IPv4 ก่อน apt เพื่อไม่เริ่มอัปเดตแพ็กเกจเมื่อ input ผิด
[[ $LISTEN =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || { echo 'Invalid IPv4 bind address.' >&2; exit 2; }
IFS=. read -r -a ip_octets <<< "$LISTEN"
for octet in "${ip_octets[@]}"; do
    ((10#$octet <= 255)) || { echo 'Invalid IPv4 bind address.' >&2; exit 2; }
done

apt-get update
if ((UPGRADE)); then
    # เคารพ apt-mark hold ของ kernel/bootloader เดิม ไม่ทำ dist-upgrade
    apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade -y
fi
apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install -y cups cups-client cups-bsd cups-filters ghostscript avahi-daemon avahi-utils samba wsdd python3 usbutils curl
drivers=(printer-driver-gutenprint hplip printer-driver-brlaser printer-driver-splix foomatic-db-engine openprinting-ppds)
compressed_candidate=$(apt-cache policy foomatic-db-compressed-ppds | awk '/Candidate:/ {print $2}')
if [[ -n $compressed_candidate && $compressed_candidate != '(none)' ]]; then
    drivers+=(foomatic-db-compressed-ppds)
else
    drivers+=(foomatic-db)
fi
available=()
missing=()
for package in "${drivers[@]}"; do
    candidate=$(apt-cache policy "$package" | awk '/Candidate:/ {print $2}')
    if [[ -n $candidate && $candidate != '(none)' ]]; then
        available+=("$package")
    else
        missing+=("$package")
    fi
done
if ((${#available[@]})); then apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install -y "${available[@]}"; fi
if ((${#missing[@]})); then
    printf 'Unavailable driver package (check enabled repositories): %s\n' "${missing[@]}" >&2
    echo 'Enable required repositories (Ubuntu: Universe), then rerun setup.' >&2
    exit 1
fi
if ((API)); then apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install -y python3-fastapi python3-uvicorn; fi

BACKUP_DIR=$(mktemp -d /var/backups/scpprint-XXXXXXXX)
chmod 700 "$BACKUP_DIR"
backup() {
    if [[ -e $1 ]]; then
        mkdir -p "$BACKUP_DIR$(dirname "$1")"
        cp -a -- "$1" "$BACKUP_DIR$1"
    fi
}
deploy() {
    backup "$2"
    install -D -m "${3:-644}" "$ROOT_DIR/$1" "$2"
}
echo "Configuration backups: $BACKUP_DIR"
usermod -aG lpadmin -- "$ADMIN_USER"
getent passwd scpprint >/dev/null || useradd --system --user-group --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin scpprint
install -d -m 755 /opt/scpprint
install -d -m 750 -o root -g scpprint /etc/scpprint
install -d -m 700 -o scpprint -g scpprint /var/spool/scpprint
deploy config/scpprint-tmpfiles.conf /etc/tmpfiles.d/scpprint.conf

backup /etc/cups/cupsd.conf
python3 "$ROOT_DIR/scripts/configure_cups.py" /etc/cups/cupsd.conf
if ! cupsd -t; then
    cp -a "$BACKUP_DIR/etc/cups/cupsd.conf" /etc/cups/cupsd.conf
    echo 'Invalid CUPS configuration; original restored.' >&2
    exit 1
fi
deploy config/smb.conf /etc/samba/smb.conf
if ! testparm -s >/dev/null; then
    cp -a "$BACKUP_DIR/etc/samba/smb.conf" /etc/samba/smb.conf
    echo 'Invalid Samba configuration; original restored.' >&2
    exit 1
fi
install -d -m 1777 /var/spool/samba
deploy scripts/usb_heal.py /opt/scpprint/usb_heal.py 755
deploy config/99-scpprint-usb.rules /etc/udev/rules.d/99-scpprint-usb.rules
deploy systemd/scpprint-usb-heal.service /etc/systemd/system/scpprint-usb-heal.service
deploy scripts/healthcheck.sh /usr/local/sbin/scpprint-healthcheck 755

if ((API)); then
    deploy agent/common.py /opt/scpprint/common.py
    deploy agent/api.py /opt/scpprint/api.py
    deploy agent/queue_control.py /opt/scpprint/queue_control.py
    for static_file in index.html dashboard.css dashboard.js; do
        deploy "agent/static/$static_file" "/opt/scpprint/static/$static_file"
    done
    deploy systemd/scpprint-agent.service /etc/systemd/system/scpprint-agent.service
    deploy systemd/scpprint-queue-control.socket /etc/systemd/system/scpprint-queue-control.socket
    deploy systemd/scpprint-queue-control@.service /etc/systemd/system/scpprint-queue-control@.service
    backup /etc/scpprint/api.env
    backup /etc/scpprint/api-bind.env
    python3 - "$LISTEN" <<'PY'
from pathlib import Path
import secrets, sys
p = Path('/etc/scpprint/api.env')
if not p.exists():
    p.write_text('SCPPRINT_TOKEN=' + secrets.token_urlsafe(32) + '\nSCPPRINT_MAX_BYTES=33554432\n')
bind = Path('/etc/scpprint/api-bind.env')
# เก็บ bind address แยกจาก token เพื่อไม่เปลี่ยน token ทุกครั้งที่ติดตั้งซ้ำ
bind.write_text('SCPPRINT_LISTEN=' + sys.argv[1] + '\n')
PY
    chmod 640 /etc/scpprint/api.env /etc/scpprint/api-bind.env
    chown root:scpprint /etc/scpprint/api.env /etc/scpprint/api-bind.env
fi
systemctl enable --now cups.service
if [[ -n $PRINTER_NAME ]]; then
    # ไม่ eval URI/ชื่อไดรเวอร์จากผู้ใช้ แยก argument ทุกตัว
    lpadmin -h /run/cups/cups.sock -p "$PRINTER_NAME" -E -v "$DEVICE_URI" -m "$DRIVER" -o printer-is-shared=true -o printer-error-policy=retry-job
fi
if [[ -n $RAW_QUEUE ]]; then
    systemctl enable --now cups.service
    lpstat -h localhost -p "$RAW_QUEUE" >/dev/null
    deploy agent/common.py /opt/scpprint/common.py
    deploy agent/raw.py /opt/scpprint/raw.py
    deploy systemd/scpprint-raw.service /etc/systemd/system/scpprint-raw.service
    backup /etc/scpprint/raw.env
    printf 'SCPPRINT_QUEUE=%s\nSCPPRINT_LISTEN=%s\nSCPPRINT_MAX_BYTES=33554432\n' "$RAW_QUEUE" "$LISTEN" > /etc/scpprint/raw.env
    chmod 640 /etc/scpprint/raw.env
    chown root:scpprint /etc/scpprint/raw.env
fi
systemctl daemon-reload
udevadm control --reload-rules
services=(cups.service avahi-daemon.service smbd.service wsdd.service scpprint-usb-heal.service)
systemctl enable "${services[@]}"
systemctl restart "${services[@]}"
# แชร์คิวเดิมทั้งหมด คิวใหม่แชร์เป็นค่าเริ่มต้นตาม cupsd.conf
while read -r queue; do
    [[ -z $queue ]] || lpadmin -h /run/cups/cups.sock -p "$queue" -o printer-is-shared=true
done < <(lpstat -h localhost -p | awk '{print $2}')
if ((API)); then
    # ย้ายจากชื่อบริการรุ่นก่อน ป้องกันสองโปรเซสแย่งพอร์ต 8631
    if systemctl cat scpprint-api.service >/dev/null 2>&1; then
        systemctl disable --now scpprint-api.service
    fi
    systemctl enable scpprint-queue-control.socket scpprint-agent.service
    systemctl restart scpprint-queue-control.socket scpprint-agent.service
fi
if [[ -n $RAW_QUEUE ]]; then systemctl enable scpprint-raw.service; systemctl restart scpprint-raw.service; fi
if systemctl cat systemd-tmpfiles-clean.timer >/dev/null 2>&1; then
    systemctl enable --now systemd-tmpfiles-clean.timer
    systemctl is-active --quiet systemd-tmpfiles-clean.timer
fi
for unit in armbian-zram-config.service armbian-ramlog.service; do
    if systemctl cat "$unit" >/dev/null 2>&1; then
        systemctl enable "$unit"
        systemctl start "$unit"
        systemctl is-active --quiet "$unit" || { echo "$unit failed" >&2; exit 1; }
    else
        echo "$unit is not provided by this image; no replacement installed."
    fi
done
/usr/local/sbin/scpprint-healthcheck
if ((API)); then
    # is-active อย่างเดียวอาจผ่านก่อน Python import เสร็จ จึงทดสอบ API จริงด้วย
    python3 - "$LISTEN" <<'PY'
from pathlib import Path
import sys, time, urllib.request
values = dict(line.split('=', 1) for line in Path('/etc/scpprint/api.env').read_text().splitlines()
              if line and not line.startswith('#') and '=' in line)
host = '127.0.0.1' if sys.argv[1] == '0.0.0.0' else sys.argv[1]
request = urllib.request.Request(f'http://{host}:8631/health',
                                 headers={'Authorization': 'Bearer ' + values['SCPPRINT_TOKEN']})
for attempt in range(15):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=2) as response:
            if response.status == 200:
                break
    except OSError:
        if attempt == 14:
            raise SystemExit('Agent readiness check failed. See journalctl -u scpprint-agent')
        time.sleep(1)
PY
fi
# ยืนยัน CUPS รับ TLS จริง; -k ใช้ตรวจ self-signed เฉพาะบนกล่องนี้
curl --insecure --fail --silent --show-error --max-time 15 https://127.0.0.1:631/ >/dev/null
echo "Done. Backups: $BACKUP_DIR"
echo 'CUPS Admin: https://<box-ip>:631 ; log out/in to refresh lpadmin membership.'
if ((API)); then echo 'Dashboard: http://<box-ip>:8631 ; token: sudo cat /etc/scpprint/api.env (keep private).'; fi
if [[ -e /var/run/reboot-required ]]; then echo 'System update requests a reboot; schedule it after reviewing the log.'; fi
