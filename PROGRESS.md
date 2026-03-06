# Development Progress

## Completed Phases
- [x] Phase 0 — Project setup (Git, venv, folder structure)
- [x] Phase 1 — Privacy Layer (obfuscator, translator, pii_handler)
- [x] Phase 2 — LangGraph Agent (graph, tools, privacy_middleware)
- [x] Phase 3 — RAG with ChromaDB (indexer, retriever)
- [x] Phase 4 — Streamlit UI (chat interface, privacy toggle, RAG sidebar)

## Open Phases
- [ ] Phase 5 — EA COM connection (real Sparx EA integration)
- [ ] Phase 6 — Integration & Tests

## Current model
- LLM: gemini-2.5-flash (via langchain-google-genai)
- Embeddings: all-MiniLM-L6-v2 (sentence-transformers, local)
- Vector DB: ChromaDB (local, .chromadb/)
- Python: 3.12.10

## Key files
- agent/config.py        — LLM configuration
- agent/graph.py         — LangGraph ReAct graph
- agent/tools.py         — EA tool definitions (mock data)
- agent/privacy_middleware.py — Privacy layer wrapper
- privacy_layer/obfuscator.py — Token mapping
- privacy_layer/translator.py — Bidirectional translation
- privacy_layer/pii_handler.py — Presidio PII masking
- rag/indexer.py         — ChromaDB indexing
- rag/retriever.py       — Hybrid search
- ui/app.py              — Streamlit chat interface
