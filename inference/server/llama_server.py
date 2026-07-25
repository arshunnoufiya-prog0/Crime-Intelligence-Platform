import asyncio
import logging
import os
import signal
import time

import httpx

from .config import settings

logger = logging.getLogger("inference.llama_server")


def _build_command() -> list[str]:
    bin_path = settings.llama_server_bin
    if not os.path.exists(bin_path):
        logger.warning("llama-server binary not found at %s (expected build artifact)", bin_path)
    return [
        bin_path,
        "--model", settings.model_path,
        "--ctx-size", str(settings.ctx_size),
        "--n-gpu-layers", str(settings.n_gpu_layers),
        "--n-parallel", str(settings.n_parallel),
        "--batch-size", str(settings.batch_size),
        "--ubatch-size", str(settings.ubatch_size),
        "--threads", str(settings.threads),
        "--flash-attn" if settings.flash_attn else "--no-flash-attn",
        "--cont-batching",
        "--mlock",
        "--mmap",
        "--host", settings.host,
        "--port", str(settings.port),
        "--chat-template", "chatml",
    ]


async def _wait_for_health(timeout_s: int = 60, poll_s: float = 2.0) -> None:
    url = f"http://{settings.host}:{settings.port}/health"
    deadline = time.monotonic() + timeout_s
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(url, timeout=3.0)
                if r.status_code == 200:
                    logger.info("llama-server healthy at %s", url)
                    return
            except Exception:
                pass
            await asyncio.sleep(poll_s)
    raise RuntimeError(f"llama-server did not become healthy within {timeout_s}s")


class LlamaServerManager:
    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_tasks: list[asyncio.Task] = []
        self._alive = False

    async def start(self) -> None:
        backoffs = [2, 4, 8]
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                cmd = _build_command()
                logger.info("starting llama-server (attempt %d): %s", attempt + 1, " ".join(cmd))
                self._proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                self._alive = True
                self._reader_tasks.append(asyncio.create_task(self._read_stream()))
                await _wait_for_health()
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.error("llama-server start failed (attempt %d): %s", attempt + 1, exc)
                await self.stop()
                if attempt < 2:
                    await asyncio.sleep(backoffs[attempt])
        raise RuntimeError(f"llama-server failed to start after 3 attempts: {last_err}")

    async def _read_stream(self) -> None:
        if self._proc is None or self._proc.stdout is None:
            return
        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    break
                logger.info("[llama-server] %s", line.decode("utf-8", "replace").rstrip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("stdout reader ended: %s", exc)
        finally:
            self._alive = False

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        for t in self._reader_tasks:
            t.cancel()
        self._reader_tasks = []
        self._proc = None
        self._alive = False

    @property
    def alive(self) -> bool:
        return self._alive and self._proc is not None and self._proc.returncode is None


llama_manager = LlamaServerManager()
