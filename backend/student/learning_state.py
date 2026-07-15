"""Deterministic concept-level learning-state machine.

No scheduling, no spaced repetition, no time. State changes are driven only by explicit
:class:`LearningSignal` events through a fixed transition table, so every transition is
deterministic and explainable. ``derive_state`` computes a state from observable profile
signals for concepts without an explicit state.

The :class:`LearningState` enum lives here (the state machine owns it); ``models.py``
imports it, keeping the dependency one-directional.
"""

from __future__ import annotations

from enum import Enum


class LearningState(str, Enum):
    """Where a student stands on a single concept."""

    UNSEEN = "unseen"
    INTRODUCED = "introduced"
    PRACTICING = "practicing"
    MASTERED = "mastered"
    FORGOTTEN = "forgotten"
    NEEDS_REVIEW = "needs_review"


class LearningSignal(str, Enum):
    """An explicit learning event that can move a concept's state."""

    INTRODUCE = "introduce"
    PRACTICE_SUCCESS = "practice_success"
    PRACTICE_FAILURE = "practice_failure"
    REVIEW = "review"
    DECAY = "decay"
    RESET = "reset"


# Fixed transition table: (state, signal) -> next state. Any pair not listed leaves the
# state unchanged (see ``transition``). Deterministic and total.
_TABLE: dict[tuple[LearningState, LearningSignal], LearningState] = {
    (LearningState.UNSEEN, LearningSignal.INTRODUCE): LearningState.INTRODUCED,

    (LearningState.INTRODUCED, LearningSignal.PRACTICE_SUCCESS): LearningState.PRACTICING,
    (LearningState.INTRODUCED, LearningSignal.PRACTICE_FAILURE): LearningState.INTRODUCED,
    (LearningState.INTRODUCED, LearningSignal.REVIEW): LearningState.INTRODUCED,

    (LearningState.PRACTICING, LearningSignal.PRACTICE_SUCCESS): LearningState.MASTERED,
    (LearningState.PRACTICING, LearningSignal.PRACTICE_FAILURE): LearningState.PRACTICING,
    (LearningState.PRACTICING, LearningSignal.REVIEW): LearningState.PRACTICING,

    (LearningState.MASTERED, LearningSignal.PRACTICE_SUCCESS): LearningState.MASTERED,
    (LearningState.MASTERED, LearningSignal.DECAY): LearningState.FORGOTTEN,
    (LearningState.MASTERED, LearningSignal.REVIEW): LearningState.MASTERED,

    (LearningState.FORGOTTEN, LearningSignal.REVIEW): LearningState.NEEDS_REVIEW,
    (LearningState.FORGOTTEN, LearningSignal.INTRODUCE): LearningState.INTRODUCED,

    (LearningState.NEEDS_REVIEW, LearningSignal.PRACTICE_SUCCESS): LearningState.MASTERED,
    (LearningState.NEEDS_REVIEW, LearningSignal.PRACTICE_FAILURE): LearningState.PRACTICING,
    (LearningState.NEEDS_REVIEW, LearningSignal.REVIEW): LearningState.NEEDS_REVIEW,
}

# Any state + RESET returns to UNSEEN.
_RESET_TARGET = LearningState.UNSEEN

# Mastery thresholds for deriving a state when none is stored explicitly.
_PRACTICING_THRESHOLD = 0.3
_MASTERED_THRESHOLD = 0.8


def transition(state: LearningState, signal: LearningSignal) -> tuple[LearningState, str]:
    """Return ``(next_state, reason)`` for applying ``signal`` to ``state``.

    Deterministic and total: an undefined (state, signal) pair leaves the state unchanged.
    """
    if signal == LearningSignal.RESET:
        return _RESET_TARGET, f"{state.value} + reset -> {_RESET_TARGET.value}"
    nxt = _TABLE.get((state, signal))
    if nxt is None:
        return state, f"no transition for ({state.value}, {signal.value}); unchanged"
    return nxt, f"{state.value} + {signal.value} -> {nxt.value}"


def derive_state(
    mastery: float, seen: bool, completed: bool, needs_review: bool = False
) -> LearningState:
    """Derive a learning state from observable profile signals (no time involved).

    ``forgotten`` is only ever reached via an explicit signal/stored state — it cannot be
    inferred from these inputs, so it is never returned here.
    """
    if needs_review:
        return LearningState.NEEDS_REVIEW
    if not seen:
        return LearningState.UNSEEN
    if completed and mastery >= _MASTERED_THRESHOLD:
        return LearningState.MASTERED
    if mastery >= _MASTERED_THRESHOLD:
        return LearningState.MASTERED
    if mastery >= _PRACTICING_THRESHOLD:
        return LearningState.PRACTICING
    return LearningState.INTRODUCED
