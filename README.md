# Codex Windows Notifier

This is a tiny background watcher for Codex on Windows.

It watches the local Codex rollout logs under `~/.codex/sessions`, looks for real top-level `task_complete` events, and shows a toast-style Windows popup when a task finishes. It does not require VS Code to be open.

It also writes a structured completion log so you can review what finished, when it finished, which project it belonged to, and whether a notification was shown.

## Why this signal

The reliable completion signal is not the window title or a heuristic. Codex writes structured session logs locally, and top-level sessions include:

- `session_meta` with a normal string `source`
- `event_msg` with `payload.type: "task_complete"`

That makes the notifier much more dependable than polling the UI.

## Run it

From this repo:

```powershell
python .\codex_notify.py
```

For local debugging in a visible terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_debug.ps1
```

That runs the watcher in the foreground with `--verbose` and appends terminal output to `.\logs\manual-debug.log`.

To manually start the hidden/background version from your own terminal session:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_background.ps1
```

That uses the Python 3.11 `pythonw.exe` install on your machine when available, which makes it easier to compare foreground vs background behavior.

Or install it in editable mode and use the console script:

```powershell
pip install -e .
codex-notify
```

## Behavior

- Existing rollout files are primed to EOF on startup without notifying, so older session history is not backfilled as new popups.
- Existing historical sessions do not notify and are not backfilled into the completion log.
- Historical `turn_id` and prompt IDs are remembered from the notifier's own completion log on startup.
- When a forked session appears with `forked_from_id`, the notifier indexes that source session's historical turn and prompt IDs before replayed events arrive, which suppresses duplicate notifications.
- Prompt and completion records older than five days are treated as historical replay and never shown, even when a workspace move appends them to an already-watched rollout file with previously unseen IDs.
- New `task_complete` events from top-level Codex sessions do notify.
- Subagent child sessions are ignored to avoid duplicate or noisy popups.
- New `task_complete` events are appended to `./logs/codex-completions.jsonl` by default.
- Notifications are shown even if VS Code is closed.
- The notification body uses the last agent message when available.
- Notification sound is disabled by default.
- The selected notification style is **01 - Refined baseline**: a 460 x 156 logical-pixel dark card with 10 px rounded corners, a subtle border, bold Segoe UI title, and muted body text. A small green dot marks completion; amber marks a request for attention. Long text ends with an ellipsis.
- The popup uses a per-monitor DPI-aware WPF renderer with antialiased text and vector corners. At 125% Windows scaling, the card renders directly at 575 x 195 physical pixels rather than enlarging a low-resolution bitmap.
- Clicking a notification currently closes it without trying to focus VS Code.

## Completion Log

Each new completion is stored as one JSON line with fields like:

- `event_time`
- `project_name`
- `cwd`
- `source`
- `originator`
- `session_id`
- `turn_id`
- `cli_version`
- `rollout_path`
- `foreground_process`
- `notification.shown`
- `notification.reason`
- `last_agent_message`

You can change the log location with:

```powershell
python .\codex_notify.py --log-path .\logs\my-codex-log.jsonl
```

Sound is off by default. To enable the bundled WAV sound:

```powershell
python .\codex_notify.py --sound-enabled
```

You can also change the Windows alert sounds:

```powershell
python .\codex_notify.py --sound-enabled --sound-file .\sounds\smallnotify.wav --completion-sound none --prompt-sound none
```

The `--completion-sound` and `--prompt-sound` options are fallback system sounds only, used when `--sound-enabled` is set and the WAV file is missing. Available values are `asterisk`, `beep`, `exclamation`, `hand`, `question`, and `none`.

Convert the bundled MP3 to WAV with:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\misc\convert_sound.ps1
```

## Notes

- The watcher polls once per second.
- Notifications are shown through PowerShell using a silent toast-style popup window, so Windows does not add its own default notification sound on top of your custom one.

## Startup Folder

If you prefer the Windows Startup folder instead of Task Scheduler, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\misc\install_startup_folder.ps1
```

That creates a `CodexNotifier.cmd` launcher in your user Startup folder that starts the working `pythonw.exe` for [codex_notify.py](c:/Users/lemondoo/PROJECTS/windows-notify-codex/codex_notify.py), so the notifier launches automatically at sign-in without going through Windows Script Host.

Remove it later with:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\misc\uninstall_startup_folder.ps1
```
