#!/usr/bin/env python3
"""
Cron Job Scheduler for OpenClaw
Runs jobs based on cron expressions and notifies on completion.
"""

import subprocess
import threading
import time
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from cron import (
    run_cron_job, should_run, cleanup_stale, 
    check_persistent_failures, query_jobs, init_db
)

class CronScheduler:
    """Scheduler for running cron jobs."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "/data/.openclaw/workspace/.cron/jobs.json"
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._load_config()
    
    def _load_config(self):
        """Load job configuration."""
        if Path(self.config_path).exists():
            with open(self.config_path, 'r') as f:
                self.jobs = json.load(f)
    
    def _save_config(self):
        """Save job configuration."""
        Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.jobs, f, indent=2)
    
    def add_job(self, name: str, command: str, schedule: str, 
                notify_on_failure: bool = False, notify_channel: Optional[str] = None,
                enabled: bool = True, timeout: Optional[int] = None):
        """
        Add a job to the scheduler.
        schedule: cron expression or 'hourly'/'daily'
        """
        self.jobs[name] = {
            "command": command,
            "schedule": schedule,
            "notify_on_failure": notify_on_failure,
            "notify_channel": notify_channel,
            "enabled": enabled,
            "timeout": timeout,
            "last_run": None,
            "last_status": None
        }
        self._save_config()
    
    def remove_job(self, name: str):
        """Remove a job from the scheduler."""
        if name in self.jobs:
            del self.jobs[name]
            self._save_config()
    
    def run_job(self, name: str, force: bool = False) -> Dict[str, Any]:
        """Run a specific job."""
        if name not in self.jobs:
            return {"error": f"Job {name} not found"}
        
        job = self.jobs[name]
        
        # Determine frequency from schedule
        frequency = "daily"
        if job["schedule"] in ("hourly", "every_hour"):
            frequency = "hourly"
        
        # Check idempotency unless forced
        if not force and not should_run(name, frequency):
            return {"skipped": True, "message": f"Already ran {frequency}"}
        
        # Run the job
        result = run_cron_job(
            job_name=name,
            command=job["command"],
            frequency=frequency,
            timeout=job.get("timeout"),
            notify_on_failure=job.get("notify_on_failure", False),
            notify_channel=job.get("notify_channel")
        )
        
        # Update job status
        job["last_run"] = datetime.now().isoformat()
        job["last_status"] = "success" if result["success"] else "failure"
        self._save_config()
        
        # Send notification if configured
        if result.get("error") and job.get("notify_on_failure"):
            self._send_notification(name, result, job.get("notify_channel"))
        
        return result
    
    def _send_notification(self, job_name: str, result: Dict, channel: Optional[str]):
        """Send notification about job failure."""
        message = f"❌ Job **{job_name}** failed: {result.get('error', 'Unknown error')}"
        
        # Check for persistent failure
        if result.get("persistent_failure"):
            message += f"\n\n⚠️ {result.get('failure_alert')}"
        
        # Use OpenClaw message tool if available
        try:
            subprocess.run([
                "openclaw", "message", "send",
                "--channel", channel or "webchat",
                "--message", message
            ], capture_output=True, timeout=10)
        except Exception as e:
            print(f"Failed to send notification: {e}")
    
    def run_all(self, force: bool = False):
        """Run all enabled jobs."""
        results = {}
        for name, job in self.jobs.items():
            if not job.get("enabled", True):
                continue
            results[name] = self.run_job(name, force)
        return results
    
    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """List all configured jobs."""
        return self.jobs.copy()
    
    def check_health(self) -> Dict[str, Any]:
        """Check scheduler health."""
        # Cleanup stale jobs
        cleaned = cleanup_stale()
        
        # Check persistent failures
        persistent = check_persistent_failures()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "stale_jobs_cleaned": cleaned,
            "persistent_failures": persistent,
            "configured_jobs": len(self.jobs),
            "enabled_jobs": sum(1 for j in self.jobs.values() if j.get("enabled", True))
        }


# Default jobs configuration
DEFAULT_JOBS = {
    "healthcheck": {
        "command": "openclaw healthcheck --brief",
        "schedule": "hourly",
        "notify_on_failure": True,
        "notify_channel": "webchat",
        "enabled": False,
        "timeout": 300
    },
    "memory-maintenance": {
        "command": "python3 -c \"from cron import query_jobs; print('OK')\"",
        "schedule": "daily",
        "notify_on_failure": False,
        "enabled": False,
        "timeout": 60
    }
}

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenClaw Cron Scheduler")
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    subparsers.add_parser("init", help="Initialize scheduler")
    
    # add
    add_parser = subparsers.add_parser("add", help="Add a job")
    add_parser.add_argument("name", help="Job name")
    add_parser.add_argument("cmd", help="Command to run")
    add_parser.add_argument("--schedule", default="daily", help="Schedule (daily/hourly/cron)")
    add_parser.add_argument("--notify", action="store_true", help="Notify on failure")
    add_parser.add_argument("--channel", help="Notification channel")
    add_parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    
    # run
    run_parser = subparsers.add_parser("run", help="Run a job")
    run_parser.add_argument("name", nargs="?", help="Job name (all if not specified)")
    run_parser.add_argument("--force", action="store_true", help="Force run even if already ran")
    
    # list
    subparsers.add_parser("list", help="List jobs")
    
    # health
    subparsers.add_parser("health", help="Check health")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_db()
        # Initialize default config if not exists
        config_path = "/data/.openclaw/workspace/.cron/jobs.json"
        if not Path(config_path).exists():
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_JOBS, f, indent=2)
        print("Scheduler initialized")
    
    elif args.command == "add":
        scheduler = CronScheduler()
        scheduler.add_job(
            args.name, args.cmd, args.schedule,
            args.notify, args.channel, timeout=args.timeout
        )
        print(f"Job '{args.name}' added")
    
    elif args.command == "run":
        scheduler = CronScheduler()
        if args.name:
            result = scheduler.run_job(args.name, args.force)
            print(json.dumps(result, indent=2))
        else:
            results = scheduler.run_all(args.force)
            print(json.dumps(results, indent=2))
    
    elif args.command == "list":
        scheduler = CronScheduler()
        print(json.dumps(scheduler.list_jobs(), indent=2))
    
    elif args.command == "health":
        scheduler = CronScheduler()
        print(json.dumps(scheduler.check_health(), indent=2))
    
    else:
        parser.print_help()
