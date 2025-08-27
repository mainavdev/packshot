#!/bin/zsh
set -e
cd ~/Desktop/campagnes-packshot 2>/dev/null || { echo "❌ Dossier ~/Desktop/campagnes-packshot introuvable"; exit 1; }
source ../packshot-env/bin/activate 2>/dev/null || true
python3 traitement.py ~/Desktop/Packshot.xlsx
echo "✅ Terminé. Fichiers mis à jour dans fichier-clean/"
