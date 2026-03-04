# sparxea-ai-assistant

A Python-based AI assistant for Sparx Enterprise Architect (EA) that enables
the use of cloud LLMs for model analysis, validation, and generation.

A bidirectional privacy layer anonymizes element names, GUIDs, and free-text
fields before any data leaves your machine, ensuring that proprietary naming
conventions and system identifiers remain confidential. The LLM receives only
anonymized tokens and structural type information. Model structure and element
type information are transmitted in clear text by design, as they are required
for meaningful reasoning by the LLM. Responses are automatically translated
back to real names in the UI.

## What is protected
- Element names, GUIDs, and custom identifiers → replaced with anonymous tokens (e.g. `ELEMENT_001`)
- Free-text fields (Notes, Descriptions) → scanned for PII and sensitive terms before transmission

## What is not protected
- Model structure (package hierarchy, connector topology)
- Element types (e.g. Block, Requirement, Port) and stereotypes

Users working with highly sensitive structural designs should be aware of this
limitation before use.
