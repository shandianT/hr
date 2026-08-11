"""Deterministic workflow runner with durable step checkpoints.

The runner may submit SERVICE commands only.  It cannot construct or replay a
HUMAN decision on somebody's behalf.
"""

import copy
import hashlib
import json
import sqlite3
from typing import Any, Dict, List, Optional

from .control import RecruitingCaseControl


class SimulatedRunnerCrash(RuntimeError):
    """Fault-injection marker used to exercise the submit/checkpoint crash window."""


class DeterministicWorkflowRunner:
    """Run fixed automatic command steps through the control-plane Interface."""

    def __init__(self, control: RecruitingCaseControl, checkpoint_path: str):
        self._control = control
        self._db = sqlite3.connect(checkpoint_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS runner_runs (
                run_id TEXT PRIMARY KEY,
                workflow_version TEXT NOT NULL,
                run_epoch INTEGER NOT NULL,
                input_manifest_hash TEXT NOT NULL,
                commands_json TEXT NOT NULL,
                next_step_index INTEGER NOT NULL,
                current_step_id TEXT,
                next_step_id TEXT,
                state TEXT NOT NULL,
                last_result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._ensure_step_checkpoint_columns()
        self._db.commit()

    def start(self, workflow_version: str, commands: List[Dict[str, Any]]) -> str:
        if not workflow_version or not commands:
            raise ValueError("workflow_version and at least one command are required")
        if any(
            command.get("actor_context", {}).get("actor_type") != "SERVICE"
            for command in commands
        ):
            raise ValueError("runner can submit SERVICE commands only")
        manifest_hash = self._hash(commands)
        run_id = "run:" + hashlib.sha256(
            (workflow_version + "|" + manifest_hash).encode("utf-8")
        ).hexdigest()[:24]
        created_at = commands[0]["requested_at"]
        existing = self._db.execute(
            "SELECT input_manifest_hash, workflow_version FROM runner_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if existing:
            if existing["input_manifest_hash"] != manifest_hash or existing["workflow_version"] != workflow_version:
                raise ValueError("run id collision")
            return run_id
        self._db.execute(
            "INSERT INTO runner_runs "
            "(run_id, workflow_version, run_epoch, input_manifest_hash, commands_json, "
            "next_step_index, current_step_id, next_step_id, state, last_result_json, "
            "created_at, updated_at) "
            "VALUES (?, ?, 1, ?, ?, 0, NULL, ?, 'RUNNING', NULL, ?, ?)",
            (
                run_id,
                workflow_version,
                manifest_hash,
                self._json(commands),
                self._step_id(0, commands[0]),
                created_at,
                created_at,
            ),
        )
        self._db.commit()
        return run_id

    def tick(
        self,
        run_id: str,
        max_steps: int = 1,
        simulate_crash_after_submit: bool = False,
    ) -> Dict[str, Any]:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        row = self._load(run_id)
        if row["state"] == "COMPLETED":
            return self.read_run(run_id)
        commands = json.loads(row["commands_json"])
        next_index = row["next_step_index"]
        last_result = json.loads(row["last_result_json"]) if row["last_result_json"] else None
        steps_run = 0
        while next_index < len(commands) and steps_run < max_steps:
            command = copy.deepcopy(commands[next_index])
            step_id = row["next_step_id"] or self._step_id(next_index, command)
            command["idempotency_key"] = self._step_key(
                run_id,
                row["run_epoch"],
                row["workflow_version"],
                step_id,
                row["input_manifest_hash"],
            )
            if row["run_epoch"] > 1:
                command["command_id"] = self._resumed_command_id(
                    command.get("command_id", "command"),
                    run_id,
                    row["run_epoch"],
                    step_id,
                )
            if command.get("actor_context", {}).get("actor_type") != "SERVICE":
                raise ValueError("runner can submit SERVICE commands only")
            last_result = self._control.submit(command)
            if simulate_crash_after_submit:
                raise SimulatedRunnerCrash("command committed before runner checkpoint")
            if last_result["status"] not in {"APPLIED", "REPLAYED", "IGNORED_STALE"}:
                state = "NEEDS_HUMAN"
                self._save_progress(
                    row,
                    next_index,
                    state,
                    last_result,
                    command["requested_at"],
                    row["current_step_id"],
                    step_id,
                )
                return self.read_run(run_id)
            next_index += 1
            steps_run += 1
            state = "COMPLETED" if next_index == len(commands) else "RUNNING"
            next_step_id = (
                self._step_id(next_index, commands[next_index])
                if next_index < len(commands)
                else None
            )
            self._save_progress(
                row,
                next_index,
                state,
                last_result,
                command["requested_at"],
                step_id,
                next_step_id,
            )
            row = self._load(run_id)
        return self.read_run(run_id)

    def resume(self, run_id: str, resumed_at: Optional[str] = None) -> Dict[str, Any]:
        """Retry the blocked step in a fresh run epoch and idempotency context."""

        row = self._load(run_id)
        if row["state"] != "NEEDS_HUMAN":
            raise ValueError("only a NEEDS_HUMAN run can be resumed")
        commands = json.loads(row["commands_json"])
        next_index = row["next_step_index"]
        if next_index >= len(commands):
            raise ValueError("run has no blocked step to resume")
        next_step_id = row["next_step_id"] or self._step_id(
            next_index, commands[next_index]
        )
        self._db.execute(
            "UPDATE runner_runs SET run_epoch = ?, state = 'RUNNING', "
            "last_result_json = NULL, next_step_id = ?, updated_at = ? WHERE run_id = ?",
            (
                row["run_epoch"] + 1,
                next_step_id,
                resumed_at or row["updated_at"],
                run_id,
            ),
        )
        self._db.commit()
        return self.read_run(run_id)

    def read_run(self, run_id: str) -> Dict[str, Any]:
        row = self._load(run_id)
        last_result = json.loads(row["last_result_json"]) if row["last_result_json"] else None
        return {
            "run_id": row["run_id"],
            "workflow_version": row["workflow_version"],
            "run_epoch": row["run_epoch"],
            "input_manifest_hash": row["input_manifest_hash"],
            "next_step_index": row["next_step_index"],
            "current_step_id": row["current_step_id"],
            "next_step_id": row["next_step_id"],
            "state": row["state"],
            "last_command_status": last_result["status"] if last_result else None,
        }

    def _load(self, run_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM runner_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            raise KeyError("unknown run_id: " + run_id)
        return row

    def _save_progress(
        self,
        row: sqlite3.Row,
        next_index: int,
        state: str,
        result: Dict[str, Any],
        updated_at: str,
        current_step_id: Optional[str],
        next_step_id: Optional[str],
    ) -> None:
        self._db.execute(
            "UPDATE runner_runs SET next_step_index = ?, current_step_id = ?, "
            "next_step_id = ?, state = ?, last_result_json = ?, updated_at = ? "
            "WHERE run_id = ?",
            (
                next_index,
                current_step_id,
                next_step_id,
                state,
                self._json(result),
                updated_at,
                row["run_id"],
            ),
        )
        self._db.commit()

    @staticmethod
    def _step_key(run_id: str, run_epoch: int, workflow_version: str, step_id: str, manifest_hash: str) -> str:
        material = "{}|{}|{}|{}|{}".format(
            run_id, run_epoch, workflow_version, step_id, manifest_hash
        )
        return "runner:" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _step_id(step_index: int, command: Dict[str, Any]) -> str:
        command_type = command.get("command_type", "UNKNOWN")
        return "step:{:04d}:{}".format(step_index + 1, command_type)

    @staticmethod
    def _resumed_command_id(
        original_command_id: str,
        run_id: str,
        run_epoch: int,
        step_id: str,
    ) -> str:
        material = "{}|{}|{}|{}".format(
            original_command_id, run_id, run_epoch, step_id
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
        return "runner-command:" + digest

    def _ensure_step_checkpoint_columns(self) -> None:
        columns = {
            row["name"]
            for row in self._db.execute("PRAGMA table_info(runner_runs)").fetchall()
        }
        for name in ("current_step_id", "next_step_id"):
            if name not in columns:
                self._db.execute(
                    "ALTER TABLE runner_runs ADD COLUMN {} TEXT".format(name)
                )

        rows = self._db.execute(
            "SELECT run_id, commands_json, next_step_index, current_step_id, next_step_id "
            "FROM runner_runs"
        ).fetchall()
        for row in rows:
            if row["current_step_id"] is not None or row["next_step_id"] is not None:
                continue
            commands = json.loads(row["commands_json"])
            next_index = row["next_step_index"]
            current_step_id = (
                self._step_id(next_index - 1, commands[next_index - 1])
                if next_index > 0
                else None
            )
            next_step_id = (
                self._step_id(next_index, commands[next_index])
                if next_index < len(commands)
                else None
            )
            self._db.execute(
                "UPDATE runner_runs SET current_step_id = ?, next_step_id = ? "
                "WHERE run_id = ?",
                (current_step_id, next_step_id, row["run_id"]),
            )

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode("utf-8")).hexdigest()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
