"""GitHub-style contribution/habit grid visualization."""

from datetime import date, timedelta
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from life_xp.engine import get_habit_history


# Color intensity levels (like GitHub's contribution graph)
LEVELS = [
    ("dim", "░"),      # No activity
    ("green", "▒"),    # Light
    ("green", "▓"),    # Medium
    ("bold green", "█"),  # High
]

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = ["Mon", "", "Wed", "", "Fri", "", "Sun"]


def render_habit_grid(habit_id: int, title: str, console: Console, weeks: int = 52):
    """Render a GitHub-style contribution grid for a habit."""
    history = get_habit_history(habit_id, days=weeks * 7)
    checked_dates = {r["checked_date"] for r in history}

    today = date.today()
    start = today - timedelta(days=weeks * 7 - 1)

    # Align to start of week (Monday)
    start = start - timedelta(days=start.weekday())

    # Build the grid data: weeks × 7 days
    grid: list[list[int]] = []  # Each inner list is a week (7 days)
    current = start
    week: list[int] = []

    while current <= today:
        if current.isoformat() in checked_dates:
            week.append(1)
        else:
            week.append(0)

        if len(week) == 7:
            grid.append(week)
            week = []
        current += timedelta(days=1)

    if week:
        # Pad incomplete final week
        while len(week) < 7:
            week.append(-1)  # Future/no-data
        grid.append(week)

    # Render as rows (one per day of week), columns = weeks
    lines = []

    # Month labels
    month_line = "    "  # Offset for day labels
    last_month = -1
    for w_idx, w in enumerate(grid):
        # First day of this week
        week_start = start + timedelta(weeks=w_idx)
        if week_start.month != last_month:
            month_line += MONTH_LABELS[week_start.month - 1][:3]
            last_month = week_start.month
        else:
            month_line += " "
    lines.append(month_line)

    # Grid rows (Mon–Sun)
    for day_idx in range(7):
        label = DAY_LABELS[day_idx].ljust(4)
        row = Text(label, style="dim")

        for w_idx, w in enumerate(grid):
            val = w[day_idx] if day_idx < len(w) else -1
            if val == -1:
                row.append(" ", style="dim")
            elif val == 0:
                row.append("░", style="dim")
            else:
                row.append("█", style="bold green")

        lines.append(row)

    # Stats
    total_checks = len(checked_dates)
    current_streak = _calc_streak(checked_dates)

    # Combine
    output = Text()
    for i, line in enumerate(lines):
        if isinstance(line, str):
            output.append(line + "\n", style="dim")
        else:
            output.append_text(line)
            output.append("\n")

    stats_line = f"  {total_checks} checks in the last {weeks} weeks"
    if current_streak > 0:
        stats_line += f"  |  Current streak: {current_streak}d 🔥"

    console.print(Panel(
        output,
        title=f"[bold]{title}[/bold]",
        subtitle=stats_line,
        border_style="green",
        padding=(0, 1),
    ))


def _calc_streak(checked_dates: set[str]) -> int:
    """Calculate current streak from today backwards."""
    if not checked_dates:
        return 0

    streak = 0
    current = date.today()
    while current.isoformat() in checked_dates:
        streak += 1
        current -= timedelta(days=1)

    return streak


def render_overview_grid(console: Console, weeks: int = 20):
    """Render an aggregated activity grid across all habits."""
    from life_xp.database import get_connection

    conn = get_connection()
    today = date.today()
    start = (today - timedelta(days=weeks * 7)).isoformat()

    # Get all check dates with counts
    rows = conn.execute(
        """SELECT checked_date, COUNT(*) as cnt
           FROM habit_checks WHERE checked_date >= ?
           GROUP BY checked_date""",
        (start,),
    ).fetchall()
    conn.close()

    date_counts = {r["checked_date"]: r["cnt"] for r in rows}
    if not date_counts:
        console.print("[dim]No habit data yet. Start checking off habits![/dim]")
        return

    max_count = max(date_counts.values()) or 1

    start_date = today - timedelta(days=weeks * 7 - 1)
    start_date = start_date - timedelta(days=start_date.weekday())  # Align to Monday

    # Build grid
    grid: list[list[float]] = []
    current = start_date
    week: list[float] = []

    while current <= today:
        iso = current.isoformat()
        if iso in date_counts:
            week.append(date_counts[iso] / max_count)
        else:
            week.append(0)

        if len(week) == 7:
            grid.append(week)
            week = []
        current += timedelta(days=1)

    if week:
        while len(week) < 7:
            week.append(-1)
        grid.append(week)

    # Render
    intensity_chars = "░▒▓█"
    lines = []

    # Month header
    month_line = "    "
    last_month = -1
    for w_idx in range(len(grid)):
        week_start = start_date + timedelta(weeks=w_idx)
        if week_start.month != last_month:
            month_line += MONTH_LABELS[week_start.month - 1][:3]
            last_month = week_start.month
        else:
            month_line += " "
    lines.append(month_line)

    for day_idx in range(7):
        label = DAY_LABELS[day_idx].ljust(4)
        row = Text(label, style="dim")

        for w in grid:
            val = w[day_idx] if day_idx < len(w) else -1
            if val == -1:
                row.append(" ", style="dim")
            elif val == 0:
                row.append("░", style="dim")
            elif val < 0.33:
                row.append("▒", style="green")
            elif val < 0.66:
                row.append("▓", style="green")
            else:
                row.append("█", style="bold green")

        lines.append(row)

    output = Text()
    for line in lines:
        if isinstance(line, str):
            output.append(line + "\n", style="dim")
        else:
            output.append_text(line)
            output.append("\n")

    total_days = sum(1 for v in date_counts.values() if v > 0)
    console.print(Panel(
        output,
        title="[bold]Activity Overview[/bold]",
        subtitle=f"  {total_days} active days in the last {weeks} weeks",
        border_style="cyan",
        padding=(0, 1),
    ))
