#!/usr/bin/env python3
"""
Knowledge Base Query Engine
- Semantic search over embeddings
- Filter by tag, source type, date range
- Configurable result limit and similarity threshold
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))
from kb_core import SimpleEmbedding, DB_PATH

def search(
    query: str,
    limit: int = 5,
    similarity_threshold: float = 0.1,
    tags: str = None,
    source_type: str = None,
    days: int = None
) -> Dict[str, Any]:
    """
    Search knowledge base with semantic similarity.
    
    Args:
        query: Search query text
        limit: Maximum results to return
        similarity_threshold: Minimum similarity score (0-1)
        tags: Filter by comma-separated tags
        source_type: Filter by source type (article, youtube, twitter, pdf)
        days: Filter to last N days
    
    Returns:
        Dict with results and metadata
    """
    results = {
        "query": query,
        "results": [],
        "total_results": 0,
        "search_time": 0
    }
    
    start_time = datetime.now()
    
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # Build embedder to convert query
    embedder = SimpleEmbedding()
    
    # Load vocabulary from DB
    c.execute("SELECT token, idf FROM vocabulary")
    for token, idf in c.fetchall():
        embedder.idf[token] = idf
    
    # Generate query embedding
    query_embedding = embedder.embed(query)
    
    if not query_embedding:
        conn.close()
        results["error"] = "Query produced no meaningful embedding"
        return results
    
    # Build SQL query
    sql = """
        SELECT c.id, c.chunk_text, c.embedding, s.url, s.title, s.source_type, s.tags, s.ingested_at
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        WHERE 1=1
    """
    params = []
    
    # Add filters
    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        tag_filter = " OR ".join(f"s.tags LIKE ?" * len(tag_list))
        sql += f" AND ({tag_filter})"
        params.extend([f"%{tag}%" for tag in tag_list])
    
    if source_type:
        sql += " AND s.source_type = ?"
        params.append(source_type)
    
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        sql += " AND s.ingested_at >= ?"
        params.append(cutoff)
    
    c.execute(sql, params)
    chunks = c.fetchall()
    conn.close()
    
    # Score all chunks
    scored_chunks = []
    for chunk_id, chunk_text, embedding_json, url, title, source_type, tags_str, ingested_at in chunks:
        try:
            chunk_embedding = json.loads(embedding_json)
        except:
            continue
        
        # Compute similarity
        similarity = SimpleEmbedding.cosine_similarity(query_embedding, chunk_embedding)
        
        if similarity >= similarity_threshold:
            scored_chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                "full_text": chunk_text,
                "url": url,
                "title": title,
                "source_type": source_type,
                "tags": tags_str,
                "ingested_at": ingested_at,
                "similarity": round(similarity, 4)
            })
        
    # Sort by similarity
    scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
    
    # Limit results
    results["results"] = scored_chunks[:limit]
    results["total_results"] = len(scored_chunks)
    results["search_time"] = (datetime.now() - start_time).total_seconds()
    
    return results


def search_by_date(
    start_date: str,
    end_date: str,
    limit: int = 100
) -> Dict[str, Any]:
    """Search by date range."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    sql = """
        SELECT s.url, s.title, s.source_type, s.ingested_at, COUNT(c.id) as chunk_count
        FROM sources s
        LEFT JOIN chunks c ON s.id = c.source_id
        WHERE s.ingested_at BETWEEN ? AND ?
        GROUP BY s.id
        ORDER BY s.ingested_at DESC
        LIMIT ?
    """
    
    c.execute(sql, (start_date, end_date, limit))
    sources = c.fetchall()
    conn.close()
    
    return {
        "date_range": f"{start_date} to {end_date}",
        "sources": [
            {
                "url": row[0],
                "title": row[1],
                "source_type": row[2],
                "ingested_at": row[3],
                "chunks": row[4]
            }
            for row in sources
        ],
        "total": len(sources)
    }


def get_stats() -> Dict[str, Any]:
    """Get knowledge base statistics."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM sources")
    source_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = c.fetchone()[0]
    
    c.execute("""
        SELECT source_type, COUNT(*) FROM sources GROUP BY source_type
    """)
    by_type = dict(c.fetchall())
    
    c.execute("""
        SELECT AVG(chunk_count) FROM (
            SELECT COUNT(*) as chunk_count FROM chunks GROUP BY source_id
        )
    """)
    avg_chunks = c.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total_sources": source_count,
        "total_chunks": chunk_count,
        "by_source_type": by_type,
        "avg_chunks_per_source": round(avg_chunks, 1)
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge Base Query Engine")
    subparsers = parser.add_subparsers(dest="command")
    
    # search
    search_parser = subparsers.add_parser("search", help="Search knowledge base")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Max results")
    search_parser.add_argument("--threshold", type=float, default=0.1, help="Similarity threshold")
    search_parser.add_argument("--tags", help="Filter by tags")
    search_parser.add_argument("--type", dest="source_type", help="Filter by source type")
    search_parser.add_argument("--days", type=int, help="Filter to last N days")
    
    # date
    date_parser = subparsers.add_parser("by-date", help="Search by date range")
    date_parser.add_argument("start", help="Start date (YYYY-MM-DD)")
    date_parser.add_argument("end", help="End date (YYYY-MM-DD)")
    
    # stats
    subparsers.add_parser("stats", help="Show KB statistics")
    
    args = parser.parse_args()
    
    if args.command == "search":
        result = search(
            args.query,
            args.limit,
            args.threshold,
            args.tags,
            args.source_type,
            args.days
        )
        print(json.dumps(result, indent=2))
    
    elif args.command == "by-date":
        result = search_by_date(args.start, args.end)
        print(json.dumps(result, indent=2))
    
    elif args.command == "stats":
        stats = get_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()
