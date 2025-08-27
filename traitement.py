
import os
import sys
import pandas as pd
from datetime import datetime

FRENCH_MONTHS = {
    "janvier": "january",
    "février": "february", "fevrier": "february",
    "mars": "march",
    "avril": "april",
    "mai": "may",
    "juin": "june",
    "juillet": "july",
    "août": "august", "aout": "august",
    "septembre": "september",
    "octobre": "october",
    "novembre": "november",
    "décembre": "december", "decembre": "december",
}

def normalize_dates_fr(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    for fr, en in FRENCH_MONTHS.items():
        s = s.str.replace(fr, en, regex=False)
    s = s.str.replace(r"\s+", " ", regex=True)
    return pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)

def prepare_from_raw(path_xlsx: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_excel(path_xlsx)
    df.columns = [c.strip() for c in df.columns]

    # Harmonise href
    if "href" not in df.columns and "Film-href" in df.columns:
        df = df.rename(columns={"Film-href": "href"})
    if "href" not in df.columns:
        raise ValueError("Colonne clé introuvable : 'href' / 'Film-href'")

    # Dates
    if "Date de sortie" not in df.columns:
        raise ValueError("Colonne 'Date de sortie' introuvable.")
    df["Date de sortie"] = normalize_dates_fr(df["Date de sortie"])
    df = df.dropna(subset=["Date de sortie"]).copy()

    # Trier par date croissante
    df = df.sort_values("Date de sortie")

    films_new = df.copy()
    campagnes_new = df.drop_duplicates(subset="href").copy()
    return campagnes_new, films_new

def incremental_merge(campagnes_new: pd.DataFrame, films_new: pd.DataFrame, outdir: str = "fichier-clean"):
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%Hh%M")

    # Fichiers cibles
    f_films = os.path.join(outdir, "films.csv")
    f_campagnes = os.path.join(outdir, "campagnes.csv")

    # Sauvegardes (roll-back possible)
    if os.path.exists(f_films):
        os.replace(f_films, os.path.join(outdir, f"films_backup_{ts}.csv"))
    if os.path.exists(f_campagnes):
        os.replace(f_campagnes, os.path.join(outdir, f"campagnes_backup_{ts}.csv"))

    # Charger existants si présents
    films_all = films_new.copy()
    campagnes_all = campagnes_new.copy()

    if os.path.exists(os.path.join(outdir, "films_backup_"+ts+".csv")):
        # Recharger l'ancien pour merger
        films_old = pd.read_csv(os.path.join(outdir, f"films_backup_{ts}.csv"))
        # Normaliser la date si besoin
        if "Date de sortie" in films_old.columns and not pd.api.types.is_datetime64_any_dtype(films_old["Date de sortie"]):
            try:
                films_old["Date de sortie"] = pd.to_datetime(films_old["Date de sortie"], errors="coerce", dayfirst=True, infer_datetime_format=True)
            except Exception:
                pass
        films_all = pd.concat([films_old, films_new], ignore_index=True)

    if os.path.exists(os.path.join(outdir, "campagnes_backup_"+ts+".csv")):
        campagnes_old = pd.read_csv(os.path.join(outdir, f"campagnes_backup_{ts}.csv"))
        campagnes_all = pd.concat([campagnes_old, campagnes_new], ignore_index=True)

    # Déduplication robuste
    # Campagnes : dédoublonner par href (garde la dernière occurrence)
    if "href" not in campagnes_all.columns:
        raise ValueError("La colonne 'href' est manquante après fusion des campagnes.")
    campagnes_all = campagnes_all.drop_duplicates(subset=["href"], keep="last")

    # Films : on utilise une clé composite robuste
    film_keys = [c for c in ["href","Client","Agence","Production","Réalisateur","Date de sortie"] if c in films_all.columns]
    if not film_keys:
        # fallback ultra-conservateur : toutes colonnes
        film_keys = list(films_all.columns)
    films_all = films_all.drop_duplicates(subset=film_keys, keep="last")

    # Tri par date
    if "Date de sortie" in films_all.columns:
        films_all = films_all.sort_values("Date de sortie")
    if "Date de sortie" in campagnes_all.columns:
        campagnes_all = campagnes_all.sort_values("Date de sortie")

    # Écritures atomiques
    films_all.to_csv(f_films, index=False)
    campagnes_all.to_csv(f_campagnes, index=False)

    # Exports datés pour archivage
    films_all.to_csv(os.path.join(outdir, f"films_{ts}.csv"), index=False)
    campagnes_all.to_csv(os.path.join(outdir, f"campagnes_{ts}.csv"), index=False)

    # Log simple
    with open(os.path.join(outdir, "traitement.log"), "a", encoding="utf-8") as lg:
        lg.write(f"[{ts}] films: {len(films_all)} lignes, campagnes: {len(campagnes_all)} lignes | clés films: {film_keys}\n")

    print("✅ Fusion incrémentale terminée.")
    print(f"   → {f_films}")
    print(f"   → {f_campagnes}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 traitement.py <chemin vers Packshot.xlsx>")
        sys.exit(1)
    campagnes_new, films_new = prepare_from_raw(sys.argv[1])
    incremental_merge(campagnes_new, films_new, outdir="fichier-clean")
