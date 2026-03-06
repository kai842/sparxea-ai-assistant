import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ea_connector.reader_db import read_model_from_db, build_package_path

QEAX_PATH = r"C:\Users\kaizu\Desktop\Sparx EA\exampleModel.qeax"

data = read_model_from_db(QEAX_PATH)

# Pakethierarchie aufbauen
pkg_paths = build_package_path(data["packages"])
print("\nPakethierarchien:")
for pid, path in pkg_paths.items():
    print(f"  [{pid}] {path}")

# Beispiel: Element mit vollständigem Pfad
print("\nElemente mit Paketpfad:")
for _, row in data["objects"].iterrows():
    path = pkg_paths.get(row["Package_ID"], "?")
    stereo = f" «{row['Stereotype']}»" if row["Stereotype"] else ""
    print(f"  [{row['Object_Type']}] {row['Name']}{stereo}  →  {path}")
