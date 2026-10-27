#!/usr/bin/env bash
set -euo pipefail
# ชื่อเดิมยังเรียกได้ โดยส่งต่อทุกตัวเลือกไปยังตัวติดตั้งหลัก
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$ROOT_DIR/setup-scpprint-armbian.sh" "$@"
