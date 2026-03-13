"""Life XP CLI — gamify your life from the terminal."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from life_xp.database import init_db

console = Console()


@click.group()
def cli():
    """⚔️  Life XP — Gamify your life."""
    init_db()


# ── Dashboard ──────────────────────────────────────────────────────────

@cli.command()
def status():
    """Show the full dashboard."""
    from life_xp.ui.dashboard import show_dashboard
    show_dashboard()


@cli.command()
def stats():
    """Show your level, XP, and title."""
    from life_xp.xp import get_stats
    from life_xp.ui.progress import render_stats_panel
    stats = get_stats()
    console.print(render_stats_panel(stats))


# ── Goals ──────────────────────────────────────────────────────────────

@cli.group()
def goal():
    """Manage goals."""
    pass


@goal.command("add")
@click.argument("title")
@click.option("-c", "--category", default="Productivity", help="Category name")
@click.option("-d", "--description", default="", help="Description")
@click.option("-x", "--xp", default=100, type=int, help="XP reward")
@click.option("-t", "--target", default=None, type=float, help="Target value (for trackable goals)")
@click.option("-u", "--unit", default=None, help="Unit of measurement")
@click.option("-p", "--parent", default=None, type=int, help="Parent goal ID (for sub-goals)")
@click.option("--due", default=None, help="Due date (YYYY-MM-DD)")
def goal_add(title, category, description, xp, target, unit, parent, due):
    """Add a new goal."""
    from life_xp.engine import create_goal
    goal_id = create_goal(title, category, description, xp, target, unit, parent, due)
    console.print(f"[green]✓[/green] Goal created: [bold]{title}[/bold] (ID: {goal_id}, +{xp} XP)")


@goal.command("list")
@click.option("-s", "--status", default="active", help="Filter by status")
@click.option("-c", "--category", default=None, help="Filter by category")
def goal_list(status, category):
    """List goals."""
    from life_xp.engine import list_goals
    goals = list_goals(status, category)
    if not goals:
        console.print("[dim]No goals found.[/dim]")
        return

    table = Table(title=f"Goals ({status})", expand=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Cat", width=3)
    table.add_column("Goal", style="bold")
    table.add_column("Progress", width=24)
    table.add_column("XP", justify="right", style="yellow")

    for g in goals:
        icon = g.get("category_icon", "⭐")
        if g["target_value"]:
            pct = min((g["current_value"] or 0) / g["target_value"] * 100, 100)
            filled = int(pct / 5)
            progress = f"{'█' * filled}{'░' * (20 - filled)} {pct:.0f}%"
        else:
            progress = "[dim]manual[/dim]"
        table.add_row(str(g["id"]), icon, g["title"], progress, f"+{g['xp_reward']}")

    console.print(table)


@goal.command("complete")
@click.argument("goal_id", type=int)
def goal_complete(goal_id):
    """Mark a goal as complete and earn XP."""
    from life_xp.engine import complete_goal
    result = complete_goal(goal_id)
    console.print(f"[green]✓[/green] Goal completed! [bold yellow]+{result['xp_awarded']} XP[/bold yellow]")
    from life_xp.xp import get_stats
    from life_xp.ui.progress import render_stats_panel
    console.print(render_stats_panel(get_stats()))


@goal.command("update")
@click.argument("goal_id", type=int)
@click.argument("value", type=float)
def goal_update(goal_id, value):
    """Update progress on a trackable goal."""
    from life_xp.engine import update_goal_progress
    result = update_goal_progress(goal_id, value)
    if result["completed"]:
        console.print(f"[green]🎯 Goal complete![/green] [bold yellow]+{result['xp_awarded']} XP[/bold yellow]")
    else:
        console.print(f"[green]✓[/green] Progress updated to {value}")


@goal.command("breakdown")
@click.argument("goal_id", type=int)
def goal_breakdown(goal_id):
    """Show a goal and its sub-goals."""
    from life_xp.engine import get_goal, get_sub_goals
    goal = get_goal(goal_id)
    if not goal:
        console.print("[red]Goal not found.[/red]")
        return

    icon = goal.get("category_icon", "⭐")
    console.print(f"\n{icon} [bold]{goal['title']}[/bold]  [dim]({goal.get('category_name', '')})[/dim]")
    if goal.get("description"):
        console.print(f"  [dim]{goal['description']}[/dim]")

    subs = get_sub_goals(goal_id)
    if subs:
        for s in subs:
            status_icon = "[green]✓[/green]" if s["status"] == "completed" else "[dim]○[/dim]"
            console.print(f"  {status_icon} {s['title']}  [yellow]+{s['xp_reward']}[/yellow]")
    else:
        console.print("  [dim]No sub-goals. Use: lxp goal add \"sub goal\" -p {goal_id}[/dim]")


# ── Habits ─────────────────────────────────────────────────────────────

@cli.group()
def habit():
    """Manage habits."""
    pass


@habit.command("add")
@click.argument("title")
@click.option("-c", "--category", default="Productivity", help="Category name")
@click.option("-d", "--description", default="", help="Description")
@click.option("-f", "--frequency", default="daily", type=click.Choice(["daily", "weekly", "monthly"]))
@click.option("-x", "--xp", default=25, type=int, help="XP per check")
def habit_add(title, category, description, frequency, xp):
    """Start tracking a new habit."""
    from life_xp.engine import create_habit
    habit_id = create_habit(title, category, description, frequency, xp)
    console.print(f"[green]✓[/green] Habit created: [bold]{title}[/bold] (ID: {habit_id}, +{xp} XP/check)")


@habit.command("check")
@click.argument("habit_id", type=int)
def habit_check(habit_id):
    """Check off a habit for today."""
    from life_xp.engine import check_habit
    result = check_habit(habit_id)
    if result["already_checked"]:
        console.print("[yellow]Already checked today![/yellow]")
    else:
        streak = result["streak"]
        console.print(f"[green]✓[/green] Habit checked! [bold yellow]+{result['xp_awarded']} XP[/bold yellow]", end="")
        if streak > 1:
            console.print(f"  [bold]🔥 {streak}-day streak![/bold]")
        else:
            console.print()


@habit.command("list")
def habit_list():
    """List all habits with today's status."""
    from life_xp.engine import list_habits
    habits = list_habits()
    if not habits:
        console.print("[dim]No habits yet. Start one with: lxp habit add \"Exercise\"[/dim]")
        return

    table = Table(title="Habits", expand=True, border_style="green")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Cat", width=3)
    table.add_column("Habit", style="bold")
    table.add_column("Today", width=6, justify="center")
    table.add_column("Streak", width=10)
    table.add_column("Freq", width=8)
    table.add_column("XP", justify="right", style="yellow")

    for h in habits:
        icon = h.get("category_icon", "⭐")
        done = "[green]✓[/green]" if h["done_today"] else "[dim]○[/dim]"
        streak = h.get("streak", 0)
        streak_str = f"🔥 {streak}d" if streak >= 7 else (f"⚡ {streak}d" if streak > 0 else "[dim]—[/dim]")
        table.add_row(str(h["id"]), icon, h["title"], done, streak_str, h["frequency"], f"+{h['xp_per_check']}")

    console.print(table)


