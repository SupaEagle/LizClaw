#!/usr/bin/env python3
"""
Cron Automation System for OpenClaw
- SQLite-based job logging
- PID-based lockfiles
- Signal handling
- Reliability features
"""

import sqlite3
import os
import sys
import signal
import time
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path("/data/.openclaw/workspace/.cron/jobs.db")
LOCK_DIR = Path("/data/.openclaw/workspace/.cron/locks")
LOG_DIR = Path("/data/.openclaw/workspace/.cron/logs")

def ensure_dirs():
    """Ensure required directories exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def init_db():
    """Initialize the SQLite database."""
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS job_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT CHECK(status IN ('running', 'success', 'failure', 'cancelled')),
            duration_seconds REAL,
            summary TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_job_name ON job_runs(job_name)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_status ON job_runs(status)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_start_time ON job_runs(start_time)
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS job_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            failure_time TEXT NOT NULL,
            summary TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_failure_job_time ON job_failures(job_name, failure_time)
    ''')
    
    conn.commit()
    conn.close()

def log_start(job_name: str) -> int:
    """Record job start, return run ID."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO job_runs (job_name, start_time, status) VALUES (?, ?, 'running')",
        (job_name, now)
    )
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id

def log_end(run_id: int, status: str, summary: str = ""):
    """Record job completion."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    now = datetime.now()
    
    c.execute("SELECT start_time FROM job_runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    
    start_time = datetime.fromisoformat(row[0])
    duration = (now - start_time).total_seconds()
    end_time = now.isoformat()
    
    c.execute(
        """UPDATE job_runs 
           SET end_time = ?, status = ?, duration_seconds = ?, summary = ?
           WHERE id = ?""",
        (end_time, status, duration, summary, run_id)
    )
    
    # Track failures for persistent failure detection
    if status == 'failure':
        c.execute(
            "INSERT INTO job_failures (job_name, failure_time, summary) VALUES (?, ?, ?)",
            (get_job_name(run_id), now.isoformat(), summary)
        )
    
    conn.commit()
    conn.close()

def get_job_name(run_id: int) -> str:
    """Get job name from run ID."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT job_name FROM job_runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "unknown"

def query_jobs(
    job_name: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Query job history with filters."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    query = "SELECT id, job_name, start_time, end_time, status, duration_seconds, summary FROM job_runs WHERE 1=1"
    params = []
    
    if job_name:
        query += " AND job_name = ?"
        params.append(job_name)
    if status:
        query += " AND status = ?"
        params.append(status)
    if start_date:
        query += " AND start_time >= ?"
        params.append(start_date)
    if end_date:
        query += " AND start_time <= ?"
        params.append(end_date)
    
    query += " ORDER BY start_time DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "id": r[0],
            "job_name": r[1],
            "start_time": r[2],
            "end_time": r[3],
            "status": r[4],
            "duration_seconds": r[5],
            "summary": r[6]
        }
        for r in rows
    ]

def should_run(job_name: str, frequency: str = "daily") -> bool:
    """
    Idempotency check - skip if already succeeded today/this hour.
    frequency: 'hourly' or 'daily'
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    now = datetime.now()
    if frequency == "hourly":
        window_start = now.replace(minute=0, second=0, microsecond=0).isoformat()
    else:  # daily
        window_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    c.execute(
        """SELECT status FROM job_runs 
           WHERE job_name = ? AND start_time >= ? AND status = 'success'
           ORDER BY start_time DESC LIMIT 1""",
        (job_name, window_start)
    )
    row = c.fetchone()
    conn.close()
    
    return row is None  # Should run if no successful run in this window

def cleanup_stale() -> int:
    """Mark jobs stuck in 'running' state for >2 hours as failed."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    cutoff = datetime.now() - timedelta(hours=2)
    c.execute(
        """UPDATE job_runs 
           SET status = 'failure', end_time = ?, summary = 'Auto-cleanup: stale job marked failed'
           WHERE status = 'running' AND start_time < ?""",
        (cutoff.isoformat(), cutoff.isoformat())
    )
    
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected

def check_persistent_failures(job_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Alert when the same job fails 3+ times within a 6-hour window.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    cutoff = datetime.now() - timedelta(hours=6)
    
    if job_name:
        query = """
            SELECT job_name, COUNT(*) as failure_count, MAX(failure_time) as last_failure
            FROM job_failures
            WHERE job_name = ? AND failure_time >= ?
            GROUP BY job_name
            HAVING COUNT(*) >= 3
        """
        c.execute(query, (job_name, cutoff.isoformat()))
    else:
        query = """
            SELECT job_name, COUNT(*) as failure_count, MAX(failure_time) as last_failure
            FROM job_failures
            WHERE failure_time >= ?
            GROUP BY job_name
            HAVING COUNT(*) >= 3
        """
        c.execute(query, (cutoff.isoformat(),))
    
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "job_name": r[0],
            "failure_count": r[1],
            "last_failure": r[2]
        }
        for r in rows
    ]

def get_lockfile_path(job_name: str) -> Path:
    """Get PID lockfile path for a job."""
    safe_name = job_name.replace("/", "_").replace(" ", "_")
    return LOCK_DIR / f"{safe_name}.pid"

