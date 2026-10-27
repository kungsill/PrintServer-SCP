# SCPPrint Armbian Print Server

เปลี่ยน Android TV Box **Amlogic/Rockchip ที่ลง Armbian ARM64 แล้ว** ให้เป็น Print Server พร้อม CUPS, Bonjour/AirPrint, Samba Guest/Public, wsdd, USB auto-heal และ Dashboard + FastAPI Agent พอร์ต **8631** ใช้แทนการรับไฟล์และส่งพิมพ์ของโปรแกรม Windows เดิม โดยไม่ต้องรัน `SCPPrint_Setup.exe` บน Linux

ชุดนี้ไม่ได้อ้างว่าใช้โปรโตคอลภายในของ `.exe` เดิมได้เหมือนกันทุกอย่าง โปรแกรมเดิมที่เชื่อมกับ Windows Agent ต้องเปลี่ยนมาเรียก HTTP API ด้านล่าง ไม่มีการแกะหรือรัน `.exe` ในขั้นตอนติดตั้ง

รองรับ **Armbian Debian 12 Bookworm / Ubuntu 24.04 Noble, arm64, systemd** เริ่มจาก [FLASH_GUIDE.md](FLASH_GUIDE.md) ถ้ายังต้องเลือก DTB หรือย้ายระบบลง eMMC

## ติดตั้งครั้งเดียว

แตก ZIP แล้วคัดลอก **ทั้งโฟลเดอร์** ไปยังกล่อง จากนั้นรันบนกล่อง:

```bash
cd /home/armbian/armbian-scpprint-server
sudo bash setup-scpprint-armbian.sh --admin-user armbian
```

หรือ clone ซอร์สจาก GitHub บนกล่องโดยตรงเมื่อมี Git ติดตั้งแล้ว:

```bash
git clone https://github.com/kungsill/PrintServer-SCP.git
cd PrintServer-SCP
sudo bash setup-scpprint-armbian.sh --admin-user armbian
```

เปลี่ยน `armbian` เป็นบัญชี Linux ที่มีอยู่จริง สามารถละ `--admin-user` เมื่อใช้ `sudo` จากผู้ใช้ปกติได้ ตัวติดตั้งใช้ `SUDO_USER` โดยไม่เดาบัญชีแรกในเครื่อง และเพิ่มบัญชีนั้นเข้า `lpadmin` ให้ logout/login ใหม่เพื่อให้กลุ่มมีผล บัญชีนี้ต้องมีรหัสผ่านสำหรับเข้า CUPS Admin

ตัวติดตั้งทำงานแบบ non-interactive: อัปเดต package index, `apt-get upgrade -y`, ติดตั้งแพ็กเกจ, สำรองคอนฟิกก่อนเปลี่ยน, ตรวจ CUPS/Samba, เปิดบริการ, ตรวจ `systemctl is-active`, ทดสอบ HTTPS ของ CUPS และรอ API health พร้อม ไม่ reboot หรือเขียน eMMC เอง หากระบบขอ reboot หลังอัปเดตจะรายงานท้ายการติดตั้ง

รันซ้ำได้โดยไม่สร้าง managed block ซ้ำและไม่เปลี่ยน token เดิม จะเขียนไฟล์ที่โปรเจกต์ดูแลใหม่ แชร์คิว CUPS ที่มีอยู่ทั้งหมด และแทน `/etc/samba/smb.conf` ทั้งไฟล์ จึงเหมาะกับกล่อง Print Server โดยเฉพาะ สำเนาก่อนเปลี่ยนอยู่ใน `/var/backups/scpprint-XXXXXXXX/` และ log อยู่ที่ `/var/log/scpprint-setup.log` (root อ่านได้)

คำสั่งนี้ตั้งค่า HTTPS สำหรับ Admin ตามข้อกำหนดล่าสุด แทน `DefaultEncryption Never` ในรุ่นก่อน CUPS จะใช้ใบรับรองของเครื่อง ซึ่งโดยทั่วไปเป็น self-signed: ต้องตรวจและเชื่อถือใบรับรอง/ติดตั้งใบรับรองขององค์กรเพื่อให้เบราว์เซอร์ไม่เตือน ไม่มีวิธีให้ self-signed ถูกเชื่อถือโดยทุกเครื่องลูกอัตโนมัติจากสคริปต์เซิร์ฟเวอร์

