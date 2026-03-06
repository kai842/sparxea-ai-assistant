import uuid


class Obfuscator:
    """
    Manages bidirectional mapping between real EA identifiers
    and anonymous tokens (e.g. ELEMENT_001, CONNECTOR_042).
    All mappings are stored in memory only — never persisted to disk.
    """

    PREFIX_MAP = {
        "element": "ELEMENT",
        "connector": "CONNECTOR",
        "package": "PACKAGE",
        "tag": "TAG",
        "diagram": "DIAGRAM",
    }

    def __init__(self):
        self._real_to_token: dict[str, str] = {}
        self._token_to_real: dict[str, str] = {}
        self._counters: dict[str, int] = {k: 0 for k in self.PREFIX_MAP}

    def obfuscate(self, real_value: str, kind: str = "element") -> str:
        """
        Returns an anonymous token for a given real identifier.
        If the identifier was seen before, returns the existing token.

        Args:
            real_value: The actual EA element name or GUID.
            kind: Category — one of 'element', 'connector', 'package',
                  'tag', 'diagram'.
        """
        if real_value in self._real_to_token:
            return self._real_to_token[real_value]

        prefix = self.PREFIX_MAP.get(kind, "ELEMENT")
        self._counters[kind] = self._counters.get(kind, 0) + 1
        token = f"{prefix}_{self._counters[kind]:03d}"

        self._real_to_token[real_value] = token
        self._token_to_real[token] = real_value
        return token

    def deobfuscate(self, token: str) -> str:
        """
        Returns the real identifier for a given token.
        Returns the token unchanged if no mapping exists.
        """
        return self._token_to_real.get(token, token)

    def has_token(self, token: str) -> bool:
        """Returns True if the token exists in the current session mapping."""
        return token in self._token_to_real

    def clear(self):
        """Resets all mappings — call this at the start of a new session."""
        self._real_to_token.clear()
        self._token_to_real.clear()
        self._counters = {k: 0 for k in self.PREFIX_MAP}

    @property
    def mapping_size(self) -> int:
        """Returns the number of currently mapped identifiers."""
        return len(self._real_to_token)
    
    @property
    def element_count(self) -> int:
        """Returns the number of mapped identifiers of kind 'element' only."""
        return sum(
            1 for token in self._token_to_real
            if token.startswith("ELEMENT_")
        )

