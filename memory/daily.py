#!/usr/bin/env python3
"""
Daily Memory System
- Appends to memory/YYYY-MM-DD.md during conversations
- Never loaded in group chats
"""

import os
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional
import json

MEMORY_DIR = Path("/data/.openclaw/workspace/memory")

def get_today_path() -> Path:
    """Get path to today's memory file."""
    today = datetime.now().strftime("%Y-%m-%d")
    return MEMORY_DIR / f"{today}.md"

def ensure_memory_dir():
    """Ensure memory directory exists."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def append_entry(content: str, entry_type: str = "note"):
    """
    Append an entry to today's memory file.
    
    entry_type: note, decision, task, event, insight
    """
    ensure_memory_dir()
    today_path = get_today_path()
    timestamp = datetime.now().strftime("%H:%M")
    
    # Header based on entry type
    headers = {
        "note": f"## [{timestamp}] Note",
        "decision": f"## [{timestamp}] Decision",
        "task": f"## [{timestamp}] Task",
        "event": f"## [{timestamp}] Event",
        "insight": f"## [{timestamp}] Insight"
    }
    
    header = headers.get(entry_type, f"## [{timestamp}] Note")
    
    # Create file if not exists with date header
    if not today_path.exists():
        date_header = f"# {datetime.now().strftime('%Y-%m-%d')}\n\n"
        with open(today_path, 'w') as f:
            f.write(date_header)
    
    # Append entry
    with open(today_path, 'a') as f:
        f.write(f"{header}\n{content}\n\n")

def append_conversation(user: str, message: str, is_user: bool = True):
    """Quick append for conversation capture."""
    role = "User" if is_user else "Assistant"
    append_entry(f"**{role}**: {message}", "note")

def add_task(task: str, priority: str = "normal"):
    """Add a task to today's memory."""
    priorities = {"high": "🔴", "normal": "🟡", "low": "🟢"}
    emoji = priorities.get(priority.lower(), "🟡")
    append_entry(f"{emoji} {task}", "task")

def add_decision(decision: str, reason: str = ""):
    """Record a decision made."""
    content = decision
    if reason:
        content += f"\n\n**Reason**: {reason}"
    append_entry(content, "decision")

def add_event(event: str, details: str = ""):
    """Record an event."""
    content = event
    if details:
        content += f"\n\n**Details**: {details}"
    append_entry(content, "event")

def add_insight(insight: str, context: str = ""):
    """Record an insight or learning."""
    content = insight
    if context:
        content += f"\n\n**Context**: {context}"
    append_entry(content, "insight")

def get_daily_note(date_obj: date = None) -> str:
    """Get contents of a specific day's memory."""
    if date_obj is None:
        date_obj = datetime.now().date()
    
    date_str = date_obj.strftime("%Y-%m-%d")
    file_path = MEMORY_DIR / f"{date_str}.md"
    
    if file_path.exists():
        with open(file_path, 'r') as f:
            return f.read()
    return ""

def get_date_range(start_date: date, end_date: date) -> list:
    """Get memory entries for a date range."""
    from datetime import timedelta
    
    entries = []
    current = start_date
    while current <= end_date:
        content = get_daily_note(current)
        if content:
            entries.append({
                "date": current.isoformat(),
                "content": content
            })
        current += timedelta(days=1)
    
    return entries

def list_available_days(days: int = 30) -> list:
    """List available memory days."""
    ensure_memory_dir()
    files = sorted(MEMORY_DIR.glob("*.md"), reverse=True)
    return [f.stem for f in files[:days]]

def search_memory(query: str, days: int = 30) -> list:
    """Search memory for a query string."""
    results = []
    for day_file in list_available_days(days):
        file_path = MEMORY_DIR / f"{day_file}.md"
        with open(file_path, 'r') as f:
            content = f.read()
            if query.lower() in content.lower():
                results.append({
                    "date": day_file,
                    "matches": content.count(query.lower())
                })
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Memory System")
    subparsers = parser.add_subparsers(dest="command")
    
    # append
    append_parser = subparsers.add_parser("append", help="Append entry")
    append_parser.add_argument("content", help="Content to append")
    append_parser.add_argument("--type", default="note", 
                              choices=["note", "decision", "task", "event", "insight"])
    
    # read
    read_parser = subparsers.add_parser("read", help="Read day's memory")
    read_parser.add_argument("--date", help="Date (YYYY-MM-DD), default today")
    
    # range
    range_parser = subparsers.add_parser("range", help="Read date range")
    range_parser.add_argument("start", help="Start date (YYYY-MM-DD)")
    range_parser.add_argument("end", help="End date (YYYY-MM-DD)")
    
    # list
    subparsers.add_parser("list", help="List available days")
    subparsers.add_parser("search", help="Search memory")
    subparsers.add_parser("tasks", help="Show tasks from today")
    
    args = parser.parse_args()
    
    if args.command == "append":
        append_entry(args.content, args.type)
        print(f"Appended: {args.type}")
    
    elif args.command == "read":
        if args.date:
            dt = datetime.strptime(args.date, "%Y-%m-%d").date()
            print(get_daily_note(dt))
        else:
            print(get_daily_note())
    
    elif args.command == "range":
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
        entries = get_date_range(start, end)
        for e in entries:
            print(f"\n=== {e['date']} ===\n{e['content']}")
    
    elif args.command == "list":
        for day in list_available_days():
            print(day)
    
    elif args.command == "search":
        parser.add_argument("query")
        args = parser.parse_args()
        results = search_memory(args.query)
        for r in results:
            print(f"{r['date']}: {r['matches']} matches")
    
    elif args.command == "tasks":
        today = get_daily_note()
        if "## [" in today:
            lines = today.split("\n")
            for line in lines:
                if "Task" in line or "🔴" in line or "🟡" in line or "🟢" in line:
                    print(line)
        else:
            print("No tasks today")
    
    else:
        parser.print_help()
