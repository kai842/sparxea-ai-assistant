from privacy_layer.obfuscator import Obfuscator
from privacy_layer.translator import Translator
from privacy_layer.pii_handler import PiiHandler
from langchain_core.messages import HumanMessage, AIMessage


class PrivacyMiddleware:
    """
    Wraps the LangGraph agent with bidirectional privacy translation.

    Outbound: obfuscates user input before it reaches the LLM.
    Inbound:  deobfuscates LLM responses before they reach the user.

    Maintains full conversation history across turns within a session.
    """

    def __init__(self, graph, custom_terms: list[str] | None = None, enabled: bool = True):
        self.graph       = graph
        self.obfuscator  = Obfuscator()
        self.translator  = Translator(self.obfuscator)
        self.pii_handler = PiiHandler(custom_terms=custom_terms or [])
        self.enabled     = enabled
        self._history: list[HumanMessage | AIMessage] = []

    def register_identifiers(self, identifiers: dict[str, str]):
        """Pre-registers known EA identifiers before a session starts."""
        for real_value, kind in identifiers.items():
            self.obfuscator.obfuscate(real_value, kind=kind)

    def clear_history(self):
        """Clears the conversation history (e.g. when user clears chat)."""
        self._history = []

    def chat(self, user_message: str) -> str:
        """
        Sends a user message through the privacy layer and agent,
        returns the final deobfuscated response.
        Conversation history is maintained across turns.
        """
        # Obfuscate input if privacy layer is active
        if self.enabled:
            processed_input = self.translator.obfuscate_text(user_message)
        else:
            processed_input = user_message

        # Build state: full history + current message
        current_message = HumanMessage(content=processed_input)
        state = {"messages": self._history + [current_message]}

        result = self.graph.invoke(state)

        last_message = result["messages"][-1]
        raw_content  = last_message.content

        # Handle list-type content (e.g. Gemini multipart responses)
        if isinstance(raw_content, list):
            raw_response = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        else:
            raw_response = str(raw_content)

        # Deobfuscate response before returning to user
        if self.enabled:
            final_response = self.translator.deobfuscate_text(raw_response)
        else:
            final_response = raw_response

        # Store obfuscated exchange in history
        # (LLM never sees real names — history stays obfuscated too)
        self._history.append(current_message)
        self._history.append(AIMessage(content=raw_response))

        return final_response
