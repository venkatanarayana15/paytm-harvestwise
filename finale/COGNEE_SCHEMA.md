# Cognee Knowledge Graph — HarvestWise (Sarvam → Cognee → n8n)

> Verified flow (`engine/cognee_client.py`): `POST /api/v1/add_text {datasetName, textData:[...]}` → `POST /api/v1/cognify {datasets:[...]}` → `POST /api/v1/recall {query, datasets:[...]}`. Timeouts measured: recall 12.3s (budget 60s), add 45s. Health cached 30s.

## What Sarvam creates, Cognee remembers

Every turn `api/main.py::_handle_merchant_message` does `cognee.remember_async(["Merchant {phone} asked: {transcript}"])` (fire-and-forget, never blocks). On dispatch, a richer fact is written: `On {at} merchant {id} approved {qty} {unit} {product} from {supplier} for Rs.{total}. Stock {before}->{after}. Reason: {engine factors}.` The dataset is `harvestwise` (env `COGNEE_DATASET`).

## Merchant Entity Schema (also stored as `data/merchant_prefs.json` for low-latency reads)

```json
{
  "merchant_id": "lakshmi",
  "phone": "917010919624",
  "voice_mode": "voice | text | both",
  "language": "ta-IN | hi-IN | te-IN | kn-IN | en-US",
  "inventory_history": {
    "tomato": { "avg_demand": 25, "seasonal_peak": "monsoon", "reorder_point": 15 }
  },
  "order_history": [{ "at": "2026-09-19T12:00:00", "product": "tomato", "qty": 20, "total_inr": 400 }],
  "cognee_facts": ["Merchant 917010919624 prefers voice replies in language ta-IN."]
}
```

## Intent Classification Rules

| Input | Intent | Action |
|-------|--------|--------|
| "Stock check" | INVENTORY_CHECK | Query current levels |
| "Order rice" | INVENTORY_ORDER | Create order |
| "Who owes money" | CREDIT_RECOVERY | List debtors |
| "How to grow" | GROWTH_ANALYSIS | Suggest opportunities |

## Agentic Decision Logic

```python
def decide(intent, context):
    if intent == "INVENTORY_ORDER":
        # Check credit score
        if context.credit_score > 0.7:
            return "auto_approve"
        return "await_approval"
    
    if intent == "CREDIT_RECOVERY":
        # Check debtor history
        if debtor.payment_history == "good":
            return "friendly_reminder"
        return "formal_notice"
```

## n8n Workflow Automations

### 1. Voice Order Flow
```
Voice → Sarvam STT → Intent → n8n Workflow
  ├─ Validate credit (Cognee)
  ├─ Check inventory (Engine)
  ├─ Create order (Database)
  └─ Send confirmation (WhatsApp)
```

### 2. Credit Recovery Flow
```
Daily Check → Cognee Recall → n8n Workflow
  ├─ Identify debtors
  ├─ Generate message
  ├─ Send WhatsApp
  └─ Update payment status
```

### 3. Growth Analysis Flow
```
Weekly → Cognee Pattern Analysis → Suggestion
  ├─ Identify seasonal trends
  ├─ Calculate opportunity
  ├─ Generate recommendation
  └─ Auto-schedule reminder
```

## Low-Latency Optimizations

| Component | Strategy | Latency |
|-----------|----------|---------|
| Sarvam STT | Bounded thread pool | <5s |
| Cognee Recall | Local cache | <100ms |
| TTS Generation | Browser SpeechSynthesis | <1s |
| Workflow Execution | Async queue | <3s |