## เพิ่มเครื่องพิมพ์

เปิด **`https://<IP-กล่อง>:631`** → Administration → Add Printer → เลือก USB และไดรเวอร์ให้ตรงรุ่น → Share This Printer ตั้งชื่อคิวที่ API รองรับ เช่น `USB_Printer`

หากต้องการสร้างคิวพร้อมติดตั้งแบบไม่ใช้หน้าเว็บ ให้ระบุ URI และ model ที่ตรวจสอบแล้ว:

```bash
lpinfo -v                    # URI ที่พบ เช่น usb://Brother/...
lpinfo -m                    # model identifier ของไดรเวอร์

sudo bash setup-scpprint-armbian.sh --admin-user armbian \
  --printer-name USB_Printer \
  --device-uri 'usb://Vendor/Model?serial=YOUR_SERIAL' \
  --driver 'MODEL_IDENTIFIER_FROM_LPINFO'
```

ตัวอย่างข้างบนมี placeholder ต้องเปลี่ยนทั้ง URI และ model ให้ตรงเครื่องจริง ไม่ใช้ `-m everywhere` กับ USB รุ่นเก่าทั่วไป ไดรเวอร์ `everywhere` ต้องใช้ IPP/IPPS URI ของเครื่องที่รองรับ

การติดตั้งไดรเวอร์และการเพิ่มคิวเป็นคนละขั้นตอน ชุดนี้ไม่เดารุ่นเครื่องพิมพ์และไม่รับประกันเครื่องที่มีเฉพาะไดรเวอร์ x86/ไดรเวอร์ปิด รองรับ Gutenprint, HPLIP, brlaser, splix, Foomatic DB/engine และ OpenPrinting PPDs ตามแพ็กเกจ ARM64 ใน repository หากขาดแพ็กเกจจะหยุดพร้อมชื่อแพ็กเกจให้แก้ repository แล้วรันใหม่ เช่น Ubuntu อาจต้องเปิด Universe

```bash
lpstat -p -d
sudo lpadmin -d USB_Printer   # ตั้ง default หากต้องการ
lp -d USB_Printer test.pdf
```

ชื่อคิวที่ API/RAW/helper รองรับ: ขึ้นต้นด้วย `A-Z`, `a-z`, `0-9`, `_` และใช้ตัวอักษรเหล่านี้รวม `.` / `-` ได้ ความยาวไม่เกิน 127 ตัวอักษร ไม่มีช่องว่าง

## Dashboard และ API

เปิด **`http://<IP-กล่อง>:8631`** แล้ววาง token จาก:

```bash
sudo cat /etc/scpprint/api.env
```

Dashboard แสดงสถานะ `lpstat -p -d`, คิวที่ตั้งค่าไว้, จำนวนงานรอ และ `lsusb` มีแบบฟอร์มส่ง PDF/RAW และปุ่ม **Clear Print Queue** เฉพาะคิวที่เลือก พร้อมยืนยันก่อนยกเลิกทุกงานในคิวนั้น โทเคนอยู่ในหน่วยความจำหน้าเว็บ ไม่เก็บใน URL/cookie/localStorage

ป้าย USB บนคิวบอกชนิด URI ที่ตั้งค่าไว้ ไม่ใช่การรับรองว่าเครื่องเปิดอยู่ `lsusb` แสดงอุปกรณ์ที่ kernel พบจริงทั้งหมดรวม hub ส่วนสถานะ idle ของ CUPS ไม่ได้ยืนยันว่าเครื่องพิมพ์พร้อมทางกายภาพทุกกรณี

ทุก API ต้องส่ง `Authorization: Bearer TOKEN` ยกเว้น HTML/static shell ของ Dashboard ซึ่งไม่มีข้อมูลสถานะหรือ token ฝังอยู่ API รับ **ไฟล์ใน HTTP body โดยตรง** ไม่รับ multipart, ชื่อพาธไฟล์บนเซิร์ฟเวอร์, URL ดาวน์โหลด หรือคำสั่ง shell

