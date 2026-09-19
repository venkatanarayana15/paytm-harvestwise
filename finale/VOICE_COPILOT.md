# Paytm Copilot: Voice-First WhatsApp Assistant

## 🎯 Core Architecture: Agentic RAG Graph

```
┌─────────────┐
│   User      │ → Voice/Text → WhatsApp
└──────┬──────┘
       │
┌──────▼───────┐
│  Sarvam STT  │ → Transcribe voice to text
└──────┬───────┘
       │
┌──────▼───────┐
│  Intent Router│ → Classify: growth, inventory, credit, Q&A
└──────┬───────┘
       │
┌──────▼───────┐
│ Cognee Graph │ → Retrieve history, patterns, preferences
└──────┬───────┘
       │
┌──────▼───────┐
│ Agentic AI   │ → Decision + Response generation
└──────┬───────┘
       │
┌──────▼───────┐
│  n8n Workflows│ → Execute: WhatsApp, UI, orders
└──────┬───────┘
       │
┌──────▼───────┐
│  Sarvam TTS  │ → Convert response to voice
└──────┬───────┘
       │
┌──────▼───────┐
│   WhatsApp   │ → Text/Voice message to merchant
└──────────────┘
```

## 🚀 Key Features

### 1. Voice-First Support
- **Input**: Voice note → Sarvam STT → Intent
- **Output**: Response → Sarvam TTS → Voice message
- **Toggle**: Users can set voice/text/both preference

### 2. Deep Cognee Knowledge Graph

| Entity | Memory Fields |
|--------|---------------|
| Merchant | language_preference, voice_mode, inventory_history, credit_score |
| Customer | payment_behavior, purchase_frequency, credit_debt |
| Product | sales_velocity, seasonal_patterns, reorder_points |

### 3. Low-Latency Optimizations
- **Edge caching** for common responses (inventory status)
- **Async processing** for non-critical operations (memory updates)
- **Connection pooling** for Sarvam calls

### 4. Enhanced n8n Workflows

```python
# Example workflows
1. Voice → Order → WhatsApp Confirmation
2. Credit → Debt Check → Reminder → Payment Link
3. Inventory → Stock Analysis → Auto-order → Supplier Notification
4. Growth → Sales Pattern → Suggestion → Action Plan
```

## 📋 Implementation Plan

### Phase 1: Backend Core (Voice/Text)
1. Add TTS endpoint to API
2. Implement voice preference system
3. Enhance Cognee memory schema

### Phase 2: UI Integration
1. Voice recording button
2. Speaker icon for voice responses
3. Preference toggle

### Phase 3: WhatsApp Integration
1. Voice message sending
2. Voice note receiving
3. Preference sync

### Phase 4: Agentic RAG
1. Intent routing logic
2. Knowledge graph queries
3. Decision making engine
