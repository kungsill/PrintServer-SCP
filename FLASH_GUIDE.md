# เตรียม Armbian / DTB / ย้ายระบบลง eMMC

คู่มือนี้ใช้ก่อนรัน `setup-scpprint-armbian.sh` สำหรับ Amlogic S905X/S905X3 และ Rockchip RK3328/RK3399 ชื่อชิปอย่างเดียวไม่พอที่จะเลือก image, DTB หรือ bootloader ให้ถูก ต้องทราบรุ่นบอร์ดและ revision, RAM, ชิป Ethernet/Wi-Fi และชนิด storage ด้วย กล่องชื่อการค้าเดียวกันอาจใช้คนละบอร์ด

## 1. เตรียมไฟล์และสื่อบูต

1. จดรุ่นบอร์ดจากฉลาก/PCB และสำรอง firmware Android พร้อมวิธีกู้คืนของรุ่นนั้นก่อน เลือก Armbian image **ARM64, Debian 12 Bookworm หรือ Ubuntu 24.04 Noble** ที่ผู้ดูแล image ระบุว่ารองรับบอร์ดของคุณ
2. ดาวน์โหลด image และ checksum จากหน้า release ของผู้ดูแลเดียวกัน ตรวจ checksum ก่อนเขียน SD/USB และเก็บชื่อ image + version + URL ไว้กับเครื่อง
3. เขียน image ลง SD/USB ด้วยเครื่องมือเขียน image และตรวจ verify หลังเขียน ต้องเลือกสื่อเป้าหมายให้ตรง เพราะข้อมูลเดิมบนสื่อนั้นจะถูกแทนที่
4. บูตจาก SD/USB ให้ Ethernet, USB, RAM และ storage ทำงานนิ่งก่อนย้ายลง eMMC แนะนำให้เริ่มด้วย Ethernet และจ่ายไฟตามสเปกของกล่อง

ตัวอย่างตรวจ SHA-256 บน Windows PowerShell (เปลี่ยนชื่อไฟล์ให้ตรงกับที่ดาวน์โหลด แล้วเทียบกับค่าจากผู้ดูแล image):

```powershell
Get-FileHash -LiteralPath '.\Armbian-image.img.xz' -Algorithm SHA256
```

บน Linux หาก release มีไฟล์ checksum รูปแบบมาตรฐาน:

```bash
sha256sum -c Armbian-image.img.xz.sha256
```

