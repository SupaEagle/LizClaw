#!/usr/bin/env python3
"""
Knowledge Base Management
- List sources with filters
- Delete by source ID
- Preflight checks
"""

import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))
from kb_core import KB_DIR, DB_PATH, LOCK_FILE

def preflight_check() -> Dict[str, Any]:
    """
    Run preflight checks before KB operations.
    - Validate required paths
    - Check for corrupted state
    - Check for stale lock files
    """
    checks = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "warnings": [],
        "errors": []
    }
    
    # Check KB directory
    if not KB_DIR.exists():
        checks["errors"].append(f"KB directory missing: {KB_DIR}")
    
    # Check database
    if not DB_PATH.exists():
        checks["warnings"].append(f"Database not initialized: {DB_PATH}")
    else:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM sources")
            count = c.fetchone()[0]
            checks["db_status"] = f"OK ({count} sources)"
            conn.close()
        except Exception as e:
            checks["errors"].append(f"Database corruption: {e}")
    
    # Check lock file
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is still running
            try:
                os.kill(pid, 0)
                checks["warnings"].append(f"Lock file active (PID {pid})")
            except OSError:
                # Process dead
                LOCK_FILE.unlink()
                checks["warnings"].append(f"Removed stale lock file (PID {pid} dead)")
        except:
            LOCK_FILE.unlink()
            checks["warnings"].append("Removed corrupted lock file")
    
    if checks["errors"]:
        checks["status"] = "error"
    elif checks["warnings"]:
        checks["status"] = "warning"
    
    return checks


def list_sources(
    source_type: str = None,
    tags: str = None,
    limit: int = 100
) -> Dict[str, Any]:
    """List sources with optional filters."""
    if not DB_PATH.exists():
        return {"error": "Database not initialized"}
    
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    sql = "SELECT id, url, title, source_type, tags, ingested_at FROM sources WHERE 1=1"
    params = []
    
    if source_type:
        sql += " AND source_type = ?"
        params.append(source_type)
    
    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        tag_filter = " OR ".join(f"tags LIKE ?" * len(tag_list))
        sql += f" AND ({tag_filter})"
        params.extend([f"%{tag}%" for tag in tag_list])
    
    sql += " ORDER BY ingested_at DESC LIMIT ?"
    params.append(limit)
    
    c.execute(sql, params)
    sources = c.fetchall()
    conn.close()
    
    return {
        "sources": [
            {
                "id": row[0],
                "url": row[1],
                "title": row[2],
                "type": row[3],
                "tags": row[4],
                "ingested_at": row[5]
            }
            for row in sources
        ],
        "total": len(sources)
    }


def delete_source(source_id: int) -> Dict[str, Any]:
    """Delete a source and its chunks."""
    if not DB_PATH.exists():
        return {"error": "Database not initialized"}
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Get source info
        c.execute("SELECT url FROM sources WHERE id = ?", (source_id,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return {"error": f"Source {source_id} not found"}
        
        url = result[0]
        
        # Delete chunks
        c.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        chunks_deleted = c.rowcount
        
        # Delete source
        c.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "source_id": source_id,
            "url": url,
            "chunks_deleted": chunks_deleted
        }
    
    except Exception as e:
        return {"error": str(e)}


def get_source_details(source_id: int) -> Dict[str, Any]:
    """Get detailed info about a source."""
    if not DB_PATH.exists():
        return {"error": "Database not initialized"}
    
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # Get source
    c.execute("""
        SELECT id, url, title, source_type, tags, ingested_at, content_hash
        FROM sources WHERE id = ?
    """, (source_id,))
    
    source = c.fetchone()
    if not source:
        conn.close()
        return {"error": f"Source {source_id} not found"}
    
    # Get chunks
    c.execute("""
        SELECT id, chunk_index, LENGTH(chunk_text) FROM chunks
        WHERE source_id = ? ORDER BY chunk_index
    """, (source_id,))
    
    chunks = c.fetchall()
    conn.close()
    
    return {
        "source": {
            "id": source[0],
            "url": source[1],
            "title": source[2],
            "type": source[3],
            "tags": source[4],
            "ingested_at": source[5],
            "content_hash": source[6]
        },
        "chunks": [
            {
                "id": c[0],
                "index": c[1],
                "size_bytes": c[2]
            }
            for c in chunks
        ],
        "total_chunks": len(chunks)
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge Base Management")
    subparsers = parser.add_subparsers(dest="command")
    
    # preflight
    subparsers.add_parser("preflight", help="Run preflight checks")
    
    # list
    list_parser = subparsers.add_parser("list", help="List sources")
    list_parser.add_argument("--type", dest="source_type", help="Filter by source type")
    list_parser.add_argument("--tags", help="Filter by tags")
    list_parser.add_argument("--limit", type=int, default=100, help="Max results")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a source")
    delete_parser.add_argument("source_id", type=int, help="Source ID")
    
    # details
    details_parser = subparsers.add_parser("details", help="Get source details")
    details_parser.add_argument("source_id", type=int, help="Source ID")
    
    args = parser.parse_args()
    
    if args.command == "preflight":
        result = preflight_check()
        print(json.dumps(result, indent=2))
    
    elif args.command == "list":
        result = list_sources(args.source_type, args.tags, args.limit)
        print(json.dumps(result, indent=2))
    
    elif args.command == "delete":
        result = delete_source(args.source_id)
        print(json.dumps(result, indent=2))
    
    elif args.command == "details":
        result = get_source_details(args.source_id)
        print(json.dumps(result, indent=2))
    
    else:
        parser.print_help()
