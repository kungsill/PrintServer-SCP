"""JetDirect-style TCP receiver. Clients must send printer-ready data and close write side."""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from common import MAX_BYTES, SPOOL, submit, validate_queue

QUEUE = os.environ['SCPPRINT_QUEUE']
HOST = os.environ.get('SCPPRINT_LISTEN', '0.0.0.0')
slots = asyncio.Semaphore(4)
logging.basicConfig(level=logging.INFO)


async def receive(reader, writer):
    path = None
    try:
        if slots.locked():
            return
        async with slots:
            total = 0
            with tempfile.NamedTemporaryFile(dir=SPOOL, delete=False) as spool:
                path = Path(spool.name)
                deadline = asyncio.get_running_loop().time() + 300
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError()
                    chunk = await asyncio.wait_for(reader.read(65536), timeout=min(30, remaining))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError('RAW job exceeds upload limit')
                    spool.write(chunk)
            if total:
                result = await asyncio.to_thread(submit, path, QUEUE, True)
                logging.info('RAW queued: %s', result)
    except Exception:
        logging.exception('RAW submission failed')
    finally:
        if path is not None:
            path.unlink(missing_ok=True)
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def main():
    validate_queue(QUEUE)
    server = await asyncio.start_server(receive, HOST, 9100)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