การเลือก image/เขียนสื่ออ้างอิง [คู่มือ Armbian](https://docs.armbian.com/getting-started/writing-the-image/) ส่วน TV Box image ของชุมชนต้องอ่านวิธีบูตและรายการรองรับจากผู้ดูแล image นั้นเพิ่ม กล่องที่ชิปอยู่ในตระกูลนี้ไม่ได้หมายความว่าทุกรุ่นได้รับการรองรับ

## 2. สำรวจ boot partition และ DTB ที่มีจริง

ก่อนบูตครั้งแรก เปิด boot partition บนคอมพิวเตอร์ หากบูต Linux ได้แล้ว ใช้:

```bash
ls -la /boot
find /boot -type f -name '*.dtb' -print
ls -l /boot/uEnv.txt /boot/extlinux/extlinux.conf /boot/armbianEnv.txt 2>/dev/null
tr -d '\0' </proc/device-tree/model
printf '\n'
uname -m
```

ใช้ DTB ที่มากับ **kernel/image ชุดเดียวกัน** และตรงกับบอร์ด ไม่คัดลอก DTB จาก firmware Android ไปใช้กับ mainline kernel โดยตรง หาก image มีไฟล์ `/etc/model_database.conf` ให้ดูรายการของรุ่นนั้น:

```bash
if [ -r /etc/model_database.conf ]; then
  grep -Ei 's905x|s905x3|rk3328|rk3399' /etc/model_database.conf
fi
```

ตัวอย่างชื่อ DTB สำหรับใช้เทียบ **เฉพาะบอร์ดที่ระบุ** ไม่ใช่ค่าเริ่มต้นสำหรับทุกกล่อง:

| SoC | ตัวอย่างบอร์ด/รุ่นในฐานข้อมูล image | ชื่อ DTB ตัวอย่าง |
|---|---|---|
| S905X | T95 / บอร์ดอ้างอิง P212 ตามรุ่นที่รองรับ | `meson-gxl-s905x-p212.dtb` |
| S905X3 | HK1 Box / Vontar X3 ตาม revision ที่รองรับ | `meson-sm1-hk1box-vontar-x3.dtb` |
| RK3328 | Station M1 / Bqeel MVR9 | `rk3328-box-trn9.dtb` |
| RK3399 | Firefly RK3399 | `rk3399-firefly.dtb` |

ตรวจ mapping และ boot config ของรุ่นจริงจาก [ฐานข้อมูลบอร์ดของ ophub](https://github.com/ophub/amlogic-s9xxx-armbian/blob/main/build-armbian/armbian-files/common-files/etc/model_database.conf) ชื่อไฟล์อาจต่างกันใน kernel/image อื่น เช่น HK1 Box ใน mainline บางชุดใช้ชื่ออีกแบบ ห้ามเลือกไฟล์เพียงเพราะชื่อใกล้เคียง

## 3. เลือก DTB ในไฟล์ที่ bootloader ใช้งานจริง

อย่าแก้ทุกไฟล์พร้อมกัน ไฟล์ `.bak` ไม่จำเป็นต้องถูกใช้ตอนบูต ตรวจเอกสาร image และ active boot entry ก่อน แต่ละ image อาจใช้ `uEnv.txt`, `extlinux.conf` หรือ `armbianEnv.txt` ต่างกัน ดูแนวทางของ [ผู้ดูแล image](https://github.com/ophub/amlogic-s9xxx-armbian/blob/main/documents/README.md#126-boot-file-selection)

สำรองไฟล์ที่มีอยู่ก่อนแก้:

```bash
backup_dir="/root/scpprint-boot-backup-$(date +%Y%m%d-%H%M%S)"
sudo mkdir -p "$backup_dir"
for config in /boot/uEnv.txt /boot/extlinux/extlinux.conf /boot/armbianEnv.txt; do
  if [ -f "$config" ]; then sudo cp --parents -a "$config" "$backup_dir/"; fi
done
```

### Amlogic: uEnv.txt

แก้เฉพาะบรรทัด `FDT=` ที่มีอยู่ เช่น สำหรับ **P212 ที่ image รองรับ** และมีไฟล์นี้จริง:

```ini
FDT=/dtb/amlogic/meson-gxl-s905x-p212.dtb
```

หรือ **HK1 Box/Vontar X3 ที่ตรงกับ mapping ของ image**:

```ini
FDT=/dtb/amlogic/meson-sm1-hk1box-vontar-x3.dtb
```

คงบรรทัด `LINUX`, `INITRD`, `APPEND`, UUID/root device และค่าคอนโซลเดิมไว้ พาธอาจเป็น `/dtb/ชื่อไฟล์.dtb` หรือแบบอื่นตาม image ต้องใช้ prefix ของไฟล์เดิมและไฟล์ที่พบจริง

### Amlogic/Rockchip: extlinux.conf

แก้ `FDT` ภายใน `LABEL` ที่ active เท่านั้น ตัวอย่างบรรทัดสำหรับบอร์ด Firefly RK3399:

```text
    FDT /dtb/rockchip/rk3399-firefly.dtb
```

ตัวอย่างบรรทัดสำหรับบอร์ด Station M1/Bqeel MVR9 ที่ image รองรับ:

```text
    FDT /dtb/rockchip/rk3328-box-trn9.dtb
```

สำหรับ Amlogic ใช้พาธ DTB ของบอร์ด Amlogic ที่ถูกต้องภายใน `FDT` เช่นเดียวกัน **ตัวอย่างนี้แสดงเฉพาะบรรทัด FDT ห้ามใช้แทน extlinux.conf ทั้งไฟล์** คง `DEFAULT`, `LABEL`, `LINUX`, `INITRD` และ `APPEND` เดิมทั้งหมด

### Rockchip: armbianEnv.txt

หลาย image ใช้ไฟล์นี้แทนสองแบบข้างบน แก้ค่า `fdtfile=` ที่มีอยู่ เช่น:

```ini
fdtfile=rockchip/rk3399-firefly.dtb
```

พาธเป็นแบบสัมพันธ์กับ DTB directory ที่ boot script กำหนด บาง image ไม่ใช้ prefix `rockchip/` ให้คงรูปแบบของ image นั้น อย่าเปลี่ยน U-Boot/trust/idbloader โดยเดาตาม SoC

หลังแก้ให้ `sync` แล้วปิดเครื่อง/รีบูตตามขั้นตอนของ image ถ้าบูตไม่ได้ ให้เปิด SD/USB บนคอมพิวเตอร์และคืนไฟล์ boot config จากสำเนาเดิม ไม่จำเป็นต้องเขียน eMMC เพื่อทดลอง DTB

## 4. ทดสอบจาก SD/USB ก่อนย้ายลง eMMC

```bash
uname -a
uname -m                  # ต้องเป็น aarch64
ip -br address
lsusb
lsblk -e7 -o NAME,PATH,SIZE,MODEL,TYPE,MOUNTPOINTS
findmnt -no SOURCE /
sudo dmesg --level=err,warn
```

ทดสอบเสียบเครื่องพิมพ์, LAN และรีบูตหลายครั้ง ต้องไม่มี USB disconnect หรือ I/O error ซ้ำๆ หากบูตได้แต่ Ethernet/eMMC/USB ทำงานผิดปกติ ให้กลับไปตรวจ DTB และไฟเลี้ยงก่อน

## 5. ย้ายระบบจาก SD/USB ลง eMMC

ขั้นตอนนี้อาจแทนที่ Android, partition table และ bootloader ใน eMMC ต้องมีสำเนา firmware/bootloader และวิธีกู้คืนของรุ่นจริงอยู่บนเครื่องอื่น **ตัวติดตั้ง Print Server ไม่เรียกขั้นตอนนี้อัตโนมัติ**

ตรวจอุปกรณ์ต้นทาง/ปลายทางให้ชัด ไม่สมมติว่า `mmcblk0` เป็น eMMC เสมอ:

```bash
lsblk -e7 -o NAME,PATH,SIZE,MODEL,TYPE,MOUNTPOINTS
findmnt -no SOURCE /
command -v armbian-install
sudo armbian-install
```

เลือกตัวเลือกติดตั้งระบบและ boot บน eMMC ตามที่ installer ของ image นั้นรองรับ เลือก filesystem ที่ image แนะนำ เช่น ext4 และอ่านชื่ออุปกรณ์ปลายทางก่อนยืนยัน `armbian-install` เป็นเครื่องมือแบบมีเมนู และพฤติกรรมต่างกันได้ระหว่าง Armbian ทางการกับ TV Box image ของชุมชน ไม่ส่งเลขเมนูผ่าน pipe เพราะเลข/ความหมายอาจเปลี่ยนไป

รายละเอียดตัวเลือกอ้างอิง [Armbian internal storage installer](https://docs.armbian.com/getting-started/install-to-internal-storage/) หากคำสั่งไม่มีหรือ image ไม่รองรับ eMMC ของบอร์ดนั้น ให้ใช้ขั้นตอนเฉพาะบอร์ดจากผู้ดูแล image และคง SD/USB ไว้ใช้งาน ไม่ใช้สคริปต์ `install-aml.sh` / `install-rk.sh` จากคนละ image แทนโดยเดา

เมื่อ installer รายงานสำเร็จ:

```bash
sync
sudo poweroff
```

ถอดไฟและถอด SD/USB ตามขั้นตอนของบอร์ด แล้วเปิดเครื่องใหม่ ตรวจ `findmnt` และ `lsblk` อีกครั้งเพื่อยืนยันว่าระบบรากอยู่บน eMMC จริง เก็บสื่อบูตเดิมสำหรับกู้คืน

## 6. เตรียมโปรเจกต์และติดตั้ง Print Server

บน Windows ถ้าใช้ OpenSSH และมีโฟลเดอร์โปรเจกต์อยู่ใน working directory:

```powershell
scp -r '.\armbian-scpprint-server' armbian@192.168.1.50:/home/armbian/
ssh armbian@192.168.1.50
```

บนกล่อง:

```bash
cd /home/armbian/armbian-scpprint-server
sudo bash setup-scpprint-armbian.sh --admin-user armbian
```

เปลี่ยนชื่อบัญชีและ IP ให้ตรงกล่อง ดู [README.md](README.md) สำหรับ provisioning เครื่องพิมพ์แบบอัตโนมัติ, Dashboard, API, firewall และการตรวจรับหลังติดตั้ง
