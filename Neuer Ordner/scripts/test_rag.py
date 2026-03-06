import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from privacy_layer.obfuscator import Obfuscator
from rag.indexer import EAIndexer
from rag.retriever import EARetriever

obfuscator = Obfuscator()
indexer    = EAIndexer(obfuscator, persist_directory=".chromadb_test")
retriever  = EARetriever(indexer, obfuscator)

# Mock EA elements — guid field required since obfuscator fix
mock_elements = [
    {
        "guid": "{MOCK-0001}", "real_name": "DriveControlModule_V4",
        "kind": "element",    "ea_type": "Block",
        "stereotype": "SysML1.4::block", "parent_path": "PowerSystem",
        "description": "Controls drive output",
    },
    {
        "guid": "{MOCK-0002}", "real_name": "BatteryManagementSystem",
        "kind": "element",    "ea_type": "Block",
        "stereotype": "SysML1.4::block", "parent_path": "PowerSystem",
        "description": "Manages battery charging cycles",
    },
    {
        "guid": "{MOCK-0003}", "real_name": "SafetyMonitor",
        "kind": "element",    "ea_type": "Block",
        "stereotype": "SysML1.4::block", "parent_path": "SafetySystem",
        "description": "Monitors safety-critical signals",
    },
    {
        "guid": "{MOCK-0004}", "real_name": "PowerRequirement_01",
        "kind": "element",    "ea_type": "Requirement",
        "stereotype": "",     "parent_path": "SafetySystem",
        "description": "System shall supply 48V nominal",
    },
]

print("Indexing mock elements...")
indexer.index_elements(mock_elements)

print("\n--- Semantic Search: 'safety monitoring' ---")
for r in retriever.semantic_search("safety monitoring", n_results=3):
    real = obfuscator.deobfuscate(r["token"])
    print(f"  {r['token']} ({real}) | type={r['ea_type']} | score={r['score']}")

print("\n--- Lexical Search: 'battery' ---")
for r in retriever.lexical_search("battery", n_results=3):
    real = obfuscator.deobfuscate(r["token"])
    print(f"  {r['token']} ({real}) | type={r['ea_type']} | score={r['score']}")

print("\n--- Hybrid Search: 'power supply block' ---")
for r in retriever.hybrid_search("power supply block", n_results=3):
    real = obfuscator.deobfuscate(r["token"])
    print(f"  {r['token']} ({real}) | type={r['ea_type']} | score={r['score']}")

print("\n--- build_context_for_llm: 'Welche Blöcke gibt es im PowerSystem?' ---")
context = retriever.build_context_for_llm("Welche Blöcke gibt es im PowerSystem?")
print(context)

# Cleanup test database
indexer.clear()
print("✅ RAG test complete.")
