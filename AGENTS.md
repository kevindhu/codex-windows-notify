# AGENTS.md

## Purpose

This repo is a small Windows notifier for Codex in VS Code.

Future Codex sessions working in this repo must optimize for:

- preserving the working baseline
- debugging one layer at a time
- avoiding launcher/startup churn
- using the user's real machine behavior as the source of truth

## Canonical Working Paths

The main entrypoint is:

- `codex_notify.py`

The main notifier logic lives in:

- `src/windows_notify_codex/notifier.py`

The preferred local Python install is:

- `C:\Users\lemondoo\AppData\Local\Programs\Python\Python311\python.exe`
- and the matching `pythonw.exe` next to it

Do not switch to Miniconda or another Python unless the user explicitly asks.

## Run Commands

Use these commands first before changing any launcher/startup behavior.

Foreground debug:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_debug.ps1
```

Manual background:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_background.ps1
```

These two commands are the baseline truth for whether the notifier itself works.

## Startup Commands

Startup install:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\misc\install_startup_folder.ps1
```

Startup uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\misc\uninstall_startup_folder.ps1
```

Do not invent alternate startup mechanisms unless the user explicitly asks.

Do not reintroduce:

- VBS launcher flow
- Task Scheduler flow
- shortcut-based startup flow

The repo standard is the Startup-folder `.cmd` launcher.

## Required Debugging Order

If something is broken, follow this order exactly.

1. Verify foreground debug runner works.
2. Verify manual background runner works.
3. Only after both of those work, verify startup automation.
4. Only after launch/persistence is verified, debug click-focus behavior.

Do not reorder these steps unless the user explicitly asks for a different approach.

## First Response Rule

If the notifier appears broken, future Codex sessions should try to resolve the issue by using the user's own local manual runs before changing code or launchers.

Use one of these first:

Foreground:

```powershell
python .\codex_notify.py
```

or

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_debug.ps1
```

Background:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_background.ps1
```

If Codex cannot reliably validate background behavior from its own execution environment, it should ask the user to run these commands manually and use those results as the primary evidence before making more changes.

## Do Not Mix Layers

Treat these as separate concerns:

1. Completion detection
2. Background persistence
3. Startup automation
4. Notification UI
5. Toast click-focus behavior

Do not patch multiple layers in one pass unless there is hard evidence they are part of the same bug.

In particular:

- do not edit startup scripts while investigating focus bugs
- do not edit focus logic while investigating persistence bugs
- do not edit notification trigger rules while investigating launcher issues

## Focus Bug Rules

If the user asks about clicking the toast focusing the correct VS Code window:

- only patch the PowerShell focus code inside `show_windows_notification()` in `src/windows_notify_codex/notifier.py`
- do not change startup scripts
- do not change `codex_notify.py`
- do not change completion parsing

Use:

- UI Automation for visible VS Code window discovery
- `logs/notification-clicks.log` as the primary debug artifact

Avoid:

- reopening workspaces as fallback
- changing launcher behavior
- changing unrelated notification logic

## Logging Rules

Keep startup debug output quiet.

Historical priming should not spam:

- `[meta] ...`
- `[prime] skipped historical ...`
- stale synthetic/manual bad JSON warnings

Verbose mode should remain useful for live debugging, not flooded with historical noise.

Useful live logs include:

- `[notify] ...`
- new live `[meta] ...`
- focus-click debug lines in `logs/notification-clicks.log`

## Source of Truth

When background-process behavior differs between:

- Codex tool execution
- the user's actual PowerShell session
- Windows sign-in/startup behavior

trust the user's actual local PowerShell and Windows session first.

Do not assume detached-process behavior inside the Codex execution environment is authoritative.

If the user can run a command locally and it stays alive, treat that as the real machine truth.

## Cleanup Rules

Keep the repo simple.

Do not add extra one-off launchers, installers, or debug files unless truly necessary.

If a temporary debug artifact is created, remove it before finishing unless the user wants it kept.

Prefer this repo structure:

- `commands/run/` for real run commands
- `commands/misc/` for setup/utilities
- `logs/` for runtime output only

## Documentation Rule

If behavior changes, update:

- `README.md`

If a future session uncovers a process failure or major debugging mistake worth preserving, append or revise:

- `learnings.md`

## Non-Negotiable Rule

Before changing launchers, startup automation, or interpreter selection, first prove whether the notifier already works via:

1. foreground debug
2. manual background run

If those are not tested first, stop and test them before making more changes.
