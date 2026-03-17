#!/usr/bin/env python3
"""
Memory Synthesis System
- Reads daily notes from past week(s)
- Identifies patterns and insights
- Updates MEMORY.md with synthesized learnings
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
import re
import json

# Add memory dir to path
MEMORY_DIR = Path("/data/.openclaw/workspace/memory")
WORKSPACE_DIR = Path("/data/.openclaw/workspace")
MEMORY_FILE = WORKSPACE_DIR / "MEMORY.md"

# Default MEMORY.md template
DEFAULT_MEMORY = """# MEMORY.md - Curated Long-Term Memory

_Last synthesized: {last_synthesized}_

## 🎯 Personal Preferences

<!-- User preferences, communication style, timezone, etc. -->

## 📁 Project History

<!-- Ongoing projects, current status, key decisions -->

## 🧠 Strategic Notes

<!-- Long-term goals, important relationships, plans -->

## ⚙️ Operational Lessons

<!-- Lessons learned, things that work/don't work, tips -->

## 💬 Communication Patterns

<!-- How the user likes to communicate, pet peeves, humor style -->

---
_This file is synthesized from daily notes. Don't edit manually - run synthesis to update._
"""

def read_daily_note(date_str: str) -> str:
    """Read a single day's memory file."""
    file_path = MEMORY_DIR / f"{date_str}.md"
    if file_path.exists():
        with open(file_path, 'r') as f:
            return f.read()
    return ""

def get_notes_for_range(days: int = 7) -> List[Dict[str, str]]:
    """Get all daily notes for the past N days."""
    notes = []
    for i in range(days):
        d = datetime.now() - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        content = read_daily_note(date_str)
        if content:
            notes.append({
                "date": date_str,
                "content": content
            })
    return notes

def extract_entries(content: str) -> Dict[str, List[str]]:
    """Extract categorized entries from daily notes."""
    entries = {
        "decisions": [],
        "tasks": [],
        "events": [],
        "insights": [],
        "notes": []
    }
    
    lines = content.split("\n")
    current_section = None
    current_content = []
    
    for line in lines:
        if "## [" in line and "]" in line:
            # Save previous section
            if current_section and current_content:
                entry_text = "\n".join(current_content).strip()
                if current_section in entries:
                    entries[current_section].append(entry_text)
            
            # Determine new section type
            if "Decision" in line:
                current_section = "decisions"
            elif "Task" in line:
                current_section = "tasks"
            elif "Event" in line:
                current_section = "events"
            elif "Insight" in line:
                current_section = "insights"
            else:
                current_section = "notes"
            
            current_content = [line]
        elif current_section:
            current_content.append(line)
    
    # Don't forget last section
    if current_section and current_content:
        entry_text = "\n".join(current_content).strip()
        if current_section in entries:
            entries[current_section].append(entry_text)
    
    return entries

def synthesize_patterns(notes: List[Dict[str, str]]) -> Dict[str, Any]:
    """Analyze notes and identify patterns."""
    all_entries = {
        "decisions": [],
        "tasks": [],
        "events": [],
        "insights": [],
        "notes": []
    }
    
    for note in notes:
        entries = extract_entries(note["content"])
        for category, items in entries.items():
            all_entries[category].extend([(note["date"], item) for item in items])
    
    # Extract key patterns
    patterns = {
        "recent_decisions": all_entries["decisions"][-5:] if all_entries["decisions"] else [],
        "pending_tasks": [t for t in all_entries["tasks"] if "✅" not in t[1]][-10:],
        "completed_tasks": [t for t in all_entries["tasks"] if "✅" in t[1]][-10:],
        "insights": all_entries["insights"][-10:],
        "events": all_entries["events"][-5:],
    }
    
    return patterns

def extract_preferences(notes: List[Dict[str, str]]) -> List[str]:
    """Extract potential preferences from notes."""
    preferences = []
    
    # Keywords that indicate preferences
    pref_keywords = [
        "prefer", "like", "dislike", "want", "don't want",
        "love", "hate", "wish", "always", "never",
        "better with", "works better", "instead of"
    ]
    
    for note in notes:
        lines = note["content"].split("\n")
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in pref_keywords):
                # Clean up the line
                cleaned = line.strip().lstrip("#*-, ")
                if cleaned and len(cleaned) > 10:
                    preferences.append(cleaned)
    
    return list(set(preferences))[:10]

