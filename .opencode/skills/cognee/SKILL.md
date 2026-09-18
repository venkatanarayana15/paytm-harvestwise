---
name: cognee
description: Cognee causal memory for HarvestWise -- graph add_text, cognify, recall via COGNEE_BASE_URL and COGNEE_API_KEY from ~/.cognee/.env. Use for Why 20kg?
---

# Cognee Skill

Use Cognee cloud tenant env from ~/.cognee/.env:
- COGNEE_BASE_URL=https://tenant-3a5f29de-c5be-4665-ab38-4bf91ac055da.aws.cognee.ai
- COGNEE_API_KEY=9091db3a...

Endpoints:
- POST /api/v1/add_text  {datasetName: harvestwise, textData: [\"...\"]}
- POST /api/v1/cognify {datasets:[\"harvestwise\"]}
- POST /api/v1/recall {query: \"Why 20kg?\", datasets:[\"harvestwise\"]} -> graph_completion

Flow: add_text -> cognify (wait 6-8s) -> recall.
Store every Final JSON + memory_note as Lakshmi causal memory. Never invent numbers, only recall Observations.
