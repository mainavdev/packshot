#!/bin/zsh
set -e

cd ~/Desktop/campagnes-packshot 2>/dev/null || { echo "❌ Dossier projet introuvable"; exit 1; }

echo "🔎 Version Python:"
python3 --version || true

echo "🔎 Paquets installés (pandas):"
python3 -c "import pandas, sys; print('pandas', pandas.__version__)" 2>/dev/null || echo "⚠️ pandas non disponible"

echo "🔎 Vérif fichiers:"
ls -lah | sed -n '1,200p'
echo "🔎 Vérif fichier-clean:"
mkdir -p fichier-clean
ls -lah fichier-clean | sed -n '1,200p'

echo "🔎 Test lecture Excel:"
python3 - << 'PY'
import pandas as pd, sys
from pathlib import Path
path = Path.home()/ "Desktop" / "Packshot.xlsx"
print("Chemin:", path)
if not path.exists():
    print("❌ Packshot.xlsx introuvable.")
    sys.exit(1)
try:
    df = pd.read_excel(path)
    print("✅ Lecture OK. Colonnes:", list(df.columns)[:12])
    print("Aperçu dates:", df.filter(like="Date", axis=1).head(3).to_dict(orient="records"))
except Exception as e:
    print("❌ Erreur lecture:", e)
PY
