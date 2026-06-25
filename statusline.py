#!/usr/bin/env python3
"""Claude Code status line — cross-platform core (Windows, macOS, Linux).

Reads Claude Code's native status-line JSON from stdin and prints two lines:
    <model> | ctx [bar] N% . used/size | 5h [bar] N% <reset IST> | 7d [bar] N% . Nd Nh
    <directory>  <git-branch>

Proactive markers prefix any metric getting tight: caution >=75%, critical >=90%,
and a reset-soon marker when a window resets within 10 minutes. Bars use Unicode
partial blocks for smooth sub-character fill. All values come from the native
status-line JSON (v2.x: context_window.* and rate_limits.five_hour/seven_day.*),
recomputed every render. Only requires Python 3.

Invoke directly as the status line command, e.g.:
    macOS/Linux:  python3 ~/.claude/statusline.py
    Windows:      python %USERPROFILE%\\.claude\\statusline.py
"""
import json
import sys
import time
import os
import subprocess
from datetime import datetime, timezone, timedelta

# Timezone for reset times. Change "Asia/Kolkata" to your zone, e.g.
# "America/New_York", "Europe/London", "UTC". On systems without a tz database
# (some Windows installs) this falls back to a fixed +5:30 offset.
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))

try:
    raw = sys.stdin.read()
except Exception:
    raw = ""
try:
    d = json.loads(raw) if raw.strip() else {}
except Exception:
    d = {}

# ---- color helpers ------------------------------------------------------
def c(code, s):
    return f"\033[{code}m{s}\033[0m"

DIM, CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE, GREY = (
    "2", "36", "32", "33", "31", "35", "34", "90"
)
SEP = c(GREY, " │ ")

BOLD_RED = "1;91"  # bold bright red for critical alerts

# usage-oriented color: low used = green (good), high used = red
def usage_color(pct):
    if pct >= 90:
        return BOLD_RED
    if pct < 50:
        return GREEN
    if pct < 80:
        return YELLOW
    return RED

# proactive marker shown *before* a metric that is getting tight.
#   >=90% critical (bold red ⚠), >=75% caution (yellow ▲). also fires when a
#   reset is imminent (<10m) so you know relief is seconds away.
def alert(pct, reset_secs=None):
    if pct >= 90:
        return c(BOLD_RED, "⚠ ")
    if pct >= 75:
        return c(YELLOW, "▲ ")
    if reset_secs is not None and 0 < reset_secs <= 600:
        return c(GREEN, "↻ ")
    return ""

# ---- progress bar with partial-block resolution -------------------------
PARTIALS = " ▏▎▍▌▋▊▉"  # 1/8 .. 7/8 of a cell
def bar(pct, width=12, color=GREEN):
    pct = max(0.0, min(100.0, float(pct)))
    filled = pct / 100.0 * width
    full = int(filled)
    frac = filled - full
    cells = "█" * full
    if full < width:
        i = int(round(frac * 8))
        if i >= 8:
            cells += "█"
        elif i > 0:
            cells += PARTIALS[i]
        cells = cells + "░" * (width - len(cells))
    cells = cells[:width]
    return c(GREY, "[") + c(color, cells) + c(GREY, "]")

# ---- compact number formatting ------------------------------------------
def human(n):
    n = int(n or 0)
    if n >= 1_000_000:
        v = n / 1_000_000
        return (f"{v:.1f}".rstrip("0").rstrip(".")) + "M"
    if n >= 1_000:
        return f"{round(n/1000)}k"
    return str(n)

def _fmt_clock(dt):
    # 12-hour clock without leading zero; %-I is unsupported on Windows libc.
    try:
        return dt.strftime("%-I:%M %p")
    except ValueError:
        try:
            return dt.strftime("%#I:%M %p")  # Windows variant
        except ValueError:
            return dt.strftime("%I:%M %p").lstrip("0")

def reset_clock(ts):
    """Absolute reset time in IST (used by the 5h window). No countdown."""
    try:
        ts = int(ts)
    except Exception:
        return None
    now = time.time()
    dt = datetime.fromtimestamp(ts, IST)
    now_ist = datetime.fromtimestamp(now, IST)
    if dt.date() == now_ist.date():
        when = _fmt_clock(dt)
    elif dt.date() == (now_ist + timedelta(days=1)).date():
        when = "tmrw " + _fmt_clock(dt)
    else:
        when = dt.strftime("%b ") + str(dt.day) + " " + _fmt_clock(dt)
    return f"{when} IST"