@habit.command("grid")
@click.argument("habit_id", type=int)
@click.option("-w", "--weeks", default=52, type=int, help="Number of weeks to show")
def habit_grid(habit_id, weeks):
    """Show the GitHub-style contribution grid for a habit."""
    from life_xp.engine import list_habits
    habits = list_habits()
    habit = next((h for h in habits if h["id"] == habit_id), None)
    if not habit:
        console.print("[red]Habit not found.[/red]")
        return
    from life_xp.ui.habit_grid import render_habit_grid
    render_habit_grid(habit_id, habit["title"], console, weeks)


@habit.command("overview")
@click.option("-w", "--weeks", default=20, type=int, help="Number of weeks to show")
def habit_overview(weeks):
    """Show an aggregated activity grid across all habits."""
    from life_xp.ui.habit_grid import render_overview_grid
    render_overview_grid(console, weeks)


# ── Quests ─────────────────────────────────────────────────────────────

@cli.group()
def quest():
    """Manage multi-objective quests."""
    pass


@quest.command("add")
@click.argument("title")
@click.option("-o", "--objective", multiple=True, required=True, help="Quest objectives (repeat for multiple)")
@click.option("-c", "--category", default="Productivity")
@click.option("-d", "--description", default="")
@click.option("-x", "--xp", default=500, type=int)
@click.option("--deadline", default=None)
def quest_add(title, objective, category, description, xp, deadline):
    """Create a new quest with objectives."""
    from life_xp.engine import create_quest
    quest_id = create_quest(title, list(objective), category, description, xp, deadline)
    console.print(f"[green]✓[/green] Quest created: [bold]{title}[/bold] (ID: {quest_id}, +{xp} XP)")
    for obj in objective:
        console.print(f"  [dim]○[/dim] {obj}")


