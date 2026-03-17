# TOOLS.md - Local Notes

Environment-specific values only (IDs, paths, and where secrets live). Skills define how tools work.

## Secrets and config
- Canonical .env: `~/.agent/.env`
- Compatibility symlinks: `~/workspace/.env`, `~/workspace/crm/.env`
- Platform config: `~/.agent/config.json`

## Attribution
- When leaving permanent text (comments, messages, notes), prefix with "🧠 Liz:" unless asked to ghostwrite

## Primary Messaging Platform (e.g., Telegram)
| Topic | Thread ID |
|-------|-----------|
| cron-updates | <id> |
| knowledge-base | <id> |
| financials | <id> |

## Topic behavior (quick)
- cron-updates: cron-owned; respond to follow-ups only
- knowledge-base: KB ingest notifications
- financials: owner only; never share outside DM

## Secondary Platform (e.g., Slack)
| Channel | ID |
|---------|----|
| <channel-name> | <id> |

## Project Management (e.g., Asana)
- Workspace: <workspace-name> (<workspace-id>)

| Project | ID |
|---------|-----|
| <project-name> | <id> |

## Paths
- Email CLI: `himalaya` (installed)
- Agent CLI: `openclaw` (gateway at ws://127.0.0.1:18789)
- Logs: `~/workspace/data/logs/` (unified: all.jsonl), SQLite mirror: `~/workspace/data/logs.db`

## Cron Systems
- Cron log DB: `/data/.openclaw/workspace/.cron/jobs.db`
- Cron daemon: `/data/.openclaw/workspace/.cron/daemon.py`
- Scheduler: `/data/.openclaw/workspace/.cron/scheduler.py`

## Knowledge Base
- DB: `/data/.openclaw/workspace/knowledge_base/knowledge.db`
- Ingest: `python3 knowledge_base/ingest.py ingest <url>`
- Query: `python3 knowledge_base/query.py search "<query>"`

## Memory System
- Daily notes: `/data/.openclaw/workspace/memory/YYYY-MM-DD.md`
- Synthesized: `/data/.openclaw/workspace/MEMORY.md`
- State: `/data/.openclaw/workspace/memory/heartbeat-state.json`

## API tokens
Stored in `~/.agent/.env`. See .env.example for the canonical list.

## Voice Memos
- **Inbound:** User can send voice memos. The gateway auto-transcribes them to text.
- **Outbound:** Use the tts tool to reply as a voice note.
- **Rule:** Only reply with voice when explicitly asked. Default to text.

## Content preferences
- User prefers direct answers, no filler
- Dry wit and understatement
- No em dashes

## Dual prompt stack
- Default: root .md files (minimax-m2.5)
- Fallback: codex-prompts/ (loaded when active)
- Switching configured in agent framework's config
