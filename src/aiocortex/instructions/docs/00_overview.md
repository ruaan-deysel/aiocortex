# CORTEX - INSTRUCTIONS FOR AI ASSISTANTS

**Version:** 1.0.0
**Base URL:** http://homeassistant.local:8123
**API Prefix:** /api/cortex/

---

## About This Guide

This guide provides comprehensive instructions for AI assistants (Cursor, VS Code, Claude Code, or any MCP-enabled IDE) on how to safely and effectively interact with Home Assistant through the Cortex integration.

**Key Principles:**
- **Safety First** - Always analyze before modifying
- **Communication** - Explain actions before executing
- **Clarity** - Format output for human readability
- **Backup** - Every change is git-versioned
- **When in doubt** - ASK the user

---

## Quick Reference

**Health Check:** `GET /api/cortex/health`
**Configuration Validation:** `POST /api/cortex/system/check-config`
**View Logs:** `GET /api/cortex/logs/`

## Authentication

Cortex uses Home Assistant's built-in authentication. All API requests (except the health endpoint) require a valid long-lived access token passed as a Bearer token in the Authorization header:

```
Authorization: Bearer <YOUR_LONG_LIVED_ACCESS_TOKEN>
```

Generate a token in Home Assistant: Profile → Security → Long-Lived Access Tokens.
