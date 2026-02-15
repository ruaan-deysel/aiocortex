# OUTPUT FORMATTING FOR USER

**CRITICAL: Always format API output for readability!**

When API endpoints return data, DON'T show raw JSON to user. Format it nicely.

---

## Examples

### 1. Entity Analysis

**BAD:** Show 7000 lines of JSON

**GOOD:**
```
Your Home Assistant has:
- 238 total entities
- 76 sensors (temperature, battery, system status)
- 7 climate devices (TRVs)
- 35 switches
- 12 automations + 5 scripts

Main rooms: Office (21), Bathroom (19), Kitchen (17)
```

### 2. App Lists

**BAD:** 83 apps JSON dump

**GOOD:**
```
Available Apps (83 total):

Popular:
- Zigbee2MQTT (a0d7b954_zigbee2mqtt)
- Node-RED (a0d7b954_nodered)
- ESPHome (hassio_esphome)
```

### 3. Logs

**BAD:** Raw JSON array

**GOOD:**
```
Recent logs:
[21:03:35] Dashboard registered
[21:03:46] Restart failed: 504 (normal during restart)
```

### 4. Dashboard Operations

**BAD:** `{"success": true, "data": {...}}`

**GOOD:**
```
Dashboard "Heating Now" created!
- File: heating-now.yaml
- Registered in configuration.yaml
- HA restarting...
- Refresh UI to see dashboard in sidebar!
```

---

## General Rules

- Show key information, hide implementation details
- Format lists, tables, and hierarchies clearly
- Highlight important values (counts, statuses, errors)
- Add context and next steps for user

---

## When to Show Raw Data

- User explicitly asks for "raw data" or "JSON"
- Debugging/troubleshooting scenarios
- Developer mode requests
