"""Bounded document-processing queue for webhook bursts."""

import asyncio
import logging
import os
from contextlib import suppress

from webhooks.service.processor import process_document


logger = logging.getLogger(__name__)


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


class DocumentQueue:
    def __init__(self):
        self.max_size = _env_int("WEBHOOK_QUEUE_MAX_SIZE", 100)
        self.worker_count = _env_int("WEBHOOK_QUEUE_WORKERS", 2)
        self.max_attempts = _env_int("WEBHOOK_QUEUE_MAX_ATTEMPTS", 3)
        self.retry_delay_seconds = _env_int("WEBHOOK_QUEUE_RETRY_DELAY_SECONDS", 2)
        self._queue = asyncio.Queue(maxsize=self.max_size)
        self._workers = []
        self._started = False
        self._processed = 0
        self._failed = 0

    async def start(self):
        if self._started:
            return

        self._started = True
        self._workers = [
            asyncio.create_task(self._worker(index + 1))
            for index in range(self.worker_count)
        ]
        logger.info("Started %s document webhook worker(s)", self.worker_count)

    async def stop(self):
        if not self._started:
            return

        self._started = False
        for worker in self._workers:
            worker.cancel()

        for worker in self._workers:
            with suppress(asyncio.CancelledError):
                await worker

        self._workers = []

    def enqueue(self, document, attempt=1):
        if self._queue.full():
            return False

        self._queue.put_nowait({"document": document, "attempt": attempt})
        return True

    def status(self):
        return {
            "queued": self._queue.qsize(),
            "max_size": self.max_size,
            "workers": self.worker_count,
            "processed": self._processed,
            "failed": self._failed,
            "started": self._started,
        }

    async def _worker(self, worker_id):
        while True:
            job = await self._queue.get()
            try:
                await self._handle_job(job, worker_id)
            finally:
                self._queue.task_done()

    async def _handle_job(self, job, worker_id):
        document = job["document"]
        attempt = job["attempt"]
        file_id = document.get("file_id")

        try:
            await process_document(document)
            self._processed += 1
            logger.info("Worker %s processed document %s", worker_id, file_id)
        except Exception:
            if attempt >= self.max_attempts:
                self._failed += 1
                logger.exception("Document %s failed after %s attempt(s)", file_id, attempt)
                return

            logger.exception("Document %s failed on attempt %s; retrying", file_id, attempt)
            await asyncio.sleep(self.retry_delay_seconds)
            if not self.enqueue(document, attempt=attempt + 1):
                self._failed += 1
                logger.error("Document %s retry dropped because the queue is full", file_id)


document_queue = DocumentQueue()