def reset_remaining(ts):
    """Time remaining until reset as days+hours (used by the 7d window)."""
    try:
        secs = int(ts) - int(time.time())
    except Exception:
        return None
    if secs <= 0:
        return "now"
    h, m = secs // 3600, (secs % 3600) // 60
    if h >= 24:
        return f"{h//24}d{h%24}h"
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"

parts = []

# ---- model --------------------------------------------------------------
model = (d.get("model") or {}).get("display_name") or (d.get("model") or {}).get("id")
if model:
    parts.append(c(MAGENTA, model))

# ---- context window -----------------------------------------------------
cw = d.get("context_window") or {}
if cw:
    used_pct = cw.get("used_percentage")
    if used_pct is None and cw.get("remaining_percentage") is not None:
        used_pct = 100 - cw["remaining_percentage"]
    used_pct = float(used_pct or 0)
    size = cw.get("context_window_size") or 200000
    cur = cw.get("current_usage") or {}
    used_tokens = (
        (cur.get("input_tokens") or 0)
        + (cur.get("cache_read_input_tokens") or 0)
        + (cur.get("cache_creation_input_tokens") or 0)
        + (cur.get("output_tokens") or 0)
    ) or cw.get("total_input_tokens") or 0
    col = usage_color(used_pct)
    parts.append(
        alert(used_pct)
        + c(GREY, "ctx ")
        + bar(used_pct, 12, col)
        + " "
        + c(col, f"{round(used_pct)}%")
        + c(GREY, f" · {human(used_tokens)}/{human(size)}")
    )

# ---- rate limits (5h / 7d) ---------------------------------------------
# Claude Code only sends rate_limits once the first API response of a session
# lands, so at session start the payload omits them. The windows are
# account-wide, so we cache the last-known values to disk and fall back to them
# until fresh data arrives — keeping the segments visible from the first render.
CACHE = os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")),
    ".statusline-cache.json",
)
try:
    with open(CACHE) as _f:
        cache = json.load(_f) or {}
except Exception:
    cache = {}

rl = d.get("rate_limits") or {}
fresh = {}
rl_segs = []
for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
    win = rl.get(key) if isinstance(rl, dict) else None
    pct = win.get("used_percentage") if isinstance(win, dict) else None
    ra = win.get("resets_at") if isinstance(win, dict) else None
    if pct is not None:
        fresh[key] = {"used_percentage": pct, "resets_at": ra}
    else:  # no live data yet — fall back to the cached value
        cached = cache.get(key) or {}
        pct = cached.get("used_percentage")
        ra = cached.get("resets_at")
    if pct is None:
        continue
    pct = float(pct)
    col = usage_color(pct)
    try:
        reset_secs = int(ra) - int(time.time())
    except Exception:
        reset_secs = None
    seg = alert(pct, reset_secs) + c(GREY, f"{label} ") + bar(pct, 8, col) + " " + c(col, f"{round(pct)}%")
    # 5h window shows the absolute reset clock time (IST); the weekly window
    # shows days+hours remaining.
    if key == "five_hour":
        rc = reset_clock(ra)
        if rc:
            seg += c(GREY, " ⟳ ") + c(BLUE, rc)
    elif key == "seven_day":
        rr = reset_remaining(ra)
        if rr:
            seg += c(GREY, " · ") + c(BLUE, rr)
    rl_segs.append(seg)
if rl_segs:
    parts.append("  ".join(rl_segs))
# persist fresh values so the next session can show them immediately
if fresh:
    merged = dict(cache)
    merged.update(fresh)
    try:
        with open(CACHE, "w") as _f:
            json.dump(merged, _f)
    except Exception:
        pass

line1 = SEP.join(parts)

# ---- line 2: directory + git branch (always shown) ----------------------
real_cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or os.getcwd()
home = os.path.expanduser("~")
disp = ("~" + real_cwd[len(home):]) if real_cwd.startswith(home) else real_cwd
line2 = c(CYAN, disp)
try:
    r = subprocess.run(["git", "-C", real_cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                       capture_output=True, text=True, timeout=1)
    if r.returncode == 0 and r.stdout.strip():
        b = r.stdout.strip()
        dirty = subprocess.run(["git", "-C", real_cwd, "status", "--porcelain"],
                               capture_output=True, text=True, timeout=1)
        mark = "*" if (dirty.returncode == 0 and dirty.stdout.strip()) else ""
        line2 += "  " + c(GREEN, f" {b}{mark}")
except Exception:
    pass

sys.stdout.write(line1 + ("\n" + line2 if line2 else ""))
