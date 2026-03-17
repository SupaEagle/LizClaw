#!/usr/bin/env python3
"""
Persistent Failure Notifier
Checks for jobs that have failed 3+ times in 6 hours.
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

def check_persistent_failures(notify: bool = False):
    """Check for persistent failures (3+ in 6 hours)."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "persistent_failures": [],
        "status": "ok"
    }
    
    try:
        # Use cron.py's persistent failure check
        proc = subprocess.run(
            ["python3", "/data/.openclaw/workspace/.cron/cron.py", "persistent-failures"],
            capture_output=True, text=True, timeout=10
        )
        
        failures = json.loads(proc.stdout)
        result["persistent_failures"] = failures
        
        if failures:
            result["status"] = "critical"
    
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    # Notify if enabled and there are persistent failures
    if notify and result["persistent_failures"]:
        message = f"🧠 Liz: Persistent Failure Alert\n"
        message += "🔴 Multiple failures detected (3+ in 6 hours):\n\n"
        
        for failure in result["persistent_failures"]:
            message += f"  - {failure['job_name']}: {failure['failure_count']} failures\n"
            message += f"    Last: {failure['last_failure']}\n"
        
        message += f"\nThese jobs need attention.\nTimestamp: {result['timestamp']}"
        
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
    
    parser = argparse.ArgumentParser(description="Persistent Failure Notifier")
    parser.add_argument("--notify", action="store_true", help="Send notification on failures")
    
    args = parser.parse_args()
    
    result = check_persistent_failures(args.notify)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["status"] == "ok" else 1)
