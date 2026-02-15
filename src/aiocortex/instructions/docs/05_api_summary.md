# API ENDPOINTS SUMMARY

All endpoints are prefixed with `/api/cortex/` and require a valid HA long-lived access token (Bearer auth), except for the health endpoint.

## Quick Reference

| Category | Endpoints |
|----------|-----------|
| **Health** | GET /api/cortex/health |
| **Files** | GET /api/cortex/files/list, /api/cortex/files/read; POST /api/cortex/files/write, /api/cortex/files/append; DELETE /api/cortex/files/delete; POST /api/cortex/files/parse-yaml |
| **Entities** | GET /api/cortex/entities/list, /api/cortex/entities/state/{entity_id}, /api/cortex/entities/services; POST /api/cortex/entities/call_service |
| **Helpers** | GET /api/cortex/helpers/list; POST /api/cortex/helpers/create; DELETE /api/cortex/helpers/delete |
| **Automations** | GET /api/cortex/automations/list, /api/cortex/automations/{id}; POST /api/cortex/automations/create; PUT /api/cortex/automations/{id}; DELETE /api/cortex/automations/delete/{id} |
| **Scripts** | GET /api/cortex/scripts/list, /api/cortex/scripts/{object_id}; POST /api/cortex/scripts/create; PUT /api/cortex/scripts/{object_id}; DELETE /api/cortex/scripts/delete/{object_id} |
| **Dashboard** | GET /api/cortex/lovelace/analyze; POST /api/cortex/lovelace/preview, /api/cortex/lovelace/apply; DELETE /api/cortex/lovelace/delete |
| **Themes** | GET /api/cortex/themes/list, /api/cortex/themes/{name}; POST /api/cortex/themes/create, /api/cortex/themes/reload, /api/cortex/themes/check-config; PUT /api/cortex/themes/{name}; DELETE /api/cortex/themes/{name} |
| **Registries** | GET /api/cortex/registries/entities, /api/cortex/registries/areas, /api/cortex/registries/devices; POST /api/cortex/registries/areas/create; PUT /api/cortex/registries/entities/{entity_id}, /api/cortex/registries/areas/{area_id}; DELETE /api/cortex/registries/areas/{area_id} |
| **System** | POST /api/cortex/system/reload, /api/cortex/system/check-config, /api/cortex/system/restart; GET /api/cortex/system/config |
| **Backup** | POST /api/cortex/backup/commit, /api/cortex/backup/rollback/{commit_hash}, /api/cortex/backup/checkpoint, /api/cortex/backup/checkpoint/end, /api/cortex/backup/cleanup; GET /api/cortex/backup/history, /api/cortex/backup/pending, /api/cortex/backup/diff, /api/cortex/backup/restore |
| **Logs** | GET /api/cortex/logs/ |
| **Logbook** | GET /api/cortex/logbook/ |
| **HACS** | GET /api/cortex/hacs/status, /api/cortex/hacs/repositories |
| **Apps** | GET /api/cortex/apps/installed, /api/cortex/apps/{slug}/info (HA OS/Supervised only) |
| **Node-RED** | GET /api/cortex/nodered/flows/list, /api/cortex/nodered/flows/get/{flow_id}; POST /api/cortex/nodered/flows/create; PUT /api/cortex/nodered/flows/update/{flow_id}; DELETE /api/cortex/nodered/flows/delete/{flow_id}; GET /api/cortex/nodered/nodes (HA OS/Supervised only) |
| **Instructions** | GET /api/cortex/instructions |
