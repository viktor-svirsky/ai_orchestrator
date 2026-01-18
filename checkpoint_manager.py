#!/usr/bin/env python3
"""
Checkpoint Manager for AI Orchestrator

Provides checkpoint/resume functionality for long-running workflows.
Allows continuation from any step if a failure or interruption occurs.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CheckpointData:
    """Represents a single checkpoint in the workflow."""

    step_id: str
    step_name: str
    timestamp: str
    status: str  # 'completed', 'failed', 'in_progress'
    data: Dict[str, Any]
    error: Optional[str] = None
    duration: float = 0.0


class CheckpointManager:
    """Manages workflow checkpoints for resume capability."""

    def __init__(self, workflow_id: str, output_dir: Optional[Path] = None):
        """
        Initialize checkpoint manager.

        Args:
            workflow_id: Unique identifier for this workflow run
            output_dir: Directory to store checkpoint files
        """
        self.workflow_id = workflow_id
        self.output_dir = output_dir or Path.cwd() / "checkpoints"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.output_dir / f"checkpoint_{workflow_id}.json"
        self.checkpoints: List[CheckpointData] = []
        self.load_checkpoints()

    def load_checkpoints(self) -> None:
        """Load existing checkpoints from file if they exist."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.checkpoints = [
                        CheckpointData(**cp) for cp in data.get("checkpoints", [])
                    ]
                logging.info(
                    f"Loaded {len(self.checkpoints)} checkpoints for workflow {self.workflow_id}"
                )
            except Exception as e:
                logging.error(f"Failed to load checkpoints: {e}")
                self.checkpoints = []

    def save_checkpoints(self) -> None:
        """Save all checkpoints to file."""
        try:
            data = {
                "workflow_id": self.workflow_id,
                "last_updated": datetime.now().isoformat(),
                "total_checkpoints": len(self.checkpoints),
                "checkpoints": [asdict(cp) for cp in self.checkpoints],
            }
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logging.debug(f"Saved checkpoint to {self.checkpoint_file}")
        except Exception as e:
            logging.error(f"Failed to save checkpoints: {e}")

    def create_checkpoint(
        self,
        step_id: str,
        step_name: str,
        status: str,
        data: Dict[str, Any],
        error: Optional[str] = None,
        duration: float = 0.0,
    ) -> CheckpointData:
        """
        Create a new checkpoint.

        Args:
            step_id: Unique identifier for this step (e.g., 'step_1', 'planning')
            step_name: Human-readable name
            status: Current status ('completed', 'failed', 'in_progress')
            data: Step data to persist
            error: Error message if failed
            duration: Time taken for this step

        Returns:
            The created checkpoint
        """
        checkpoint = CheckpointData(
            step_id=step_id,
            step_name=step_name,
            timestamp=datetime.now().isoformat(),
            status=status,
            data=data,
            error=error,
            duration=duration,
        )
        self.checkpoints.append(checkpoint)
        self.save_checkpoints()
        return checkpoint

    def get_checkpoint(self, step_id: str) -> Optional[CheckpointData]:
        """Get a specific checkpoint by step_id."""
        for cp in self.checkpoints:
            if cp.step_id == step_id:
                return cp
        return None

    def get_last_checkpoint(self) -> Optional[CheckpointData]:
        """Get the most recent checkpoint."""
        return self.checkpoints[-1] if self.checkpoints else None

    def get_completed_steps(self) -> List[str]:
        """Get list of completed step IDs."""
        return [cp.step_id for cp in self.checkpoints if cp.status == "completed"]

    def should_skip_step(self, step_id: str) -> bool:
        """Check if a step should be skipped (already completed)."""
        return step_id in self.get_completed_steps()

    def get_step_data(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get data from a completed step."""
        checkpoint = self.get_checkpoint(step_id)
        return checkpoint.data if checkpoint else None

    def mark_failed(self, step_id: str, error: str) -> None:
        """Mark a step as failed."""
        checkpoint = self.get_checkpoint(step_id)
        if checkpoint:
            checkpoint.status = "failed"
            checkpoint.error = error
            self.save_checkpoints()

    def mark_completed(self, step_id: str) -> None:
        """Mark a step as completed."""
        checkpoint = self.get_checkpoint(step_id)
        if checkpoint:
            checkpoint.status = "completed"
            self.save_checkpoints()

    def can_resume(self) -> bool:
        """Check if workflow can be resumed from checkpoints."""
        return len(self.checkpoints) > 0

    def get_resume_point(self) -> Optional[str]:
        """Get the step ID where workflow should resume."""
        if not self.checkpoints:
            return None

        # Find first non-completed step
        completed = set(self.get_completed_steps())
        workflow_steps = [
            "planning",
            "coding",
            "testing",
            "reviewing",
            "refining",
            "documenting",
        ]

        for step in workflow_steps:
            if step not in completed:
                return step

        return None  # All steps completed

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of checkpoint status."""
        total = len(self.checkpoints)
        completed = len([cp for cp in self.checkpoints if cp.status == "completed"])
        failed = len([cp for cp in self.checkpoints if cp.status == "failed"])
        in_progress = len([cp for cp in self.checkpoints if cp.status == "in_progress"])

        return {
            "workflow_id": self.workflow_id,
            "total_checkpoints": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "can_resume": self.can_resume(),
            "resume_point": self.get_resume_point(),
            "last_checkpoint": asdict(self.checkpoints[-1])
            if self.checkpoints
            else None,
        }

    def clear_checkpoints(self) -> None:
        """Clear all checkpoints (start fresh)."""
        self.checkpoints = []
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        logging.info(f"Cleared checkpoints for workflow {self.workflow_id}")

    def export_to_file(self, filepath: Path) -> None:
        """Export checkpoints to a custom file location."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "workflow_id": self.workflow_id,
                        "exported_at": datetime.now().isoformat(),
                        "checkpoints": [asdict(cp) for cp in self.checkpoints],
                    },
                    f,
                    indent=2,
                )
            logging.info(f"Exported checkpoints to {filepath}")
        except Exception as e:
            logging.error(f"Failed to export checkpoints: {e}")


class WorkflowRecovery:
    """Handles recovery of failed workflows using checkpoints."""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    def get_recovery_plan(self) -> Dict[str, Any]:
        """Generate a recovery plan based on checkpoints."""
        summary = self.checkpoint_manager.get_summary()

        recovery_plan = {
            "can_recover": summary["can_resume"],
            "resume_from": summary["resume_point"],
            "completed_steps": self.checkpoint_manager.get_completed_steps(),
            "failed_steps": [
                cp.step_id
                for cp in self.checkpoint_manager.checkpoints
                if cp.status == "failed"
            ],
            "recommendations": [],
        }

        # Add recommendations
        if recovery_plan["failed_steps"]:
            recovery_plan["recommendations"].append(
                f"Review errors in failed steps: {', '.join(recovery_plan['failed_steps'])}"
            )

        if recovery_plan["resume_from"]:
            recovery_plan["recommendations"].append(
                f"Resume workflow from step: {recovery_plan['resume_from']}"
            )

        return recovery_plan

    def can_use_cached_step(self, step_id: str) -> bool:
        """Check if a step's cached result can be reused."""
        checkpoint = self.checkpoint_manager.get_checkpoint(step_id)
        if not checkpoint:
            return False

        return checkpoint.status == "completed" and checkpoint.data is not None

    def get_cached_result(self, step_id: str) -> Optional[Any]:
        """Get cached result from a completed step."""
        if not self.can_use_cached_step(step_id):
            return None

        checkpoint = self.checkpoint_manager.get_checkpoint(step_id)
        return checkpoint.data if checkpoint else None


def create_workflow_checkpoint_manager(
    prompt: str, mode: str = "workflow", output_dir: Optional[Path] = None
) -> CheckpointManager:
    """
    Factory function to create a checkpoint manager for a workflow.

    Args:
        prompt: The workflow prompt (used to generate workflow_id)
        mode: Workflow mode
        output_dir: Output directory for checkpoints

    Returns:
        Configured CheckpointManager instance
    """
    # Generate a simple workflow ID from prompt hash and timestamp
    import hashlib

    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workflow_id = f"{mode}_{prompt_hash}_{timestamp}"

    return CheckpointManager(workflow_id, output_dir)
