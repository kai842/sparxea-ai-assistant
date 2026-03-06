import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from privacy_layer.obfuscator import Obfuscator
from rag.indexer import EAIndexer

QEAX_PATH = r"C:\Users\kaizu\Desktop\Sparx EA\exampleModel.qeax"

obfuscator = Obfuscator()
indexer    = EAIndexer(obfuscator=obfuscator)

count = indexer.reindex_all(QEAX_PATH)
print(f"\n✅ {count} Elemente indexiert.")
