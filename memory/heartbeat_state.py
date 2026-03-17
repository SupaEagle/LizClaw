#!/usr/bin/env python3
"""
Heartbeat State Manager
- Track timestamps for periodic checks
- Reset corrupted state to defaults
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

STATE_FILE = Path("/data/.openclaw/workspace/memory/heartbeat-state.json")

DEFAULT_STATE = {
    "lastChecks": {
        "email": None,
        "calendar": None,
        "weather": None,
        "memory_synthesize": None,
        "error_log_scan": None,
        "security_audit": None,
        "healthcheck": None
    },
    "memory": {
        "last_synthesize": None,
        "synthesize_interval_days": 7
    },
    "cron": {
        "last_full_run": None,
        "stale_job_warnings": []
    }
}

def load_state() -> Dict[str, Any]:
    """Load heartbeat state, resetting if corrupted."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            # Validate structure
            if not isinstance(state, dict):
                print("State corrupted: not a dict, resetting")
                return reset_state()
            
            # Ensure all keys exist
            for key in DEFAULT_STATE:
                if key not in state:
                    state[key] = DEFAULT_STATE[key]
            
            return state
        else:
            return DEFAULT_STATE.copy()
    
    except json.JSONDecodeError:
        print("State corrupted: JSON parse error, resetting")
        return reset_state()
    except Exception as e:
        print(f"Error loading state: {e}, resetting")
        return reset_state()

def save_state(state: Dict[str, Any]):
    """Save heartbeat state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def reset_state() -> Dict[str, Any]:
    """Reset state to defaults."""
    state = DEFAULT_STATE.copy()
    save_state(state)
    return state

def update_check(check_name: str, value: Any = None):
    """Update a check timestamp."""
    state = load_state()
    
    if value is None:
        value = datetime.now().isoformat()
    
    if "lastChecks" not in state:
        state["lastChecks"] = {}
    
    state["lastChecks"][check_name] = value
    save_state(state)

def get_last_check(check_name: str) -> Optional[str]:
    """Get last check timestamp."""
    state = load_state()
    return state.get("lastChecks", {}).get(check_name)

def should_run(check_name: str, interval_hours: int = 24) -> bool:
    """Check if a periodic task should run."""
    last = get_last_check(check_name)
    
    if last is None:
        return True
    
    try:
        last_time = datetime.fromisoformat(last)
        elapsed = (datetime.now() - last_time).total_seconds() / 3600
        return elapsed >= interval_hours
    except:
        return True  # Invalid timestamp = should run

def set_memory_synthesize(days: int = 7):
    """Update memory synthesis interval."""
    state = load_state()
    state["memory"]["synthesize_interval_days"] = days
    save_state(state)

def get_memory_synthesize_interval() -> int:
    """Get memory synthesis interval."""
    state = load_state()
    return state.get("memory", {}).get("synthesize_interval_days", 7)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Heartbeat State Manager")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("show", help="Show current state")
    subparsers.add_parser("reset", help="Reset to defaults")
    
    update_parser = subparsers.add_parser("update", help="Update a check")
    update_parser.add_argument("check_name", help="Name of check")
    update_parser.add_argument("--value", help="Value (default: now")
    
    check_parser = subparsers.add_parser("should-run", help="Check if should run")
    check_parser.add_argument("check_name")
    check_parser.add_argument("--hours", type=int, default=24)
    
    args = parser.parse_args()
    
    if args.command == "show":
        state = load_state()
        print(json.dumps(state, indent=2))
    
    elif args.command == "reset":
        state = reset_state()
        print("State reset to defaults")
    
    elif args.command == "update":
        update_check(args.check_name, args.value)
        print(f"Updated {args.check_name}")
    
    elif args.command == "should-run":
        if should_run(args.check_name, args.hours):
            print("YES")
        else:
            print("NO")
    
    else:
        parser.print_help()
