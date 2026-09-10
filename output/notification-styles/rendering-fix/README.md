# Retained rendering verification

Keep these images and results for visual comparison.

- `completion-120dpi.png`, `attention-120dpi.png`, and `long-120dpi.png` are renders from the actual WPF popup at this machine's native 125% display scale.
- The JSON files record the real window DPI, DPI-awareness level, physical dimensions, and visual scale.
- Other DPI PNGs are offscreen exports, not evidence of tests on differently scaled monitors. Use the 120 DPI images for the native-size comparison on this machine.
- `verify_rendering.py` exercises the real notification function, captures the window content, and checks routed click dismissal. Auto-dismiss is test-only.
- `notifier-before.py` preserves the pre-fix source. The earlier Windows Forms render remains in `../implemented/completion.png`.

The chosen design remains 01 - Refined baseline. The rendering implementation now draws text and rounded edges directly at the monitor's resolution.
