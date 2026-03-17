#!/usr/bin/env python3
"""
Memory Cron Job - Weekly synthesis + daily check
Run this via cron to keep memory updated.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add memory dir to path
sys.path.insert(0, str(Path(__file__).parent))

from synthesize import synthesize_memory
from heartbeat_state import load_state, update_check, should_run, get_memory_synthesize_interval

def run_memory_cron():
    """Main memory cron job."""
    state = load_state()
    now = datetime.now()
    
    # Get synthesize interval (default 7 days)
    interval_days = get_memory_synthesize_interval()
    
    # Check last synthesize
    last_synth = state.get("memory", {}).get("last_synthesize")
    
    should_synthesize = True
    if last_synth:
        try:
            last_time = datetime.fromisoformat(last_synth)
            days_since = (now - last_time).days
            should_synthesize = days_since >= interval_days
        except:
            should_synthesize = True
    
    if should_synthesize:
        print(f"Running memory synthesis (last: {last_synth})...")
        synthesize_memory(days=7)
        
        # Update state
        state = load_state()
        state["memory"]["last_synthesize"] = now.isoformat()
        
        # Save with other state
        state_path = Path("/data/.openclaw/workspace/memory/heartbeat-state.json")
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"✅ Memory synthesized at {now.isoformat()}")
    else:
        print(f"Memory synthesis not due yet (interval: {interval_days} days)")
    
    # Always update the check timestamp
    update_check("memory_synthesize")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Cron Job")
    parser.add_argument("--days", type=int, default=7, help="Days to synthesize")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--force", action="store_true", help="Force synthesis")
    
    args = parser.parse_args()
    
    if args.force:
        synthesize_memory(args.days, args.dry_run)
        if not args.dry_run:
            state = load_state()
            state["memory"]["last_synthesize"] = datetime.now().isoformat()
            state_path = Path("/data/.openclaw/workspace/memory/heartbeat-state.json")
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)
    else:
        run_memory_cron()
