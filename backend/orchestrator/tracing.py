"""Execution tracing for the orchestrator.

Records one :class:`StageTrace` per pipeline stage with wall-clock timing. The **structure**
(stage names, statuses, order) is deterministic and used for determinism checks; the timing
fields are wall-clock and therefore excluded from any determinism comparison.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from enum import Enum

from pydantic import BaseModel, ConfigDict


class StageStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: StageStatus
    start_ms: float = 0.0
    end_ms: float = 0.0
    duration_ms: float = 0.0


class ExecutionTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    stages: tuple[StageTrace, ...] = ()
    total_duration_ms: float = 0.0

    def stage_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.stages)

    def stage(self, name: str) -> StageTrace | None:
        return next((s for s in self.stages if s.name == name), None)

    def structure(self) -> tuple[tuple[str, str], ...]:
        """Timing-free (name, status) view — the deterministic part of the trace."""
        return tuple((s.name, s.status.value) for s in self.stages)


class Tracer:
    """Accumulates stage traces. Use ``with tracer.stage(name): ...`` per stage."""

    def __init__(self) -> None:
        self._stages: list[StageTrace] = []
        self._t0 = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        except BaseException:
            self._record(name, StageStatus.FAILED, start)
            raise
        else:
            self._record(name, StageStatus.SUCCESS, start)

    def _record(self, name: str, status: StageStatus, start: float) -> None:
        end = time.perf_counter()
        self._stages.append(StageTrace(
            name=name, status=status,
            start_ms=round((start - self._t0) * 1000, 3),
            end_ms=round((end - self._t0) * 1000, 3),
            duration_ms=round((end - start) * 1000, 3)))

    def build(self) -> ExecutionTrace:
        total = round((time.perf_counter() - self._t0) * 1000, 3)
        return ExecutionTrace(stages=tuple(self._stages), total_duration_ms=total)

    def per_stage_ms(self) -> dict[str, float]:
        return {s.name: s.duration_ms for s in self._stages}
