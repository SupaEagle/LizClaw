#!/usr/bin/env python3
"""
Cron Failure Delta Notifier
Checks for cron job failures since last run and notifies.
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

def check_cron_failures(notify: bool = False):
    """Check for cron job failures since last check."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "failures": [],
        "new_failures": 0,
        "status": "ok"
    }
    
    # State file for last check
    state_path = Path("/data/.openclaw/workspace/memory/heartbeat-state.json")
    
    try:
        with open(state_path) as f:
            state = json.load(f)
        
        last_check = state.get("lastChecks", {}).get("cron_failure_check")
        
        if last_check is None:
            # First run - check last 24 hours
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        else:
            cutoff = last_check
        
        # Query failures since cutoff
        db_path = Path("/data/.openclaw/workspace/.cron/jobs.db")
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        c.execute("""
            SELECT job_name, start_time, end_time, summary
            FROM job_runs
            WHERE status = 'failure' AND start_time >= ?
            ORDER BY start_time DESC
        """, (cutoff,))
        
        failures = c.fetchall()
        conn.close()
        
        for job_name, start_time, end_time, summary in failures:
            result["failures"].append({
                "job": job_name,
                "time": start_time,
                "summary": summary[:100] if summary else ""
            })
        
        result["new_failures"] = len(failures)
        
        if failures:
            result["status"] = "failure"
    
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    # Update state
    try:
        with open(state_path) as f:
            state = json.load(f)
        
        if "lastChecks" not in state:
            state["lastChecks"] = {}
        
        state["lastChecks"]["cron_failure_check"] = result["timestamp"]
        
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
    except:
        pass
    
    # Notify if enabled and there are failures
    if notify and result["new_failures"] > 0:
        message = f"🧠 Liz: Cron Failure Alert\n"
        message += f"❌ {result['new_failures']} job(s) failed since last check:\n\n"
        
        for failure in result["failures"][:5]:  # Max 5 in message
            message += f"  - {failure['job']} ({failure['time']})\n"
        
        if len(result["failures"]) > 5:
            message += f"  ... and {len(result['failures']) - 5} more\n"
        
        message += f"\nTimestamp: {result['timestamp']}"
        
        try:
            subprocess.run([
                "openclaw", "message", "send",
                "--channel", "webchat",
                "--message", message
            ], capture_output=True, timeout=10)
        except Exception as e:
            print(f"Failed to send notification: {e}", file=sys.stderr)
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cron Failure Delta Notifier")
    parser.add_argument("--notify", action="store_true", help="Send notification on failures")
    
    args = parser.parse_args()
    
    result = check_cron_failures(args.notify)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["status"] == "ok" else 1)
