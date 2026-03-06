import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from privacy_layer.obfuscator import Obfuscator
from rag.indexer import EAIndexer
from rag.retriever import EARetriever
from agent.tools import init_tools
from agent.graph import build_graph
from agent.privacy_middleware import PrivacyMiddleware
from langchain_core.messages import HumanMessage

QEAX_PATH = r"C:\Users\kaizu\Desktop\Sparx EA\exampleModel.qeax"

# Startup: index model + init tools
obfuscator = Obfuscator()
indexer    = EAIndexer(obfuscator, persist_directory=".chromadb")
retriever  = EARetriever(indexer, obfuscator)

print("Re-indexing model...")
indexer.reindex_all(QEAX_PATH)

init_tools(retriever, QEAX_PATH)

# Build agent
graph      = build_graph()
middleware = PrivacyMiddleware(graph)

print("\nAgent ready. Sending test questions...\n")

questions = [
    "Welche Elemente gibt es im Modell?",
    "Was sind die Details zum ersten Block den du findest?",
]

for q in questions:
    print(f"Frage: {q}")
    response = middleware.chat(q)
    print(f"Antwort: {response}\n")
