# Learnings

## Notification rendering and DPI

The Python design lookbook rendered cards at high resolution, while the original Windows Forms popup
ran inside a DPI-unaware PowerShell host. On this machine Windows scaling was 125% (120 DPI), but
the host reported 96 DPI and DPI awareness 0. Approving the mockup and a 460 x 156 DrawToBitmap
image did not establish that the actual popup would look smooth at the user's display scale.

The popup now sets DPI awareness before creating its window and uses WPF for antialiased text and
vector rounded corners. Runtime verification confirmed awareness 2, a 1.25 visual scale, and a
575 x 195 physical window for the same 460 x 156 logical layout. Verify the actual window's DPI
and native-size rendering, not just enlarged design mockups. Offscreen exports at other DPI values
are not a substitute for testing a real monitor at those scales.

Keep UI comparison images and selected-design evidence for the user to review. The retained evidence
for this change is under `output/notification-styles/rendering-fix/`.

## What Actually Happened

The project had two separate classes of problems:

1. The notifier logic itself.
2. The launch/startup path used to keep it running in the background.

Those got mixed together during debugging, which made the work slower and much more frustrating than it should have been.

## The Main Mistake

The biggest mistake was changing too many things outside the real bug at once.

Instead of keeping the working baseline stable and testing one layer at a time, I changed:

- startup folder launch behavior
- hidden launcher mechanism
- Python interpreter selection
- background launch scripts
- focus logic
- notification suppression behavior
- repo structure

That created multiple moving parts at the same time and made it harder to tell which problem was real.

## What The Real Problems Were

### 1. Foreground vs background execution got confused

The foreground debug watcher worked.

When you ran:

```powershell
powershell -ExecutionPolicy Bypass -File .\commands\run\run_notifier_debug.ps1
```

the notifier stayed alive, read rollout files, and detected completions correctly.

That proved:

- the core watcher loop was fine
- session parsing was fine
- completion detection was fine

So the core notifier was not the first thing that needed to be changed.

### 2. The background launch path was the actual operational issue

The real operational problem was keeping the watcher alive in the background automatically.

This was made harder by the fact that my tool execution environment is not the same as your real Windows desktop session.

In the tool environment:

- detached child processes can disappear after the command finishes
- script host / startup simulation is not trustworthy
- some background launch tests can look broken even when they would work on your actual machine

I treated those results too confidently at first.

That led to too much time spent trying to "fix" launch paths from inside an environment that could not reliably validate them.

### 3. I used the wrong Python path at several points

Another real issue was interpreter mismatch.

Different paths were being used in different contexts:

- Miniconda `python.exe`
- Miniconda `pythonw.exe`
- Python 3.11 installed under `AppData\Local\Programs\Python\Python311`

That caused confusion because:

- one path worked for foreground tests
- another path was getting written into startup launchers
- some launchers ended up pointing somewhere different from the manual working command

Once you made it clear you wanted Python 3.11, the path strategy became much simpler and more consistent.

### 4. I temporarily changed behavior outside the requested scope

At one point I changed notification suppression logic and other surrounding behavior while also debugging startup/focus issues.

That was not good process.

The right way was:

- stabilize the launcher
- verify the watcher stays alive
- verify completions are detected
- then fix the click-focus logic only

Instead, I blended multiple fixes together.

## Why It Took Too Long

It took too long because I failed to lock down the correct debugging order.

The correct order should have been:

1. Prove the watcher works in foreground.
2. Prove the exact same command works in manual background.
3. Make startup use that exact same working path.
4. Only then touch toast click-focus behavior.

Instead, I spent too much time on:

- speculative launcher changes
- multiple startup mechanisms
- mixed Python path selection
- background tests inside a tool environment that could not reliably prove persistence

That produced a lot of churn and made it feel like I was fighting the repo instead of fixing it cleanly.

## Specific Technical Errors

### Error: trusting tool-environment background behavior too much

I treated disappearing background processes inside the Codex execution environment as proof that your real Windows background process was failing the same way.

That was not a safe assumption.

