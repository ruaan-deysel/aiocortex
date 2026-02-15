# EXPLAIN BEFORE EXECUTING

**CRITICAL: Always explain what you're about to do BEFORE calling API endpoints!**

**Why:** Users need to understand your plan before you execute it.

---

## Format

```
I'm going to [high-level goal]:
1. [API call] - [what it does]
2. [API call] - [what it does]
3. [Expected result]

Proceeding...
```

---

## Examples

### Good Example: Dashboard Creation

```
User: "Create a dashboard"

AI: "I'll create a custom dashboard for your climate system:
1. GET /api/cortex/lovelace/analyze - Get your devices and sensors
2. Generate YAML based on your requirements
3. POST /api/cortex/lovelace/apply - Create and register the dashboard
4. POST /api/cortex/system/restart - Restart HA to make it visible

Proceeding..."

[then executes API calls]
```

### Good Example: Add-on Installation (HA OS only)

```
User: "Check my add-ons"

AI: "I'll check your installed add-ons:
1. GET /api/cortex/addons/installed - List installed add-ons
2. Summarize the results

Proceeding..."

[then executes API calls]
```

### Bad Example

```
User: "Create dashboard"
AI: [calls GET /api/cortex/lovelace/analyze without explanation]
```

---

## Exceptions

**Simple read-only checks don't need explanation:**
- `POST /api/cortex/system/check-config` (quick validation)
- `GET /api/cortex/logs/` (when user asks for logs)
- `GET /api/cortex/entities/state/{entity_id}` (checking specific entity)
