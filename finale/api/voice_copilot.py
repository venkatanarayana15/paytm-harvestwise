"""
Paytm Copilot AI - Voice-First WhatsApp Assistant
Enhanced Agentic RAG Graph Architecture
"""

# Agentic RAG + Intent Router Design
# 1. Sarvam: Intent classification
# 2. Cognee: Knowledge graph retrieval
# 3. Decision Engine: Agentic reasoning
# 4. n8n: Workflow execution
# 5. Sarvam TTS: Voice output

# Core routing table
INTENT_TYPES = [
    "GROWTH_ANALYSIS",      # Business growth suggestions
    "INVENTORY_CHECK",      # Stock levels, reorder
    "INVENTORY_ORDER",      # Place orders
    "CREDIT_RECOVERY",      # Pending payments
    "CUSTOMER_SUPPORT",     # General Q&A
    "ORDER_STATUS",         # Track orders
    "VOICE_PREFERENCE",     # Set voice/text mode
    "VOICE_OUTPUT",         # Request voice response
]

# Low-latency caching for common queries
RESPONSE_CACHE = {
    "inventory_status": 300,  # Cache 5 minutes
    "credit_status": 600,      # Cache 10 minutes
    "order_history": 1200,     # Cache 20 minutes
}

# Agentic decision weights
DECISION_WEIGHTS = {
    "inventory_order": 0.8,    # High confidence needed
    "credit_recovery": 0.7,
    "growth_suggestion": 0.6,
}