| Method / Path | หน้าที่ |
|---|---|
| `GET /health` | ตรวจ scheduler ของ CUPS |
| `GET /status` | สถานะคิว, lpstat, lsusb, งานรอ และ upload limit |
| `GET /printers` | ชื่อคิวที่มีอยู่ |
| `POST /print/pdf?printer=NAME` | รับ `application/pdf` แล้วแปลงด้วย CUPS/ไดรเวอร์บนกล่อง |
| `POST /print/raw?printer=NAME` | รับ `application/octet-stream` ส่ง `lp -o raw` |
| `POST /queue/clear?printer=NAME` | รับ JSON `{"confirm":true}` เพื่อยกเลิกทุกงานในคิวนั้น |
| `POST /print?printer=NAME` | เส้นทางเดิม ยังรองรับ PDF/RAW ตาม Content-Type |

ตัวอย่างจาก Linux/macOS:

```bash
export SCPPRINT_TOKEN='ใส่โทเคนของกล่อง'
curl --fail-with-body \
  -H "Authorization: Bearer $SCPPRINT_TOKEN" \
  http://192.168.1.50:8631/status

curl --fail-with-body \
  -H "Authorization: Bearer $SCPPRINT_TOKEN" \
  -H 'Content-Type: application/pdf' --data-binary @document.pdf \
  'http://192.168.1.50:8631/print/pdf?printer=USB_Printer&copies=1&duplex=false'

curl --fail-with-body \
  -H "Authorization: Bearer $SCPPRINT_TOKEN" \
  -H 'Content-Type: application/octet-stream' --data-binary @printer-ready.prn \
  'http://192.168.1.50:8631/print/raw?printer=USB_Printer'

# คำสั่งนี้ยกเลิกทุกงานในคิว USB_Printer รวมงานของผู้อื่น
curl --fail-with-body \
  -H "Authorization: Bearer $SCPPRINT_TOKEN" \
  -H 'Content-Type: application/json' --data '{"confirm":true}' \
  'http://192.168.1.50:8631/queue/clear?printer=USB_Printer'
```

บน Windows PowerShell ใช้ `curl.exe` แทน `curl` เพื่อเลี่ยง alias และใช้ `$env:SCPPRINT_TOKEN` แทน `$SCPPRINT_TOKEN` ตัวอย่าง:

```powershell
$env:SCPPRINT_TOKEN = 'ใส่โทเคนของกล่อง'
curl.exe --fail-with-body -H "Authorization: Bearer $env:SCPPRINT_TOKEN" `
  -H 'Content-Type: application/pdf' --data-binary '@document.pdf' `
  'http://192.168.1.50:8631/print/pdf?printer=USB_Printer'
```

PDF ไม่ต้องมีไดรเวอร์บนเครื่องลูก เพราะกล่องแปลงให้ผ่าน CUPS ส่วน RAW ต้องเป็นภาษาที่เครื่องพิมพ์รองรับอยู่แล้ว เช่น PCL, PostScript, ESC/POS หรือ raster ของรุ่นนั้น การส่ง PDF ที่ยังไม่แปลงไป `/print/raw` ไม่ทำให้เครื่อง USB ที่ไม่รองรับ PDF พิมพ์ได้เอง

HTTP 202 หมายถึงรับเข้าคิว CUPS แล้ว ไม่ได้ยืนยันว่ากระดาษออกสำเร็จ จำกัด `copies=1..100`; `duplex=true` มีผลกับ PDF และฮาร์ดแวร์ต้องรองรับ จำกัดไฟล์ปริยาย 32 MiB / 4 uploads พร้อมกันต่อบริการ / ช่วงไม่ส่งข้อมูล 30 วินาที / API รวมไม่เกิน 300 วินาที HTTP 400 คือคิวหรือไฟล์ไม่ถูกต้อง, 401 token ผิด/หาย, 413 ใหญ่เกิน, 415 Content-Type ผิด, 429 slot เต็ม, 503 ส่งต่อ CUPS/helper ไม่สำเร็จ ถ้า timeout/503 ให้ตรวจคิวก่อนส่งซ้ำเพื่อหลีกเลี่ยงงานซ้ำ

Clear Queue ใช้ root helper แบบ systemd socket activation ตรวจ UID ผู้เรียกจาก kernel และตรวจชื่อคิวก่อนสั่ง `cancel -a <queue>` เว็บ Agent ยังรันเป็น user `scpprint`, ไม่มี sudo และเปิด `NoNewPrivileges` ไม่มีคำสั่งล้างทุกเครื่องพร้อมกันหรือรัน shell จาก API การล้างคิวไม่แก้กระดาษติด ไม่รีเซ็ตฮาร์ดแวร์ และไม่รับประกันหยุดงานที่ถูกส่งถึงหน่วยความจำเครื่องแล้ว

