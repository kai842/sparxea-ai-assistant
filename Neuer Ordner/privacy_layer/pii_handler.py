from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


class PiiHandler:
    """
    Scans and masks PII in EA free-text fields (Notes, Descriptions,
    Tagged Value content) before transmission to cloud LLMs.

    Uses Microsoft Presidio for entity detection. Custom EA-specific
    terms can be added via the custom_terms list.
    """

    def __init__(self, custom_terms: list[str] | None = None):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        self.custom_terms = custom_terms or []

    def mask(self, text: str, language: str = "en") -> str:
        """
        Detects and masks PII entities in the given text.
        Masked entities are replaced with their type label,
        e.g. <EMAIL_ADDRESS>, <PHONE_NUMBER>, <PERSON>.

        Args:
            text: Free-text content from EA Notes or Description fields.
            language: Language code for analysis (default: 'en').
        """
        if not text or not text.strip():
            return text

        # Mask custom domain-specific terms first (simple replacement)
        for term in self.custom_terms:
            text = text.replace(term, "<CUSTOM_TERM>")

        results = self.analyzer.analyze(text=text, language=language)

        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
        )
        return anonymized.text

    def add_custom_term(self, term: str):
        """Registers a domain-specific term to be masked (e.g. project codenames)."""
        if term not in self.custom_terms:
            self.custom_terms.append(term)
