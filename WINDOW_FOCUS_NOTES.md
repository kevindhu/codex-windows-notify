# Window Focus Notes

## Goal

Keep the existing completion watcher and notification flow exactly as-is.

Only improve one behavior:

- when the custom toast is clicked
- focus the correct VS Code window for the workspace that produced the notification

Do not change:

- completion detection from `~/.codex/sessions`
- startup / background launching
- the existing notification trigger conditions
- logging format unless needed for focus debugging

## Important Lesson

The Codex completion signal was already good enough.

The working implementation already detected real completions from rollout logs written under:

- `C:\Users\lemondoo\.codex\sessions`

The thing that broke later was not completion detection itself.

The breakage came from changing extra infrastructure around:

- launcher behavior
- background process startup
- hidden `pythonw` execution
- startup folder scripts

That was scope creep and should not be repeated.

## Working Baseline Assumption

The baseline that should be preserved is:

- `codex_notify.py` launches the watcher
- `src/windows_notify_codex/notifier.py` watches rollout files
- completions are appended to `logs/codex-completions.jsonl`
- notifications are shown when VS Code is not focused
- `run_codex_notifier_hidden.vbs` launches the watcher in the background

If starting from a fresh reset, verify these first before any focus changes:

1. a real completion adds a row to `logs/codex-completions.jsonl`
2. a real completion shows a toast when VS Code is not focused
3. no launcher or startup files are changed unless explicitly needed

## The Real Focus Problem

The old toast click handler focused "a VS Code window", but not always the correct workspace window.

The reason:

- simple process-based inspection like `Get-Process Code` was unreliable
- Windows often showed many `Code.exe` processes but only one `MainWindowHandle`
- with two visible VS Code windows, the old logic often only saw one strong candidate

So the correct improvement is:

- change only the click-focus logic inside the PowerShell popup script
- use a better way to enumerate visible VS Code windows
- leave the rest of the notifier unchanged

## What Actually Worked Best

The most promising approach was using Windows UI Automation from inside the PowerShell popup script.

These assemblies were useful:

- `UIAutomationClient`
- `UIAutomationTypes`

This was the key discovery:

- UI Automation could see both visible VS Code windows
- the older `Get-Process` / `EnumWindows` approach often could not

### Example of the UI Automation probe that worked

This PowerShell command could see both windows:

```powershell
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$children = $root.FindAll(
    [System.Windows.Automation.TreeScope]::Children,
    [System.Windows.Automation.Condition]::TrueCondition
)

$rows = foreach ($child in $children) {
    try {
        $procId = [int]$child.GetCurrentPropertyValue(
            [System.Windows.Automation.AutomationElement]::ProcessIdProperty
        )
        $handle = [int]$child.GetCurrentPropertyValue(
            [System.Windows.Automation.AutomationElement]::NativeWindowHandleProperty
        )
        $name = [string]$child.GetCurrentPropertyValue(
            [System.Windows.Automation.AutomationElement]::NameProperty
        )
        if (-not $procId -or -not $handle) { continue }
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($null -ne $proc -and $proc.ProcessName -like 'Code*') {
            [pscustomobject]@{
                Pid = $procId
                Handle = $handle
                Title = $name
            }
        }
    } catch {}
}

$rows | Format-Table -AutoSize
```

At one point this returned both visible windows:

- `AGENTS.md - rocket-game - Visual Studio Code`
- `notification-clicks.log - windows-notify-codex - Visual Studio Code`

That is the path to build on.

## Recommended Implementation

Inside `show_windows_notification()` in `src/windows_notify_codex/notifier.py`:

1. keep the existing popup UI behavior
2. replace only the candidate-enumeration part of `Focus-VSCodeWindow`
3. use UI Automation to enumerate top-level visible VS Code windows
4. score those windows against the workspace name from `cwd`
5. focus the highest-scoring match
6. preserve the existing maximize / restore behavior

