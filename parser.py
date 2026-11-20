"""
Natural language task parser for To-Do application.
Extracts title, deadline date/time, and priority from plain English strings.
Example: 'call CA Friday 4pm, high' ->
    title: 'call CA'
    deadline: 2026-11-27 16:00:00
    priority: 'high'
"""

import re
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional, Tuple
from dateutil import parser as du_parser
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU

WEEKDAYS = {
    'mon': 0, 'monday': 0,
    'tue': 1, 'tues': 1, 'tuesday': 1,
    'wed': 2, 'wednesday': 2,
    'thu': 3, 'thur': 3, 'thurs': 3, 'thursday': 3,
    'fri': 4, 'friday': 4,
    'sat': 5, 'saturday': 5,
    'sun': 6, 'sunday': 6
}

PRIORITY_PATTERNS = [
    (r'(?i)\b(?:priority[:\s]+)?(p1|high|urgent|critical|asap|highest)\b', 'high'),
    (r'(?i)\b(?:priority[:\s]+)?(p3|p4|low|minor)\b', 'low'),
    (r'(?i)\b(?:priority[:\s]+)?(p2|med|medium|normal|moderate)\b', 'medium'),
    (r'(?i)!(?:high|1|urgent)\b', 'high'),
    (r'(?i)!(?:med|medium|2)\b', 'medium'),
    (r'(?i)!(?:low|3)\b', 'low'),
]


def extract_priority(text: str) -> Tuple[str, str]:
    """
    Extracts priority ('high', 'medium', 'low') and returns (clean_text, priority).
    Defaults to 'medium' if not found.
    """
    detected_priority = 'medium'
    matched_span = None

    for pattern, prio in PRIORITY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            detected_priority = prio
            matched_span = match.span()
            # Remove matched priority substring
            start, end = matched_span
            text = text[:start] + ' ' + text[end:]
            break

    # Clean leftover punctuation around removal
    text = re.sub(r'[,;]\s*$', '', text.strip())
    text = re.sub(r'^\s*[,;]', '', text.strip())
    return text.strip(), detected_priority


def parse_time_component(text: str) -> Tuple[str, Optional[time]]:
    """
    Extracts explicit time like 4pm, 4:30pm, 16:00, noon, midnight, etc.
    Returns (cleaned_text, time_object or None).
    """
    cleaned = text

    # Keyword times
    named_times = [
        (r'(?i)\bnoon\b', time(12, 0)),
        (r'(?i)\bmidnight\b', time(0, 0)),
        (r'(?i)\bmorning\b', time(9, 0)),
        (r'(?i)\bafternoon\b', time(14, 0)),
        (r'(?i)\bevening\b', time(18, 0)),
        (r'(?i)\bnight\b', time(21, 0)),
    ]
    for pattern, t in named_times:
        match = re.search(pattern, cleaned)
        if match:
            start, end = match.span()
            cleaned = cleaned[:start] + ' ' + cleaned[end:]
            return cleaned.strip(), t

    # 12-hour or 24-hour patterns: 4pm, 4:30pm, 04:30 pm, 16:00, 9am
    # Pattern: (at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b
    p12 = re.search(r'(?i)(?:\b(?:at|@)\s+)?\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', cleaned)
    if p12:
        hours = int(p12.group(1))
        mins = int(p12.group(2)) if p12.group(2) else 0
        ampm = p12.group(3).lower()
        if ampm == 'pm' and hours < 12:
            hours += 12
        elif ampm == 'am' and hours == 12:
            hours = 0
        if 0 <= hours <= 23 and 0 <= mins <= 59:
            start, end = p12.span()
            cleaned = cleaned[:start] + ' ' + cleaned[end:]
            return cleaned.strip(), time(hours, mins)

    # 24-hour format: 14:30, 09:00, with optional 'at'
    p24 = re.search(r'(?i)(?:\b(?:at|@)\s+)?\b([01]?\d|2[0-3]):([0-5]\d)\b(?!\s*%)', cleaned)
    if p24:
        hours = int(p24.group(1))
        mins = int(p24.group(2))
        start, end = p24.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]
        return cleaned.strip(), time(hours, mins)

    return cleaned.strip(), None


