#!/bin/zsh
set -e

echo "📂 Dossier courant: $(pwd)"
cd ~/Desktop/campagnes-packshot 2>/dev/null || { echo "❌ Dossier ~/Desktop/campagnes-packshot introuvable"; exit 1; }
echo "📂 Dossier projet: $(pwd)"

# Vérif fichier source
SOURCE=~/Desktop/Packshot.xlsx
if [ ! -f "$SOURCE" ]; then
  echo "❌ Fichier brut introuvable: $SOURCE"
  echo "➡️  Place 'Packshot.xlsx' sur le Bureau puis relance."
  exit 1
fi
echo "✅ Fichier source trouvé: $SOURCE"

# Activer venv si présent (sinon, continuer)
if [ -f ../packshot-env/bin/activate ]; then
  echo "🟢 Activation de l'environnement virtuel..."
  source ../packshot-env/bin/activate
else
  echo "⚠️ Pas d'environnement virtuel détecté à ../packshot-env. On continue avec python3 global."
fi

# Vérif python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 introuvable. Installe-le (ex: 'brew install python')"
  exit 1
fi

echo "🔄 Lancement du traitement..."
python3 traitement.py "$SOURCE" || { echo "❌ Échec du traitement"; exit 1; }

echo "📁 Contenu de 'fichier-clean' après traitement:"
mkdir -p fichier-clean
ls -lah fichier-clean || true

echo "✅ Traitement terminé."
