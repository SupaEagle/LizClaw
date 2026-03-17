#!/usr/bin/env python3
"""
Git Backup Script
Commits and pushes workspace changes.
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/data/.openclaw/workspace")

def git_backup():
    """Commit and push workspace changes."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "committed": False,
        "pushed": False,
        "status": "ok",
        "errors": []
    }
    
    os.chdir(WORKSPACE)
    
    # Check if git is available
    try:
        subprocess.run(["git", "status"], capture_output=True, check=True)
    except:
        result["status"] = "not_a_git_repo"
        return result
    
    # Add all changes
    try:
        subprocess.run(["git", "add", "-A"], capture_output=True, check=True)
        
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        
        if status.stdout.strip():
            # Commit
            commit_msg = f"Auto-backup: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, check=True)
            result["committed"] = True
            
            # Push
            push = subprocess.run(["git", "push"], capture_output=True, text=True, timeout=30)
            
            if push.returncode == 0:
                result["pushed"] = True
            else:
                result["errors"].append(f"Push failed: {push.stderr}")
                # Don't fail the whole script for push issues
                result["status"] = "push_failed"
        else:
            result["committed"] = False  # No changes to commit
    
    except subprocess.CalledProcessError as e:
        result["errors"].append(f"Git error: {e.stderr}")
        result["status"] = "error"
    except Exception as e:
        result["errors"].append(str(e))
        result["status"] = "error"
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Git Backup Script")
    parser.add_argument("--notify", action="store_true", help="Notify on failure")
    
    args = parser.parse_args()
    
    result = git_backup()
    
    import json
    print(json.dumps(result, indent=2))
    
    # Notify on real breakages (merge conflicts, persistent push failures)
    if args.notify and result["status"] not in ("ok", "push_failed"):
        message = f"🧠 Liz: Git Backup Failed\n"
        
        if result["status"] == "error":
            message += "❌ Git operation error:\n"
        else:
            message += f"⚠️ Status: {result['status']}\n"
        
        for error in result["errors"]:
            message += f"  - {error}\n"
        
        try:
            subprocess.run([
                "openclaw", "message", "send",
                "--channel", "webchat",
                "--message", message
            ], capture_output=True, timeout=10)
        except:
            pass
    
    # Exit non-zero only for real errors, not for push failures or no-changes
    sys.exit(1 if result["status"] == "error" else 0)