## ตั้งค่าเพิ่มเติม

```bash
sudo bash setup-scpprint-armbian.sh --help

# ข้าม upgrade ทั้งระบบ แต่ยังติดตั้ง/อัปเดตแพ็กเกจที่จำเป็น
sudo bash setup-scpprint-armbian.sh --admin-user armbian --skip-upgrade

# จำกัด bind เฉพาะ Agent/RAW; IP ต้องมีอยู่บนกล่องจริง
sudo bash setup-scpprint-armbian.sh --admin-user armbian --listen 192.168.1.50

# เปิด RAW TCP 9100 ให้คิวที่มีอยู่แล้ว
sudo bash setup-scpprint-armbian.sh --admin-user armbian --raw-queue USB_Printer
```

RAW 9100 รับหนึ่ง connection เป็นหนึ่งงาน ต้องส่งข้อมูล printer-ready แล้วปิดด้านส่งเพื่อจบงาน ไม่มี token/SNMP หรือการตอบยืนยันผลการพิมพ์ หากเพิ่ม Windows Standard TCP/IP Port ให้เลือก RAW 9100, ไดรเวอร์ Windows ตรงรุ่น และปิด SNMP Status Enabled

ไฟล์ `/etc/scpprint/api.env` มี `SCPPRINT_TOKEN`, `SCPPRINT_MAX_BYTES` (1..134217728) เปลี่ยนแล้ว restart Agent หากเว็บแอปของคุณอยู่คนละ origin ให้เพิ่ม `SCPPRINT_CORS_ORIGINS=https://app.example.local` หรือหลาย origin คั่น comma ไม่มี wildcard และไม่เปิด CORS โดยปริยาย หน้า Dashboard ที่มากับ Agent ใช้งานแบบ same-origin ได้ทันที

```bash
sudo systemctl restart scpprint-agent
```

`install.sh` และ `--with-api` เป็นทางเข้าที่รองรับการเรียกแบบเดิม แต่ Agent เปิดเป็นค่าเริ่มต้นแล้ว การติดตั้งจะหยุด/disable `scpprint-api.service` รุ่นเก่าและใช้ `scpprint-agent.service` แทน โทเคนเดิมคงอยู่

`--without-agent` ข้ามการติดตั้ง/อัปเดต Agent ในรอบนั้น ไม่หยุด Agent ที่เปิดไว้ก่อนหน้า เช่นเดียวกับการละ `--raw-queue` ไม่ปิด RAW เดิม ถ้าต้องการปิด:

```bash
sudo systemctl disable --now scpprint-agent.service scpprint-queue-control.socket
sudo systemctl disable --now scpprint-raw.service
```

## LAN, AirPrint และ Windows Guest

| บริการ | พอร์ต |
|---|---|
| CUPS / IPP / HTTPS Admin | TCP 631 |
| Avahi / mDNS | UDP 5353 multicast |
| Samba | TCP 445 |
| wsdd | UDP 3702, TCP 5357 |
| Dashboard/API | TCP 8631 |
| RAW ถ้าเปิด | TCP 9100 |

