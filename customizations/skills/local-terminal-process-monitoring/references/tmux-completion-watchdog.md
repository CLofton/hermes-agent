# tmux Completion Watchdog

Reusable deterministic pattern for “notify me when this terminal task finishes.” Adapt the session name, task anchor, and program-specific completion marker.

```python
#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

SESSION = "replace-me"
TASK_ANCHOR = "exact unique text from the submitted task"
STATE = Path.home() / ".hermes" / "cron" / "state" / "replace-me.json"
STATE.parent.mkdir(parents=True, exist_ok=True)

try:
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
except Exception:
    state = {}

if state.get("notified"):
    raise SystemExit(0)

try:
    pane = subprocess.check_output(
        ["tmux", "capture-pane", "-pt", SESSION, "-S", "-250"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
except (subprocess.CalledProcessError, FileNotFoundError):
    # Missing session is not reliable proof of completion.
    raise SystemExit(0)

pos = pane.rfind(TASK_ANCHOR)
task_output = pane[pos + len(TASK_ANCHOR):] if pos >= 0 else ""

# Replace this regex with the target program's real completion marker.
completed = bool(re.search(r"(?:✻|Worked|Sautéed).*?·\s*done\b", task_output, re.I))

if completed:
    # Write the sentinel before printing to minimize duplicate delivery risk.
    STATE.write_text(json.dumps({"notified": True, "session": SESSION}))
    print("🟢 The watched terminal task is done.")
```

## Required verification

1. **Incomplete live state:** run the script before the task finishes; stdout must be empty and exit code zero.
2. **False-positive fixture:** include banner/help/release-note text containing “done” before `TASK_ANCHOR`; stdout must remain empty.
3. **Complete fixture:** include a valid marker after `TASK_ANCHOR`; exactly one notification must print.
4. **Repeat run:** run again after the sentinel is written; stdout must be empty.
5. **Missing session:** confirm the script stays quiet unless a separate failure alert was explicitly requested.

## Hermes cron shape

- Put the script in `~/.hermes/scripts/`.
- Pass `script="watch_name.py"`, not an absolute path.
- Set `no_agent=true`; empty stdout delivers nothing.
- For a temporary watch, cap the repeat window instead of leaving a permanent silent cron.
- Verify the created job has the intended destination and next-run time.

## Better-than-pane signals

Prefer these whenever available:
- process exit code,
- expected file/artifact exists and validates,
- expected commit or test report exists,
- API/job status says succeeded,
- a durable application-specific completion record.

Pane text is a fallback for interactive TUIs, not the strongest possible signal.
