# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# Public Preview — basic implementation
"""Execution checkpoints with in-memory replay lookup semantics."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class SemanticCheckpoint:
    """A checkpoint record used to skip already achieved saga goals."""

    checkpoint_id: str = field(default_factory=lambda: f"ckpt:{uuid.uuid4().hex[:8]}")
    saga_id: str = ""
    step_id: str = ""
    goal_description: str = ""
    goal_hash: str = ""
    achieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    invalidated_reason: str | None = None

    @staticmethod
    def compute_goal_hash(goal: str, step_id: str) -> str:
        """Compute deterministic hash for a goal."""
        content = f"{goal}:{step_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class CheckpointManager:
    """In-memory checkpoint manager for saga replay planning."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, list[SemanticCheckpoint]] = {}
        self._by_goal_hash: dict[str, SemanticCheckpoint] = {}

    def save(
        self,
        saga_id: str,
        step_id: str,
        goal_description: str,
        state_snapshot: dict[str, Any] | None = None,
    ) -> SemanticCheckpoint:
        """Save a checkpoint record."""
        goal_hash = SemanticCheckpoint.compute_goal_hash(goal_description, step_id)
        checkpoint = SemanticCheckpoint(
            saga_id=saga_id,
            step_id=step_id,
            goal_description=goal_description,
            goal_hash=goal_hash,
            state_snapshot=state_snapshot or {},
        )
        self._checkpoints.setdefault(saga_id, []).append(checkpoint)
        self._by_goal_hash[goal_hash] = checkpoint
        return checkpoint

    def is_achieved(
        self,
        saga_id: str,
        goal_description: str,
        step_id: str,
    ) -> bool:
        """Return whether a valid checkpoint exists for this goal."""
        checkpoint = self.get_checkpoint(saga_id, goal_description, step_id)
        return checkpoint is not None

    def get_checkpoint(
        self,
        saga_id: str,
        goal_description: str,
        step_id: str,
    ) -> SemanticCheckpoint | None:
        """Return the valid checkpoint for this goal, if any."""
        goal_hash = SemanticCheckpoint.compute_goal_hash(goal_description, step_id)
        checkpoint = self._by_goal_hash.get(goal_hash)
        if checkpoint is None:
            return None
        if checkpoint.saga_id != saga_id or checkpoint.step_id != step_id:
            return None
        if not checkpoint.is_valid:
            return None
        return checkpoint

    def invalidate(
        self,
        saga_id: str,
        step_id: str,
        reason: str = "",
    ) -> int:
        """Invalidate checkpoints for a saga step."""
        count = 0
        for checkpoint in self._checkpoints.get(saga_id, []):
            if checkpoint.step_id != step_id or not checkpoint.is_valid:
                continue
            checkpoint.is_valid = False
            checkpoint.invalidated_reason = reason
            count += 1
        return count

    def get_saga_checkpoints(self, saga_id: str) -> list[SemanticCheckpoint]:
        """Get all checkpoints for a saga."""
        return list(self._checkpoints.get(saga_id, []))

    def get_replay_plan(self, saga_id: str, steps: list[str]) -> list[str]:
        """Return step ids that do not have a valid checkpoint."""
        valid_step_ids = {
            checkpoint.step_id
            for checkpoint in self._checkpoints.get(saga_id, [])
            if checkpoint.is_valid
        }
        return [step_id for step_id in steps if step_id not in valid_step_ids]

    @property
    def total_checkpoints(self) -> int:
        return sum(len(v) for v in self._checkpoints.values())

    @property
    def valid_checkpoints(self) -> int:
        return sum(
            1
            for checkpoints in self._checkpoints.values()
            for checkpoint in checkpoints
            if checkpoint.is_valid
        )
