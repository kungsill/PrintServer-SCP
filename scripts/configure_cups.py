"""Preserve existing CUPS policies; replace only managed directives/locations."""
from pathlib import Path
import re
import sys


def configure(text: str) -> str:
    text = text.replace('# Managed by SCPPrint\n', '')
    keys = r"Listen|Port|SSLListen|SSLPort|DefaultEncryption|Browsing|BrowseLocalProtocols|WebInterface|DefaultShared"
    # คง policy เดิมไว้ เปลี่ยนเฉพาะ directive ที่ชุดติดตั้งนี้รับผิดชอบ
    text = re.sub(rf"(?mi)^\s*(?:{keys})\s+[^\n]*$", "", text)
    for path in ("/", "/admin", "/admin/conf", "/admin/log"):
        text = re.sub(
            rf"(?ims)^\s*<Location\s+{re.escape(path)}\s*>.*?</Location>\s*", "", text
        )
    # ทำให้รันซ้ำได้ผลลัพธ์เดิม ไม่สะสมบรรทัดว่างหรือ managed block
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    text += "\n\n# Managed by SCPPrint\nListen *:631\nListen /run/cups/cups.sock\n"
    text += "DefaultEncryption Required\nBrowsing On\nBrowseLocalProtocols dnssd\nWebInterface Yes\nDefaultShared Yes\n"
    for path in ("/", "/admin", "/admin/conf", "/admin/log"):
        text += f"<Location {path}>\n  Order allow,deny\n  Allow @LOCAL\n  Allow localhost\n"
        if path != "/":
            # บังคับ HTTPS สำหรับรหัสผ่านผู้ดูแล แต่ยังรับงาน IPP ใน LAN ได้
            text += "  Encryption Required\n  AuthType Default\n  Require user @SYSTEM\n"
        text += "</Location>\n"
    return text


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.write_text(configure(target.read_text()))
