## Codex Completion Notifications Notes

### What we confirmed

- The Codex desktop app appears to support built-in completion notifications.
- The Codex VS Code extension does not necessarily support the same notification behavior.
- A setting shown in Codex like `Turn completion notifications` means the app can alert when a task finishes, for example only when the app is unfocused.

### Goal

Create a very small background app, likely in Python, that behaves similarly for the Codex VS Code extension:

- Detect when a Codex task has finished
- Check whether VS Code is currently focused
- If VS Code is not focused, show a native Windows notification

### Important constraint
    
The notifier needs a reliable signal that a Codex task is finished.

Possible signals to detect:

1. VS Code window title or status text changes
2. Codex extension output or log file changes
3. Terminal/task patterns if Codex activity is visible there

If the extension does not expose a clean event, the app can still use a practical heuristic based on one of the signals above.

### Suggested implementation

A simple Windows background Python script could use:

- `pywin32` or similar to detect the currently focused window
- `winotify` or `win10toast` to show native Windows toast notifications
- a lightweight polling loop to watch for Codex completion events

Basic behavior:

1. Monitor for a "Codex finished" event
2. Check whether `Code.exe` is the foreground window
3. If VS Code is not focused, show a Windows notification

### Next step in a new repo

The best first step is to inspect the local VS Code Codex extension and identify what completion signal is available. Once that is known, wire a small notifier around it.
