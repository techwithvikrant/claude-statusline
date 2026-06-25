# Claude Code Status Line — context + rate-limit bars

A custom [status line](https://docs.claude.com/en/docs/claude-code/statusline) for
[Claude Code](https://claude.com/claude-code) that shows your **context-window usage**
and **5-hour / weekly rate-limit usage** as smooth progress bars, with proactive
warnings and the next reset time — plus your working directory and git branch on a
second line.

```
Opus 4.8 │ ctx [██▉░░░░░░░░░] 24% · 240k/1M │ 5h [█████░░░] 62% ⟳ 7:46 PM IST  7d [███▎░░░░] 40% · 5d6h
~/code/my-project   main*
```

> Colors shift **green → yellow → red** as a metric fills up. The example above is
> shown without color; in your terminal each segment is colored.

---

## Features

- **Context window** — `ctx [bar] N% · used/size` (e.g. `240k/1M`), straight from
  Claude Code's native token accounting.
- **5-hour limit** — `5h [bar] N%` plus the **exact reset clock time** (in IST by
  default).
- **Weekly limit** — `7d [bar] N%` plus **days + hours remaining** until reset.
- **Proactive markers** before any metric that's getting tight:
  - `▲` caution at **≥ 75%** (yellow)
  - `⚠` critical at **≥ 90%** (bold red — bar and number also turn bold red)
  - `↻` relief when a window **resets within 10 minutes** (green)
- **Smooth bars** using Unicode partial-block characters (`▏▎▍▌▋▊▉█`) for
  sub-character resolution.
- **Second line**: current directory (`~` for home) + git branch (with `*` when the
  working tree is dirty; hidden outside a git repo).
- **Visible from the first render** — rate-limit values are cached to disk and reused
  at session start (see [How it works](#how-it-works)).
- **No dependencies** beyond `python3`. No `jq`, no extra installs.

---

## Requirements

- **Claude Code v2.x** (the status-line JSON must include `context_window` and
  `rate_limits` — recent 2.x builds do). On older builds those segments simply don't
  render; nothing errors.
- **python3** on your `PATH`.

---

## Install

### Option A — one-line installer (recommended)

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
./install.sh
```

The installer copies `statusline-command.sh` into `~/.claude/` and adds the
`statusLine` block to `~/.claude/settings.json`, preserving any settings you already
have. Open a new Claude Code session (or wait for the next render) to see it.

### Option B — manual

1. **Copy the script** into your Claude config directory and make it executable:

   ```bash
   mkdir -p ~/.claude
   cp statusline-command.sh ~/.claude/statusline-command.sh
   chmod +x ~/.claude/statusline-command.sh
   ```

2. **Wire it into `~/.claude/settings.json`.** Create the file as `{}` if it doesn't
   exist, then add the `statusLine` block (keep any existing keys). Use **your own
   absolute home path** — `~` is not expanded here:

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "/Users/YOUR_USERNAME/.claude/statusline-command.sh",
       "padding": 0
     }
   }
   ```

   Tip: print the exact path with
   `echo "$HOME/.claude/statusline-command.sh"`.

3. **Verify** the JSON parses and the script runs (see [Testing](#testing)). The
   status line shows up on the next render.

---

## Configuration

### Timezone

Reset times display in **IST (Asia/Kolkata)** by default. To change it, edit one line
near the top of `statusline-command.sh`:

```python
IST = ZoneInfo("Asia/Kolkata")      # e.g. "America/New_York", "Europe/London", "UTC"
```

### Warning thresholds

Tune the caution/critical cutoffs in the `alert()` and `usage_color()` functions
(defaults: caution ≥ 75%, critical ≥ 90%).

### Bar width

`bar(pct, 12, ...)` for the context bar and `bar(pct, 8, ...)` for the rate-limit bars
— change the width argument to taste.

### Directory / branch line

The second line (directory + git branch) is always shown. To drop it, remove the
`line2` block at the bottom of the script and change the final write to
`sys.stdout.write(line1)`.

---

## How it works

Claude Code invokes the status-line command on each render and pipes it a JSON blob on
stdin describing the session. This script reads it and prints one (or two) lines. Key
fields it uses:

| Field | Used for |
|-------|----------|
| `model.display_name` | model name |
| `context_window.used_percentage`, `.context_window_size`, `.current_usage.*` | context bar + token counts |
| `rate_limits.five_hour.{used_percentage,resets_at}` | 5h bar + reset clock |
| `rate_limits.seven_day.{used_percentage,resets_at}` | weekly bar + remaining |
| `workspace.current_dir` | directory line |

**Session-start caching.** Claude Code only sends `rate_limits` once the first API
response of a session arrives, so at the very start of a session those fields are
absent. Because the 5-hour and weekly windows are **account-wide**, the script caches
the last-known values to `~/.claude/.statusline-cache.json` and falls back to them, so
the bars are visible immediately. They snap to live values the moment the first
response lands.

---

## Limitations (worth knowing)

- **Refresh cadence is controlled by Claude Code, not this script.** Claude Code
  re-runs the command on UI events (tool calls, message updates), not on a fixed
  timer — gaps can range from sub-second to ~20 seconds when nothing else is updating.
  There is **no `refreshInterval` setting** for the status line.
- **Rate-limit numbers advance only as API responses arrive.** Mid-turn, the `%` can
  briefly lag what `/usage` reports, then catch up when the turn completes. A status
  line cannot fetch fresher numbers than Claude Code hands it on stdin.
- On a brand-new machine with no cache yet, the rate-limit segments appear only after
  the session's first response.

---

## Testing

Pipe a sample payload to the script and confirm it prints two colored lines:

```bash
echo '{
  "model": {"display_name": "Opus 4.8"},
  "workspace": {"current_dir": "'"$PWD"'"},
  "context_window": {
    "context_window_size": 1000000,
    "used_percentage": 24,
    "current_usage": {"input_tokens": 240000}
  },
  "rate_limits": {
    "five_hour": {"used_percentage": 62, "resets_at": 9999999999},
    "seven_day": {"used_percentage": 40, "resets_at": 9999999999}
  }
}' | ~/.claude/statusline-command.sh
```

Expected: line 1 with the model, context bar, and 5h/7d bars; line 2 with the
directory and (if `$PWD` is a git repo) the branch.

---

## Uninstall

1. Remove the `statusLine` block from `~/.claude/settings.json`.
2. Delete `~/.claude/statusline-command.sh` and `~/.claude/.statusline-cache.json`.

---

## License

MIT. Do whatever you like with it.
