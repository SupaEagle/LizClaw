#!/usr/bin/env python3
"""
System Health Check Notifier
Runs health checks and notifies on failures.
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

def run_health_check(notify: bool = False):
    """Run system health check."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "status": "ok",
        "checks": {},
        "errors": []
    }
    
    # Check cron daemon
    try:
        cron_result = subprocess.run(
            ["python3", "/data/.openclaw/workspace/.cron/scheduler.py", "health"],
            capture_output=True, text=True, timeout=30
        )
        health_data = json.loads(cron_result.stdout)
        result["checks"]["cron"] = health_data
        
        if health_data.get("persistent_failures"):
            result["errors"].append(f"Cron persistent failures: {len(health_data['persistent_failures'])}")
            result["status"] = "warning"
    except Exception as e:
        result["errors"].append(f"Cron check failed: {e}")
        result["status"] = "error"
    
    # Check knowledge base preflight
    try:
        kb_result = subprocess.run(
            ["python3", "/data/.openclaw/workspace/knowledge_base/manage.py", "preflight"],
            capture_output=True, text=True, timeout=10
        )
        preflight = json.loads(kb_result.stdout)
        result["checks"]["knowledge_base"] = preflight
        
        if preflight.get("status") != "ok":
            result["errors"].append(f"KB preflight: {preflight.get('status')}")
            result["status"] = "warning"
    except Exception as e:
        result["errors"].append(f"KB check failed: {e}")
        result["status"] = "error"
    
    # Check memory state
    try:
        state_path = Path("/data/.openclaw/workspace/memory/heartbeat-state.json")
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            result["checks"]["memory_state"] = "ok"
        else:
            result["errors"].append("Memory state file missing")
            result["status"] = "error"
    except json.JSONDecodeError:
        result["errors"].append("Memory state corrupted")
        result["status"] = "error"
    except Exception as e:
        result["errors"].append(f"Memory check failed: {e}")
        result["status"] = "error"
    
    # Notify if enabled and there are errors
    if notify and result["status"] != "ok":
        message = f"🧠 Liz: System Health Alert\n"
        
        if result["status"] == "error":
            message += "❌ Errors detected:\n"
        else:
            message += "⚠️ Warnings:\n"
        
        for error in result["errors"]:
            message += f"  - {error}\n"
        
        message += f"\nTimestamp: {result['timestamp']}"
        
        # Send notification via OpenClaw
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
    
    parser = argparse.ArgumentParser(description="System Health Check")
    parser.add_argument("--notify", action="store_true", help="Send notification on issues")
    
    args = parser.parse_args()
    
    result = run_health_check(args.notify)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["status"] == "ok" else 1)
