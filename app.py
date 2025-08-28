import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re

st.set_page_config(page_title="Analyse Packshot", layout="wide")
st.title("📺 Analyse des campagnes publicitaires TV")

DATA_DIR = "fichier-clean"

# -------------------- Helpers --------------------
@st.cache_data(show_spinner=False)
def load_clean_default():
    films_path = os.path.join(DATA_DIR, "films.csv")
    campagnes_path = os.path.join(DATA_DIR, "campagnes.csv")
    if os.path.exists(campagnes_path):
        return pd.read_csv(campagnes_path), "campagnes.csv"
    if os.path.exists(films_path):
        return pd.read_csv(films_path), "films.csv"
    return None, None

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    if "href" not in df.columns and "Film-href" in df.columns:
        df = df.rename(columns={"Film-href": "href"})
    return df

def ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    if "Date de sortie" not in df.columns:
        raise ValueError("Colonne 'Date de sortie' manquante.")
    out = pd.to_datetime(df["Date de sortie"], errors="coerce", dayfirst=True, infer_datetime_format=True)
    if out.isna().mean() > 0.5:
        months = {
            "janvier":"january","février":"february","fevrier":"february","mars":"march","avril":"april","mai":"may",
            "juin":"june","juillet":"july","août":"august","aout":"august","septembre":"september","octobre":"october",
            "novembre":"november","décembre":"december","decembre":"december"
        }
        s = df["Date de sortie"].astype(str).str.lower()
        for fr,en in months.items():
            s = s.str.replace(fr, en, regex=False)
        out = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
    df = df.copy()
    df["Date de sortie"] = out
    df = df.dropna(subset=["Date de sortie"])
    return df

def normalize_text_cols(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].astype(str).str.strip()
            out[c] = out[c].replace({"": "Inconnu", "nan": "Inconnu", "None": "Inconnu"})
    return out

# split robust pour réalisateurs multiples
SPLIT_RE = re.compile(r"\s*(?:,|/|&| x | \+ | et )\s*", flags=re.IGNORECASE)

def first_non_null(series: pd.Series):
    for v in series:
        if pd.notna(v) and str(v).strip() != "":
            return v
    return "Inconnu"

def aggregate_campaigns_from_films(df_films: pd.DataFrame) -> pd.DataFrame:
    # construit une vue Campagnes à partir d’un tableau films
    df = df_films.copy()
    for col in ["Client","Agence","Production","Réalisateur"]:
        if col not in df.columns:
            df[col] = "Inconnu"

    # Exploser réalisateurs pour récupérer l’union par href, mais garder un champ concat
    df["_Reals_list"] = (
        df["Réalisateur"].fillna("Inconnu").astype(str).apply(lambda s: [r for r in SPLIT_RE.split(s) if r] )
    )

    agg = df.sort_values("Date de sortie").groupby("href").agg({
        "Date de sortie": "min",  # première diffusion de la campagne
        "Client": first_non_null,
        "Agence": first_non_null,
        "Production": first_non_null,
        "_Reals_list": lambda lists: sorted(set(sum(lists, [])))  # union unique
    }).reset_index()

    # pour affichage lisible
    agg["Réalisateur"] = agg["_Reals_list"].apply(lambda lst: " & ".join(lst) if lst else "Inconnu")
    return agg.drop(columns=["_Reals_list"])

def detect_granularity(df: pd.DataFrame) -> str:
    # si href unique => dataset campagnes, sinon films
    if "href" in df.columns and df["href"].nunique(dropna=True) == len(df):
        return "campagnes"
    return "films"

def build_views(df_raw: pd.DataFrame):
    # normaliser colonnes + date + textes
    df = normalize_columns(df_raw)
    needed = ["href","Client","Agence","Production","Réalisateur","Date de sortie"]
    # certaines bases "campagnes" n'ont pas forcément tous les champs — on comble
    for col in needed:
        if col not in df.columns:
            if col == "href":
                raise ValueError("Colonne clé 'href' (ou 'Film-href') manquante.")
            df[col] = "Inconnu"
    df = ensure_date(df)
    df = normalize_text_cols(df, ["Client","Agence","Production","Réalisateur"])

    detected = detect_granularity(df)
    if detected == "campagnes":
        campagnes = df.copy()
        films = None
    else:
        films = df.copy()
        campagnes = aggregate_campaigns_from_films(df)

    return campagnes, films, detected

