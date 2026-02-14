# 🎨 LOVELACE DASHBOARD GENERATION (AI-DRIVEN)

**IMPORTANT:** Dashboard generation happens in CURSOR AI, not on agent!
Agent only provides entity data and applies final YAML.

---

## Conversational Workflow for Dashboard Creation

When user asks to create dashboard, follow this dialog:

### STEP 0: Pre-Creation Checks (MANDATORY!)

**Before creating any dashboard:**

1. **Check if dashboard already exists:**
   ```
   ha_preview_dashboard
   ha_list_files (directory="/")
   ```
   - Look for existing .yaml dashboard files
   - Check configuration.yaml for registered dashboards
   - If exists: Ask user if they want to overwrite or use different name

2. **Validate dashboard filename:**
   ```
   ⚠️ CRITICAL: Dashboard URL path MUST contain a hyphen (-)!
   
   ❌ BAD:  "heating" (no hyphen)
   ❌ BAD:  "stat" (no hyphen)
   ❌ BAD:  "climate" (no hyphen)
   
   ✅ GOOD: "heating-now"
   ✅ GOOD: "climate-control"
   ✅ GOOD: "my-dashboard"
   ```
   
   **Rules:**
   - If user suggests name without hyphen (e.g., "Heating Now")
   - Convert to kebab-case: "heating-now" ✅
   - If single word: add "-dashboard": "heating" → "heating-dashboard"
   - Always confirm filename with user before proceeding

3. **Example dialog:**
   ```
   User: "Create dashboard called 'Heating'"
   
   AI: "I'll create a dashboard for you. 
   
   Note: Home Assistant requires dashboard filenames to contain a hyphen.
   I suggest: 'heating-dashboard.yaml'
   
   Or would you prefer: 'heating-monitor', 'heating-control', or another name?"
   ```

### STEP 1: Understand Requirements

Ask clarifying questions:
- "What's the main purpose of this dashboard?" (overview, climate control, monitoring, etc)
- "Which devices/rooms are most important to you?"
- "Do you prefer detailed view or simple quick controls?"
- "Any specific features you want to see? (battery levels, temperature, automations)"

### STEP 2: Analyze Available Entities

```
ha_analyze_entities_for_dashboard
→ Get complete entity list with attributes
→ Understand what user has available
```

### STEP 3: Propose Dashboard Structure

Based on user requirements and available entities, propose:
- "I suggest 4 views: Home (overview), Climate (7 TRVs), Sensors (battery+temp), Automation"
- "Would you like to add Media view for your 3 media players?"
- Show entity counts per view

### STEP 4: Generate YAML in Cursor (YOU)

Create dashboard YAML structure:

```yaml
title: "User's Dashboard Title"
views:
  - title: Home
    path: home
    icon: mdi:home
    cards:
      - type: weather-forecast
        entity: weather.forecast_home
      - type: entities
        title: Quick Controls
        entities:
          - climate.bedroom_trv
          - light.living_room
  
  - title: Climate
    path: climate  
    icon: mdi:thermostat
    cards:
      - type: thermostat
        entity: climate.entity1
      - type: thermostat
        entity: climate.entity2
```

### STEP 5: Show Preview to User

- Display generated YAML structure
- Highlight key features
- Ask for approval or modifications

### STEP 6: Apply Dashboard

```
ha_apply_dashboard({
  dashboard_config: your_generated_yaml,
  filename: 'custom-dashboard.yaml',
  register_dashboard: true
})
→ Agent applies, registers, restarts HA
→ Dashboard appears in sidebar!
```

---

## Card Type Guidelines

| Entity Domain | Recommended Card Type | Example |
|---------------|----------------------|---------|
| `weather.*` | `weather-forecast` | Full weather card |
| `climate.*` | `thermostat` | Interactive thermostat |
| `media_player.*` | `media-control` | Media controls |
| `camera.*` | `picture-entity` | Live camera feed |
| `light.*` | `light` or `entities` | Light controls |
| `sensor.*` | `entities` or `sensor` | Grouped sensors |
| `automation.*` | `entities` | List with toggle |
| `script.*` | `entities` | List with run button |

---

## View Organization Best Practices

### 1. Home View (Always first)
- Weather card (if available)
- Person tracking
- Quick access to 4-6 most used devices
- Important sensors (battery, alerts)

### 2. Domain-Specific Views
- Group by function (Climate, Lights, Media)
- 3-8 cards per view (not too many)
- Logical ordering

### 3. Monitoring View
- Battery levels
- Temperature sensors
- System status
- Grouped by type/room

### 4. Automation View
- Automations + Scripts together
- Easy enable/disable
- Execution buttons for scripts

---

## Key Points

- ✅ AI generates YAML in Cursor (flexible, intelligent)
- ✅ AI asks questions to understand needs
- ✅ AI proposes before creating
- ✅ Agent only applies (simple, reliable)
- ✅ User gets custom dashboard, not template

---

## 🎯 Advanced Features

### Conditional Cards

For dynamic dashboards that show/hide cards based on entity state (e.g., showing only TRVs that are actively heating), see **06_conditional_cards.md** for detailed patterns and examples.

**Common use cases:**
- Heating monitoring (show only active TRVs)
- Low battery alerts
- Active media players
- Problem/warning cards





