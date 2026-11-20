# Prioritask — Personal To-Do Web Application

A clean, mobile-first personal to-do web application featuring natural language task parsing and an automated 10 PM nightly rollover with morning prioritization.

---

## Key Features

1. **Natural Language Task Entry**:
   - Add tasks in plain English, e.g. `"call CA Friday 4pm, high"`, `"submit tax return tomorrow 5:30 pm, p1"`, `"buy groceries at 7pm urgent"`.
   - Real-time live parsing pill indicators show parsed task title, deadline date/time, and priority as you type.

2. **Automatic Date, Time & Priority Parsing**:
   - **Priority**: Detects `high`, `urgent`, `critical`, `asap`, `p1`, `p2`, `med`, `medium`, `low`, `p3`, etc. Defaults to `medium`.
   - **Date & Time**: Handles relative dates (`today`, `tomorrow`, `day after tomorrow`, `next monday`, `this friday`), specific dates (`25th Nov`, `2026-11-25`), and times (`4pm`, `4:30pm`, `16:00`, `noon`, `morning`, `evening`).

3. **Smart Sorting**:
   - **Deadline & Priority (Default)**: Overdue & today's tasks first, sorted by deadline and high priority.
   - **Priority First**: High → Medium → Low.
   - **Deadline First**: Earliest deadline first.
   - **Newest Added**: Chronological creation order.

4. **10 PM Nightly Rollover & Morning Prioritisation**:
   - Background scheduler checks every night at **10:00 PM (22:00)** local time.
   - Unfinished tasks due today or earlier roll over to tomorrow (preserving time slots).
   - Generates an intelligent **Morning Prioritised Plan**:
     - **The Big 3**: Top 3 high-impact focus tasks to conquer first.
     - **Time Blocks**: Morning (9 AM - 12 PM), Afternoon (12 PM - 5 PM), Evening (5 PM - 8 PM).
     - **Summary & Productivity Tip**: Actionable briefing for tomorrow morning.
   - **Test Button**: Click **"Test 10 PM Rollover"** anytime to simulate the rollover instantly.

5. **Clean, Minimal, Mobile-First UI**:
   - Touch-friendly checkboxes and actions (>= 48px tap targets).
   - Light and Dark mode toggle with system preference auto-detection.
   - Quick sample phrase chips for one-click testing.
   - Task edit modal and delete confirmation.

6. **Local Persistence**:
   - Local SQLite database (`todo_app/todo.db`).

---

## Quick Start

The app is currently running on **http://127.0.0.1:3000**.

To run manually:
```bash
./todo_app/run.sh
# OR
python3 -m uvicorn todo_app.server:app --host 127.0.0.1 --port 3000
```