def top_df(df: pd.DataFrame, label_col: str, n: int) -> pd.DataFrame:
    s = df[label_col].value_counts().reset_index()
    s.columns = [label_col, "Nombre"]
    s.insert(0, "Rang", range(1, len(s) + 1))
    return s.head(n)

def top_director_by_campaigns(campagnes_df: pd.DataFrame, n: int) -> pd.DataFrame:
    # exploser les réalisateurs multiples pour compter 1 campagne par réal
    tmp = campagnes_df.copy()
    # créer une liste de réals
    reals_lists = tmp["Réalisateur"].fillna("Inconnu").astype(str).apply(lambda s: [r for r in SPLIT_RE.split(s) if r])
    exploded = tmp.loc[reals_lists.index.repeat(reals_lists.str.len())].copy()
    exploded["Réalisateur"] = [r for lst in reals_lists for r in lst]
    # compter par réal (chaque href apparaît une seule fois par réal)
    counts = exploded.drop_duplicates(["href","Réalisateur"])["Réalisateur"].value_counts().reset_index()
    counts.columns = ["Réalisateur","Nombre"]
    counts.insert(0, "Rang", range(1, len(counts) + 1))
    return counts.head(n)

# -------------------- Sidebar --------------------
st.sidebar.header("Paramètres")
mode_src = st.sidebar.radio("Source des données", ["Par défaut (fichier-clean)", "Uploader un fichier clean (.csv/.xlsx)"])
granularity = st.sidebar.radio("Unité de comptage", ["Campagnes (href unique)", "Films"], index=0)
top_n = st.sidebar.selectbox("Taille du TOP", [5, 10, 20, 50], index=1)

# -------------------- Chargement --------------------
df_raw = None
source_label = ""

if mode_src == "Par défaut (fichier-clean)":
    df_raw, source_label = load_clean_default()
    if df_raw is None:
        st.warning("Aucun fichier trouvé dans 'fichier-clean/'. Uploade un fichier clean ou lance le traitement.")
else:
    up = st.file_uploader("Uploader un fichier déjà clean (.csv ou .xlsx)", type=["csv","xlsx"])
    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                df_raw = pd.read_csv(up)
            else:
                df_raw = pd.read_excel(up)
            source_label = up.name
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")

if df_raw is None:
    st.stop()

try:
    campagnes_view, films_view, detected = build_views(df_raw)
except Exception as e:
    st.error(f"Erreur de préparation des données : {e}")
    st.stop()

# choisir la table de travail en fonction de la granularité souhaitée
if granularity.startswith("Campagnes"):
    df_work = campagnes_view.copy()
else:
    # si chargement d'un fichier campagnes mais on a demandé films, on ne peut pas remonter les films → on reste campagnes
    df_work = films_view if films_view is not None else campagnes_view.copy()

st.caption(f"Source: {source_label} — jeu détecté: {detected} — granularité utilisée: {'campagnes' if granularity.startswith('Campagnes') else 'films'} — {len(df_work)} lignes")

required = ["Agence","Client","Production","Réalisateur","Date de sortie","href"]
missing = [c for c in required if c not in df_work.columns]
if missing:
    st.error(f"Colonnes manquantes: {', '.join(missing)}")
    st.stop()

if df_work.empty:
    st.error("Aucune ligne exploitable après normalisation.")
    st.stop()

# -------------------- Filtre période --------------------
min_date = df_work["Date de sortie"].min()
max_date = df_work["Date de sortie"].max()
date_range = st.slider(
    "🗓️ Période",
    min_value=min_date.to_pydatetime(),
    max_value=max_date.to_pydatetime(),
    value=(min_date.to_pydatetime(), max_date.to_pydatetime())
)
mask = (df_work["Date de sortie"] >= pd.to_datetime(date_range[0])) & (df_work["Date de sortie"] <= pd.to_datetime(date_range[1]))
dfp = df_work.loc[mask].copy()
st.success(f"{len(dfp)} éléments sur la période sélectionnée.")

