"""
src/cdp/event_broadcaster.py

Central hub for event distribution from CDP monitors.
Handles emission to Firehose and broadcasting to WebSocket clients.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import WebSocket

from cdp.monitors.abstract_async_monitor import AbstractAsyncMonitor
from data_models.cdp.cdp_events import BaseCDPEvent, CDPEventWrapper
from data_models.websockets import (
    WebSocketSessionEndedResponse,
    WebSocketSnapshotResponse,
    WebSocketUpdateResponse,
    WebSocketUpdateEvent,
)
from env_config import APIEnvConfig
from utils.aws.firehose import firehose_send_event
from utils.aws.s3 import s3_client
from utils.logger import get_logger

logger = get_logger(name=__name__)


class EventBroadcaster:
    """
    Central hub for event distribution from CDP monitors.
    - Emits events to Firehose (existing behavior)
    - Broadcasts to connected WebSocket clients (new)
    - Tracks generic category-based accumulators for real-time stats
    - Optionally writes directly to S3 for immediate availability (bypassing Firehose's 60s buffer)
    """

    # Magic methods ________________________________________________________________________________________________________

    def __init__(
        self,
        cdp_captures_id: str,
        session_start_dtm: str,
        firehose_stream_name: str,
        broadcast_interval: float = 1.0,
    ) -> None:
        """
        Initialize EventBroadcaster.
        Args:
            cdp_captures_id: The CDP captures ID for this session.
            session_start_dtm: Session start datetime in format YYYY-MM-DDTHH-MM-SSZ.
            firehose_stream_name: The Firehose stream name to emit events to.
            broadcast_interval: Minimum interval between WebSocket broadcasts in seconds.
        """
        self.cdp_captures_id = cdp_captures_id
        self.session_start_dtm = session_start_dtm
        self.firehose_stream_name = firehose_stream_name
        self.broadcast_interval = broadcast_interval

        # S3 direct write configuration
        self.s3_bucket_name = APIEnvConfig.S3_CDP_CAPTURE_BUCKET_NAME
        self.s3_write_interval = APIEnvConfig.DIRECT_S3_WRITE_INTERVAL

        # generic category-based accumulators: category -> count
        self._event_counts: dict[str, int] = {}

        # WebSocket clients: ws -> set of subscribed categories (empty = all)
        self._ws_clients: dict[WebSocket, set[str]] = {}

        # lock for thread-safe operations on _ws_clients
        self._ws_lock = asyncio.Lock()

        # throttling state for WebSocket broadcasts
        self._last_broadcast_time = 0.0
        self._pending_events: list[dict[str, Any]] = []

        # S3 direct write state: category -> list of event wrappers
        self._s3_buffer: dict[str, list[dict[str, Any]]] = {}
        self._s3_lock = asyncio.Lock()
        self._last_s3_write_time = time.time()
        self._s3_flush_task: asyncio.Task | None = None

        # start periodic S3 flush task
        self._s3_flush_task = asyncio.create_task(
            coro=self._periodic_s3_flush()
        )

        # shutdown flag
        self._shutdown = False


    # Private methods ______________________________________________________________________________________________________

    ## Event handling (called by CDP monitors via callback)

    async def _handle_event(
        self, 
        category: str, 
        detail: BaseCDPEvent
    ) -> None:
        """
        Main event handler called by CDP monitors.
        Args:
            category: Event category (class name of the monitor, e.g., "AsyncNetworkMonitor").
            detail: CDP event model (NetworkTransactionEvent, StorageEvent, or WindowPropertyEvent).
        """
        # 1. always emit to Firehose (passes model, will dump inside)
        if not self._shutdown:
            await self._emit_to_firehose(category, detail)

        # 2. buffer for direct S3 writes (always enabled, continue buffering during shutdown for final flush)
        await self._buffer_for_s3(category, detail)

        # 3. update generic accumulator
        self._event_counts[category] = self._event_counts.get(category, 0) + 1

        # 4. buffer event for WebSocket broadcast (needs dict) - skip during shutdown
        if not self._shutdown:
            ws_summary = self._get_ws_event_summary(category, detail.model_dump())
            self._pending_events.append({
                "category": category,
                "summary": ws_summary,
                "timestamp": time.time(),
            })

            # 5. trigger throttled broadcast
            await self._maybe_broadcast()

    ## Firehose emission

    async def _emit_to_firehose(
        self, 
        category: str, 
        detail: BaseCDPEvent
    ) -> None:
        """
        Emit event to Firehose.
        Args:
            category: Event category (class name of the monitor).
            detail: CDP event model (subclass of BaseCDPEvent).
        """
        try:
            # convert model to dict (timestamp is already included from BaseCDPEvent)
            detail_dict = detail.model_dump()

            # create properly typed event wrapper
            event_wrapper = CDPEventWrapper(
                cdp_captures_id=self.cdp_captures_id,
                session_start_dtm=self.session_start_dtm,
                category=category,
                detail=detail_dict,
            )
            await firehose_send_event(
                stream_name=self.firehose_stream_name,
                event_record=event_wrapper.model_dump(),
            )
        except Exception as e:
            logger.error("❌ Error emitting to Firehose: %s", e)

    ## Direct S3 writes

    async def _buffer_for_s3(
        self,
        category: str,
        detail: BaseCDPEvent
    ) -> None:
        """
        Buffer event for direct S3 writes.
        Args:
            category: Event category (class name of the monitor).
            detail: CDP event model (subclass of BaseCDPEvent).
        """
        try:
            # convert model to dict
            detail_dict = detail.model_dump()

            # create event wrapper
            event_wrapper = CDPEventWrapper(
                cdp_captures_id=self.cdp_captures_id,
                session_start_dtm=self.session_start_dtm,
                category=category,
                detail=detail_dict,
            )

            # buffer by category
            async with self._s3_lock:
                if category not in self._s3_buffer:
                    self._s3_buffer[category] = []
                self._s3_buffer[category].append(event_wrapper.model_dump())

        except Exception as e:
            logger.error("❌ Error buffering event for S3: %s", e)

    async def _periodic_s3_flush(self) -> None:
        """
        Periodically flush S3 buffer to S3.
        """
        while not self._shutdown:
            try:
                await asyncio.sleep(
                    delay=self.s3_write_interval
                )
                await self._flush_s3_buffer()
            except asyncio.CancelledError:
                logger.info("📦 S3 flush task cancelled")
                break
            except Exception as e:
                logger.error("❌ Error in periodic S3 flush: %s", e)

    async def _flush_s3_buffer(self, allow_during_shutdown: bool = False) -> None:
        """
        Flush buffered events to S3 as .jsonl.gz files.
        Args:
            allow_during_shutdown: If True, allow flush even when _shutdown is True (for final flush).
        """
        if not allow_during_shutdown and self._shutdown:
            return

        if not self.s3_bucket_name:
            return

        async with self._s3_lock:
            if not self._s3_buffer:
                return

            # get snapshot of buffer and clear it
            buffer_snapshot = dict(self._s3_buffer)
            self._s3_buffer = {}
            self._last_s3_write_time = time.time()

        # write each category to its own file
        for category, events in buffer_snapshot.items():
            if not events:
                continue

            try:
                # create .jsonl content (one JSON per line)
                # use ensure_ascii=False to preserve Unicode characters (emojis, etc.)
                jsonl_lines = [json.dumps(event, ensure_ascii=False, default=str) for event in events]
                jsonl_content = "\n".join(jsonl_lines) + "\n"

                # compress with gzip
                gzipped_content = gzip.compress(
                    data=jsonl_content.encode(encoding="utf-8")
                )

                # create S3 key with flush-time timestamp for uniqueness
                # structure: direct_writes/{cdp_captures_id}/{session_start_dtm}/{category}/{timestamp}.jsonl.gz
                timestamp = datetime.now(timezone.utc).strftime(format="%Y%m%d-%H%M%S-%f")[:-3]  # milliseconds
                s3_key = str(
                    Path("direct_writes") / self.cdp_captures_id / self.session_start_dtm / category / f"{timestamp}.jsonl.gz"
                )

                # write to S3 (run in executor to avoid blocking)
                await asyncio.get_event_loop().run_in_executor(
                    executor=None,
                    func=lambda: s3_client.put_object(
                        Bucket=self.s3_bucket_name,
                        Key=s3_key,
                        Body=gzipped_content,
                        ContentType='application/gzip',
                        ContentEncoding='gzip',
                    )
                )
                logger.info(
                    "📦 Wrote %d events to S3: s3://%s/%s",
                    len(events),
                    self.s3_bucket_name,
                    s3_key
                )

            except Exception as e:
                logger.error("❌ Error writing to S3 for category %s: %s", category, e)

    ## WebSocket event summarization

    def _get_ws_event_summary(self, category: str, detail: dict) -> dict[str, Any]:
        """
        Get a lightweight summary of an event for WebSocket streaming.
        Delegates to the monitor's get_ws_event_summary method if found.
        Args:
            category: Event category (class name of the monitor, e.g., "AsyncNetworkMonitor").
            detail: Event detail dict.
        Returns:
            A simplified dict with only the fields relevant for WebSocket streaming.
        """
        # find monitor class by matching class name
        for monitor_class in AbstractAsyncMonitor.get_all_subclasses():
            if monitor_class.get_monitor_category() == category:
                return monitor_class.get_ws_event_summary(detail)

        # fallback: return a minimal summary
        logger.warning(
            "❌ No monitor class found for category: \"%s\" (options: %s)",
            category,
            [mc.get_monitor_category() for mc in AbstractAsyncMonitor.get_all_subclasses()],
        )
        return {"type": detail.get("type", "unknown")}

    ## WebSocket broadcasting

    def _build_snapshot_message(self) -> dict[str, Any]:
        """Build a snapshot message with current state."""
        resp = WebSocketSnapshotResponse(
            cdp_captures_id=self.cdp_captures_id,
            stats=self.get_current_stats(),
        )
        return resp.model_dump()

    def _build_update_message(self, events: list[dict]) -> dict[str, Any]:
        """Build an update message with stats and events."""
        # convert raw event dicts to WebSocketUpdateEvent models
        event_models = [
            WebSocketUpdateEvent(**event) for event in events
        ]
        resp = WebSocketUpdateResponse(
            stats=self.get_current_stats(),
            events=event_models,
        )
        return resp.model_dump()

    async def _maybe_broadcast(self) -> None:
        """Throttled broadcast to all WebSocket clients."""
        if self._shutdown:
            return

        async with self._ws_lock:
            if not self._ws_clients:
                # no clients, just clear buffer
                self._pending_events = []
                return

        now = time.time()
        if now - self._last_broadcast_time < self.broadcast_interval:
            return

        self._last_broadcast_time = now

        # get events and clear buffer
        events_to_send = self._pending_events[-50:]  # limit to last 50 events
        self._pending_events = []

        await self._broadcast_to_clients(events_to_send)

    async def _broadcast_to_clients(self, events: list[dict]) -> None:
        """Broadcast events to all subscribed WebSocket clients."""
        async with self._ws_lock:
            clients_copy = dict(self._ws_clients)

        if not clients_copy:
            return

        failed_clients: list[WebSocket] = []

        for ws, subscribed_categories in clients_copy.items():
            # filter events based on subscription
            if subscribed_categories:
                # client subscribed to specific categories
                filtered_events = [
                    e for e in events if e["category"] in subscribed_categories
                ]
            else:
                # client subscribed to all
                filtered_events = events

            message = self._build_update_message(filtered_events)
            success = await self._send_to_client_raw(ws, message)
            if not success:
                failed_clients.append(ws)

        # cleanup failed clients
        for ws in failed_clients:
            await self.unregister_ws_client(ws)

    async def _send_to_all(self, message: dict) -> None:
        """Send a message to all connected WebSocket clients."""
        async with self._ws_lock:
            clients = list(self._ws_clients.keys())

        failed_clients: list[WebSocket] = []
        for ws in clients:
            success = await self._send_to_client_raw(ws, message)
            if not success:
                failed_clients.append(ws)

        # cleanup failed clients
        for ws in failed_clients:
            await self.unregister_ws_client(ws)

    async def _send_to_client_raw(self, ws: WebSocket, message: dict) -> bool:
        """
        Send a message to a specific client without handling failures.
        Args:
            ws: The WebSocket connection.
            message: The message dict to send.
        Returns:
            True if send succeeded, False if it failed.
        """
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.debug("⚠️ Failed to send to WebSocket client: %s", e)
            return False

    async def _send_to_client(self, ws: WebSocket, message: dict) -> None:
        """Send a message to a specific client, unregistering on failure."""
        success = await self._send_to_client_raw(ws, message)
        if not success:
            await self.unregister_ws_client(ws)


    # Public methods _______________________________________________________________________________________________________

    async def register_ws_client(
        self,
        ws: WebSocket,
        subscribed_categories: set[str] | None = None,
    ) -> None:
        """
        Register a WebSocket client.
        Args:
            ws: The WebSocket connection.
            subscribed_categories: Set of categories to subscribe to. None or empty = all.
        """
        async with self._ws_lock:
            self._ws_clients[ws] = subscribed_categories or set()
        logger.info("📡 WebSocket client registered (total: %d)", len(self._ws_clients))

        # send initial snapshot
        await self._send_to_client(
            ws=ws,
            message=self._build_snapshot_message(),
        )

    async def unregister_ws_client(self, ws: WebSocket) -> None:
        """Unregister a WebSocket client."""
        async with self._ws_lock:
            self._ws_clients.pop(ws, None)
        logger.info("📡 WebSocket client unregistered (total: %d)", len(self._ws_clients))

    async def update_client_subscriptions(self, ws: WebSocket, categories: set[str]) -> None:
        """
        Update the subscribed categories for a WebSocket client.
        Args:
            ws: The WebSocket connection.
            categories: New set of class names to subscribe to. Empty = all.
        """
        async with self._ws_lock:
            if ws in self._ws_clients:
                self._ws_clients[ws] = categories
                logger.info("📡 Updated subscriptions for client: %s", categories or "all")

    def get_event_callback(self) -> Callable[[str, dict], Awaitable[None]]:
        """Return the callback function to pass to AsyncCDPSession."""
        return self._handle_event

    def get_current_stats(self) -> dict[str, Any]:
        """Return current accumulator stats."""
        return {
            "total_events": sum(self._event_counts.values()),
            "event_counts": dict(self._event_counts),
        }

    async def shutdown(self, reason: str = "Session ended", error_message: str | None = None) -> None:
        """
        Shutdown the broadcaster and disconnect all WebSocket clients.
        Sends a session-ended notification to all clients before closing connections.
        Called when session ends or times out.
        Args:
            reason: Human-readable reason for session end.
            error_message: Optional error message if the session ended due to an error.
        """
        self._shutdown = True
        logger.info("📡 Shutting down EventBroadcaster, disconnecting %d clients", len(self._ws_clients))

        # cancel S3 flush task and wait for it to handle cancellation
        if self._s3_flush_task:
            self._s3_flush_task.cancel()
            try:
                await self._s3_flush_task
            except asyncio.CancelledError:
                pass

        # flush any remaining S3 buffered events
        try:
            await self._flush_s3_buffer(allow_during_shutdown=True)
            logger.info("📦 Final S3 buffer flush completed")
        except Exception as e:
            logger.error("❌ Error during final S3 flush: %s", e)

        async with self._ws_lock:
            clients = list(self._ws_clients.keys())

        # send session-ended notification to all clients before closing
        session_ended_message = WebSocketSessionEndedResponse(
            reason=reason,
            error_message=error_message,
        ).model_dump()

        for ws in clients:
            try:
                # send structured notification before closing
                await self._send_to_client_raw(ws, session_ended_message)
            except Exception as e:
                logger.debug("⚠️ Error sending session-ended message to WebSocket: %s", e)

        # close all WebSocket connections
        for ws in clients:
            try:
                await ws.close(code=1000, reason=reason)
            except Exception as e:
                logger.debug("⚠️ Error closing WebSocket: %s", e)

        async with self._ws_lock:
            self._ws_clients.clear()
