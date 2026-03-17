#!/usr/bin/env python3
"""
Cron Daemon for OpenClaw
Runs jobs on their schedules in the background.
"""

import time
import threading
import signal
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add cron directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scheduler import CronScheduler
from cron import cleanup_stale, check_persistent_failures

class CronDaemon:
    """Background daemon for running scheduled jobs."""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # seconds
        self.running = False
        self.scheduler = CronScheduler()
        self._health_check_interval = 1800  # 30 minutes
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False
        sys.exit(0)
    
    def _run_scheduled_jobs(self):
        """Check and run jobs due for execution."""
        now = datetime.now()
        
        for name, job in self.scheduler.list_jobs().items():
            if not job.get("enabled", True):
                continue
            
            schedule = job.get("schedule", "daily")
            last_run = job.get("last_run")
            
            # Determine if job should run
            should_run = False
            
            if schedule == "hourly":
                if not last_run:
                    should_run = True
                else:
                    last_time = datetime.fromisoformat(last_run)
                    if (now - last_time) >= timedelta(hours=1):
                        should_run = True
            elif schedule == "daily":
                if not last_run:
                    should_run = True
                else:
                    last_time = datetime.fromisoformat(last_run)
                    # Check if last run was not today
                    if last_time.date() < now.date():
                        should_run = True
            
            if should_run:
                print(f"[{now.isoformat()}] Running job: {name}")
                try:
                    result = self.scheduler.run_job(name)
                    status = "success" if result.get("success") else "failed"
                    print(f"  → {status}")
                except Exception as e:
                    print(f"  → Error: {e}")
    
    def _run_health_checks(self):
        """Run periodic health checks."""
        # Cleanup stale jobs
        cleaned = cleanup_stale()
        if cleaned > 0:
            print(f"[Health] Cleaned up {cleaned} stale jobs")
        
        # Check persistent failures
        persistent = check_persistent_failures()
        if persistent:
            print(f"[Health] Persistent failures detected: {len(persistent)}")
            for p in persistent:
                print(f"  - {p['job_name']}: {p['failure_count']} failures in 6 hours")
    
    def run(self):
        """Main daemon loop."""
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.running = True
        last_health_check = datetime.now()
        
        print(f"Cron daemon started (check interval: {self.check_interval}s)")
        
        while self.running:
            try:
                self._run_scheduled_jobs()
                
                # Run health checks periodically
                if (datetime.now() - last_health_check).seconds >= self._health_check_interval:
                    self._run_health_checks()
                    last_health_check = datetime.now()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"Error in daemon loop: {e}")
                time.sleep(self.check_interval)
        
        print("Cron daemon stopped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenClaw Cron Daemon")
    parser.add_argument("--interval", type=int, default=60, 
                       help="Check interval in seconds (default: 60)")
    parser.add_argument("--once", action="store_true",
                       help="Run once instead of daemon mode")
    
    args = parser.parse_args()
    
    daemon = CronDaemon(check_interval=args.interval)
    
    if args.once:
        print("Running jobs once...")
        daemon._run_scheduled_jobs()
        daemon._run_health_checks()
    else:
        daemon.run()
