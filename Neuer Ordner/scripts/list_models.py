# scripts/list_models.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
import google.generativeai as genai
load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)
