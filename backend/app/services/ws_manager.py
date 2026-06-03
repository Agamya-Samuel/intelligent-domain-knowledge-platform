"""WebSocket connection manager — relays real-time training metrics to frontend clients.

Manages per-job WebSocket connections and broadcasts training events:
  - step:    Individual training step (loss, lr, step number)
  - epoch:   Epoch boundary with aggregate metrics
  - eval:    Evaluation results after training
  - complete: Job finished successfully
  - error:   Job failed with error details

The manager supports multiple clients per job (e.g., multiple browser
tabs or team members watching the same job).
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by job_id."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, job_id: str, ws: WebSocket) -> None:
        """Accept a WebSocket connection and register it for the given job."""
        await ws.accept()
        async with self._lock:
            self._connections[job_id].append(ws)
        logger.info("WS connected: job=%s (total=%d)", job_id, len(self._connections[job_id]))

    async def disconnect(self, job_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            conns = self._connections[job_id]
            if ws in conns:
                conns.remove(ws)
            if not conns:
                del self._connections[job_id]
        logger.info("WS disconnected: job=%s", job_id)

    async def broadcast(self, job_id: str, message: dict[str, Any]) -> None:
        """Send a message to all clients watching a specific job."""
        conns = self._connections.get(job_id, [])
        if not conns:
            return

        payload = json.dumps(message)
        stale: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        # Clean up broken connections
        if stale:
            async with self._lock:
                for ws in stale:
                    if ws in self._connections.get(job_id, []):
                        self._connections[job_id].remove(ws)

    async def send_event(
        self,
        job_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Convenience wrapper: broadcast a typed event to all job clients."""
        await self.broadcast(job_id, {"type": event_type, "job_id": job_id, "data": data})

    def active_jobs(self) -> list[str]:
        """Return list of job IDs with active connections."""
        return list(self._connections.keys())

    def connection_count(self, job_id: str) -> int:
        """Return number of active connections for a job."""
        return len(self._connections.get(job_id, []))


# Singleton instance used across the application
ws_manager = ConnectionManager()
