#!/usr/bin/env python3
"""
Cross-Post Script
- Post summaries to other channels after ingestion
- Clean content (strip metadata, UTM tags, tracking)
- Keep untrusted page content out of conversation loop
"""

import re
import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))
from kb_core import clean_url_for_display

def clean_summary(text: str) -> str:
    """
    Clean summary for posting.
    - Remove tracking params
    - Strip metadata
    - Limit length
    """
    # Remove UTM and tracking params from URLs
    text = re.sub(r'[?&]utm_\w+=[^&\s]*', '', text)
    text = re.sub(r'[?&]fbclid=[^&\s]*', '', text)
    text = re.sub(r'[?&]gclid=[^&\s]*', '', text)
    
    # Remove metadata patterns
    metadata_patterns = [
        r'\[.*?metadata.*?\]',
        r'\(Posted by.*?\)',
        r'Share this.*?\.?',
        r'Read more at.*?\.?'
    ]
    
    for pattern in metadata_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Limit to reasonable length for posting
    max_length = 500
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()


def generate_summary(source_data: Dict[str, Any]) -> str:
    """
    Generate a clean summary for cross-posting.
    """
    url = clean_url_for_display(source_data["url"])
    title = source_data.get("title", "Untitled")
    source_type = source_data.get("source_type", "article")
    
    summary = f"📚 **{title}**\n"
    summary += f"Type: {source_type.upper()} | "
    summary += f"[Link]({url})"
    
    return summary


def post_to_channel(
    summary: str,
    channel: str = "webchat",
    service: str = "openclaw"
) -> Dict[str, Any]:
    """
    Post summary to a channel.
    Supports: webchat, slack, telegram, discord, etc.
    """
    result = {
        "channel": channel,
        "service": service,
        "posted": False,
        "error": None
    }
    
    try:
        if service == "openclaw":
            # Use OpenClaw message tool
            cmd = [
                "openclaw", "message", "send",
                "--channel", channel,
                "--message", summary
            ]
            
            proc = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
            
            if proc.returncode == 0:
                result["posted"] = True
            else:
                result["error"] = proc.stderr
        
        elif service == "slack":
            # Would require Slack API token and webhook
            result["error"] = "Slack posting requires webhook setup"
        
        else:
            result["error"] = f"Unknown service: {service}"
    
    except subprocess.TimeoutExpired:
        result["error"] = "Post operation timed out"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def post_ingest_notification(
    source_data: Dict[str, Any],
    channels: list = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Post notification about newly ingested content.
    """
    if channels is None:
        channels = ["webchat"]
    
    results = {
        "source": source_data.get("url"),
        "notifications": [],
        "dry_run": dry_run
    }
    
    summary = generate_summary(source_data)
    
    for channel in channels:
        if dry_run:
            results["notifications"].append({
                "channel": channel,
                "would_post": True,
                "summary": summary
            })
        else:
            result = post_to_channel(summary, channel)
            results["notifications"].append(result)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cross-Post Script")
    subparsers = parser.add_subparsers(dest="command")
    
    # post
    post_parser = subparsers.add_parser("post", help="Post a summary")
    post_parser.add_argument("--channel", default="webchat", help="Target channel")
    post_parser.add_argument("--title", help="Content title")
    post_parser.add_argument("--url", help="Source URL")
    post_parser.add_argument("--type", dest="source_type", default="article", help="Source type")
    post_parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    if args.command == "post":
        source_data = {
            "title": args.title or "Content",
            "url": args.url or "unknown",
            "source_type": args.source_type
        }
        
        result = post_ingest_notification([args.channel], args.dry_run)
        print(json.dumps(result, indent=2))
    
    else:
        parser.print_help()
