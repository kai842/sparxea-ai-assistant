import re
from privacy_layer.obfuscator import Obfuscator


class Translator:
    """
    Scans text for known EA identifiers and replaces them with tokens
    (outbound) or replaces tokens back with real names (inbound).
    """

    # Matches tokens like ELEMENT_001, CONNECTOR_042, TAG_007 etc.
    TOKEN_PATTERN = re.compile(
        r'\b(ELEMENT|CONNECTOR|PACKAGE|TAG|DIAGRAM)_(\d{3})\b'
    )

    def __init__(self, obfuscator: Obfuscator):
        self.obfuscator = obfuscator

    def obfuscate_text(self, text: str) -> str:
        """
        Outbound: Replaces all known real identifiers in text with tokens.
        Only replaces identifiers already registered in the obfuscator.
        """
        for real_value, token in self.obfuscator._real_to_token.items():
            text = text.replace(real_value, token)
        return text

    def deobfuscate_text(self, text: str) -> str:
        """
        Inbound: Replaces all tokens in text with their real identifiers.
        Tokens without a mapping are left unchanged.
        """
        def replace_token(match: re.Match) -> str:
            token = match.group(0)
            return self.obfuscator.deobfuscate(token)

        return self.TOKEN_PATTERN.sub(replace_token, text)
