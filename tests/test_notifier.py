from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from windows_notify_codex.notifier import CodexNotifier, FileCursor


def write_jsonl(path: Path, records: list[dict[str, object]], mode: str = "w") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def session_meta(session_id: str, **extra: object) -> dict[str, object]:
    payload = {
        "id": session_id,
        "cwd": r"C:\Users\lemondoo\PROJECTS\demo",
        "source": "vscode",
        "originator": "panes",
        "cli_version": "0.131.0",
    }
    payload.update(extra)
    return {
        "timestamp": "2026-06-26T19:15:19.389Z",
        "type": "session_meta",
        "payload": payload,
    }


def live_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class RecordingNotifier(CodexNotifier):
    def __init__(self, sessions_root: Path, log_path: Path) -> None:
        super().__init__(sessions_root=sessions_root, log_path=log_path)
        self.completions: list[dict[str, object]] = []
        self.prompts: list[dict[str, object]] = []

    def _record_completion(
        self,
        session,
        rollout_path: Path,
        turn_id: str | None,
        event_time: str,
        last_message: str,
    ) -> None:
        self.completions.append(
            {
                "session_id": session.session_id,
                "turn_id": turn_id,
                "event_time": event_time,
                "last_message": last_message,
                "rollout_path": str(rollout_path),
            }
        )

    def _record_prompt(
        self,
        session,
        rollout_path: Path,
        prompt_id: str,
        prompt_kind: str,
        event_time: str,
        message: str,
    ) -> None:
        self.prompts.append(
            {
                "session_id": session.session_id,
                "prompt_id": prompt_id,
                "prompt_kind": prompt_kind,
                "event_time": event_time,
                "message": message,
                "rollout_path": str(rollout_path),
            }
        )


