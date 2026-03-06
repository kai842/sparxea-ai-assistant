from privacy_layer.obfuscator import Obfuscator
from privacy_layer.translator import Translator
from privacy_layer.pii_handler import PiiHandler
from langchain_core.messages import HumanMessage


class PrivacyMiddleware:
    """
    Wraps the LangGraph agent with bidirectional privacy translation.

    Outbound: obfuscates user input before it reaches the LLM.
    Inbound:  deobfuscates LLM responses before they reach the user.

    Privacy layer can be disabled for non-sensitive models or testing.
    """

    def __init__(self, graph, custom_terms: list[str] | None = None, enabled: bool = True):
        self.graph = graph
        self.obfuscator = Obfuscator()
        self.translator = Translator(self.obfuscator)
        self.pii_handler = PiiHandler(custom_terms=custom_terms or [])
        self.enabled = enabled

    def register_identifiers(self, identifiers: dict[str, str]):
        """
        Pre-registers known EA identifiers before a session starts.
        identifiers: dict mapping real names to their kind,
                     e.g. {"DriveControlModule_V4": "element"}
        """
        for real_value, kind in identifiers.items():
            self.obfuscator.obfuscate(real_value, kind=kind)

    def chat(self, user_message: str) -> str:
        """
        Sends a user message through the privacy layer and agent,
        returns the final deobfuscated response.

        Args:
            user_message: Raw input from the user (may contain real names).
        """
        if self.enabled:
            processed_input = self.translator.obfuscate_text(user_message)
        else:
            processed_input = user_message

        state = {"messages": [HumanMessage(content=processed_input)]}
        result = self.graph.invoke(state)

        last_message = result["messages"][-1]
        raw_content = last_message.content

        if isinstance(raw_content, list):
            raw_response = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        else:
            raw_response = str(raw_content)

        if self.enabled:
            return self.translator.deobfuscate_text(raw_response)
        else:
            return raw_response