Samba ตั้ง `guest ok=yes`, `guest only=yes`, `map to guest=Bad User`, SMB2 ขึ้นไป ฝั่งเซิร์ฟเวอร์จึงแชร์ Public โดยไม่ขอรหัสผ่าน SMB1 ไม่ถูกเปิดใช้ Windows บางรุ่น/นโยบายยังบล็อก guest หรือบังคับ SMB signing ซึ่ง guest ไม่รองรับ จึงไม่สามารถรับประกันว่าจะเชื่อมต่อแบบไร้รหัสผ่านได้ทุกเครื่องจากการแก้เซิร์ฟเวอร์อย่างเดียว ตาม [เอกสาร Microsoft เรื่อง Guest](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/guest-access-in-smb2-is-disabled-by-default) และ [SMB signing](https://learn.microsoft.com/en-us/windows-server/storage/file-server/smb-signing)

บน Windows ให้เครือข่ายเป็น Private และเปิด Network Discovery จากนั้นลอง `\\<IP-กล่อง>\USB_Printer` การใช้ SMB/RAW อาจต้องมีไดรเวอร์ Windows ตรงรุ่นบนเครื่องลูก ชุดนี้ไม่แจก Windows driver ผ่าน `print$` หากต้องการหลีกเลี่ยงไดรเวอร์ลูกข่ายให้ส่ง PDF ผ่าน Dashboard/API หรือใช้ IPP ที่เครื่องลูกและคิวรองรับ แทนการลดนโยบายความปลอดภัย Windows ทั้งเครื่องโดยอัตโนมัติ

iOS/macOS ใช้ Bonjour/AirPrint ใน LAN เดียวกัน ส่วน Android ใช้บริการพิมพ์ที่รองรับ IPP/Mopria การเห็นและพิมพ์สำเร็จขึ้นกับ driver/filter ของคิว, client, VLAN, firewall และ Wi-Fi client isolation ไม่รับประกัน discovery ข้าม subnet

API ปริยายเป็น HTTP เพื่อใช้ใน LAN ตามพอร์ตที่กำหนด โทเคนจึงไม่มีการเข้ารหัสระหว่างทาง ควรใช้ใน LAN ที่ควบคุมได้ หรือวาง HTTPS reverse proxy/VPN ก่อนเปิดนอกวงนั้น CUPS Admin ใช้ HTTPS แยกจาก API

ตัวติดตั้ง **ไม่แก้ firewall/router** และไม่เปิด port forwarding ให้ จำกัดการเข้าถึงเฉพาะ subnet ที่ใช้งาน ตัวอย่างเพิ่ม rule เมื่อกล่องมี UFW อยู่แล้ว (เปลี่ยน interface/subnet ให้ตรงจริง และคง SSH rule เดิมไว้):

```bash
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 631 proto tcp
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 8631 proto tcp
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 445 proto tcp
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 5353 proto udp
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 3702 proto udp
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 5357 proto tcp
# เฉพาะกรณีเปิด RAW
sudo ufw allow in on eth0 from 192.168.1.0/24 to any port 9100 proto tcp
sudo ufw status verbose
```

ตัวอย่างข้างบนเพิ่ม allow rules เท่านั้น ไม่ทำให้ firewall ที่ยังไม่เปิดกลายเป็นเปิด และไม่ลบ broad allow rules เดิม ต้องทบทวนนโยบายที่ใช้อยู่ ส่วน `--listen` จำกัด Agent/RAW เท่านั้น CUPS ใช้ `Listen *:631`, `Allow @LOCAL`; Samba/wsdd ใช้ interface ตามระบบ

## USB auto-heal และการดูแล

udev ส่งงานให้ systemd เมื่อ USB device ถูกเพิ่ม บริการตรวจซ้ำ 5 รอบ โดยเทียบ URI ของคิว `usb://...` / `hp:/usb/...` กับอุปกรณ์ที่ CUPS backend พบจริง แล้ว `cupsenable` + `cupsaccept` เพื่อปลด Paused โดยไม่ยกเลิกงานเดิม ไม่สร้างคิวใหม่ และไม่แตะคิวเครือข่าย มีการตรวจเมื่อบูตด้วย พิมพ์ต่อได้เมื่อ hardware/backend พร้อม ไม่ใช่ real-time guarantee

บริการนี้เป็น oneshot หลังทำงานจบ `inactive` เป็นสถานะปกติ ต้องดู `Result=success` / `ExecMainStatus=0` ร่วมด้วยเพื่อให้ USB event ครั้งถัดไปเรียกซ้ำได้

```bash
sudo scpprint-healthcheck
systemctl is-active cups avahi-daemon smbd wsdd scpprint-agent scpprint-queue-control.socket
sudo systemctl start scpprint-usb-heal
sudo journalctl -u scpprint-usb-heal -u scpprint-agent -n 100 --no-pager
sudo journalctl -u 'scpprint-queue-control@*' -n 100 --no-pager
lpstat -t
lsusb
```

`armbian-zram-config` และ `armbian-ramlog` จะถูก enable/start และตรวจสถานะหาก image มี unit อยู่แล้ว ไม่ดึงแพ็กเกจ Armbian จากแหล่งอื่นมาปะปน ไฟล์ upload ชั่วคราวอยู่ใน `/var/spool/scpprint` (0700); ลบหลังส่งให้ CUPS และมี tmpfiles rule สำหรับเศษไฟล์อายุเกิน 1 วันจากกรณีไฟดับ CUPS มี spool ของตัวเอง ต้องเฝ้าดูพื้นที่ว่างและอุณหภูมิ/ไฟเลี้ยงตามปริมาณงาน

การอัปเดตเคารพ `apt-mark hold` เดิม แต่ TV Box image บางชุดต้องใช้ kernel/bootloader เฉพาะรุ่น ควรตรวจนโยบายอัปเดตของผู้ดูแล image และทดสอบ image ที่จะใช้จริง ไม่กำหนด apt hold ใหม่แทนผู้ดูแลโดยเดาชื่อแพ็กเกจ

## ตรวจรับก่อนใช้งานจริง

| ตรวจ | วิธี |
|---|---|
| บริการ/คอนฟิก | `sudo scpprint-healthcheck`, `sudo cupsd -t`, `sudo testparm -s` |
| พิมพ์จริง | PDF หนึ่งหน้า → หลายหน้า → สองหน้าเมื่อรองรับ |
| ไฟ/USB | ปิด-เปิดเครื่องพิมพ์ระหว่างงาน รอ auto-heal แล้วตรวจคิวและกระดาษจริง |
| ล้างคิว | คิวทดสอบมีงานของผู้ใช้ปกติ → กด Clear → ยืนยันว่าเฉพาะคิวนั้นถูกยกเลิก |
| เริ่มระบบใหม่ | reboot แล้วตรวจ IP, printer URI, default queue, Agent และ discovery |
| เครือข่าย | ทดสอบ Windows/iOS/Android รุ่นที่จะใช้งานจริง และ firewall จาก subnet อื่น |

หากติดตั้งล้มเหลว สคริปต์ไม่ rollback แพ็กเกจ/บัญชี/บริการทั้งหมด คอนฟิก CUPS/Samba ที่ตรวจ syntax ไม่ผ่านจะคืนไฟล์นั้นทันที สำหรับ rollback รอบอื่นให้เลือก backup และคืนไฟล์ `/etc/...` ที่ต้องการ ตรวจ syntax แล้ว restart บริการ ไฟล์ใหม่ที่ไม่เคยมีจะไม่มีสำเนาเดิมใน backup และต้อง disable/จัดการแยก เก็บ token, `/etc/cups`, PPD และ config ที่ใช้งานจริงในระบบสำรองข้อมูลของคุณ

## โครงสร้างและการทดสอบฝั่งพัฒนา

```text
setup-scpprint-armbian.sh   ตัวติดตั้งหลัก (install.sh เรียกต่อมาที่นี่)
FLASH_GUIDE.md              image, DTB และ eMMC
agent/api.py               Dashboard + FastAPI
agent/static/              หน้าเว็บภาษาไทย ไม่ใช้ CDN
agent/queue_control.py     root helper สำหรับล้างคิวที่ระบุ
agent/raw.py               ตัวเลือก RAW TCP 9100
config/                    Samba, udev, tmpfiles
scripts/                   CUPS config, USB recovery, healthcheck, release packaging
systemd/                   บริการและ Unix socket
tests/                     mock CUPS/helper และ TCP integration test
```

```bash
bash -n setup-scpprint-armbian.sh
bash -n install.sh
bash -n scripts/healthcheck.sh
python3 -m unittest discover -s tests -v
node --check agent/static/dashboard.js
python3 scripts/package_release.py
```

unit tests ใช้ FastAPI/httpx (เวอร์ชันที่ตรวจร่วมกัน: FastAPI 0.92.0, httpx 0.24.1) ไม่พิมพ์หรือยกเลิกงานจริง ดูผลและข้อจำกัดที่ [VALIDATION.md](VALIDATION.md) การตรวจบน Windows ไม่แทนการติดตั้ง ARM64 / systemd / USB จริง

ทดลอง UI ฝั่งพัฒนาได้ด้วย `python3 tests/preview_dashboard.py` เมื่อมี uvicorn แล้วเปิด `http://127.0.0.1:18631` token คือ `preview-only-scpprint-not-for-production` ตัว preview ไม่รับพิมพ์หรือล้างคิวจริง และไม่ถูกติดตั้งเป็นบริการ

อ้างอิงการตั้งค่า: [CUPS](https://www.cups.org/doc/man-cupsd.conf.html), [lp](https://www.cups.org/doc/man-lp.html), [cancel](https://www.cups.org/doc/man-cancel.html), [Samba](https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html), [systemd socket activation](https://www.freedesktop.org/software/systemd/man/latest/systemd.socket.html)
