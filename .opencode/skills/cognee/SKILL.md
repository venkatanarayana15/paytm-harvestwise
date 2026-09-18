---
name: cognee
description: Cognee causal memory for HarvestWise -- graph add_text, cognify, recall via COGNEE_BASE_URL and COGNEE_API_KEY from ~/.cognee/.env. Use for Why 20kg?
---

# Cognee Skill

Use Cognee cloud tenant env from ~/.cognee/.env:
- COGNEE_BASE_URL=https://tenant-<id>.aws.cognee.ai   (real value lives in finale/.env — never commit it)
- COGNEE_API_KEY=<set in finale/.env>   (a key fragment was committed here before 2026-09-18 — see SECURITY.md rotation list)

Endpoints:
- POST /api/v1/add_text  {datasetName: harvestwise, textData: [\"...\"]}
- POST /api/v1/cognify {datasets:[\"harvestwise\"]}
- POST /api/v1/recall {query: \"Why 20kg?\", datasets:[\"harvestwise\"]} -> graph_completion

Flow: add_text -> cognify (measured 4.8s) -> recall (measured 12.3s — budget >=45s or every recall times out).
See finale/engine/cognee_client.py and finale/IMPROVEMENTS.md (finding #6).
Store every Final JSON + memory_note as Lakshmi causal memory. Never invent numbers, only recall Observations.