# -------------------- TOPS (tables, index caché) --------------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("🏆 Top clients")
    st.dataframe(top_df(dfp, "Client", top_n), use_container_width=True, hide_index=True)

    st.subheader("🏆 Top productions")
    st.dataframe(top_df(dfp, "Production", top_n), use_container_width=True, hide_index=True)

with c2:
    st.subheader("🏆 Top agences")
    st.dataframe(top_df(dfp, "Agence", top_n), use_container_width=True, hide_index=True)

    st.subheader("🏆 Top réalisateurs")
    if granularity.startswith("Campagnes"):
        st.dataframe(top_director_by_campaigns(dfp, top_n), use_container_width=True, hide_index=True)
    else:
        st.dataframe(top_df(dfp, "Réalisateur", top_n), use_container_width=True, hide_index=True)

# -------------------- Timeline (chart par défaut) --------------------
st.subheader("📈 Répartition mensuelle")
timeline = dfp.groupby(dfp["Date de sortie"].dt.to_period("M")).size().reset_index(name="Nombre")
timeline["Mois"] = timeline["Date de sortie"].dt.to_timestamp()
timeline_show = timeline[["Mois", "Nombre"]].sort_values("Mois")
fig = px.bar(timeline_show, x="Mois", y="Nombre")
st.plotly_chart(fig, use_container_width=True)
if st.checkbox("📄 Voir les données (timeline)", key="table_timeline"):
    st.dataframe(timeline_show.reset_index(drop=True), use_container_width=True, hide_index=True)

# -------------------- Analyses croisées (TOP N) --------------------
st.subheader("🔁 Analyses croisées (TOP) — tables par défaut")

tab_agence, tab_real, tab_prod, tab_client = st.tabs([
    "Agence sélectionnée", "Réalisateur sélectionné", "Production sélectionnée", "Client sélectionné"
])

def top_for_selection(sub: pd.DataFrame, col: str, n: int, count_by_campaigns_director=False):
    if count_by_campaigns_director and col == "Réalisateur":
        return top_director_by_campaigns(sub, n)
    return top_df(sub, col, n)

