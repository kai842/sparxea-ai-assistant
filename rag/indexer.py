import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from privacy_layer.obfuscator import Obfuscator


# Local embedding model — runs fully offline, no API calls needed
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class EAIndexer:
    """
    Indexes EA model elements into a local ChromaDB vector database.
    All elements are stored with their obfuscated tokens — real names
    never enter the vector database.

    Metadata fields stored per element:
        - ea_type:      Element type (e.g. Block, Requirement, Port)
        - stereotype:   SysML or custom stereotype
        - parent_path:  Package path in the model hierarchy
        - obfuscated_id: Token used by the privacy layer (e.g. ELEMENT_001)
    """

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

    def index_elements(self, elements: list[dict]):
        """
        Indexes a list of EA elements into ChromaDB.
        Each element dict must contain:
            - real_name:   The actual element name (will be obfuscated)
            - kind:        Obfuscator kind ('element', 'package', etc.)
            - ea_type:     EA element type (e.g. 'Block', 'Requirement')
            - stereotype:  Stereotype string (can be empty)
            - parent_path: Package path string (e.g. 'PowerSystem/Subsystems')
            - description: Free text description (already PII-masked)
        """
        ids, embeddings, documents, metadatas = [], [], [], []

        for elem in elements:
            token = self.obfuscator.obfuscate(elem["real_name"], kind=elem["kind"])

            # Build a text representation for semantic search
            # Uses obfuscated token — real name never stored in ChromaDB
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
                "ea_type": elem["ea_type"],
                "stereotype": elem.get("stereotype", ""),
                "parent_path": elem.get("parent_path", ""),
                "obfuscated_id": token,
            })

        if ids:
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            print(f"Indexed {len(ids)} elements into ChromaDB.")

    def clear(self):
        """Removes all entries from the collection."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
