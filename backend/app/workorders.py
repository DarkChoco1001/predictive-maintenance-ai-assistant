"""In-memory work order store (demo). A real deployment writes to the EAM/CMMS instead."""
from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime, timezone

from .schemas import WorkOrder, WorkOrderCreate

MAX_ORDERS = 200  # bounded so the demo cannot be filled until it runs out of memory


class WorkOrderStore:
    def __init__(self) -> None:
        self._orders: deque[WorkOrder] = deque(maxlen=MAX_ORDERS)
        self._lock = threading.Lock()

    def create(self, data: WorkOrderCreate) -> WorkOrder:
        order = WorkOrder(**data.model_dump(), id=uuid.uuid4().hex[:12], status="open",
                          created_at=datetime.now(timezone.utc))
        with self._lock:
            self._orders.appendleft(order)
        return order

    def list(self) -> list[WorkOrder]:
        with self._lock:
            return list(self._orders)