@quest.command("list")
@click.option("-s", "--status", default="active")
def quest_list(status):
    """List quests."""
    from life_xp.engine import list_quests
    quests = list_quests(status)
    if not quests:
        console.print("[dim]No quests found.[/dim]")
        return

    for q in quests:
        done = sum(1 for o in q["objectives"] if o["completed"])
        total = len(q["objectives"])
        console.print(f"\n[bold]{q['title']}[/bold]  [dim](ID: {q['id']})[/dim]  [yellow]+{q['xp_reward']} XP[/yellow]")
        for o in q["objectives"]:
            icon = "[green]✓[/green]" if o["completed"] else "[dim]○[/dim]"
            console.print(f"  {icon} {o['description']}  [dim](obj ID: {o['id']})[/dim]")
        console.print(f"  Progress: {done}/{total}")


@quest.command("complete-obj")
@click.argument("quest_id", type=int)
@click.argument("objective_id", type=int)
def quest_complete_obj(quest_id, objective_id):
    """Complete a quest objective."""
    from life_xp.engine import complete_quest_objective
    result = complete_quest_objective(quest_id, objective_id)
    if result["quest_completed"]:
        console.print(f"[green]🏆 Quest complete![/green] [bold yellow]+{result['xp_awarded']} XP[/bold yellow]")
    else:
        console.print(f"[green]✓[/green] Objective completed! {result['remaining']} remaining.")


# ── Rewards ────────────────────────────────────────────────────────────

@cli.group()
def reward():
    """Manage rewards you can redeem with XP."""
    pass


@reward.command("add")
@click.argument("title")
@click.option("-x", "--xp-cost", required=True, type=int, help="XP cost to redeem")
@click.option("-d", "--description", default="")
def reward_add(title, xp_cost, description):
    """Add a reward you can earn."""
    from life_xp.engine import create_reward
    reward_id = create_reward(title, xp_cost, description)
    console.print(f"[green]✓[/green] Reward added: [bold]{title}[/bold] (costs {xp_cost} XP)")


@reward.command("list")
def reward_list():
    """List available rewards."""
    from life_xp.engine import list_rewards
    from life_xp.xp import get_stats
    rewards = list_rewards()
    stats = get_stats()

    if not rewards:
        console.print("[dim]No rewards yet. Add one with: lxp reward add \"Coffee treat\" -x 500[/dim]")
        return

    console.print(f"[bold]Your XP: {stats.total_xp:,}[/bold]\n")
    table = Table(title="Rewards Shop", border_style="yellow")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Reward", style="bold")
    table.add_column("Cost", justify="right")
    table.add_column("Affordable?", justify="center")

    for r in rewards:
        affordable = "[green]✓[/green]" if stats.total_xp >= r["xp_cost"] else "[red]✗[/red]"
        table.add_row(str(r["id"]), r["title"], f"{r['xp_cost']} XP", affordable)

    console.print(table)


