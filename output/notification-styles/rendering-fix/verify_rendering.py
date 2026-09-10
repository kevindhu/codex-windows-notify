"""Retained Windows runtime verification for the DPI-aware notification renderer."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from windows_notify_codex import notifier

RUN = notifier.subprocess.run
INSTRUMENT = r'''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PreviewProbe {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr window, out Rect rect);
    [DllImport("user32.dll")]
    public static extern IntPtr GetWindowDpiAwarenessContext(IntPtr window);
    [DllImport("user32.dll")]
    public static extern int GetAwarenessFromDpiAwarenessContext(IntPtr context);
}
"@
$script:previewCaptured = $false
$previewTimer = [System.Windows.Threading.DispatcherTimer]::new()
$previewTimer.Interval = [TimeSpan]::FromMilliseconds([int]$env:PREVIEW_DURATION)
$previewTimer.Add_Tick({
    $previewTimer.Stop()
    $target = switch ($env:PREVIEW_CASE) {
        'completion' { $titleLabel }
        'attention' { $messageLabel }
        default { $card }
    }
    $event = [System.Windows.Input.MouseButtonEventArgs]::new(
        [System.Windows.Input.Mouse]::PrimaryDevice, [Environment]::TickCount,
        [System.Windows.Input.MouseButton]::Left
    )
    $event.RoutedEvent = [System.Windows.Input.Mouse]::MouseUpEvent
    $target.RaiseEvent($event)
    if (-not $script:notificationClosing) { throw 'Click did not reach the dismissal handler.' }
})
$form.Add_ContentRendered({
    if ($script:previewCaptured) { return }
    $script:previewCaptured = $true
    $handle = [System.Windows.Interop.WindowInteropHelper]::new($form).Handle
    $dpi = [NotificationDpi]::GetDpiForWindow($handle)
    $awareness = [PreviewProbe]::GetAwarenessFromDpiAwarenessContext(
        [PreviewProbe]::GetWindowDpiAwarenessContext($handle)
    )
    $bounds = [PreviewProbe+Rect]::new()
    [void][PreviewProbe]::GetWindowRect($handle, [ref]$bounds)
    if ($awareness -ne 2) { throw 'Window is not per-monitor DPI-aware.' }
    $width = $bounds.Right - $bounds.Left
    $height = $bounds.Bottom - $bounds.Top
    if ([Math]::Abs($width - $form.Width * $dpi / 96.0) -gt 1) {
        throw 'Window pixels do not match its logical size and monitor DPI.'
    }
    $details = @{
        case = $env:PREVIEW_CASE
        window_dpi = $dpi
        window_awareness = $awareness
        logical_width = $form.Width
        logical_height = $form.Height
        physical_width = $width
        physical_height = $height
        content_width = $card.ActualWidth
        content_height = $card.ActualHeight
        message_height = $messageLabel.ActualHeight
        visual_scale = [System.Windows.PresentationSource]::FromVisual($form).CompositionTarget.TransformToDevice.M11
        left = $bounds.Left
        top = $bounds.Top
    }
    foreach ($renderDpi in @(96, 120, 144, 192)) {
        $bitmap = [System.Windows.Media.Imaging.RenderTargetBitmap]::new(
            [int][Math]::Ceiling($form.Width * $renderDpi / 96.0),
            [int][Math]::Ceiling($form.Height * $renderDpi / 96.0),
            $renderDpi, $renderDpi, [System.Windows.Media.PixelFormats]::Pbgra32
        )
        $bitmap.Render($card)
        $encoder = [System.Windows.Media.Imaging.PngBitmapEncoder]::new()
        $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
        $path = Join-Path $env:PREVIEW_DIR ($env:PREVIEW_CASE + '-' + $renderDpi + 'dpi.png')
        $stream = [System.IO.File]::Create($path)
        try { $encoder.Save($stream) } finally { $stream.Dispose() }
    }
    $details | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $env:PREVIEW_DIR ($env:PREVIEW_CASE + '.json'))
    $previewTimer.Start()
})
$form.Add_Closed({ $previewTimer.Stop() })
'''


def verify(name, title, body):
    def checked_run(args, **kwargs):
        args = list(args)
        args[-1] = '$ErrorActionPreference = "Stop"\n' + args[-1].replace(
            '[void]$form.ShowDialog()', INSTRUMENT + '\n[void]$form.ShowDialog()'
        )
        kwargs['env'].update({
            'PREVIEW_DIR': str(OUT), 'PREVIEW_CASE': name,
            'PREVIEW_DURATION': os.environ.get('PREVIEW_DURATION', '1000'),
            'CODEX_NOTIFY_CLICK_LOG': str(ROOT / 'logs' / 'notification-rendering-tests.log'),
        })
        kwargs['timeout'] = 25
        result = RUN(args, **kwargs)
        stderr = result.stderr.decode(errors='replace')
        assert result.returncode == 0 and not stderr, stderr
        data = json.loads((OUT / f'{name}.json').read_text(encoding='utf-8-sig'))
        print(json.dumps(data), flush=True)
        return result
    notifier.subprocess.run = checked_run
    notifier.show_windows_notification(title, body, 'none', None, 'rendering-test', str(ROOT))


if __name__ == '__main__':
    verify('completion', 'Codex task finished',
           'windows-notify-codex: The update is ready to review. All checks passed.')
    verify('attention', 'Codex needs attention',
           'windows-notify-codex: This is a rendering test. No action is required.')
    verify('long', 'Codex task finished',
           notifier._truncate('design & development: The update is ready to review. '
                              'Files & folders, long project names, and longer messages '
                              'should remain clear at the actual display resolution. '
                              'Extra text should end cleanly with an ellipsis instead of being cut off.', 240))
    print('All runtime render, DPI, and routed-click checks passed.')
