import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from privacy_layer.obfuscator import Obfuscator
from privacy_layer.translator import Translator
from privacy_layer.pii_handler import PiiHandler

print("=== Obfuscator & Translator ===\n")

obfuscator = Obfuscator()
translator = Translator(obfuscator)

token_a = obfuscator.obfuscate("DriveControlModule_V4", kind="element")
token_b = obfuscator.obfuscate("BatteryManagementSystem", kind="element")
token_c = obfuscator.obfuscate("PowerSupply_Main", kind="connector")
token_d = obfuscator.obfuscate("Safety-Level", kind="tag")

print(f"Mapped {obfuscator.mapping_size} identifiers")
print(f"DriveControlModule_V4  → {token_a}")
print(f"BatteryManagementSystem → {token_b}")
print(f"PowerSupply_Main        → {token_c}")
print(f"Safety-Level            → {token_d}")

original = "DriveControlModule_V4 depends on BatteryManagementSystem via PowerSupply_Main"
obfuscated = translator.obfuscate_text(original)
print(f"\nOutbound (to LLM):\n  {obfuscated}")

llm_response = f"I recommend connecting {token_a} directly to {token_b}."
deobfuscated = translator.deobfuscate_text(llm_response)
print(f"\nInbound (from LLM):\n  {deobfuscated}")

assert obfuscator.deobfuscate(token_a) == "DriveControlModule_V4"
assert obfuscator.deobfuscate(token_b) == "BatteryManagementSystem"
assert obfuscator.deobfuscate(token_d) == "Safety-Level"
print("\n✅ Obfuscator assertions passed.")

print("\n=== PII Handler ===\n")

pii = PiiHandler(custom_terms=["Project-Phoenix", "ASIL-B"])
test_note = (
    "This block was designed by john.doe@company.com. "
    "Contact the owner at +49 170 1234567 for details. "
    "Codename: Project-Phoenix. Safety classification: ASIL-B."
)
masked = pii.mask(test_note)
print(f"Original:\n  {test_note}")
print(f"\nMasked:\n  {masked}")
print("\n✅ PII handler executed.")
