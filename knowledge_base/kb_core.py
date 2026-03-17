#!/usr/bin/env python3
"""
Knowledge Base - RAG System
Pure-Python implementation without heavy ML dependencies
Uses TF-IDF-style embeddings for semantic search
"""

import sqlite3
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import urllib.request
import urllib.error
from html.parser import HTMLParser
import math

KB_DIR = Path("/data/.openclaw/workspace/knowledge_base")
DB_PATH = KB_DIR / "knowledge.db"
LOCK_FILE = KB_DIR / ".ingest.lock"
CACHE_DIR = KB_DIR / "cache"

class SimpleEmbedding:
    """Simple TF-IDF style embedding without ML dependencies."""
    
    def __init__(self):
        self.vocab = {}
        self.idf = {}
        self.doc_count = 0
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer."""
        text = text.lower()
        # Remove special chars but keep some punctuation
        text = re.sub(r'[^\w\s\-]', ' ', text)
        tokens = text.split()
        # Filter short tokens
        tokens = [t for t in tokens if len(t) > 2]
        return tokens
    
    def add_document(self, text: str):
        """Add document to vocabulary."""
        self.doc_count += 1
        tokens = self._tokenize(text)
        unique_tokens = set(tokens)
        
        for token in unique_tokens:
            if token not in self.vocab:
                self.vocab[token] = 0
            self.vocab[token] += 1
    
    def build_idf(self):
        """Build IDF weights."""
        for token, doc_freq in self.vocab.items():
            # Use log with floor to prevent negative values
            idf = math.log(self.doc_count / (1 + doc_freq))
            # Ensure IDF is at least a small positive value
            self.idf[token] = max(idf, 0.1)
    
    def embed(self, text: str) -> Dict[str, float]:
        """Generate TF-IDF vector for text."""
        tokens = self._tokenize(text)
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        
        # Normalize TF
        total = len(tokens) if tokens else 1
        for token in tf:
            tf[token] /= total
        
        # Apply IDF - use default for unknown tokens
        default_idf = 0.5  # Default IDF for unknown terms
        vector = {}
        for token, tf_val in tf.items():
            idf = self.idf.get(token, default_idf)
            vector[token] = tf_val * idf
        
        # Store only non-zero values
        return {k: v for k, v in vector.items() if v > 0}
    
    @staticmethod
    def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Compute cosine similarity between two TF-IDF vectors."""
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in set(vec1) | set(vec2))
        
        norm1 = math.sqrt(sum(v**2 for v in vec1.values())) if vec1 else 0
        norm2 = math.sqrt(sum(v**2 for v in vec2.values())) if vec2 else 0
        
        denominator = norm1 * norm2
        if denominator == 0:
            return 0.0
        
        return dot_product / denominator


class HTMLStripper(HTMLParser):
    """Strip HTML tags and extract text."""
    
    def __init__(self):
        super().__init__()
        self.reset()
        self.text_parts = []
    
    def handle_data(self, data):
        self.text_parts.append(data)
    
    def get_text(self):
        return ' '.join(self.text_parts)


def strip_html(html: str) -> str:
    """Remove HTML tags."""
    stripper = HTMLStripper()
    try:
        stripper.feed(html)
        return stripper.get_text()
    except:
        return html


def sanitize_content(content: str, use_semantic_check: bool = False) -> Tuple[bool, str]:
    """
    Sanitize content for injection attacks.
    Returns (is_safe, cleaned_content)
    """
    original = content
    
    # Deterministic checks - regex for common injection patterns
    # More precise patterns to avoid false positives
    dangerous_patterns = [
        r'<script[^>]*>(?!</script>)',  # Unclosed script tags
        r'javascript:\s*\w+\s*\(',        # JS protocol with function calls
        r'on\w+\s*=\s*["\']?\s*[\w\(]', # Event handlers with code
        r'eval\s*\(\s*["\']',            # eval() with string
        r'__import__\s*\(\s*["\']',      # Python dynamic imports
        r'<iframe[^>]*src\s*=\s*["\']?javascript:',  # Iframe with JS
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
            return False, f"[BLOCKED: Dangerous pattern detected]"
    
    # Clean up common tracking/UTM params in text references
    content = re.sub(r'\?utm_\w+=[^&\s]*', '', content)
    content = re.sub(r'&utm_\w+=[^&\s]*', '', content)
    
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content)
    
    return True, content.strip()