def acquire_lock(job_name: str) -> Optional[int]:
    """
    Acquire PID-based lock. Returns PID if locked, None if acquired.
    """
    lock_path = get_lockfile_path(job_name)
    
    if lock_path.exists():
        try:
            with open(lock_path, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process is still running
            try:
                os.kill(old_pid, 0)
                # Process still running - check if it's actually the same job
                return old_pid
            except OSError:
                # Process dead, stale lock - remove it
                lock_path.unlink()
        except (ValueError, IOError):
            lock_path.unlink()
    
    # Write our PID
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))
    
    return None

def release_lock(job_name: str):
    """Release PID lock."""
    lock_path = get_lockfile_path(job_name)
    if lock_path.exists():
        lock_path.unlink()

def run_cron_job(
    job_name: str,
    command: str,
    frequency: str = "daily",
    timeout: Optional[int] = None,
    notify_on_failure: bool = False,
    notify_channel: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a cron job with full automation features.
    """
    result = {
        "success": False,
        "run_id": None,
        "output": "",
        "error": None,
        "skipped": False
    }
    
    # Cleanup stale jobs first
    cleaned = cleanup_stale()
    
    # Check idempotency
    if not should_run(job_name, frequency):
        result["skipped"] = True
        result["output"] = "Job already ran successfully in this window"
        return result
    
    # Acquire lock
    locked_by = acquire_lock(job_name)
    if locked_by:
        result["error"] = f"Job already running (PID: {locked_by})"
        return result
    
    # Set up signal handlers for clean shutdown
    def signal_handler(signum, frame):
        if result["run_id"]:
            log_end(result["run_id"], "cancelled", f"Received signal {signum}")
        release_lock(job_name)
        sys.exit(128 + signum)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    
    # Record start
    run_id = log_start(job_name)
    result["run_id"] = run_id
    
    # Set timeout if specified
    if timeout:
        def timeout_handler(signum, frame):
            log_end(run_id, "failure", f"Job timed out after {timeout} seconds")
            release_lock(job_name)
            sys.exit(124)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    
    # Execute command
    start_time = time.time()
    try:
        proc = os.popen(command)
        output = proc.read()
        exit_code = proc.close()
        
        result["output"] = output
        
        if exit_code is None:
            status = "success"
        elif exit_code == 0:
            status = "success"
        else:
            status = "failure"
            result["error"] = f"Exit code: {exit_code}"
        
    except Exception as e:
        status = "failure"
        result["error"] = str(e)
    
    # Record end
    log_end(run_id, status, result["output"][:500] if result["output"] else "")
    
    # Release lock
    release_lock(job_name)
    
    result["success"] = status == "success"
    
    # Check for persistent failures
    if not result["success"]:
        persistent = check_persistent_failures(job_name)
        if persistent:
            result["persistent_failure"] = True
            result["failure_alert"] = f"Job {job_name} has failed {persistent[0]['failure_count']} times in 6 hours"
    
    return result

def list_jobs() -> List[Dict[str, Any]]:
    """List all jobs with their latest status."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute("""
        SELECT job_name, status, start_time, duration_seconds 
        FROM job_runs 
        WHERE id IN (
            SELECT MAX(id) FROM job_runs GROUP BY job_name
        )
    """)
    
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "job_name": r[0],
            "last_status": r[1],
            "last_run": r[2],
            "last_duration": r[3]
        }
        for r in rows
    ]

# CLI interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw Cron System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    subparsers.add_parser("init", help="Initialize database")
    
    # run
    run_parser = subparsers.add_parser("run", help="Run a cron job")
    run_parser.add_argument("job_name", help="Job name")
    run_parser.add_argument("command", help="Command to run")
    run_parser.add_argument("--frequency", default="daily", choices=["hourly", "daily"])
    run_parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    run_parser.add_argument("--no-idempotency", action="store_true", help="Skip idempotency check")
    
    # query
    query_parser = subparsers.add_parser("query", help="Query job history")
    query_parser.add_argument("--job", help="Filter by job name")
    query_parser.add_argument("--status", help="Filter by status")
    query_parser.add_argument("--start", help="Start date (ISO)")
    query_parser.add_argument("--end", help="End date (ISO)")
    query_parser.add_argument("--limit", type=int, default=100)
    
    # should-run
    should_parser = subparsers.add_parser("should-run", help="Check if job should run")
    should_parser.add_argument("job_name")
    should_parser.add_argument("--frequency", default="daily")
    
    # cleanup
    subparsers.add_parser("cleanup", help="Clean up stale jobs")
    
    # persistent-failures
    subparsers.add_parser("persistent-failures", help="Check persistent failures")
    
    # list
    subparsers.add_parser("list", help="List all jobs")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_db()
        print("Database initialized")
    elif args.command == "run":
        if not args.no_idempotency:
            if not should_run(args.job_name, args.frequency):
                print(f"SKIPPED: {args.job_name} already ran successfully in this {args.frequency} window")
                sys.exit(0)
        result = run_cron_job(args.job_name, args.command, args.frequency, args.timeout)
        print(json.dumps(result, indent=2))
    elif args.command == "query":
        results = query_jobs(args.job, args.status, args.start, args.end, args.limit)
        print(json.dumps(results, indent=2))
    elif args.command == "should-run":
        if should_run(args.job_name, args.frequency):
            print("YES")
        else:
            print("NO")
    elif args.command == "cleanup":
        cleaned = cleanup_stale()
        print(f"Cleaned up {cleaned} stale jobs")
    elif args.command == "persistent-failures":
        failures = check_persistent_failures()
        print(json.dumps(failures, indent=2))
    elif args.command == "list":
        jobs = list_jobs()
        print(json.dumps(jobs, indent=2))
    else:
        parser.print_help()
