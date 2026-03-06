import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.graph import build_graph
from agent.privacy_middleware import PrivacyMiddleware

graph = build_graph()
middleware = PrivacyMiddleware(graph)

# Pre-register known EA identifiers for this session
middleware.register_identifiers({
    "DriveControlModule_V4": "element",
    "BatteryManagementSystem": "element",
    "PowerSystem": "package",
})

print("Agent ready. Sending test message...\n")

response = middleware.chat(
    "What elements are available in the model? "
    "Also check the connectors for DriveControlModule_V4."
)

print(f"Agent response:\n{response}")