def validate_url(url: str) -> bool:
    """Validate URL scheme and format."""
    try:
        parsed = urlparse(url)
        
        # Only allow http/https
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Must have hostname
        if not parsed.netloc:
            return False
        
        return True
    except:
        return False


def clean_url_for_display(url: str) -> str:
    """Remove tracking params from URL."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # Remove UTM and tracking params
    tracking_keys = [k for k in query_params.keys() if 'utm_' in k or k in ('fbclid', 'gclid', 'msclkid')]
    for key in tracking_keys:
        del query_params[key]
    
    # Rebuild URL
    if query_params:
        new_query = '&'.join(f"{k}={v[0]}" for k, v in query_params.items())
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
    else:
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    return clean_url


def fetch_content(url: str) -> Optional[Tuple[str, str, str]]:
    """
    Fetch content from URL based on source type.
    Returns (text_content, title, source_type) or None
    """
    if not validate_url(url):
        return None
    
    try:
        # Set user agent to avoid blocks
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; OpenClaw-KB/1.0)'
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            content_type = response.headers.get('Content-Type', '')
            
            # Determine source type
            if 'youtube.com' in url or 'youtu.be' in url:
                source_type = 'youtube'
                # For YouTube, we'd normally use API, but for now extract from page
                html = response.read().decode('utf-8', errors='ignore')
                text = strip_html(html)
                # Extract title from og:title or title tag
                title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
                title = title_match.group(1) if title_match else "YouTube Video"
            
            elif 'twitter.com' in url or 'x.com' in url:
                source_type = 'twitter'
                html = response.read().decode('utf-8', errors='ignore')
                text = strip_html(html)
                title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
                title = title_match.group(1) if title_match else "Twitter/X Post"
            
            elif 'pdf' in content_type.lower() or url.endswith('.pdf'):
                source_type = 'pdf'
                # For now, store PDF as binary reference
                # In production, use PyPDF2 or pdfplumber
                text = f"[PDF Document - {url}]"
                title = url.split('/')[-1]
            
            else:
                source_type = 'article'
                html = response.read().decode('utf-8', errors='ignore')
                text = strip_html(html)
                
                # Extract title
                title_match = re.search(r'<title>([^<]*)</title>', html)
                if not title_match:
                    title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
                
                title = title_match.group(1) if title_match else url
        
        return text, title, source_type
    
    except urllib.error.URLError as e:
        print(f"URL Error fetching {url}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence.split())
        
        if current_length + sentence_length > chunk_size and current_chunk:
            # Save chunk
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)
            
            # Keep last `overlap` words for next chunk
            overlap_words = ' '.join(current_chunk)[-overlap:] if overlap > 0 else ""
            current_chunk = [overlap_words] if overlap_words else []
            current_length = len(current_chunk[0].split()) if current_chunk else 0
        
        current_chunk.append(sentence)
        current_length += sentence_length
    
    # Don't forget last chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def ensure_db():
    """Initialize or verify database."""
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # Sources table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            source_type TEXT,
            tags TEXT,
            ingested_at TEXT,
            content_hash TEXT
        )
    ''')
    
    # Chunks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            chunk_index INTEGER,
            embedding TEXT,
            created_at TEXT,
            FOREIGN KEY(source_id) REFERENCES sources(id)
        )
    ''')
    
    # Vocabulary table (for embeddings)
    c.execute('''
        CREATE TABLE IF NOT EXISTS vocabulary (
            token TEXT PRIMARY KEY,
            idf REAL,
            doc_count INTEGER
        )
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_source_id ON chunks(source_id)
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_url ON sources(url)
    ''')
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    ensure_db()
    print("Knowledge base initialized")
