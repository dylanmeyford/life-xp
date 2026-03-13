"""Cross-platform notification system."""

import subprocess
import platform


def notify(title: str, message: str, sound: bool = True):
    """Send a desktop notification. Works on macOS, Linux, and Windows."""
    system = platform.system()

    if system == "Darwin":
        _notify_macos(title, message, sound)
    elif system == "Linux":
        _notify_linux(title, message)
    else:
        _notify_terminal(title, message)


def _notify_macos(title: str, message: str, sound: bool):
    sound_part = 'sound name "Hero"' if sound else ""
    script = f'display notification "{message}" with title "{title}" {sound_part}'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _notify_terminal(title, message)


def _notify_linux(title: str, message: str):
    try:
        subprocess.run(["notify-send", title, message], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _notify_terminal(title, message)


def _notify_terminal(title: str, message: str):
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(f"[bold]{message}[/bold]", title=title, border_style="gold1"))
