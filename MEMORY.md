# MEMORY.md - Core Lessons & Preferences

_Last synthesized: 2026-03-17_

## Personal Contact Info (DM-only)
- **Personal email:** <personal-email>
- This section exists here instead of USER.md so it only loads in private chats, never in group contexts.

## User Preferences
- **Writing:** Use the humanizer/style skill for drafts. User wants to avoid AI-sounding writing.
- **Tone in DMs:** More informal, friendly, and positively jokey in direct conversations. Friend-first, assistant-second.
- **Interests:** <user's interests and focus areas>
- **Content format preferences:** <how the user likes updates formatted>
- **Cross-posting rules:** <when to cross-post vs. store-only>
- **Time display:** All times shown must be in user's timezone.

## Project History (Distilled)
Full project history archived in reference/project-history.md. Key current-state facts:
- Cron automation system: `.cron/` with SQLite logging, PID locks, scheduler
- Knowledge base: `knowledge_base/` with TF-IDF semantic search
- Memory system: `memory/` with daily notes + weekly synthesis

## Content Preferences
- Direct, point-first answers
- No em dashes
- 🧠 as natural emphasis
- Dry wit and understatement

## Knowledge Base Patterns
- Cross-post to channels only when explicitly requested
- Keep KB content in internal context, summarize for external

## Task Management Rules
- Address follow-ups to existing content without re-sending
- New items get new messages

## Strategic Notes
- Priority areas: cron health, knowledge base coverage, memory synthesis
- Active integrations: cron system, KB ingestion, heartbeat automation

## Security & Privacy Infrastructure
- **PII redaction:** Automated layer catches personal emails, phone numbers, dollar amounts.
- **Data classification tiers:** Confidential (DM-only), Internal (group chats OK), Restricted (external only with approval).
- **Content gates:** Frontier scanner for outbound emails and security-sensitive operations.
- **Secret handling:** Never share credentials unless explicitly requested by name with confirmed destination.

## Analysis Patterns
- When the user asks about a recommendation in conversation, pull the data locally and include it in the reply. Don't re-post to messaging.
- When discussing config changes, just make the fix. Skip the accounting of alternative approaches unless asked.

## LLM Usage Queries
- Gateway usage tracked in session transcripts
- Model routing via centralized config

## Operational Lessons
- **Duplicate delivery prevention:** Content already posted is delivered. Don't re-send it.
- **Lock files:** Check for stale lock files if ingestion hangs. Delete if owning PID is dead.
- **Gateway token sync:** Multiple locations store the gateway token. After updates, verify they match.
- **Notification validation:** Always validate API responses, not just CLI exit codes. Silent failures happen.
- **Model routing:** All LLM calls route through a centralized router with comprehensive logging.

## Email Triage Patterns
- **High priority:** Meetings, partner communications, payments, tax documents, family/school, bills
- **Medium:** Inbound leads, guest bookings, shipping
- **Low:** Newsletters, social notifications, marketing

## System Health & Monitoring
- Consolidated health check runs during heartbeats
- Persistent failure tracking alerts on repeated failures
- Notification batching reduces noise

---
*Specific task logs are moved to daily memory files to keep this file concise.*