with tab_agence:
    ag_list = sorted(dfp["Agence"].dropna().unique())
    if ag_list:
        ag_sel = st.selectbox("Choisir une agence", ag_list, key="ag_top")
        sub = dfp[dfp["Agence"] == ag_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} productions (pour cette agence)**")
            st.dataframe(top_for_selection(sub, "Production", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} réalisateurs (pour cette agence)**")
            st.dataframe(top_for_selection(sub, "Réalisateur", top_n, count_by_campaigns_director=granularity.startswith('Campagnes')), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune agence disponible sur la période filtrée.")

with tab_real:
    r_list = sorted(dfp["Réalisateur"].dropna().unique())
    if r_list:
        r_sel = st.selectbox("Choisir un réalisateur", r_list, key="real_top")
        sub = dfp[dfp["Réalisateur"] == r_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} productions (avec ce réalisateur)**")
            st.dataframe(top_for_selection(sub, "Production", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} agences (avec ce réalisateur)**")
            st.dataframe(top_for_selection(sub, "Agence", top_n), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun réalisateur disponible sur la période filtrée.")

with tab_prod:
    p_list = sorted(dfp["Production"].dropna().unique())
    if p_list:
        p_sel = st.selectbox("Choisir une production", p_list, key="prod_top")
        sub = dfp[dfp["Production"] == p_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} agences (ayant travaillé avec cette production)**")
            st.dataframe(top_for_selection(sub, "Agence", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} réalisateurs (ayant travaillé avec cette production)**")
            st.dataframe(top_for_selection(sub, "Réalisateur", top_n, count_by_campaigns_director=granularity.startswith('Campagnes')), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune production disponible sur la période filtrée.")

with tab_client:
    c_list = sorted(dfp["Client"].dropna().unique())
    if c_list:
        c_sel = st.selectbox("Choisir un client", c_list, key="client_top")
        sub = dfp[dfp["Client"] == c_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} agences (pour ce client)**")
            st.dataframe(top_for_selection(sub, "Agence", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} productions (pour ce client)**")
            st.dataframe(top_for_selection(sub, "Production", top_n), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun client disponible sur la période filtrée.")

# -------------------- Mode comparaison (deux périodes) --------------------
st.subheader("📊 Mode comparaison (deux périodes) — choisir le Top à comparer")
col1, col2 = st.columns(2)
with col1:
    a1, a2 = st.date_input("Période A", [min_date.date(), (min_date + pd.Timedelta(days=30)).date()])
with col2:
    b1, b2 = st.date_input("Période B", [(min_date + pd.Timedelta(days=31)).date(), (min_date + pd.Timedelta(days=61)).date()])

top_choice = st.selectbox("Comparer :", ["Client", "Agence", "Production", "Réalisateur"], index=0)

dfa = df[(df["Date de sortie"] >= pd.to_datetime(a1)) & (df["Date de sortie"] <= pd.to_datetime(a2))]
dfb = df[(df["Date de sortie"] >= pd.to_datetime(b1)) & (df["Date de sortie"] <= pd.to_datetime(b2))]

# selon la granularité choisie, on doit reconstituer la vue correspondante pour A et B
def view_for_period(df_all: pd.DataFrame, start, end):
    sub = df_all[(df_all["Date de sortie"] >= pd.to_datetime(start)) & (df_all["Date de sortie"] <= pd.to_datetime(end))].copy()
    if granularity.startswith("Campagnes"):
        if detect_granularity(sub) == "films":
            return aggregate_campaigns_from_films(sub)
        return sub
    else:
        return sub

dfa_view = view_for_period(df, a1, a2)
dfb_view = view_for_period(df, b1, b2)

def compare_block(dfA, dfB, colname, label, n: int, key="cmp"):
    def clean_labels(s: pd.Series) -> pd.Series:
        s = s.astype(str).str.strip()
        s = s.replace({"": "Inconnu", "nan": "Inconnu", "None": "Inconnu"})
        return s

    if granularity.startswith("Campagnes") and colname == "Réalisateur":
        # Exploser côté campagnes pour compter 1 par href
        def explode_reals(df_in: pd.DataFrame):
            base = df_in.copy()
            lists = base["Réalisateur"].fillna("Inconnu").astype(str).apply(lambda s: [r for r in SPLIT_RE.split(s) if r])
            exploded = base.loc[lists.index.repeat(lists.str.len())].copy()
            exploded["Réalisateur"] = [r for lst in lists for r in lst]
            return exploded.drop_duplicates(["href","Réalisateur"])
        dfA_use = explode_reals(dfA)
        dfB_use = explode_reals(dfB)
    else:
        dfA_use = dfA
        dfB_use = dfB

    colA = clean_labels(dfA_use[colname].fillna("Inconnu"))
    colB = clean_labels(dfB_use[colname].fillna("Inconnu"))

    ta = colA.value_counts().reset_index()
    ta.columns = ["Nom", "Période A"]
    ta = ta.head(n)

    tb = colB.value_counts().reset_index()
    tb.columns = ["Nom", "Période B"]
    tb = tb.head(n)

    comp = ta.merge(tb, on="Nom", how="outer").fillna(0)
    comp = comp.sort_values(["Période B", "Période A"], ascending=False).reset_index(drop=True)
    comp = comp.head(n)

    comp.insert(0, "Rang", range(1, len(comp) + 1))
    comp["Δ (B-A)"] = comp["Période B"] - comp["Période A"]

    st.markdown(f"**{label} (TOP {n})**")
    st.dataframe(comp, use_container_width=True, hide_index=True)

label_map = {"Client": "Top clients", "Agence": "Top agences", "Production": "Top productions", "Réalisateur": "Top réalisateurs"}
compare_block(dfa_view, dfb_view, top_choice, label_map[top_choice], n=top_n, key=f"cmp_{top_choice}")