from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
from datetime import datetime, timezone
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


POLL_SECONDS = 1.0
DEFAULT_COMPLETION_SOUND = "none"
DEFAULT_PROMPT_SOUND = "none"
DEFAULT_SOUND_FILE = "./sounds/smallnotify.wav"
VSCODE_PROCESS_NAMES = {
    "code.exe",
    "code - insiders.exe",
}
SOUND_CHOICES = {
    "asterisk": "[System.Media.SystemSounds]::Asterisk.Play()",
    "beep": "[System.Media.SystemSounds]::Beep.Play()",
    "exclamation": "[System.Media.SystemSounds]::Exclamation.Play()",
    "hand": "[System.Media.SystemSounds]::Hand.Play()",
    "question": "[System.Media.SystemSounds]::Question.Play()",
    "none": "",
}


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def _truncate(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def get_foreground_process_name() -> str | None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    process_id = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if not process_id.value:
        return None

    handle = kernel32.OpenProcess(0x1000, False, process_id.value)
    if not handle:
        return None

    try:
        size = ctypes.wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        if not ok:
            return None
        return os.path.basename(buffer.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def is_vscode_focused() -> bool:
    name = get_foreground_process_name()
    return name in VSCODE_PROCESS_NAMES


def show_windows_notification(
    title: str,
    message: str,
    sound: str,
    sound_file: str | None,
    project_name: str,
    cwd: str | None,
) -> None:
    sound_command = SOUND_CHOICES.get(sound, "")
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$wshell = New-Object -ComObject WScript.Shell
$title = $env:CODEX_NOTIFY_TITLE
$message = $env:CODEX_NOTIFY_MESSAGE
$soundFile = $env:CODEX_NOTIFY_SOUND_FILE
$soundCommand = $env:CODEX_NOTIFY_SOUND_COMMAND
$projectName = $env:CODEX_NOTIFY_PROJECT_NAME
$cwd = $env:CODEX_NOTIFY_CWD
$clickLogPath = $env:CODEX_NOTIFY_CLICK_LOG

function Write-DebugLog {
    param([string]$Line)
    if (-not $clickLogPath) {
        return
    }

    try {
        $directory = Split-Path -Parent $clickLogPath
        if ($directory) {
            New-Item -ItemType Directory -Path $directory -Force | Out-Null
        }
        Add-Content -Path $clickLogPath -Value ("{0} {1}" -f [DateTime]::Now.ToString("o"), $Line)
    } catch {}
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class Win32 {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsZoomed(IntPtr hWnd);
}
"@

function Get-WindowTitle {
    param([IntPtr]$Handle)
    $builder = New-Object System.Text.StringBuilder 512
    [void][Win32]::GetWindowText($Handle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Focus-VSCodeWindow {
    param(
        [string]$PreferredProjectName,
        [string]$PreferredCwd
    )

    $candidates = New-Object System.Collections.Generic.List[object]
    $fallbackProcesses = @()

    try {
        $fallbackProcesses = Get-Process | Where-Object {
            $_.ProcessName -like 'Code*' -and $_.MainWindowHandle -ne 0 -and -not [string]::IsNullOrWhiteSpace($_.MainWindowTitle)
        }
    } catch {
        Write-DebugLog ("Get-Process fallback failed: {0}" -f $_.Exception.Message)
    }

    foreach ($process in $fallbackProcesses) {
        $score = 0
        if ($PreferredProjectName -and $process.MainWindowTitle -like "*$PreferredProjectName*") {
            $score += 3
        }
        if ($PreferredCwd) {
            $leaf = Split-Path $PreferredCwd -Leaf
            if ($leaf -and $process.MainWindowTitle -like "*$leaf*") {
                $score += 3
            }
        }
        if ($process.MainWindowTitle -like '*Visual Studio Code*' -or $process.MainWindowTitle -like '*Code*') {
            $score += 1
        }

        $candidates.Add([pscustomobject]@{
            Handle = [IntPtr]$process.MainWindowHandle
            Title = $process.MainWindowTitle
            Score = $score
            ProcessId = $process.Id
            Source = 'GetProcess'
        }) | Out-Null
        Write-DebugLog ("process candidate pid={0} score={1} title={2}" -f $process.Id, $score, $process.MainWindowTitle)
    }

    [Win32]::EnumWindows({
        param($hWnd, $lParam)
        if (-not [Win32]::IsWindowVisible($hWnd)) {
            return $true
        }

        $title = Get-WindowTitle $hWnd
        if ([string]::IsNullOrWhiteSpace($title)) {
            return $true
        }

        [uint32]$pid = 0
        [void][Win32]::GetWindowThreadProcessId($hWnd, [ref]$pid)
        if ($pid -eq 0) {
            return $true
        }

        try {
            $process = Get-Process -Id $pid -ErrorAction Stop
        } catch {
            return $true
        }

        if ($process.ProcessName -notin @('Code', 'Code - Insiders')) {
            return $true
        }

        $score = 0
        if ($PreferredProjectName -and $title -like "*$PreferredProjectName*") {
            $score += 3
        }
        if ($PreferredCwd) {
            $leaf = Split-Path $PreferredCwd -Leaf
            if ($leaf -and $title -like "*$leaf*") {
                $score += 3
            }
        }
        if ($title -like '*Visual Studio Code*' -or $title -like '*Code*') {
            $score += 1
        }

        $candidates.Add([pscustomobject]@{
            Handle = $hWnd
            Title = $title
            Score = $score
            ProcessId = $pid
            Source = 'EnumWindows'
        }) | Out-Null
        Write-DebugLog ("candidate pid={0} score={1} title={2}" -f $pid, $score, $title)
        return $true
    }, [IntPtr]::Zero) | Out-Null

    $target = $candidates |
        Sort-Object @{ Expression = 'Score'; Descending = $true }, @{ Expression = 'Source'; Descending = $false } |
        Select-Object -First 1
    if ($null -eq $target) {
        Write-DebugLog "focus failed: no VS Code window candidates found"

        try {
            $activated = $wshell.AppActivate('Visual Studio Code')
            Write-DebugLog ("fallback AppActivate by title returned {0}" -f $activated)
        } catch {
            Write-DebugLog ("fallback AppActivate by title failed: {0}" -f $_.Exception.Message)
        }
        return
    }

    Write-DebugLog ("focus target source={0} pid={1} score={2} title={3}" -f $target.Source, $target.ProcessId, $target.Score, $target.Title)

    try {
        $activated = $wshell.AppActivate([int]$target.ProcessId)
        Write-DebugLog ("AppActivate returned {0}" -f $activated)
        Start-Sleep -Milliseconds 60
        $wshell.SendKeys('%')
        Write-DebugLog "SendKeys Alt dispatched"
        Start-Sleep -Milliseconds 60
    } catch {
        Write-DebugLog ("AppActivate/SendKeys failed: {0}" -f $_.Exception.Message)
    }

    $isMinimized = [Win32]::IsIconic($target.Handle)
    $isMaximized = [Win32]::IsZoomed($target.Handle)
    Write-DebugLog ("window state before focus minimized={0} maximized={1}" -f $isMinimized, $isMaximized)

    if ($isMaximized) {
        $shown = [Win32]::ShowWindowAsync($target.Handle, 3)
        Write-DebugLog ("ShowWindowAsync maximize returned {0}" -f $shown)
    } elseif ($isMinimized) {
        $shown = [Win32]::ShowWindowAsync($target.Handle, 9)
        Write-DebugLog ("ShowWindowAsync restore returned {0}" -f $shown)
    }

    $setForeground = [Win32]::SetForegroundWindow($target.Handle)
    Write-DebugLog ("SetForegroundWindow returned {0}" -f $setForeground)
    Start-Sleep -Milliseconds 80
    $afterMinimized = [Win32]::IsIconic($target.Handle)
    $afterMaximized = [Win32]::IsZoomed($target.Handle)
    Write-DebugLog ("window state after focus minimized={0} maximized={1}" -f $afterMinimized, $afterMaximized)
}

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$form.ShowInTaskbar = $false
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(28, 28, 30)
$form.ForeColor = [System.Drawing.Color]::White
$form.Size = New-Object System.Drawing.Size(460, 156)
$form.Padding = New-Object System.Windows.Forms.Padding(18, 16, 18, 16)
$form.Cursor = [System.Windows.Forms.Cursors]::Hand

$workingArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(
    ($workingArea.Right - $form.Width - 12),
    ($workingArea.Bottom - $form.Height - 12)
)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = $title
$titleLabel.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 13)
$titleLabel.ForeColor = [System.Drawing.Color]::White
$titleLabel.AutoSize = $false
$titleLabel.Location = New-Object System.Drawing.Point(18, 16)
$titleLabel.Size = New-Object System.Drawing.Size(424, 30)

$messageLabel = New-Object System.Windows.Forms.Label
$messageLabel.Text = $message
$messageLabel.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$messageLabel.ForeColor = [System.Drawing.Color]::FromArgb(232, 232, 235)
$messageLabel.AutoSize = $false
$messageLabel.Location = New-Object System.Drawing.Point(18, 50)
$messageLabel.Size = New-Object System.Drawing.Size(424, 84)
$messageLabel.Cursor = [System.Windows.Forms.Cursors]::Hand

$form.Controls.Add($titleLabel)
$form.Controls.Add($messageLabel)

function Invoke-ClickFeedback {
    $originalSize = $form.Size
    $originalLocation = $form.Location
    $shrinkWidth = [Math]::Max(420, $originalSize.Width - 14)
    $shrinkHeight = [Math]::Max(138, $originalSize.Height - 8)
    $shrinkX = $originalLocation.X + [Math]::Floor(($originalSize.Width - $shrinkWidth) / 2)
    $shrinkY = $originalLocation.Y + [Math]::Floor(($originalSize.Height - $shrinkHeight) / 2)

    $form.Size = New-Object System.Drawing.Size($shrinkWidth, $shrinkHeight)
    $form.Location = New-Object System.Drawing.Point($shrinkX, $shrinkY)
    Start-Sleep -Milliseconds 80
    $form.Size = $originalSize
    $form.Location = $originalLocation
    Start-Sleep -Milliseconds 70
}

$closeForm = {
    Write-DebugLog ("notification clicked project={0} cwd={1}" -f $projectName, $cwd)
    Invoke-ClickFeedback
    Focus-VSCodeWindow -PreferredProjectName $projectName -PreferredCwd $cwd
    if (-not $form.IsDisposed) {
        $form.Close()
    }
}

$form.Add_Click($closeForm)
$titleLabel.Add_Click($closeForm)
$messageLabel.Add_Click($closeForm)

if ($soundFile -and (Test-Path $soundFile)) {
    try {
        $player = New-Object System.Media.SoundPlayer $soundFile
        $player.Play()
    } catch {}
} elseif ($soundCommand) {
    try {
        Invoke-Expression $soundCommand
    } catch {}
}

[void]$form.Show()
[System.Windows.Forms.Application]::Run($form)
"""
    env = os.environ.copy()
    env["CODEX_NOTIFY_TITLE"] = title
    env["CODEX_NOTIFY_MESSAGE"] = message
    env["CODEX_NOTIFY_SOUND_COMMAND"] = sound_command
    env["CODEX_NOTIFY_SOUND_FILE"] = sound_file or ""
    env["CODEX_NOTIFY_PROJECT_NAME"] = project_name
    env["CODEX_NOTIFY_CWD"] = cwd or ""
    env["CODEX_NOTIFY_CLICK_LOG"] = str((Path.cwd() / "logs" / "notification-clicks.log").resolve())
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        env=env,
        check=False,
        capture_output=True,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )


@dataclass
class SessionInfo:
    source: str | None = None
    cwd: str | None = None
    originator: str | None = None
    session_id: str | None = None
    cli_version: str | None = None


@dataclass
class FileCursor:
    position: int = 0
    initialized: bool = False
    session: SessionInfo = field(default_factory=SessionInfo)


class CodexNotifier:
    def __init__(
        self,
        sessions_root: Path,
        log_path: Path,
        poll_seconds: float = POLL_SECONDS,
        completion_sound: str = DEFAULT_COMPLETION_SOUND,
        prompt_sound: str = DEFAULT_PROMPT_SOUND,
        sound_file: Path | None = None,
        verbose: bool = False,
    ) -> None:
        self.sessions_root = sessions_root
        self.log_path = log_path
        self.poll_seconds = poll_seconds
        self.completion_sound = completion_sound
        self.prompt_sound = prompt_sound
        self.sound_file = sound_file
        self.verbose = verbose
        self._running = True
        self._is_priming = False
        self._files: dict[Path, FileCursor] = {}
        self._seen_turn_ids: set[str] = set()
        self._seen_prompt_ids: set[str] = set()

    def log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    def stop(self, *_args: object) -> None:
        self._running = False

    def iter_rollout_files(self) -> Iterable[Path]:
        if not self.sessions_root.exists():
            return []
        return sorted(self.sessions_root.glob("*/*/*/rollout-*.jsonl"))

    def prime_existing_files(self) -> None:
        self._is_priming = True
        try:
            for path in self.iter_rollout_files():
                cursor = self._files.setdefault(path, FileCursor())
                self._read_new_lines(path, cursor, notify=False)
                cursor.initialized = True
        finally:
            self._is_priming = False
        self.log(f"Primed {len(self._files)} rollout file(s)")

    def watch_forever(self) -> None:
        self.prime_existing_files()
        while self._running:
            for path in self.iter_rollout_files():
                cursor = self._files.setdefault(path, FileCursor())
                notify = cursor.initialized
                self._read_new_lines(path, cursor, notify=notify)
                cursor.initialized = True
            time.sleep(self.poll_seconds)

    def _read_new_lines(self, path: Path, cursor: FileCursor, notify: bool) -> None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                handle.seek(cursor.position)
                while True:
                    raw_line = handle.readline()
                    if not raw_line:
                        break
                    cursor.position = handle.tell()
                    line = raw_line.strip()
                    if not line:
                        continue
                    self._handle_line(path, cursor, line, notify=notify)
                cursor.position = handle.tell()
        except FileNotFoundError:
            self._files.pop(path, None)
        except OSError as exc:
            self.log(f"[warn] failed reading {path}: {exc}")

    def _handle_line(self, path: Path, cursor: FileCursor, line: str, notify: bool) -> None:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if not self._is_priming:
                self.log(f"[warn] bad json in {path}")
            return

        record_type = record.get("type")
        payload = record.get("payload", {})

        if record_type == "session_meta":
            cursor.session.source = payload.get("source")
            cursor.session.cwd = payload.get("cwd")
            cursor.session.originator = payload.get("originator")
            cursor.session.session_id = payload.get("id")
            cursor.session.cli_version = payload.get("cli_version")
            if not self._is_priming:
                self.log(
                    f"[meta] {path.name} source={cursor.session.source} originator={cursor.session.originator}"
                )
            return

        is_vscode = cursor.session.source == "vscode"
        if not is_vscode:
            return

        if record_type == "response_item":
            self._handle_response_item(path, cursor, record, notify=notify)
            return

        if record_type != "event_msg":
            return

        event_type = payload.get("type")
        if event_type != "task_complete":
            return

        turn_id = payload.get("turn_id")
        if turn_id:
            if turn_id in self._seen_turn_ids:
                return
            self._seen_turn_ids.add(turn_id)

        last_message = payload.get("last_agent_message") or "Codex finished a task in VS Code."
        event_time = record.get("timestamp") or datetime.now(timezone.utc).isoformat()
        if notify:
            self._record_completion(
                session=cursor.session,
                rollout_path=path,
                turn_id=turn_id,
                event_time=event_time,
                last_message=last_message,
            )
        elif not self._is_priming:
            self.log(f"[prime] skipped historical completion for {path.name}")

    def _handle_response_item(
        self,
        path: Path,
        cursor: FileCursor,
        record: dict[str, object],
        notify: bool,
    ) -> None:
        payload = record.get("payload", {})
        if not isinstance(payload, dict):
            return

        payload_type = payload.get("type")
        prompt_kind: str | None = None
        prompt_message: str | None = None
        prompt_id: str | None = None

        if payload_type == "function_call" and payload.get("name") == "request_user_input":
            prompt_kind = "user_question"
            prompt_id = str(payload.get("call_id") or payload.get("name") or record.get("timestamp"))
            prompt_message = "Codex is waiting for your answer to a question prompt."
        elif payload_type in {"custom_tool_call", "function_call"}:
            nested = self._parse_nested_payload(payload)
            if self._is_approval_payload(payload, nested):
                prompt_kind = "approval_request"
                prompt_id = str(payload.get("call_id") or payload.get("name") or record.get("timestamp"))
                prompt_message = self._extract_approval_message(payload, nested)

        if prompt_kind is None or prompt_id is None:
            return

        if prompt_id in self._seen_prompt_ids:
            return
        self._seen_prompt_ids.add(prompt_id)

        if not notify:
            if not self._is_priming:
                self.log(f"[prime] skipped historical prompt for {path.name}")
            return

        event_time = str(record.get("timestamp") or datetime.now(timezone.utc).isoformat())
        self._record_prompt(
            session=cursor.session,
            rollout_path=path,
            prompt_id=prompt_id,
            prompt_kind=prompt_kind,
            event_time=event_time,
            message=prompt_message or "Codex needs your attention.",
        )

    def _parse_nested_payload(self, payload: dict[str, object]) -> dict[str, object] | None:
        for key in ("input", "arguments"):
            value = payload.get(key)
            if not isinstance(value, str):
                continue
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _is_approval_payload(
        self,
        payload: dict[str, object],
        nested: dict[str, object] | None,
    ) -> bool:
        direct_sandbox = payload.get("sandbox_permissions")
        direct_justification = payload.get("justification")
        nested_sandbox = nested.get("sandbox_permissions") if nested else None
        nested_justification = nested.get("justification") if nested else None
        return (
            (direct_sandbox == "require_escalated" and isinstance(direct_justification, str))
            or (nested_sandbox == "require_escalated" and isinstance(nested_justification, str))
        )

    def _extract_approval_message(
        self,
        payload: dict[str, object],
        nested: dict[str, object] | None,
    ) -> str:
        if nested:
            justification = nested.get("justification")
            if isinstance(justification, str) and justification.strip():
                return justification.strip()

        justification = payload.get("justification")
        if isinstance(justification, str) and justification.strip():
            return justification.strip()
        return "Codex is waiting for your approval to continue."

    def _record_completion(
        self,
        session: SessionInfo,
        rollout_path: Path,
        turn_id: str | None,
        event_time: str,
        last_message: str,
    ) -> None:
        foreground_process = get_foreground_process_name()
        cwd = session.cwd or "VS Code"
        project_name = Path(cwd).name
        notified = True
        notification_reason = "shown"
        record = {
            "event_time": event_time,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "project_name": project_name,
            "cwd": session.cwd,
            "source": session.source,
            "originator": session.originator,
            "session_id": session.session_id,
            "turn_id": turn_id,
            "cli_version": session.cli_version,
            "rollout_path": str(rollout_path),
            "foreground_process": foreground_process,
            "notification": {
                "attempted": True,
                "shown": notified,
                "reason": notification_reason,
            },
            "last_agent_message": last_message,
        }
        self._append_log_record(record)

        title = "Codex task finished"
        body = _truncate(f"{project_name}: {last_message}", 240)
        self.log(f"[notify] {body}")
        show_windows_notification(
            title,
            body,
            self.completion_sound,
            self._sound_file_str(),
            project_name,
            session.cwd,
        )

    def _record_prompt(
        self,
        session: SessionInfo,
        rollout_path: Path,
        prompt_id: str,
        prompt_kind: str,
        event_time: str,
        message: str,
    ) -> None:
        foreground_process = get_foreground_process_name()
        cwd = session.cwd or "VS Code"
        project_name = Path(cwd).name
        notified = True
        notification_reason = "shown"
        record = {
            "event_time": event_time,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "event_kind": "prompt",
            "prompt_kind": prompt_kind,
            "project_name": project_name,
            "cwd": session.cwd,
            "source": session.source,
            "originator": session.originator,
            "session_id": session.session_id,
            "prompt_id": prompt_id,
            "cli_version": session.cli_version,
            "rollout_path": str(rollout_path),
            "foreground_process": foreground_process,
            "notification": {
                "attempted": True,
                "shown": notified,
                "reason": notification_reason,
            },
            "message": message,
        }
        self._append_log_record(record)

        title = "Codex needs attention"
        body = _truncate(f"{project_name}: {message}", 240)
        self.log(f"[notify] {body}")
        show_windows_notification(
            title,
            body,
            self.prompt_sound,
            self._sound_file_str(),
            project_name,
            session.cwd,
        )

    def _append_log_record(self, record: dict[str, object]) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except OSError as exc:
            self.log(f"[warn] failed writing completion log {self.log_path}: {exc}")

    def _sound_file_str(self) -> str | None:
        if self.sound_file is None:
            return None
        return str(self.sound_file)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Notify on Codex task completion in VS Code.")
    parser.add_argument(
        "--sessions-root",
        default="~/.codex/sessions",
        help="Path to the Codex sessions directory. Default: %(default)s",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=POLL_SECONDS,
        help="Polling interval in seconds. Default: %(default)s",
    )
    parser.add_argument(
        "--log-path",
        default="./logs/codex-completions.jsonl",
        help="Path to the structured completion log file. Default: %(default)s",
    )
    parser.add_argument(
        "--sound-file",
        default=DEFAULT_SOUND_FILE,
        help="Path to a WAV file to play for notifications. Default: %(default)s",
    )
    parser.add_argument(
        "--completion-sound",
        choices=sorted(SOUND_CHOICES.keys()),
        default=DEFAULT_COMPLETION_SOUND,
        help="Fallback system sound for completion notifications if the WAV file is missing. Default: %(default)s",
    )
    parser.add_argument(
        "--prompt-sound",
        choices=sorted(SOUND_CHOICES.keys()),
        default=DEFAULT_PROMPT_SOUND,
        help="Fallback system sound for prompt notifications if the WAV file is missing. Default: %(default)s",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print watcher activity while running.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    notifier = CodexNotifier(
        sessions_root=_expand(args.sessions_root),
        log_path=_expand(args.log_path),
        poll_seconds=args.poll_seconds,
        completion_sound=args.completion_sound,
        prompt_sound=args.prompt_sound,
        sound_file=_expand(args.sound_file),
        verbose=args.verbose,
    )

    signal.signal(signal.SIGINT, notifier.stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, notifier.stop)

    print(f"Watching {notifier.sessions_root} for VS Code Codex completions...", flush=True)
    print(f"Logging completions to {notifier.log_path}", flush=True)
    notifier.watch_forever()
    print("Stopped.", flush=True)
    return 0