@reward.command("redeem")
@click.argument("reward_id", type=int)
def reward_redeem(reward_id):
    """Redeem a reward with your XP."""
    from life_xp.engine import redeem_reward
    try:
        result = redeem_reward(reward_id)
        console.print(f"[green]🎁 Redeemed![/green] {result['reward']}  [dim](-{result['xp_spent']} XP)[/dim]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")


# ── Sensors ────────────────────────────────────────────────────────────

@cli.group()
def sensor():
    """Manage automated sensors that track your progress."""
    pass


@sensor.command("list")
def sensor_list():
    """List available and configured sensors."""
    from life_xp.sensors.base import SensorRegistry
    # Import sensors to register them
    import life_xp.sensors.steps
    import life_xp.sensors.screentime
    import life_xp.sensors.git_sensor
    import life_xp.sensors.finance
    import life_xp.sensors.imessage

    console.print("[bold]Available Sensors:[/bold]\n")
    for name, sensor_cls in SensorRegistry.all().items():
        sensor = sensor_cls()
        available = "[green]✓ available[/green]" if sensor.is_available() else "[dim]✗ not available[/dim]"
        console.print(f"  {name:20s} {available}")


@sensor.command("run")
def sensor_run():
    """Run all configured sensors now."""
    from life_xp.sensors.base import SensorRegistry
    import life_xp.sensors.steps
    import life_xp.sensors.screentime
    import life_xp.sensors.git_sensor
    import life_xp.sensors.finance
    import life_xp.sensors.imessage

    console.print("[dim]Running sensors...[/dim]")
    SensorRegistry.run_all()
    console.print("[green]✓[/green] Sensor check complete.")


# ── Categories ─────────────────────────────────────────────────────────

@cli.command("categories")
def categories():
    """List all categories."""
    from life_xp.engine import list_categories
    cats = list_categories()
    for c in cats:
        console.print(f"  {c['icon']}  {c['name']}")


# ── XP History ─────────────────────────────────────────────────────────

@cli.command("history")
@click.option("-d", "--days", default=30, type=int, help="Number of days")
def history(days):
    """Show XP earning history."""
    from life_xp.engine import get_xp_history
    xp_hist = get_xp_history(days)
    if not xp_hist:
        console.print("[dim]No XP earned yet.[/dim]")
        return

    table = Table(title=f"XP History (last {days} days)", border_style="yellow")
    table.add_column("Date", style="dim")
    table.add_column("XP", justify="right", style="yellow")
    table.add_column("", width=30)

    max_xp = max(d["xp"] for d in xp_hist) or 1
    for d in xp_hist:
        bar_len = int(d["xp"] / max_xp * 30)
        bar = "█" * bar_len
        table.add_row(d["day"], f"+{d['xp']}", f"[green]{bar}[/green]")

    console.print(table)
    total = sum(d["xp"] for d in xp_hist)
    console.print(f"\n  Total: [bold yellow]{total:,} XP[/bold yellow]")


# ── Watch Mode (Daemon) ───────────────────────────────────────────────

@cli.command("watch")
@click.option("-i", "--interval", default=300, type=int, help="Check interval in seconds")
def watch(interval):
    """Run in daemon mode — continuously check sensors and award XP."""
    import time
    from life_xp.sensors.base import SensorRegistry
    import life_xp.sensors.steps
    import life_xp.sensors.screentime
    import life_xp.sensors.git_sensor
    import life_xp.sensors.finance
    import life_xp.sensors.imessage

    console.print(f"[bold]⚔️  Life XP Watch Mode[/bold]  [dim](checking every {interval}s, Ctrl+C to stop)[/dim]\n")

    try:
        while True:
            SensorRegistry.run_all()
            from life_xp.xp import get_stats
            stats = get_stats()
            console.print(
                f"[dim]{time.strftime('%H:%M:%S')}[/dim]  "
                f"Lv.{stats.level} {stats.title}  "
                f"[yellow]{stats.total_xp:,} XP[/yellow]  "
                f"[{'green' if stats.progress_pct > 50 else 'yellow'}]{stats.progress_pct:.0f}%[/] to next level"
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch mode stopped.[/dim]")


if __name__ == "__main__":
    cli()
