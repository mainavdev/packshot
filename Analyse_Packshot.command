#!/bin/zsh
cd ~/Desktop/campagnes-packshot
source ../packshot-env/bin/activate 2>/dev/null || true
streamlit run app.py
