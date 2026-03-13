"""Main dashboard — the command center for your Life XP."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.columns import Columns
from rich.progress_bar import ProgressBar

from life_xp.xp import get_stats
from life_xp.engine import list_goals, list_habits, list_quests, get_xp_history
from life_xp.ui.habit_grid import render_habit_grid
from life_xp.ui.progress import render_xp_bar, render_stats_panel

console = Console()


def show_dashboard():
    """Render the full dashboard."""
    stats = get_stats()
    goals = list_goals("active")
    habits = list_habits()
    quests = list_quests("active")
    xp_history = get_xp_history(30)

    console.clear()
    console.print()

    # ── Header ──
    console.print(render_stats_panel(stats))
    console.print()

    # ── Active Goals ──
    if goals:
        goal_table = Table(title="Active Goals", expand=True, border_style="blue")
        goal_table.add_column("ID", style="dim", width=4)
        goal_table.add_column("Cat", width=3)
        goal_table.add_column("Goal", style="bold")
        goal_table.add_column("Progress", width=20)
        goal_table.add_column("XP", justify="right", style="yellow")
        goal_table.add_column("Due", width=12)

        for g in goals[:10]:
            icon = g.get("category_icon", "⭐")
            progress = ""
            if g["target_value"]:
                pct = min((g["current_value"] or 0) / g["target_value"] * 100, 100)
                filled = int(pct / 5)
                progress = f"{'█' * filled}{'░' * (20 - filled)} {pct:.0f}%"
            else:
                progress = "manual"

            goal_table.add_row(
                str(g["id"]),
                icon,
                g["title"],
                progress,
                f"+{g['xp_reward']}",
                g.get("due_date", "") or "",
            )
        console.print(goal_table)
        console.print()

    # ── Habits ──
    if habits:
        habit_table = Table(title="Habits", expand=True, border_style="green")
        habit_table.add_column("ID", style="dim", width=4)
        habit_table.add_column("Cat", width=3)
        habit_table.add_column("Habit", style="bold")
        habit_table.add_column("Today", width=6)
        habit_table.add_column("Streak", width=12)
        habit_table.add_column("XP", justify="right", style="yellow")

        for h in habits:
            icon = h.get("category_icon", "⭐")
            done = "[green]✓[/green]" if h.get("done_today") else "[dim]○[/dim]"
            streak = h.get("streak", 0)
            streak_display = f"{'🔥' if streak >= 7 else '⚡'} {streak}d" if streak > 0 else "[dim]—[/dim]"

            habit_table.add_row(
                str(h["id"]),
                icon,
                h["title"],
                done,
                streak_display,
                f"+{h['xp_per_check']}",
            )
        console.print(habit_table)
        console.print()

    # ── Quests ──
    if quests:
        quest_table = Table(title="Active Quests", expand=True, border_style="magenta")
        quest_table.add_column("ID", style="dim", width=4)
        quest_table.add_column("Quest", style="bold")
        quest_table.add_column("Progress", width=24)
        quest_table.add_column("XP", justify="right", style="yellow")
        quest_table.add_column("Deadline", width=12)

        for q in quests:
            progress = q.get("progress", 0)
            objs = q.get("objectives", [])
            done = sum(1 for o in objs if o["completed"])
            total = len(objs)
            filled = int(progress * 20)
            bar = f"{'█' * filled}{'░' * (20 - filled)} {done}/{total}"

            quest_table.add_row(
                str(q["id"]),
                q["title"],
                bar,
                f"+{q['xp_reward']}",
                q.get("deadline", "") or "",
            )
        console.print(quest_table)
        console.print()

    # ── Habit Grids ──
    if habits:
        console.print(Panel("[bold]Habit Grids[/bold]", border_style="green"))
        for h in habits[:5]:  # Show grids for top 5 habits
            render_habit_grid(h["id"], h["title"], console)
            console.print()

    # ── XP Activity (last 30 days) ──
    if xp_history:
        _render_xp_sparkline(xp_history, console)

    if not goals and not habits and not quests:
        console.print(Panel(
            "[dim]No goals, habits, or quests yet.\n\n"
            "Get started:\n"
            "  [bold]lxp goal add[/bold]     — Set a new goal\n"
            "  [bold]lxp habit add[/bold]    — Start tracking a habit\n"
            "  [bold]lxp quest add[/bold]    — Begin a quest[/dim]",
            title="Welcome to Life XP!",
            border_style="cyan",
        ))


def _render_xp_sparkline(xp_history: list[dict], console: Console):
    """Render a mini bar chart of XP earned per day."""
    if not xp_history:
        return

    max_xp = max(d["xp"] for d in xp_history) or 1
    bars = []
    for d in xp_history[-30:]:
        height = max(1, int(d["xp"] / max_xp * 8))
        block_chars = " ▁▂▃▄▅▆▇█"
        bars.append(block_chars[height])

    sparkline = "".join(bars)
    total = sum(d["xp"] for d in xp_history)

    console.print(Panel(
        f"[green]{sparkline}[/green]\n"
        f"[dim]{xp_history[0]['day']} → {xp_history[-1]['day']}[/dim]  "
        f"Total: [bold yellow]{total:,} XP[/bold yellow]",
        title="XP Activity (30 days)",
        border_style="yellow",
    ))
