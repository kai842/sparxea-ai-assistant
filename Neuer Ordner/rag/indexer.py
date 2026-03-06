import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from privacy_layer.obfuscator import Obfuscator
from ea_connector.reader_db import read_model_from_db
from indexer.chunk_builder import build_chunks
from datetime import datetime

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class EAIndexer:
    COLLECTION_NAME = "ea_elements"

    def __init__(self, obfuscator: Obfuscator, persist_directory: str = ".chromadb"):
        self.obfuscator = obfuscator
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def reindex_all(self, qeax_path: str) -> int:
        """
        Full re-index: reads entire .qeax model via SQLite,
        builds enriched chunks, clears and rebuilds the collection.
        Triggered by the 'Update Data' button in the UI.
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting full re-index...")
        data   = read_model_from_db(qeax_path)
        chunks = build_chunks(data)
        self.clear()
        self.index_elements(chunks)
        print(f"✅ Re-index complete: {len(chunks)} chunks indexed.")
        return len(chunks)

    def index_elements(self, elements: list[dict]):
        ids, embeddings, documents, metadatas = [], [], [], []

        for elem in elements:
            # Unique key = GUID, but deobfuscation returns real_name
            token = self.obfuscator.obfuscate_with_label(
                guid=elem["guid"],
                real_name=elem["real_name"],
                kind=elem["kind"],
            )

            document = (
                f"Type: {elem['ea_type']}. "
                f"Stereotype: {elem.get('stereotype', '')}. "
                f"Location: {elem.get('parent_path', '')}. "
                f"Description: {elem.get('description', '')}"
            )

            ids.append(token)
            embeddings.append(self.encoder.encode(document).tolist())
            documents.append(document)
            metadatas.append({
                "ea_type":       elem["ea_type"],
                "stereotype":    elem.get("stereotype", ""),
                "parent_path":   elem.get("parent_path", ""),
                "obfuscated_id": token,
                "indexed_at":    datetime.utcnow().isoformat(),
            })

        if ids:
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            print(f"   Indexed {len(ids)} elements into ChromaDB.")


    def clear(self):
        """Removes all entries from the collection."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
