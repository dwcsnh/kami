"""Bounded fan-out history: slow or absent clients never block the simulation."""
from __future__ import annotations

import asyncio
import json
import math
import threading
from collections import deque

TERMINAL = {"succeeded", "failed", "cancelled"}


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def frame(kind, data, sequence=None):
    prefix = f"id: {sequence}\n" if sequence is not None else ""
    return prefix + f"event: {kind}\ndata: " + json.dumps(clean(data), ensure_ascii=False, allow_nan=False) + "\n\n"


class Broker:
    def __init__(self, capacity=256):
        self.capacity = capacity
        self.history = deque(maxlen=capacity)
        self.sequence = 0
        self.lock = threading.Lock()

    def publish(self, run_id, kind, data):
        with self.lock:
            self.sequence += 1
            self.history.append((self.sequence, run_id, kind, clean(data)))

    def read(self, run_id, cursor):
        with self.lock:
            lost = bool(self.history and cursor < self.history[0][0] - 1)
            items = [x for x in self.history if x[0] > cursor and x[1] == run_id]
            return lost, items, self.sequence


async def events(supervisor, run_id, cursor, request):
    # Initial DB state allows reconnect after process restart or history eviction.
    state = supervisor.detail(run_id)
    yield frame("status", {"run_id": run_id, "status": state["status"], "progress": state["progress"]})
    if state["status"] in TERMINAL:
        yield frame("terminal", {"run_id": run_id, "status": state["status"], "error_code": state["error_code"]})
        return
    heartbeat = 0
    while not await request.is_disconnected():
        lost, items, latest = supervisor.broker.read(run_id, cursor)
        if lost or cursor > latest:
            yield frame("resync", {"run_id": run_id, "reason": "history_unavailable"})
        for seq, _, kind, data in items:
            yield frame(kind, data, seq)
            if kind == "terminal":
                return
        cursor = latest
        state = supervisor.detail(run_id)
        if state["status"] in TERMINAL:
            # DB commit is authoritative even if an IPC terminal frame was dropped.
            yield frame("terminal", {"run_id": run_id, "status": state["status"], "error_code": state["error_code"]})
            return
        heartbeat += 1
        if heartbeat >= 200:
            yield ": keepalive\n\n"
            heartbeat = 0
        await asyncio.sleep(0.05)
