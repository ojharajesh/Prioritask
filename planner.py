"""
Nightly Rollover & Morning Prioritisation Engine.
Rolls unfinished tasks to tomorrow and synthesizes an intelligent morning plan.
"""

from datetime import datetime, date, time, timedelta
from typing import Dict, Any, List, Optional
from .database import (
    get_unfinished_tasks_before,
    update_task,
    get_tasks,
    save_daily_plan,
    get_db_connection,
    get_latest_plan
)


def execute_nightly_rollover(now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Executes the 10pm rollover:
    1. Rolls over all pending tasks due up to end of today to tomorrow.
    2. Constructs a prioritized morning plan for tomorrow.
    """
    if now is None:
        now = datetime.now()

    today = now.date()
    tomorrow = today + timedelta(days=1)
    tomorrow_str = tomorrow.strftime('%Y-%m-%d')

    # Cutoff: end of today (or current time if called late at night)
    cutoff = datetime.combine(today, time(23, 59, 59))

    # 1. Fetch pending tasks due today or earlier
    overdue_and_today_tasks = get_unfinished_tasks_before(cutoff)

    rolled_tasks = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for t in overdue_and_today_tasks:
            # Calculate new deadline on tomorrow
            orig_dt_str = t.get('deadline_dt')
            new_has_time = t.get('has_time', 0)

            if orig_dt_str:
                try:
                    orig_dt = datetime.strptime(orig_dt_str, '%Y-%m-%d %H:%M:%S')
                    # Keep the original time component if task had time, else 18:00
                    if new_has_time:
                        new_dt = datetime.combine(tomorrow, orig_dt.time())
                    else:
                        new_dt = datetime.combine(tomorrow, time(18, 0))
                except Exception:
                    new_dt = datetime.combine(tomorrow, time(18, 0))
            else:
                new_dt = datetime.combine(tomorrow, time(18, 0))

            new_dt_str = new_dt.strftime('%Y-%m-%d %H:%M:%S')
            new_rolled_count = (t.get('rolled_over_count') or 0) + 1
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                UPDATE tasks
                SET deadline_dt = ?, rolled_over_count = ?, last_rolled_at = ?
                WHERE id = ?
            """, (new_dt_str, new_rolled_count, now_str, t['id']))

            updated_t = dict(t)
            updated_t['deadline_dt'] = new_dt_str
            updated_t['rolled_over_count'] = new_rolled_count
            updated_t['last_rolled_at'] = now_str
            rolled_tasks.append(updated_t)

        conn.commit()

    # 2. Query all pending tasks now due on tomorrow (both newly rolled and already scheduled)
    all_tomorrow_tasks = get_tasks(
        status='pending',
        filter_date='tomorrow',
        sort_by='deadline_priority'
    )

    # If tomorrow has no tasks, also look ahead or include any remaining pending tasks
    if not all_tomorrow_tasks:
        all_tomorrow_tasks = get_tasks(status='pending', sort_by='deadline_priority')[:5]

    # 3. Build prioritized morning plan
    # Rank tasks: High priority first, then rolled-over count, then time
    ranked_tasks = sorted(
        all_tomorrow_tasks,
        key=lambda x: (
            -x.get('priority_score', 1),
            -(x.get('rolled_over_count', 0)),
            x.get('deadline_dt') or '9999-12-31'
        )
    )

    # Top 3 Focus ("Big Three")
    big_three = ranked_tasks[:3]

    # Schedule Blocks for tomorrow:
    # Morning Focus (9:00 - 12:00)
    # Afternoon Action (12:00 - 17:00)
    # Evening Wrap-up (17:00 - 20:00)
    morning_block = []
    afternoon_block = []
    evening_block = []

    for task in ranked_tasks:
        t_dt_str = task.get('deadline_dt')
        task_hour = None
        if t_dt_str and task.get('has_time'):
            try:
                task_hour = datetime.strptime(t_dt_str, '%Y-%m-%d %H:%M:%S').hour
            except Exception:
                pass

        if task_hour is not None:
            if task_hour < 12:
                morning_block.append(task)
            elif task_hour < 17:
                afternoon_block.append(task)
            else:
                evening_block.append(task)
        else:
            # Assign based on priority: High to Morning, Medium to Afternoon, Low to Evening
            if task.get('priority') == 'high':
                morning_block.append(task)
            elif task.get('priority') == 'low':
                evening_block.append(task)
            else:
                afternoon_block.append(task)

    # Generate smart summary
    rolled_count = len(rolled_tasks)
    total_count = len(all_tomorrow_tasks)
    high_count = sum(1 for t in all_tomorrow_tasks if t.get('priority') == 'high')

    day_name = tomorrow.strftime('%A')
    date_formatted = tomorrow.strftime('%b %d, %Y')

    if rolled_count > 0:
        summary = (
            f"Plan for {day_name} ({date_formatted}): {total_count} total tasks ready. "
            f"🔄 {rolled_count} task{'s' if rolled_count > 1 else ''} rolled over from today. "
            f"Target your {high_count} High-priority item{'s' if high_count != 1 else ''} early!"
        )
    else:
        summary = (
            f"Plan for {day_name} ({date_formatted}): Clean slate! {total_count} tasks scheduled. "
            f"Focus on your Big 3 to win the morning."
        )

    # Motivational productivity tip
    tips = [
        "Pro tip: Complete your #1 highest priority task before checking email.",
        "Eat the frog first thing in the morning when mental energy is at its peak.",
        "Timebox your morning block to 45-minute sprints with 5-minute pauses.",
        "Knocking out rolled-over tasks first clears psychological debt."
    ]
    tip_index = tomorrow.day % len(tips)

    plan_data = {
        'plan_date': tomorrow_str,
        'day_name': day_name,
        'date_formatted': date_formatted,
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'summary': summary,
        'tip': tips[tip_index],
        'rolled_tasks_count': rolled_count,
        'total_tasks_count': total_count,
        'high_priority_count': high_count,
        'rolled_tasks': [
            {'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'rolled_over_count': t['rolled_over_count']}
            for t in rolled_tasks
        ],
        'big_three': [
            {'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline_dt': t.get('deadline_dt'), 'has_time': bool(t.get('has_time'))}
            for t in big_three
        ],
        'schedule_blocks': {
            'morning': [
                {'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline_dt': t.get('deadline_dt'), 'has_time': bool(t.get('has_time'))}
                for t in morning_block
            ],
            'afternoon': [
                {'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline_dt': t.get('deadline_dt'), 'has_time': bool(t.get('has_time'))}
                for t in afternoon_block
            ],
            'evening': [
                {'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline_dt': t.get('deadline_dt'), 'has_time': bool(t.get('has_time'))}
                for t in evening_block
            ]
        }
    }

    plan_id = save_daily_plan(plan_data)
    plan_data['id'] = plan_id
    return plan_data
