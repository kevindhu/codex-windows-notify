# Codex VS Code Windows Notifier

This is a tiny background watcher for Codex in VS Code on Windows.

It watches the local Codex rollout logs under `~/.codex/sessions`, looks for real `task_complete` events from `source: "vscode"`, checks whether VS Code is focused, and shows a toast-style Windows popup when a task finishes while VS Code is unfocused.

It also writes a structured completion log so you can review what finished, when it finished, which project it belonged to, and whether a notification was shown.

## Why this signal

The reliable completion signal is not the window title or a heuristic. Codex writes structured session logs locally, and VS Code-originated sessions include:

- `session_meta` with `source: "vscode"`
- `event_msg` with `payload.type: "task_complete"`

That makes the notifier much more dependable than polling the UI.

## Run it

From this repo:

```powershell
python .\codex_notify.py
```

For local debugging in a visible terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_notifier_debug.ps1
```

That runs the watcher in the foreground with `--verbose` and appends terminal output to `.\logs\manual-debug.log`.

To manually start the hidden/background version from your own terminal session:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_notifier_background.ps1
```

That uses the `pythonw.exe` next to whatever `python` resolves to on your machine, which makes it easier to compare foreground vs background behavior.

Run it without a console window:

```powershell
wscript.exe .\run_codex_notifier_hidden.vbs
```

Or install it in editable mode and use the console script:

```powershell
pip install -e .
codex-notify
```

## Behavior

- Existing historical sessions are indexed on startup but do not notify.
- Existing historical sessions are indexed on startup but are not backfilled into the completion log.
- New `task_complete` events from VS Code sessions do notify.
- New `task_complete` events are appended to `./logs/codex-completions.jsonl` by default.
- Notifications are skipped while the foreground app is `Code.exe` or `Code - Insiders.exe`.
- The notification body uses the last agent message when available.
- Notifications use `.\sounds\smallnotify.wav` by default when that file exists.

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

You can also change the Windows alert sounds:

```powershell
python .\codex_notify.py --sound-file .\sounds\smallnotify.wav --completion-sound none --prompt-sound none
```

The `--completion-sound` and `--prompt-sound` options are fallback system sounds only, used if the WAV file is missing. Available values are `asterisk`, `beep`, `exclamation`, `hand`, `question`, and `none`.

Convert the bundled MP3 to WAV with:

```powershell
powershell -ExecutionPolicy Bypass -File .\convert_sound.ps1
```

## Notes

- The watcher polls once per second.
- Notifications are shown through PowerShell using a silent toast-style popup window, so Windows does not add its own default notification sound on top of your custom one.

## Always On

The easiest reliable setup on Windows 10 is Task Scheduler.

Install the scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_startup_task.ps1
```

That creates a per-user task named `Codex VS Code Notifier`, starts it immediately, and runs it again automatically every time you sign in.

Remove it later with:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_startup_task.ps1
```

Useful checks:

```powershell
Get-ScheduledTask -TaskName "Codex VS Code Notifier"
Get-ScheduledTaskInfo -TaskName "Codex VS Code Notifier"
```

Scheduler logs go to:

- `.\logs\scheduler-stdout.log`
- `.\logs\scheduler-stderr.log`

Completion events still go to:

- `.\logs\codex-completions.jsonl`

## Startup Folder

If you prefer the Windows Startup folder instead of Task Scheduler, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_startup_folder.ps1
```

That creates a `CodexNotifier.cmd` launcher in your user Startup folder that starts the working `pythonw.exe` for [codex_notify.py](c:/Users/lemondoo/PROJECTS/windows-notify-codex/codex_notify.py), so the notifier launches automatically at sign-in without going through Windows Script Host.

Remove it later with:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_startup_folder.ps1
```