The better approach would have been to ask you to run the manual background command much earlier and use that as the real source of truth.

### Error: using too many launcher variants

I cycled through too many launcher ideas:

- VBS
- shortcut
- batch file
- `Start-Process`
- startup folder
- scheduled task

That created unnecessary complexity.

Once the manual background PowerShell runner worked, the startup solution should have been made to match that exact known-good path and then left alone.

### Error: changing focus logic before isolating startup behavior

The focus bug was real, but it was a separate problem from startup persistence.

I mixed them together, which made it harder to know whether:

- the watcher was dead
- the notification was suppressed
- the click-focus code picked the wrong window

Those should have been debugged separately.

### Error: PowerShell `$PID` naming bug in UI Automation code

When implementing the UI Automation focus path, I used `$pid` as a local variable.

In PowerShell, `$PID` is a built-in read-only variable, so that caused this failure:

`Cannot overwrite variable PID because it is read-only or constant.`

That prevented UI Automation candidate discovery from working until it was renamed.

This was a straightforward implementation bug and should have been caught faster.

### Error: launcher scripts walked up to `commands/` instead of the repo root

The run and startup scripts used:

```powershell
Split-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) -Parent
```

That resolves to `...\windows-notify-codex\commands`, not the actual repo root, for scripts under
`commands/run/` and `commands/misc/`.

That broke script-derived paths like:

- `commands\codex_notify.py`
- startup launchers that `cd` into `...\commands`

The safer fix is to derive the repo root from `$PSScriptRoot` with an explicit `..\..` and
`Resolve-Path`, so the scripts keep working if they are launched from any current working directory.

### Error: startup priming logs were too noisy

The debug runner originally printed massive amounts of historical startup noise:

- `[meta] ...`
- `[prime] skipped historical completion ...`
- `[prime] skipped historical prompt ...`
- old synthetic file JSON warnings

That made live debugging harder because the useful output was buried in junk.

That should have been cleaned up earlier.

## What Finally Worked

These ended up being the reliable pieces:

- foreground debug runner for real diagnosis
- manual background runner for real machine validation
- Python 3.11 as the explicit preferred interpreter
- startup folder launcher matching the known-good Python 3.11 background command
- UI Automation for discovering visible VS Code windows when clicking the toast

## Fork Replay Note

Codex forked sessions can append historical source-thread events as fresh lines in the new rollout file.

The important detail is that those replayed `task_complete` and prompt events keep their original IDs.

That means a fast startup path that reads `session_meta` and jumps to EOF is not enough by itself.

The notifier still needs a second dedupe path:

- seed seen IDs from its own completion log on startup
- when a forked session appears, use `forked_from_id` to index the source session's historical turn and prompt IDs

That targeted indexing suppresses replay noise without reparsing every historical rollout file on each startup.

## Workspace-Move Replay Note

Moving or reopening a workspace can append historical events directly to old rollout files without creating a
fork or preserving IDs that the notifier has already logged. In the observed failure, May completion and
approval records were appended again in September and produced a series of stale notifications.

ID deduplication and fork-source indexing cannot catch unseen IDs in this case. Prompt and completion records
must also pass a freshness check before notifying. Records more than five days old are marked seen but silently
discarded, preventing workspace moves from resurfacing historical questions while preserving recent
notifications.

## What I Should Do Next Time

If a similar issue happens again, the process should be:

1. Identify the exact layer that is failing.
2. Keep everything else unchanged.
3. Prove the core script works in foreground first.
4. Use the user's own manual background run as the truth for persistence.
5. Only after that, mirror the same command into startup automation.
6. Treat tool-environment background behavior as suggestive, not authoritative.
7. Avoid scope creep unless the user explicitly asks for a broader refactor.

## Short Version

The reason this took too long and annoyed you was:

- I changed too many things at once
- I trusted misleading background-process behavior from my tool environment
- I mixed startup issues, notifier issues, and focus issues together
- I used inconsistent Python paths until you forced the issue

The better approach would have been much simpler:

- prove foreground works
- prove manual background works
- copy that exact command into startup
- then fix click-focus only
