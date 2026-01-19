"""
web_hacker/cdp/__init__.py

CDP (Chrome DevTools Protocol) monitoring package.
Provides async CDP session management and event monitoring.

Primary classes:
- AsyncCDPSession: Async CDP session for browser monitoring
- FileEventWriter: Callback adapter for writing events to files
"""

from web_hacker.cdp.async_cdp_session import AsyncCDPSession
from web_hacker.cdp.file_event_writer import FileEventWriter
from web_hacker.cdp.data_models import (
    BaseCDPEvent,
    NetworkTransactionEvent,
    StorageEvent,
    WindowPropertyChange,
    WindowPropertyEvent,
)

__all__ = [
    "AsyncCDPSession",
    "FileEventWriter",
    "BaseCDPEvent",
    "NetworkTransactionEvent",
    "StorageEvent",
    "WindowPropertyChange",
    "WindowPropertyEvent",
]
