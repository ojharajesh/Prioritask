"""
FastAPI Server for Personal To-Do Web Application.
Provides REST API, background 10 PM nightly rollover scheduler, and serves UI.
"""

import os
import asyncio
import threading
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List

APP_TZ_NAME = os.environ.get("APP_TIMEZONE", "Asia/Kolkata").strip()
try:
    APP_TZ = ZoneInfo(APP_TZ_NAME)
except Exception:
    try:
        APP_TZ = ZoneInfo("Asia/Kolkata")
        APP_TZ_NAME = "Asia/Kolkata"
    except Exception:
        APP_TZ = None

def get_now() -> datetime:
    """Returns timezone-aware or local datetime."""
    if APP_TZ:
        return datetime.now(APP_TZ)
    return datetime.now()

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .database import (
        init_db,
        add_task,
        get_task,
        update_task,
        delete_task,
        get_tasks,
        get_latest_plan,
        get_plan_history,
        sync_tasks_from_client
    )
    from .parser import parse_task
    from .planner import execute_nightly_rollover
except ImportError:
    from database import (
        init_db,
        add_task,
        get_task,
        update_task,
        delete_task,
        get_tasks,
        get_latest_plan,
        get_plan_history,
        sync_tasks_from_client
    )
    from parser import parse_task
    from planner import execute_nightly_rollover

app = FastAPI(title="Personal To-Do App with Natural Language & 10 PM Rollover")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background scheduler state
_last_rollover_date: Optional[str] = None
_scheduler_running = True


def nightly_scheduler_loop():
    """Background worker that executes nightly rollover every day at 22:00 (10 PM)."""
    global _last_rollover_date, _scheduler_running
    while _scheduler_running:
        try:
            now = get_now()
            today_str = now.strftime('%Y-%m-%d')
            # Check if current time is 22:00 or later, and hasn't run yet today
            if now.hour >= 22 and _last_rollover_date != today_str:
                print(f"[Scheduler] 10 PM Rollover triggered at {now.strftime('%Y-%m-%d %H:%M:%S')} ({APP_TZ_NAME})")
                execute_nightly_rollover(now)
                _last_rollover_date = today_str
        except Exception as e:
            print(f"[Scheduler Error] {e}")
        time.sleep(30)  # Check every 30 seconds


@app.on_event("startup")
def startup_event():
    init_db()
    # Start the 10 PM background scheduler thread
    t = threading.Thread(target=nightly_scheduler_loop, daemon=True)
    t.start()
    print("[Server] Database initialized and 10 PM rollover scheduler started.")


# Request models
class TasksSyncRequest(BaseModel):
    tasks: List[Dict[str, Any]]


class TaskCreateRequest(BaseModel):
    raw_text: str


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    deadline_dt: Optional[str] = None
    has_time: Optional[bool] = None
    priority: Optional[str] = None
    status: Optional[str] = None


class ParsePreviewRequest(BaseModel):
    text: str


# Endpoints
@app.get("/api/status")
def get_status():
    """Returns local time, rollover schedule status, and summary counts."""
    now = get_now()
    today_str = now.strftime('%Y-%m-%d')

    # Next 10 PM time
    target_10pm = datetime.combine(now.date(), datetime.min.time().replace(hour=22))
    if APP_TZ:
        target_10pm = target_10pm.replace(tzinfo=APP_TZ)
    if now >= target_10pm:
        target_10pm = datetime.combine(now.date() + timedelta(days=1), datetime.min.time().replace(hour=22))
        if APP_TZ:
            target_10pm = target_10pm.replace(tzinfo=APP_TZ)

    diff_seconds = max(0, int((target_10pm - now).total_seconds()))
    hours_left = diff_seconds // 3600
    minutes_left = (diff_seconds % 3600) // 60

    all_tasks = get_tasks(status='all')
    pending_tasks = [t for t in all_tasks if t['status'] == 'pending']
    completed_tasks = [t for t in all_tasks if t['status'] == 'completed']
    rolled_tasks = [t for t in pending_tasks if (t.get('rolled_over_count') or 0) > 0]

    return {
        "local_time": now.strftime('%Y-%m-%d %H:%M:%S'),
        "local_time_display": now.strftime('%A, %b %d • %I:%M %p'),
        "timezone": APP_TZ_NAME,
        "next_rollover": target_10pm.strftime('%Y-%m-%d 22:00:00'),
        "countdown_seconds": diff_seconds,
        "countdown_display": f"{hours_left}h {minutes_left}m",
        "pending_count": len(pending_tasks),
        "completed_count": len(completed_tasks),
        "rolled_over_count": len(rolled_tasks),
        "last_rollover_date": _last_rollover_date
    }


@app.post("/api/tasks/parse")
def preview_task_parse(req: ParsePreviewRequest):
    """Parses plain English text without saving, for live UI feedback."""
    parsed = parse_task(req.text)
    return parsed


@app.get("/api/tasks")
def list_tasks(
    status: Optional[str] = Query('all', description="'pending', 'completed', or 'all'"),
    sort_by: str = Query('deadline_priority', description="Sort option"),
    search: Optional[str] = Query(None, description="Search keyword"),
    filter_date: Optional[str] = Query(None, description="'today', 'tomorrow', 'upcoming', 'overdue'")
):
    """Retrieves tasks sorted and filtered."""
    tasks = get_tasks(status=status, sort_by=sort_by, search=search, filter_date=filter_date)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/tasks")
def create_task(req: TaskCreateRequest):
    """Creates a new task by parsing natural language plain English input."""
    raw = req.raw_text.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Task text cannot be empty")

    parsed = parse_task(raw)
    task = add_task(parsed)
    return {"success": True, "task": task, "parsed": parsed}


@app.post("/api/tasks/sync")
def sync_tasks_endpoint(req: TasksSyncRequest):
    """Syncs tasks from client localStorage to persist across cloud restarts."""
    tasks = sync_tasks_from_client(req.tasks)
    return {"success": True, "count": len(tasks), "tasks": tasks}


@app.put("/api/tasks/{task_id}")
def update_task_endpoint(task_id: int, req: TaskUpdateRequest):
    """Updates a task status or details."""
    updates = req.model_dump(exclude_unset=True)
    updated = update_task(task_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": updated}


@app.delete("/api/tasks/{task_id}")
def delete_task_endpoint(task_id: int):
    """Deletes a task."""
    deleted = delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True}


@app.post("/api/plans/rollover")
def trigger_rollover():
    """
    Manually triggers the 10 PM rollover:
    Rolls unfinished tasks due today or earlier to tomorrow and generates a prioritised morning plan.
    """
    global _last_rollover_date
    now = get_now()
    plan = execute_nightly_rollover(now)
    _last_rollover_date = now.strftime('%Y-%m-%d')
    return {
        "success": True,
        "message": f"Successfully executed 10 PM rollover. {plan['rolled_tasks_count']} tasks rolled to tomorrow.",
        "plan": plan
    }


@app.get("/api/plans/latest")
def get_latest_plan_endpoint():
    """Gets the most recent morning prioritised plan."""
    plan = get_latest_plan()
    return {"plan": plan}


@app.get("/api/plans")
def list_plans():
    """Gets history of morning plans."""
    plans = get_plan_history()
    return {"plans": plans}


# Static web app
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_ui():
    """Serves the main application page with no-cache headers for instant iOS updates."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        response = FileResponse(index_file)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return {"message": "To-Do app backend is running. UI not found."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("todo_app.server:app", host=host, port=port, reload=False)

