"""WebSocket endpoints — real-time fine-tuning metrics relay.

WS /ws/fine-tune/{job_id}
  Authenticates via JWT token query parameter, then streams
  real-time training events (step, epoch, eval, complete, error)
  to the connected client.

Authentication:
  The client passes the JWT token as a query parameter:
    ws://host/ws/fine-tune/{job_id}?token=<jwt>

Message types:
  step     — {step, loss, learning_rate, epoch}
  epoch    — {epoch, avg_loss, eval_loss}
  eval     — {faithfulness, context_relevance, answer_relevance, context_recall}
  complete — {final_loss, adapter_path, cost, duration_seconds}
  error    — {message, stage}
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import verify_token
from app.dependencies import get_db_context
from app.models.fine_tuning_job import FineTuningJob
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/fine-tune/{job_id}")
async def fine_tune_ws(websocket: WebSocket, job_id: str) -> None:
    """
    WebSocket endpoint for real-time fine-tuning job metrics.

    Flow:
      1. Authenticate via JWT token query param
      2. Validate the job exists
      3. Register connection with the ws_manager
      4. Keep connection alive; relay events from training service
      5. Clean up on disconnect
    """
    # 1. Authenticate
    token = websocket.query_params.get("token", "")
    user_id: str | None = None
    if token:
        try:
            payload = verify_token(token)
            user_id = payload.get("sub") if isinstance(payload, dict) else None
        except Exception:
            pass

    if not user_id:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # 2. Validate job exists
    async with get_db_context() as db:
        result = await db.execute(
            select(FineTuningJob).where(FineTuningJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            await websocket.close(code=4004, reason="Job not found")
            return

        # Send initial job state
        await websocket.accept()
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "data": {
                "status": job.status,
                "model_id": job.model_id,
                "dataset_id": job.dataset_id,
                "queue_position": job.queue_position,
                "training_metrics": job.training_metrics,
                "eval_report": job.eval_report,
            },
        })

    # 3. Register with connection manager
    await ws_manager.connect(job_id, websocket)

    try:
        # 4. Keep connection alive — listen for client messages (ping/pong)
        while True:
            data = await websocket.receive_text()
            # Client can send "ping" for keepalive
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await ws_manager.disconnect(job_id, websocket)
    except Exception as exc:
        logger.warning("WS error for job %s: %s", job_id, exc)
        await ws_manager.disconnect(job_id, websocket)
