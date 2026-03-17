# OpenClaw Cron Automation System

A comprehensive cron automation system for OpenClaw with SQLite-based logging, PID locks, signal handling, and reliability features.

## Components

### 1. Core Database (`cron.py`)
- **log-start**: Record job name, start time, returns run ID
- **log-end**: Record completion with status, duration, summary
- **query**: Filter history by job name, status, date range
- **should-run**: Idempotency check (skip if already succeeded today/hour)
- **cleanup-stale**: Auto-mark jobs stuck in "running" >2 hours as failed

### 2. Wrapper Script (`cron-wrapper.sh`)
- Signal traps (SIGTERM/SIGINT/SIGHUP) for clean shutdown
- PID-based lockfile to prevent concurrent runs
- Optional timeout support
- Integrates with cron log for start/end recording

### 3. Job Scheduler (`scheduler.py`)
- Add/remove/list scheduled jobs
- Run jobs with notifications
- Health check with persistent failure detection

## Usage

### Initialize
```bash
python3 .cron/scheduler.py init
```

### Add a Job
```bash
python3 .cron/scheduler.py add <name> <command> [options]
Options:
  --schedule daily|hourly    Schedule frequency (default: daily)
  --notify                   Send notification on failure
  --channel <channel>        Channel to notify (default: webchat)
  --timeout <seconds>        Job timeout
```

### Run a Job
```bash
python3 .cron/scheduler.py run <name>       # Run specific job
python3 .cron/scheduler.py run              # Run all enabled jobs
python3 .cron/scheduler.py run --force      # Skip idempotency check
```

### Query History
```bash
python3 .cron/cron.py query --job <name> --status success --limit 10
python3 .cron/cron.py query --start 2026-01-01 --end 2026-12-31
```

### Health Check
```bash
python3 .cron/scheduler.py health
```

### Wrapper Script Usage
```bash
./cron-wrapper.sh <job_name> <command> [options]
Options:
  --frequency daily|hourly
  --timeout SECONDS
  --no-idempotency
  --notify
```

## Database Schema

### job_runs
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_name | TEXT | Job identifier |
| start_time | TEXT | ISO timestamp |
| end_time | TEXT | ISO timestamp |
| status | TEXT | running/success/failure/cancelled |
| duration_seconds | REAL | Job duration |
| summary | TEXT | Output summary |

### job_failures
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_name | TEXT | Job identifier |
| failure_time | TEXT | ISO timestamp |
| summary | TEXT | Error summary |

## Reliability Features

1. **Persistent Failure Detection**: Alerts when same job fails 3+ times in 6 hours
2. **Stale Job Cleanup**: Auto-marks running jobs >2 hours as failed
3. **Duplicate Prevention**: PID-based locks prevent concurrent runs
4. **Idempotency**: Skip jobs that already ran successfully in the window

## Files

- `.cron/jobs.db` - SQLite database
- `.cron/jobs.json` - Job configuration
- `.cron/locks/` - PID lockfiles
- `.cron/logs/` - Job output logs
