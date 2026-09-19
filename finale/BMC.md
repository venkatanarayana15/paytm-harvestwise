# HarvestWise - Business Model Canvas

## 1. Value Propositions
| Problem | Solution |
| :--- | :--- |
| Farmers/merchants lose 30% produce to spoilage | **Real-time inventory & price alerts** via WhatsApp |
| Middlemen dictate prices; lack of transparency | **Market rate visibility** using historical data + live API |
| Language barrier (low literacy) | **Voice-first interface** (Sarvam STT) + vernacular support |
| Manual record-keeping is tedious | **Zero-touch digital ledger** via chatbot + UI |

## 2. Customer Segments
- **Smallholder Farmers** (<2 acres, limited tech access)
- **Agri-Merchants / Retailers** (need digital inventory tracking)
- **FPOs / Cooperatives** (need bulk coordination + price intelligence)

## 3. Channels
- **WhatsApp** (Primary, 400M+ users in India)
- **Web Dashboard** (Admin view for merchants)
- **On-ground Workshops** (FPO training + QR code signup)

## 4. Customer Relationships
- **Automated Copilot:** 24/7 chat + voice support
- **Human-in-the-Loop:** Escalation to real agent for complex queries
- **Trust Building:** Verified price data + historical tracking

## 5. Revenue Streams
- **B2B SaaS:** ₹50-100/user/month for FPOs/co-ops
- **Premium Features:** Analytics + logistics coordination
- **Data Monetization:** Aggregated pricing insights (future)

## 6. Key Activities
- Price monitoring & forecasting
- Inventory management via chat
- User onboarding & training
- API integration (market data, logistics)

## 7. Key Resources
- **AI Stack:** Sarvam (LLM + STT), Cognee (memory)
- **Backend:** FastAPI, N8N workflows
- **Platform:** WhatsApp Cloud API
- **Team:** AI engineers + agri-experts

## 8. Key Partnerships
- Agri-retailers & wholesalers
- Logistics providers (transport coordination)
- Government schemes (PMFBY insurance, MSP alerts)
- FPO networks

## 9. Cost Structure
- **API Costs:** Sarvam LLM, Twilio/WhatsApp, Market APIs
- **Cloud:** 1x VPS + Database
- **DevOps:** Monitoring, CI/CD

---

# Technical Architecture: Why This Wins

## Stronger Integration

### 1. **Sarvam (Brain)**
- **STT:** Converts voice notes (Hindi/Tamil/Kannada) to text
- **LLM:** Extracts intent ("check price", "add stock") using few-shot prompts
- **Optimization:** Use deterministic fallback for price calculations (not pure LLM)

### 2. **Cognee (Memory)**
- **Short-term:** User context (last 10 messages)
- **Long-term:** User preferences, historical prices, order history
- **Benefit:** "Show me what I bought last week" → instant recall

### 3. **n8n (Orchestrator)**
- **Workflow A:** When order confirmed → notify buyer via WhatsApp
- **Workflow B:** When price drops 10% → alert merchant
- **Benefit:** Business logic without code changes

### 4. **Unified Flow**
```
WhatsApp/Voice → Sarvam STT → Intent Detection → Cognee Memory
                                                    ↓
                                            API Logic (Price/Stock)
                                                    ↓
                                          n8n Actions (Notifications)
                                                    ↓
                                           WhatsApp Response
```

---

# Hackathon Demo Strategy

## What Judges Will See

### 1. UI Copilot (Merchant Dashboard)
- **Live price tracking** with charts
- **Inventory management** via chat commands
- **Backend activity log** showing AI processing

### 2. WhatsApp Copilot (Real User)
- **Voice note:** "check tomato price today"
- **Instant reply:** "₹40/kg (up 5% from yesterday)"
- **Follow-up:** "add 50kg to stock" → inventory updated

### 3. Behind the Scenes
- **Sarvam** processes voice + intent
- **Cognee** recalls historical prices
- **n8n** triggers buyer notification

## Success Criteria
✅ **Functional:** Both WhatsApp + UI work
✅ **Fast:** Response time <3 seconds
✅ **Vernacular:** Voice note works
✅ **Memory:** Recalls past prices/orders
✅ **Scalable:** Clean separation of concerns (API + n8n + AI)
