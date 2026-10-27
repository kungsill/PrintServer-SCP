"""เว็บ Dashboard และ API: รับไฟล์แบบ streaming โดยไม่รับพาธหรือคำสั่ง shell"""
import asyncio
import hmac
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StrictBool
from common import MAX_BYTES, SPOOL, printers, run, submit, validate_queue, clear_queue

TOKEN = os.environ.get('SCPPRINT_TOKEN', '')
if len(TOKEN) < 32:
    raise RuntimeError('Set SCPPRINT_TOKEN to at least 32 characters')
app = FastAPI(title='SCPPrint', docs_url=None, redoc_url=None, openapi_url=None)
slots = asyncio.Semaphore(4)
STATIC = Path(__file__).resolve().parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC), name='static')
# หน้าเว็บที่อยู่คนละ origin ต้องระบุ allowlist เอง ไม่เปิด CORS แบบ wildcard
origins = [item.strip() for item in os.environ.get('SCPPRINT_CORS_ORIGINS', '').split(',') if item.strip()]
if '*' in origins:
    raise RuntimeError('Explicit CORS origins required')
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST'],
                       allow_headers=['Authorization', 'Content-Type'])


@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.get('/', include_in_schema=False)
async def dashboard():
    # หน้าเปล่าเปิดได้ แต่สถานะ/คำสั่งทั้งหมดด้านล่างต้องใช้ token
    return FileResponse(STATIC / 'index.html')


def authorize(authorization: str = Header(default='')):
    if not hmac.compare_digest(authorization.encode(), ('Bearer ' + TOKEN).encode()):
        raise HTTPException(401, 'Bearer token required', headers={'WWW-Authenticate': 'Bearer'})


@app.get('/health', dependencies=[Depends(authorize)])
async def health():
    try:
        scheduler = await asyncio.to_thread(run, 'lpstat', '-r')
        if 'scheduler is running' not in scheduler:
            raise HTTPException(503, 'CUPS scheduler is not running')
        return {'cups': scheduler}
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(503, 'CUPS unavailable')


@app.get('/printers', dependencies=[Depends(authorize)])
async def list_printers():
    try:
        return {'printers': await asyncio.to_thread(printers)}
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(503, 'CUPS unavailable or no queues configured')


def snapshot():
    def observe(*args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return {'output': (result.stdout + result.stderr).strip()[:32768], 'exit_code': result.returncode}
    # เก็บทั้ง stdout/stderr เพราะ lpstat อาจคืน code 1 เมื่อยังไม่มีคิวหรือ default
    scheduler = observe('lpstat', '-r')
    status = observe('lpstat', '-p', '-d')
    devices = observe('lpstat', '-v')
    jobs = observe('lpstat', '-o')
    usb = observe('lsusb')
    queues = []
    uris = {}
    for line in devices['output'].splitlines():
        if line.startswith('device for ') and ': ' in line:
            name, uri = line[len('device for '):].split(': ', 1)
            uris[name] = uri
    for line in status['output'].splitlines():
        if line.startswith('printer '):
            name = line.split()[1]
            state = 'disabled' if ' disabled ' in line else 'printing' if ' now printing ' in line else 'idle' if ' is idle' in line else 'unknown'
            queues.append({'name': name, 'state': state, 'description': line,
                           'usb': uris.get(name, '').startswith(('usb://', 'hp:/usb/'))})
    return {'scheduler': scheduler, 'lpstat': status, 'lsusb': usb, 'jobs': jobs,
            'printers': queues, 'max_upload_bytes': MAX_BYTES}


@app.get('/status', dependencies=[Depends(authorize)])
async def status():
    try:
        return await asyncio.to_thread(snapshot)
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(503, 'Cannot read system status')


class ClearRequest(BaseModel):
    confirm: StrictBool


@app.post('/queue/clear', dependencies=[Depends(authorize)])
async def clear_print_queue(body: ClearRequest, printer: str = Query(..., min_length=1, max_length=127)):
    if body.confirm is not True:
        raise HTTPException(400, 'Explicit confirmation required')
    try:
        # จำกัดเฉพาะคิวที่เลือก ไม่มี endpoint ล้างทุกเครื่องพร้อมกัน
        return await asyncio.to_thread(clear_queue, printer)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(503, 'Queue control failed; inspect journal')


@app.post('/print', status_code=202, dependencies=[Depends(authorize)])
@app.post('/print/pdf', status_code=202, dependencies=[Depends(authorize)])
@app.post('/print/raw', status_code=202, dependencies=[Depends(authorize)])
async def print_file(request: Request, printer: str = Query(..., min_length=1, max_length=127),
                     copies: int = Query(1, ge=1, le=100), duplex: bool = False):
    kind = request.headers.get('content-type', '').split(';')[0].lower()
    if kind not in ('application/pdf', 'application/octet-stream'):
        raise HTTPException(415, 'Use application/pdf or application/octet-stream for RAW')
    expected = {'/print/pdf': 'application/pdf', '/print/raw': 'application/octet-stream'}.get(request.url.path)
    if expected and kind != expected:
        raise HTTPException(415, f'This endpoint requires {expected}')
    if slots.locked():
        raise HTTPException(429, 'All upload slots busy')
    async with slots:
        path = None
        try:
            await asyncio.to_thread(validate_queue, printer)
            with tempfile.NamedTemporaryFile(dir=SPOOL, delete=False) as spool:
                path = Path(spool.name)
                total = 0
                prefix = b''
                stream = request.stream().__aiter__()
                deadline = asyncio.get_running_loop().time() + 300
                while True:
                    try:
                        # จำกัดเวลารวมด้วย เพื่อไม่ให้การส่งช้ามากยึด slot ค้างไม่สิ้นสุด
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            raise asyncio.TimeoutError()
                        chunk = await asyncio.wait_for(anext(stream), timeout=min(30, remaining))
                    except StopAsyncIteration:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise HTTPException(413, 'File exceeds upload limit')
                    prefix = (prefix + chunk[:5])[:5]
                    spool.write(chunk)
                if total == 0:
                    raise HTTPException(400, 'Empty file')
                if kind == 'application/pdf' and prefix != b'%PDF-':
                    raise HTTPException(400, 'Invalid PDF header')
            result = await asyncio.to_thread(submit, path, printer, kind == 'application/octet-stream', copies, duplex)
            return {'status': 'queued', 'cups_response': result}
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except asyncio.TimeoutError:
            raise HTTPException(408, 'Upload timed out')
        except (OSError, subprocess.SubprocessError):
            raise HTTPException(503, 'CUPS submission failed; check service logs before retrying')
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
