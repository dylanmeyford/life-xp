"""XP bar and stats rendering."""

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.columns import Columns

from life_xp.xp import PlayerStats


def render_xp_bar(stats: PlayerStats, width: int = 40) -> Text:
    """Render a fancy XP progress bar."""
    filled = int(stats.progress_pct / 100 * width)
    empty = width - filled

    bar = Text()
    bar.append("  ⟨", style="bold cyan")
    bar.append("█" * filled, style="bold cyan")
    bar.append("░" * empty, style="dim")
    bar.append("⟩", style="bold cyan")
    bar.append(f" {stats.xp_in_level}/{stats.xp_for_next} XP", style="yellow")

    return bar


def render_stats_panel(stats: PlayerStats) -> Panel:
    """Render the player stats header panel."""
    level_display = f"Level {stats.level}"
    title_display = stats.title

    # Build the content
    content = Text()
    content.append(f"  {title_display}", style="bold")
    content.append(f"  ·  ", style="dim")
    content.append(level_display, style="bold cyan")
    content.append(f"  ·  ", style="dim")
    content.append(f"{stats.total_xp:,} XP", style="bold yellow")
    content.append("\n")
    content.append_text(render_xp_bar(stats))

    return Panel(
        content,
        title="[bold]⚔️  LIFE XP[/bold]",
        border_style="cyan",
        padding=(0, 1),
    )


def render_level_up(old_level: int, new_level: int, title: str) -> Panel:
    """Render a level up celebration."""
    art = Text()
    art.append("\n")
    art.append("  ╔══════════════════════════╗\n", style="bold yellow")
    art.append("  ║                          ║\n", style="bold yellow")
    art.append("  ║", style="bold yellow")
    art.append(f"    ⬆️  LEVEL UP!  ⬆️     ", style="bold")
    art.append("║\n", style="bold yellow")
    art.append("  ║                          ║\n", style="bold yellow")
    art.append("  ║", style="bold yellow")
    art.append(f"   {old_level} → {new_level}".center(26), style="bold cyan")
    art.append("║\n", style="bold yellow")
    art.append("  ║", style="bold yellow")
    art.append(f'   "{title}"'.center(26), style="italic")
    art.append("║\n", style="bold yellow")
    art.append("  ║                          ║\n", style="bold yellow")
    art.append("  ╚══════════════════════════╝\n", style="bold yellow")

    return Panel(art, border_style="yellow")