def parse_date_component(text: str, base_dt: datetime) -> Tuple[str, Optional[date], bool]:
    """
    Extracts date component.
    Returns (cleaned_text, date_object or None, is_relative_or_found).
    """
    cleaned = text
    base_date = base_dt.date()

    # 1. 'in X hours' or 'in X mins' / 'in X minutes'
    rel_time = re.search(r'(?i)\bin\s+(\d+)\s*(hours?|hrs?|minutes?|mins?)\b', cleaned)
    if rel_time:
        amount = int(rel_time.group(1))
        unit = rel_time.group(2).lower()
        start, end = rel_time.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]
        if 'h' in unit:
            target_dt = base_dt + timedelta(hours=amount)
        else:
            target_dt = base_dt + timedelta(minutes=amount)
        return cleaned.strip(), target_dt.date(), True

    # 2. 'in X days'
    rel_days = re.search(r'(?i)\bin\s+(\d+)\s*days?\b', cleaned)
    if rel_days:
        amount = int(rel_days.group(1))
        start, end = rel_days.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]
        return cleaned.strip(), base_date + timedelta(days=amount), True

    # 3. 'day after tomorrow' / 'overmorrow'
    m_over = re.search(r'(?i)\b(?:day after tomorrow|overmorrow)\b', cleaned)
    if m_over:
        start, end = m_over.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]
        return cleaned.strip(), base_date + timedelta(days=2), True

    # 4. 'tomorrow' / 'tmrw' / 'tom'
    m_tom = re.search(r'(?i)\b(?:tomorrow|tmrw|tom)\b', cleaned)
    if m_tom:
        start, end = m_tom.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]
        return cleaned.strip(), base_date + timedelta(days=1), True

    # 5. 'today' / 'tonight'
    m_today = re.search(r'(?i)\b(?:today|tonight)\b', cleaned)
    if m_today:
        start, end = m_today.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]
        return cleaned.strip(), base_date, True

    # 6. Day of the week: 'next Friday', 'this Friday', 'Friday', 'on Friday'
    m_dow = re.search(r'(?i)\b(?:(next|this|coming|on)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b', cleaned)
    if m_dow:
        prefix = (m_dow.group(1) or '').lower()
        day_str = m_dow.group(2).lower()
        target_weekday = WEEKDAYS[day_str]
        cur_weekday = base_date.weekday()

        start, end = m_dow.span()
        cleaned = cleaned[:start] + ' ' + cleaned[end:]

        days_ahead = (target_weekday - cur_weekday) % 7
        if prefix == 'next':
            # 'next monday' usually means next week's monday (+7 days)
            days_ahead += 7
        elif days_ahead == 0:
            # Same day: if specified "this friday" or just "friday" on a friday, assume next week if later, or today
            days_ahead = 7

        return cleaned.strip(), base_date + timedelta(days=days_ahead), True

    # 7. Specific date formats: '25th Nov', 'Nov 25', '25 Nov', '25th November 2026', '2026-11-25', '11/25'
    # Match patterns like: (by\s+|on\s+)? (25th|25)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*(\d{1,2})?(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?
    m_month = re.search(r'(?i)\b(?:(?:by|on)\s+)?(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?(?:\s*,?\s*(\d{4}))?\b', cleaned)
    if m_month:
        day_val = m_month.group(1) or m_month.group(3)
        month_str = m_month.group(2)
        year_str = m_month.group(4)
        if day_val:
            try:
                date_str = f"{day_val} {month_str} {year_str if year_str else base_date.year}"
                parsed_d = du_parser.parse(date_str, default=datetime(base_date.year, 1, 1)).date()
                if not year_str and parsed_d < base_date:
                    parsed_d = parsed_d.replace(year=base_date.year + 1)
                start, end = m_month.span()
                cleaned = cleaned[:start] + ' ' + cleaned[end:]
                return cleaned.strip(), parsed_d, True
            except Exception:
                pass

    # Standard ISO or numeric date: 2026-11-25 or 25/11 or 11/25
    m_num_date = re.search(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b', cleaned)
    if m_num_date:
        raw_date_str = m_num_date.group(0)
        try:
            parsed_d = du_parser.parse(raw_date_str, dayfirst=True, default=datetime(base_date.year, 1, 1)).date()
            start, end = m_num_date.span()
            cleaned = cleaned[:start] + ' ' + cleaned[end:]
            return cleaned.strip(), parsed_d, True
        except Exception:
            pass

    return cleaned.strip(), None, False


def clean_title(text: str) -> str:
    """Cleans leftover prepositions, punctuation, and extra whitespace."""
    t = text
    # Remove leading/trailing quotes
    t = t.strip(' "\'()[]{}')
    # Remove leading/trailing prepositions like 'by', 'at', 'on', 'due'
    t = re.sub(r'^(?:by|at|on|due|for)\s+', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+(?:by|at|on|due|for|priority)$', '', t, flags=re.IGNORECASE)
    # Remove dangling commas or dashes
    t = re.sub(r'[\s,\-–—:;]+$', '', t)
    t = re.sub(r'^[\s,\-–—:;]+', '', t)
    # Collapse spaces
    t = re.sub(r'\s{2,}', ' ', t)
    return t.strip()


def parse_task(raw_text: str, base_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Parses a raw English task string into structured task attributes.
    Returns:
    {
        'raw_text': str,
        'title': str,
        'deadline_dt': str (ISO format) or None,
        'deadline_date': str (YYYY-MM-DD) or None,
        'deadline_time': str (HH:MM) or None,
        'has_time': bool,
        'priority': 'high' | 'medium' | 'low',
        'is_relative': bool
    }
    """
    if not raw_text or not raw_text.strip():
        return {
            'raw_text': '',
            'title': '',
            'deadline_dt': None,
            'deadline_date': None,
            'deadline_time': None,
            'has_time': False,
            'priority': 'medium',
            'is_relative': False
        }

    if base_dt is None:
        base_dt = datetime.now()

    working_text = raw_text.strip()

    # Step 1: Extract Priority
    working_text, priority = extract_priority(working_text)

    # Step 2: Extract explicit Time
    working_text, extracted_time = parse_time_component(working_text)

    # Step 3: Extract Date
    working_text, extracted_date, has_date = parse_date_component(working_text, base_dt)

    # Step 4: Handle combination cases
    deadline_dt = None
    has_time = False

    if extracted_date and extracted_time:
        deadline_dt = datetime.combine(extracted_date, extracted_time)
        has_time = True
    elif extracted_date and not extracted_time:
        # Default deadline time if date specified without time: 18:00 (end of workday)
        deadline_dt = datetime.combine(extracted_date, time(18, 0))
        has_time = False
    elif not extracted_date and extracted_time:
        # Time specified without date: e.g. "meeting at 4pm"
        # If time is earlier than current time today, could be today or tomorrow
        # If user specifies a time today that already passed, let's keep today
        # so user can see it or it rolls over.
        deadline_dt = datetime.combine(base_dt.date(), extracted_time)
        has_time = True
    else:
        # Neither date nor time specified: default to Today 22:00
        # or leave as None / Today end of day.
        # Let's set default deadline to today 22:00 so all tasks can be sorted and rolled over!
        deadline_dt = datetime.combine(base_dt.date(), time(22, 0))
        has_time = False

    # Step 5: Clean title
    final_title = clean_title(working_text)
    if not final_title:
        final_title = raw_text.strip()

    return {
        'raw_text': raw_text.strip(),
        'title': final_title,
        'deadline_dt': deadline_dt.strftime('%Y-%m-%d %H:%M:%S') if deadline_dt else None,
        'deadline_date': deadline_dt.strftime('%Y-%m-%d') if deadline_dt else None,
        'deadline_time': deadline_dt.strftime('%H:%M') if (deadline_dt and has_time) else None,
        'has_time': has_time,
        'priority': priority,
    }
