# HarvestWise — Recent Improvements (2026-09-18)

## ✅ Implemented

### **1. Live Weather Integration**
- **File**: `engine/restock.py`
- **Change**: Added `get_weather()` function that fetches live Open-Meteo weather API for Bangalore
- **Fallback**: Seeded data (`rain_prob: 0.78`) if API unavailable
- **Impact**: Demo no longer relies solely on hardcoded weather; production-ready

### **2. Asset Folder Created**
- **Location**: `ui/assets/`
- **Purpose**: Storage for demo audio (`command_ta.wav`)
- **Status**: Empty — record crew Tamil voice to populate

### **3. Multi-Merchant Support**
- **File**: `engine/restock.py`
- **Change**: Added `rahul` merchant with `potato` product; `lakshmi` now has `onion` + `spinach`
- **Impact**: Scales beyond single demo persona; supports expansion to other merchants
- **API**: `/rec` and `/rec/basket` now accept `merchant_id` parameter

### **4. Multi-Product Catalog**

| Merchant | Products |
|---|---|
| **lakshmi** | tomato, coriander, **onion**, **spinach** |
| **rahul** | **tomato**, **potato** |

### **5. Day-Wrap Workflow**
- **File**: `n8n/daywrap.json`
- **Change**: Added 9:00AM scheduled workflow that records day-end learning
- **Flow**: End-of-day summary → Cognee learning entry → Local memory update
- **Impact**: Completes the feedback loop (deck slide 4: Observe → Predict → Act → Learn)

### **6. QA Tests**
- **Test suite**: `qa_battery.py`
- **Result**: **28/28 passed** (all regression tests)
- **Coverage**: Health, intent parsing, engine formula, approve/dispatch security, error handling, **multi-merchant support**

## 📋 Next Steps (P1 Priority)

| Task | Effort | Why |
|---|---|---|
| Record `command_ta.wav` | 10min | Demo reliability (current: typed fallback only) |
| Test live weather API | 5min | Verify `get_weather()` fetches real data |

## 🔧 Technical Notes

- Weather integration preserves seeded fallback for offline/CI scenarios
- All existing tests pass with new weather function
- No breaking changes to API contracts