def extract_lessons(notes: List[Dict[str, str]]) -> List[str]:
    """Extract lessons learned from insights and decisions."""
    lessons = []
    
    lesson_keywords = ["learned", "lesson", "figured out", "discovered", "realized"]
    
    for note in notes:
        entries = extract_entries(note["content"])
        
        for insight in entries["insights"]:
            if any(kw in insight.lower() for kw in lesson_keywords):
                lessons.append(f"[{note['date']}] {insight[:200]}")
        
        for decision in entries["decisions"]:
            if "because" in decision.lower() or "reason" in decision.lower():
                lessons.append(f"[{note['date']}] {decision[:200]}")
    
    return lessons[-10:]

def synthesize_memory(days: int = 7, dry_run: bool = False) -> str:
    """
    Synthesize memory from daily notes.
    Returns the synthesized content (or prints if dry_run=True).
    """
    print(f"📚 Synthesizing memory from past {days} days...")
    
    notes = get_notes_for_range(days)
    
    if not notes:
        print("No notes found for synthesis")
        return ""
    
    print(f"Found {len(notes)} days with notes")
    
    patterns = synthesize_patterns(notes)
    preferences = extract_preferences(notes)
    lessons = extract_lessons(notes)
    
    # Build synthesized content
    synthesized = f"""# MEMORY.md - Curated Long-Term Memory

_Last synthesized: {datetime.now().strftime('%Y-%m-%d %H:%M')}_

## 🎯 Personal Preferences

{chr(10).join(f"- {p}" for p in preferences) if preferences else "_No preferences recorded yet_"}

## 📁 Project History

### Recent Decisions
{chr(10).join(f"- **{d[0]}**: {d[1][:150]}" for d in patterns["recent_decisions"]) if patterns["recent_decisions"] else "_No recent decisions_"}

### Recent Events
{chr(10).join(f"- **{e[0]}**: {e[1][:150]}" for e in patterns["events"]) if patterns["events"] else "_No events recorded_"}

## 🧠 Strategic Notes

<!-- Long-term goals, important relationships, plans -->

## ⚙️ Operational Lessons

{chr(10).join(f"- {l}" for l in lessons) if lessons else "_No lessons recorded yet_"}

## 💬 Communication Patterns

<!-- How the user likes to communicate, pet peeves, humor style -->

### Pending Tasks
{chr(10).join(f"- {t[1]}" for t in patterns["pending_tasks"]) if patterns["pending_tasks"] else "_No pending tasks_"}

### Completed Tasks
{chr(10).join(f"- {t[1]}" for t in patterns["completed_tasks"]) if patterns["completed_tasks"] else "_No completed tasks_"}

---
_This file is synthesized from daily notes. Don't edit manually - run synthesis to update._
"""
    
    if dry_run:
        print("\n" + "="*50)
        print("SYNTHESIZED MEMORY (dry run):")
        print("="*50)
        print(synthesized)
    else:
        # Read existing MEMORY.md to preserve manual sections
        existing = {}
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, 'r') as f:
                content = f.read()
            
            # Extract manual sections
            sections = ["Strategic Notes", "Communication Patterns"]
            for section in sections:
                match = re.search(rf'## 💬 {section}.*?(?=##|---|\Z)', content, re.DOTALL)
                if match:
                    existing[section] = match.group(0)
        
        # Update synthesized with preserved sections
        for section, content in existing.items():
            if "Strategic Notes" in section:
                synthesized = synthesized.replace(
                    "## 🧠 Strategic Notes\n\n<!-- Long-term goals, important relationships, plans -->",
                    content
                )
            elif "Communication Patterns" in section:
                synthesized = synthesized.replace(
                    "## 💬 Communication Patterns\n\n<!-- How the user likes to communicate, pet peeves, humor style -->",
                    content
                )
        
        with open(MEMORY_FILE, 'w') as f:
            f.write(synthesized)
        
        print(f"✅ Memory synthesized and saved to MEMORY.md")
    
    return synthesized


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Synthesis System")
    parser.add_argument("--days", type=int, default=7, help="Days to synthesize")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--init", action="store_true", help="Initialize MEMORY.md")
    
    args = parser.parse_args()
    
    if args.init:
        if MEMORY_FILE.exists():
            print("MEMORY.md already exists")
        else:
            with open(MEMORY_FILE, 'w') as f:
                f.write(DEFAULT_MEMORY.format(last_synthesized="never"))
            print("Created MEMORY.md")
    else:
        synthesize_memory(args.days, args.dry_run)