class NotifierPrimingTests(unittest.TestCase):
    def test_fork_session_meta_indexes_source_turn_ids_to_suppress_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            sessions_root = temp_root / "sessions"
            log_path = temp_root / "codex-completions.jsonl"
            source_path = (
                sessions_root
                / "2026"
                / "06"
                / "24"
                / "rollout-2026-06-24T23-38-48-source-session.jsonl"
            )
            fork_path = (
                sessions_root
                / "2026"
                / "06"
                / "26"
                / "rollout-2026-06-26T19-15-19-fork-session.jsonl"
            )

            write_jsonl(
                source_path,
                [
                    session_meta("source-session"),
                    {
                        "timestamp": "2026-06-24T23:38:48.816Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": "old-turn",
                            "last_agent_message": "Historical completion",
                        },
                    },
                ],
            )

            notifier = RecordingNotifier(sessions_root=sessions_root, log_path=log_path)
            notifier.prime_existing_files()

            self.assertNotIn("old-turn", notifier._seen_turn_ids)
            self.assertEqual(notifier.completions, [])

            write_jsonl(
                fork_path,
                [session_meta("fork-session", forked_from_id="source-session")],
            )

            cursor = notifier._files.setdefault(fork_path, FileCursor())
            notifier._read_new_lines(fork_path, cursor, notify=False)
            cursor.initialized = True
            self.assertIn("old-turn", notifier._seen_turn_ids)

            write_jsonl(
                fork_path,
                [
                    {
                        "timestamp": "2026-06-26T19:15:25.601Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": "old-turn",
                            "last_agent_message": "Historical completion replayed by fork",
                        },
                    }
                ],
                mode="a",
            )
            notifier._read_new_lines(fork_path, cursor, notify=True)
            self.assertEqual(notifier.completions, [])

            write_jsonl(
                fork_path,
                [
                    {
                        "timestamp": live_timestamp(),
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": "new-turn",
                            "last_agent_message": "Fresh fork completion",
                        },
                    }
                ],
                mode="a",
            )
            notifier._read_new_lines(fork_path, cursor, notify=True)

            self.assertEqual([record["turn_id"] for record in notifier.completions], ["new-turn"])

    def test_fork_session_meta_indexes_source_prompt_ids_to_suppress_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            sessions_root = temp_root / "sessions"
            log_path = temp_root / "codex-completions.jsonl"
            source_path = (
                sessions_root
                / "2026"
                / "06"
                / "24"
                / "rollout-2026-06-24T23-00-00-source-session.jsonl"
            )
            fork_path = (
                sessions_root
                / "2026"
                / "06"
                / "26"
                / "rollout-2026-06-26T19-15-19-fork-session.jsonl"
            )

            write_jsonl(
                source_path,
                [
                    session_meta("source-session"),
                    {
                        "timestamp": "2026-06-24T23:00:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "old-prompt",
                        },
                    },
                ],
            )

            notifier = RecordingNotifier(sessions_root=sessions_root, log_path=log_path)
            notifier.prime_existing_files()

            self.assertNotIn("old-prompt", notifier._seen_prompt_ids)
            self.assertEqual(notifier.prompts, [])

            write_jsonl(
                fork_path,
                [session_meta("fork-session", forked_from_id="source-session")],
            )

            cursor = notifier._files.setdefault(fork_path, FileCursor())
            notifier._read_new_lines(fork_path, cursor, notify=False)
            cursor.initialized = True
            self.assertIn("old-prompt", notifier._seen_prompt_ids)

            write_jsonl(
                fork_path,
                [
                    {
                        "timestamp": "2026-06-26T19:15:25.601Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "old-prompt",
                        },
                    }
                ],
                mode="a",
            )
            notifier._read_new_lines(fork_path, cursor, notify=True)
            self.assertEqual(notifier.prompts, [])

            write_jsonl(
                fork_path,
                [
                    {
                        "timestamp": live_timestamp(),
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "new-prompt",
                        },
                    }
                ],
                mode="a",
            )
            notifier._read_new_lines(fork_path, cursor, notify=True)

            self.assertEqual([record["prompt_id"] for record in notifier.prompts], ["new-prompt"])

    def test_restart_primes_seen_ids_from_completion_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            sessions_root = temp_root / "sessions"
            log_path = temp_root / "codex-completions.jsonl"
            rollout_path = (
                sessions_root
                / "2026"
                / "06"
                / "26"
                / "rollout-2026-06-26T19-15-19-session-a.jsonl"
            )

            write_jsonl(
                log_path,
                [
                    {
                        "turn_id": "logged-turn",
                        "prompt_id": "logged-prompt",
                    }
                ],
            )
            write_jsonl(rollout_path, [session_meta("session-a")])

            notifier = RecordingNotifier(sessions_root=sessions_root, log_path=log_path)
            notifier.prime_existing_files()

            self.assertIn("logged-turn", notifier._seen_turn_ids)
            self.assertIn("logged-prompt", notifier._seen_prompt_ids)

            cursor = notifier._files.setdefault(rollout_path, FileCursor())
            notifier._read_new_lines(rollout_path, cursor, notify=False)
            cursor.initialized = True

            write_jsonl(
                rollout_path,
                [
                    {
                        "timestamp": "2026-06-26T19:16:00.000Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": "logged-turn",
                            "last_agent_message": "Duplicate completion",
                        },
                    },
                    {
                        "timestamp": "2026-06-26T19:16:10.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "logged-prompt",
                        },
                    },
                ],
                mode="a",
            )
            notifier._read_new_lines(rollout_path, cursor, notify=True)

            self.assertEqual(notifier.completions, [])
            self.assertEqual(notifier.prompts, [])

    def test_old_unseen_events_appended_to_watched_file_are_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            sessions_root = temp_root / "sessions"
            log_path = temp_root / "codex-completions.jsonl"
            rollout_path = (
                sessions_root
                / "2026"
                / "09"
                / "09"
                / "rollout-2026-09-09T17-00-00-session-a.jsonl"
            )

            write_jsonl(rollout_path, [session_meta("session-a")])
            notifier = RecordingNotifier(sessions_root=sessions_root, log_path=log_path)
            notifier.prime_existing_files()
            cursor = notifier._files[rollout_path]

            write_jsonl(
                rollout_path,
                [
                    {
                        "timestamp": "2026-05-20T11:50:08.052Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "replayed-old-prompt",
                        },
                    },
                    {
                        "timestamp": "2026-05-20T11:52:13.493Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": "replayed-old-turn",
                            "last_agent_message": "Historical completion replayed after a workspace move",
                        },
                    },
                ],
                mode="a",
            )
            notifier._read_new_lines(rollout_path, cursor, notify=True)

            self.assertEqual(notifier.prompts, [])
            self.assertEqual(notifier.completions, [])
            self.assertIn("replayed-old-prompt", notifier._seen_prompt_ids)
            self.assertIn("replayed-old-turn", notifier._seen_turn_ids)

            write_jsonl(
                rollout_path,
                [
                    {
                        "timestamp": live_timestamp(),
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "fresh-prompt",
                        },
                    },
                    {
                        "timestamp": live_timestamp(),
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": "fresh-turn",
                            "last_agent_message": "Fresh completion",
                        },
                    },
                ],
                mode="a",
            )
            notifier._read_new_lines(rollout_path, cursor, notify=True)

            self.assertEqual([record["prompt_id"] for record in notifier.prompts], ["fresh-prompt"])
            self.assertEqual([record["turn_id"] for record in notifier.completions], ["fresh-turn"])


if __name__ == "__main__":
    unittest.main()
