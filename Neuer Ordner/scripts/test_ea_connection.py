import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import win32com.client

def test_connection():
    """
    Tests the COM connection to a running Sparx EA instance.
    EA must be open with a model loaded before running this script.
    """
    print("Connecting to Sparx EA via COM...")

    try:
        ea = win32com.client.GetActiveObject("EA.App")
        repo = ea.Repository
        print(f"✅ Connected to EA successfully.")
        print(f"   Model: {repo.ConnectionString}")

        # Count top-level packages
        models = repo.Models
        print(f"   Top-level models: {models.Count}")

        for i in range(models.Count):
            model = models.GetAt(i)
            print(f"   → [{i}] {model.Name}")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nMake sure:")
        print("  1. Sparx EA is running")
        print("  2. A model is open (.qeax file)")
        print("  3. pywin32 is installed in your venv")

if __name__ == "__main__":
    test_connection()
