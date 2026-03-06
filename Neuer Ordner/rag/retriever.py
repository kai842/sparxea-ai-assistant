from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from rag.indexer import EAIndexer, EMBEDDING_MODEL
from privacy_layer.obfuscator import Obfuscator


class EARetriever:
    """
    Performs hybrid search over the ChromaDB index:
    - Semantic search: finds elements by meaning (via vector similarity)
    - Lexical search:  finds elements by exact terms (via BM25)

    Results are merged and returned as obfuscated tokens with metadata.
    build_context_for_llm() deobfuscates and assembles the final LLM context.
    """

    def __init__(self, indexer: EAIndexer, obfuscator: Obfuscator):
        self.indexer    = indexer
        self.obfuscator = obfuscator
        self.encoder    = SentenceTransformer(EMBEDDING_MODEL)

    # ------------------------------------------------------------------ #
    #  Search methods                                                      #
    # ------------------------------------------------------------------ #

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        ea_type_filter: str | None = None,
    ) -> list[dict]:
        """
        Finds the most semantically similar elements to the query.

        Args:
            query:          Natural language search query.
            n_results:      Maximum number of results to return.
            ea_type_filter: Optional filter by EA type (e.g. 'Block').
        """
        query_embedding = self.encoder.encode(query).tolist()
        where = {"ea_type": ea_type_filter} if ea_type_filter else None

        results = self.indexer.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

        return self._format_results(results)

    def lexical_search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Finds elements using BM25 keyword matching.
        Useful for exact technical terms, abbreviations, and IDs.

        Args:
            query:     Keyword-based search query.
            n_results: Maximum number of results to return.
        """
        # ids are always returned automatically — do NOT include in include=[]
        all_docs = self.indexer.collection.get(
            include=["documents", "metadatas"]
        )

        if not all_docs["documents"]:
            return []

        tokenized = [doc.lower().split() for doc in all_docs["documents"]]
        bm25      = BM25Okapi(tokenized)
        scores    = bm25.get_scores(query.lower().split())

        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:n_results]

        return [
            {
                "token":       all_docs["ids"][i],
                "document":    all_docs["documents"][i],
                "ea_type":     all_docs["metadatas"][i]["ea_type"],
                "stereotype":  all_docs["metadatas"][i]["stereotype"],
                "parent_path": all_docs["metadatas"][i]["parent_path"],
                "score":       round(scores[i], 4),
                "search_type": "lexical",
            }
            for i in top_indices if scores[i] > 0
        ]

    def hybrid_search(
        self,
        query: str,
        n_results: int = 5,
        ea_type_filter: str | None = None,
    ) -> list[dict]:
        """
        Combines semantic and lexical search results.
        Deduplicates by token — semantic results take priority.

        Args:
            query:          Search query (natural language or keyword).
            n_results:      Maximum number of results to return.
            ea_type_filter: Optional filter by EA type.
        """
        semantic = self.semantic_search(query, n_results, ea_type_filter)
        lexical  = self.lexical_search(query, n_results)

        seen, merged = set(), []
        for result in semantic + lexical:
            token = result["token"]
            if token not in seen:
                seen.add(token)
                merged.append(result)

        return merged[:n_results]

    # ------------------------------------------------------------------ #
    #  LLM context builder                                                 #
    # ------------------------------------------------------------------ #

    def build_context_for_llm(self, query: str, n_results: int = 5) -> str:
        """
        Main entry point for the agent/graph.
        Returns a deobfuscated context string ready to inject into the LLM prompt.

        Flow: hybrid_search → deobfuscate tokens → assemble context block
        """
        hits = self.hybrid_search(query, n_results)

        if not hits:
            return "Keine relevanten Elemente im Modell gefunden."

        lines = ["Relevante EA-Modellelemente:\n"]
        for i, hit in enumerate(hits, 1):
            real_name = self.obfuscator.deobfuscate(hit["token"])
            score_pct = f"{hit['score'] * 100:.0f}%"
            lines.append(
                f"{i}. [{hit['ea_type']}] {real_name}\n"
                f"   Paket: {hit['parent_path']}\n"
                f"   Relevanz: {score_pct} ({hit['search_type']})\n"
                f"   Details: {hit.get('document', '')}\n"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _format_results(self, raw: dict) -> list[dict]:
        """Formats ChromaDB query results into a clean list of dicts."""
        results = []
        if not raw["ids"] or not raw["ids"][0]:
            return results

        for i, token in enumerate(raw["ids"][0]):
            results.append({
                "token":       token,
                "document":    raw["documents"][0][i],
                "ea_type":     raw["metadatas"][0][i]["ea_type"],
                "stereotype":  raw["metadatas"][0][i]["stereotype"],
                "parent_path": raw["metadatas"][0][i]["parent_path"],
                "score":       round(1 - raw["distances"][0][i], 4),
                "search_type": "semantic",
            })

        return results