### Scoring idea

Build preferred tokens from:

- `project_name`
- `Split-Path $cwd -Leaf`

Then score a VS Code window title like this:

- `+3` if title contains workspace token
- `+1` if title contains `Visual Studio Code`

That was enough in practice to distinguish:

- `rocket-game`
- `windows-notify-codex`

### Important constraint

Do not add fallback behavior that reopens workspaces or changes the launcher.

Specifically avoid:

- `code -r <cwd>` fallback
- changing `run_codex_notifier_hidden.vbs`
- changing `install_startup_folder.ps1`
- changing `codex_notify.py`

The user explicitly wants only the correct-window click focus improvement.

## Recommended PowerShell Functions

These are the logical pieces to add inside the notification script:

### 1. `Get-PreferredWorkspaceTokens`

Inputs:

- preferred project name
- preferred cwd

Output:

- unique lowercase tokens to match against titles

Suggested logic:

- add `$PreferredProjectName.ToLowerInvariant()`
- add `Split-Path $PreferredCwd -Leaf`

### 2. `Get-VSCodeWindowCandidates`

Inputs:

- preferred tokens

Output:

- array of objects like:

```powershell
[pscustomobject]@{
    Handle = [IntPtr]$handleValue
    Title = $titleValue
    Score = $score
    ProcessId = $pidValue
    Source = 'UIAutomation'
}
```

Use:

- `AutomationElement.RootElement`
- `TreeScope.Children`
- `ProcessIdProperty`
- `NativeWindowHandleProperty`
- `NameProperty`
- `ClassNameProperty`

Filter to:

- process name like `Code*`
- non-empty title
- non-zero handle

### 3. `Focus-VSCodeWindow`

Inputs:

- preferred project name
- preferred cwd

Behavior:

- compute preferred tokens
- gather UI Automation candidates
- sort descending by score
- pick first candidate
- call:
  - `AppActivate`
  - `SendKeys('%')`
  - `ShowWindowAsync`
  - `SetForegroundWindow`

Keep the logic that preserves maximized windows:

- if maximized, call show maximize
- if minimized, restore
- otherwise just foreground

## Logging That Was Helpful

The following click-debug lines were useful and should be retained if added:

- `notification clicked project=... cwd=...`
- `uia candidate pid=... handle=... score=... matched=... title=...`
- `uia candidate count=...`
- `focus target source=... pid=... handle=... score=... title=...`
- `AppActivate returned ...`
- `SendKeys Alt dispatched`
- `window state before focus minimized=... maximized=...`
- `SetForegroundWindow returned ...`
- `window state after focus minimized=... maximized=...`

These go to:

- `logs/notification-clicks.log`

## Bug To Avoid

There was a prior mistake where candidates were logged but later counted as zero.

That likely came from returning or constructing the PowerShell collection incorrectly.

Safer pattern:

```powershell
$candidates = @()
$candidates += $candidate
return $candidates
```

Avoid mixing:

- `System.Collections.Generic.List[object]`
- pipeline return behavior
- implicit enumeration

unless tested carefully.

## What Not To Touch

Do not modify these again for this task:

- `codex_notify.py`
- `run_codex_notifier_hidden.vbs`
- `install_startup_folder.ps1`
- startup/background process design
- completion watcher logic in `_record_completion`
- session parsing logic

## Clean Success Criteria

The change is done when all of these are true:

1. real completions still show notifications exactly like before
2. `logs/codex-completions.jsonl` keeps updating on real completions
3. clicking the toast from repo A while repo B is focused brings repo A's VS Code window forward
4. no startup or launcher behavior was changed

## Suggested Next Session Plan

1. verify baseline completion notifications still work before editing anything
2. patch only the PowerShell toast script inside `show_windows_notification()`
3. use UI Automation for click-focus candidate discovery
4. test with two visible VS Code windows
5. stop immediately once click focus works
