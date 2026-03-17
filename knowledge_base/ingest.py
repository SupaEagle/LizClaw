#!/usr/bin/env python3
"""
Knowledge Base Ingestion Pipeline
- Fetch content from URLs
- Validate and sanitize
- Chunk and embed
- Store in database
"""

import sqlite3
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict
import hashlib

sys.path.insert(0, str(Path(__file__).parent))
from kb_core import (
    ensure_db, validate_url, fetch_content, sanitize_content,
    chunk_text, clean_url_for_display, SimpleEmbedding,
    KB_DIR, DB_PATH, LOCK_FILE, CACHE_DIR
)

class LockFile:
    """PID-based lock file manager."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.pid = os.getpid()

    def acquire(self) -> bool:
        """Try to acquire lock. Returns True if acquired."""
        if self.lock_path.exists():
            try:
                with open(self.lock_path, 'r') as f:
                    old_pid = int(f.read().strip())

                # Check if process is still running
                try:
                    os.kill(old_pid, 0)
                    # Still running
                    return False
                except OSError:
                    # Process dead, remove stale lock
                    self.lock_path.unlink()
            except (ValueError, IOError):
                self.lock_path.unlink()

        # Write our PID
        with open(self.lock_path, 'w') as f:
            f.write(str(self.pid))

        return True

    def release(self):
        """Release lock."""
        if self.lock_path.exists():
            try:
                with open(self.lock_path, 'r') as f:
                    pid = int(f.read().strip())

                if pid == self.pid:
                    self.lock_path.unlink()
            except:
                pass


def ingest_url(url: str, tags: str = "", semantic_check: bool = False) -> Dict:
    """
    Ingest a single URL into knowledge base.

    Returns:
        Dict with status, chunks_added, and any errors
    """
    result = {
        "url": url,
        "success": False,
        "chunks_added": 0,
        "errors": []
    }

    # Validate URL
    if not validate_url(url):
        result["errors"].append(f"Invalid URL scheme (must be http/https)")
        return result

    # Fetch content
    content_result = fetch_content(url)
    if not content_result:
        result["errors"].append("Failed to fetch content from URL")
        return result

    text, title, source_type = content_result

    # Sanitize content
    is_safe, text = sanitize_content(text, use_semantic_check=semantic_check)
    if not is_safe:
        result["errors"].append("Content failed security checks")
        return result

    # Check if URL already ingested
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT id, content_hash FROM sources WHERE url = ?", (url,))
    existing = c.fetchone()

    # Compute content hash
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    if existing:
        existing_id, existing_hash = existing
        if existing_hash == content_hash:
            conn.close()
            result["errors"].append("Content already ingested (same hash)")
            return result
        else:
            # Update existing
            source_id = existing_id
            c.execute("""
                UPDATE sources SET title = ?, ingested_at = ?, content_hash = ?
                WHERE id = ?
            """, (title, datetime.now().isoformat(), content_hash, source_id))
    else:
        # Insert new source
        c.execute("""
            INSERT INTO sources (url, title, source_type, tags, ingested_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (url, title, source_type, tags, datetime.now().isoformat(), content_hash))
        source_id = c.lastrowid

    # Chunk the text
    chunks = chunk_text(text, chunk_size=500, overlap=50)

    if not chunks:
        result["errors"].append("No text chunks generated")
        conn.close()
        return result

    # Build embeddings
    embedder = SimpleEmbedding()
    for chunk in chunks:
        embedder.add_document(chunk)
    embedder.build_idf()

    # Store chunks
    for idx, chunk in enumerate(chunks):
        embedding = embedder.embed(chunk)
        embedding_json = json.dumps(embedding)
        
        c.execute("""
            INSERT INTO chunks (source_id, chunk_text, chunk_index, embedding, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (source_id, chunk, idx, embedding_json, datetime.now().isoformat()))
    
    # Store/update vocabulary
    for token, idf in embedder.idf.items():
        c.execute("""
            INSERT OR REPLACE INTO vocabulary (token, idf, doc_count)
            VALUES (?, ?, ?)
        """, (token, idf, embedder.vocab.get(token, 1)))
    
    conn.commit()
    conn.close()

    result["success"] = True
    result["chunks_added"] = len(chunks)

    return result


def bulk_ingest(urls_file: str, tags: str = "", dry_run: bool = False) -> Dict:
    """
    Bulk ingest from a file of URLs (one per line).
    Supports comments (#) and empty lines.
    """
    results = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "ingestions": []
    }

    file_path = Path(urls_file)
    if not file_path.exists():
        results["error"] = f"File not found: {urls_file}"
        return results

    with open(file_path, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    results["total"] = len(urls)

    for url in urls:
        if dry_run:
            results["ingestions"].append({
                "url": url,
                "status": "would_ingest"
            })
        else:
            result = ingest_url(url, tags)
            results["ingestions"].append(result)

            if result["success"]:
                results["successful"] += 1
                print(f"✓ {url} ({result['chunks_added']} chunks)")
            else:
                results["failed"] += 1
                print(f"✗ {url}: {', '.join(result['errors'])}")

    return results


if __name__ == "__main__":
    import argparse

    ensure_db()

    parser = argparse.ArgumentParser(description="Knowledge Base Ingestion")
    subparsers = parser.add_subparsers(dest="command")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a URL")
    ingest_parser.add_argument("url", help="URL to ingest")
    ingest_parser.add_argument("--tags", default="", help="Comma-separated tags")
    ingest_parser.add_argument("--semantic-check", action="store_true", help="Enable semantic security check")

    # bulk
    bulk_parser = subparsers.add_parser("bulk", help="Bulk ingest from file")
    bulk_parser.add_argument("file", help="File with URLs (one per line)")
    bulk_parser.add_argument("--tags", default="", help="Comma-separated tags")
    bulk_parser.add_argument("--dry-run", action="store_true", help="Preview only")

    args = parser.parse_args()

    if args.command == "ingest":
        # Acquire lock
        lock = LockFile(LOCK_FILE)
        if not lock.acquire():
            print("Ingestion in progress, try again later")
            sys.exit(1)

        try:
            result = ingest_url(args.url, args.tags, args.semantic_check)
            print(json.dumps(result, indent=2))
        finally:
            lock.release()

    elif args.command == "bulk":
        lock = LockFile(LOCK_FILE)
        if not lock.acquire():
            print("Ingestion in progress, try again later")
            sys.exit(1)

        try:
            result = bulk_ingest(args.file, args.tags, args.dry_run)
            print(json.dumps(result, indent=2))
        finally:
            lock.release()

    else:
        parser.print_help()
