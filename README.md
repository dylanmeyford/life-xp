# Life XP

Gamify your life. Set goals, build habits, complete quests, earn XP, level up.

A local agent that lives on your computer, tracks your progress using local tools
(Apple Health, iMessage, git, bank transactions), and reactively rewards you when
you hit milestones.

```
  ╔══════════════════════════════════════╗
  ║  ⚔️  LIFE XP                        ║
  ║  Adept  ·  Level 15  ·  4,230 XP    ║
  ║  ⟨████████████████░░░░⟩ 680/1000 XP ║
  ╚══════════════════════════════════════╝
```

## Features

- **Goals** — Set discrete goals with XP rewards. Break big goals into sub-goals.
- **Habits** — Daily/weekly tracking with streak bonuses and GitHub-style contribution grids.
- **Quests** — Multi-objective challenges with big XP payouts.
- **Rewards** — Define rewards you can redeem with earned XP.
- **Sensors** — Local tool integrations that auto-detect goal completion:
  - Apple Health (steps via Shortcuts)
  - iMessage (social activity tracking)
  - Git (commit tracking)
  - Transactions (CSV/JSON bank exports)
  - Screen time (focused app usage)
- **Reactive notifications** — Desktop popups when you hit milestones.
- **Watch mode** — Background daemon that continuously monitors sensors.

## Install

```bash
pip install -e .
```

## Quick Start

```bash
# See your dashboard
lxp status

# Add a goal
lxp goal add "Run a 5K" -c Fitness -x 500 -t 5 -u km

# Add a daily habit
lxp habit add "Meditate" -c Mindfulness -f daily -x 30

# Check off a habit
lxp habit check 1

# See your habit grid (GitHub-style)
lxp habit grid 1

# See activity overview
lxp habit overview

# Create a quest
lxp quest add "Healthy Week" \
  -o "Exercise 3 times" \
  -o "Cook dinner 5 times" \
  -o "Sleep 8 hours every night" \
  -c Health -x 1000

# Add a reward
lxp reward add "Nice dinner out" -x 2000

# Start watch mode (auto-detect achievements)
lxp watch
```

## Commands

| Command | Description |
|---|---|
| `lxp status` | Full dashboard with goals, habits, quests, grids |
| `lxp stats` | Quick XP/level summary |
| `lxp goal add/list/complete/update/breakdown` | Manage goals |
| `lxp habit add/list/check/grid/overview` | Manage habits |
| `lxp quest add/list/complete-obj` | Manage quests |
| `lxp reward add/list/redeem` | Manage rewards |
| `lxp sensor list/run` | Manage auto-detection sensors |
| `lxp watch` | Run in daemon mode |
| `lxp categories` | List goal categories |
| `lxp history` | XP earning history with chart |

## Sensors

Sensors are local tool integrations that poll data sources on your machine and
automatically detect when goals/habits are completed. No cloud auth needed — everything
runs locally.

| Sensor | Platform | What it does |
|---|---|---|
| `steps` | macOS | Reads step count from Apple Health via Shortcuts |
| `imessage` | macOS | Counts messages sent today from Messages.app |
| `git` | All | Counts commits in configured repos |
| `transactions` | All | Watches CSV/JSON exports for keyword matches |
| `screentime` | macOS | Detects focused app usage |

Drop transaction files into `~/.life-xp/transactions/` and health data into
`~/.life-xp/health/` for the sensors to pick up.

## XP System

- Each level requires progressively more XP (base 100, exponent 1.5)
- Habit streaks give bonus XP (up to 4x at 30-day streaks)
- Milestone streaks (7, 14, 30, 50, 100, 365 days) give big bonus XP
- Titles evolve as you level: Novice → Apprentice → Journeyman → ... → Ascended

## Architecture

```
life_xp/
├── cli.py            # Click CLI interface
├── database.py       # SQLite schema and connection
├── engine.py         # Core logic: goals, habits, quests, rewards
├── xp.py             # XP/leveling calculations
├── sensors/          # Local tool integrations
│   ├── base.py       # Sensor framework
│   ├── steps.py      # Apple Health steps
│   ├── imessage.py   # iMessage tracking
│   ├── git_sensor.py # Git commit tracking
│   ├── finance.py    # Transaction monitoring
│   └── screentime.py # App usage tracking
├── ui/               # Rich terminal UI
│   ├── dashboard.py  # Main dashboard
│   ├── habit_grid.py # GitHub-style grids
│   └── progress.py   # XP bars and stats
└── notifications/    # Desktop notification system
```

Data is stored in `~/.life-xp/life.db` (SQLite). Override with `LIFE_XP_DATA` env var.
