import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Analyse Packshot", layout="wide")
st.title("📺 Analyse des campagnes publicitaires TV")

DATA_DIR = "fichier-clean"

# -------------------- Helpers --------------------
@st.cache_data(show_spinner=False)
def load_clean_default():
    films_path = os.path.join(DATA_DIR, "films.csv")
    campagnes_path = os.path.join(DATA_DIR, "campagnes.csv")
    if os.path.exists(films_path):
        return pd.read_csv(films_path), "films.csv"
    if os.path.exists(campagnes_path):
        return pd.read_csv(campagnes_path), "campagnes.csv"
    return None, None

def ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    if "Date de sortie" not in df.columns:
        raise ValueError("Colonne 'Date de sortie' manquante.")
    out = pd.to_datetime(df["Date de sortie"], errors="coerce", dayfirst=True, infer_datetime_format=True)
    # Conversion FR → EN si beaucoup de NaT
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

def top_df(df: pd.DataFrame, col: str, n: int) -> pd.DataFrame:
    # Produit un tableau avec une vraie colonne "Rang" (1..N) + "Nombre"
    s = df[col].value_counts().reset_index()
    s.columns = [col, "Nombre"]
    s.insert(0, "Rang", range(1, len(s) + 1))
    return s.head(n)

# -------------------- Sidebar --------------------
st.sidebar.header("Paramètres")
mode = st.sidebar.radio("Source des données", ["Par défaut (fichier-clean)", "Uploader un fichier clean (.csv/.xlsx)"])
top_n = st.sidebar.selectbox("Taille du TOP", [5, 10, 20, 50], index=1)

# -------------------- Chargement --------------------
df = None
source_label = ""

if mode == "Par défaut (fichier-clean)":
    df, source_label = load_clean_default()
    if df is None:
        st.warning("Aucun fichier trouvé dans 'fichier-clean/'. Uploade un fichier clean ou lance le traitement.")
else:
    up = st.file_uploader("Uploader un fichier déjà clean (.csv ou .xlsx)", type=["csv","xlsx"])
    if up is not None:
        try:
            name = up.name.lower()
            if name.endswith(".csv"):
                df = pd.read_csv(up)
            elif name.endswith(".xlsx"):
                df = pd.read_excel(up)
            else:
                st.error("Format non supporté. Utilise .csv ou .xlsx.")
            source_label = up.name
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")

if df is None:
    st.stop()

required = ["Agence","Client","Production","Réalisateur","Date de sortie"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes: {', '.join(missing)}")
    st.stop()

df = ensure_date(df)
if df.empty:
    st.error("Aucune date valide détectée après conversion.")
    st.stop()

# Normaliser les colonnes texte
df = normalize_text_cols(df, ["Client","Agence","Production","Réalisateur"])

st.caption(f"Source: {source_label} — {len(df)} lignes après nettoyage — TOP {top_n}")

# -------------------- Filtre période --------------------
min_date = df["Date de sortie"].min()
max_date = df["Date de sortie"].max()
date_range = st.slider(
    "🗓️ Période",
    min_value=min_date.to_pydatetime(),
    max_value=max_date.to_pydatetime(),
    value=(min_date.to_pydatetime(), max_date.to_pydatetime())
)
mask = (df["Date de sortie"] >= pd.to_datetime(date_range[0])) & (df["Date de sortie"] <= pd.to_datetime(date_range[1]))
dfp = df.loc[mask].copy()
st.success(f"{len(dfp)} éléments sur la période sélectionnée.")

# -------------------- TOPS (tables par défaut, index masqué) --------------------
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
    st.dataframe(top_df(dfp, "Réalisateur", top_n), use_container_width=True, hide_index=True)

# -------------------- Timeline (chart par défaut, table en option) --------------------
st.subheader("📈 Répartition mensuelle")
timeline = dfp.groupby(dfp["Date de sortie"].dt.to_period("M")).size().reset_index(name="Nombre")
timeline["Mois"] = timeline["Date de sortie"].dt.to_timestamp()
timeline_show = timeline[["Mois", "Nombre"]].sort_values("Mois")

fig = px.bar(timeline_show, x="Mois", y="Nombre")
st.plotly_chart(fig, use_container_width=True)
if st.checkbox("📄 Voir les données (timeline)", key="table_timeline"):
    # On peut garder un index caché aussi ici
    st.dataframe(timeline_show.reset_index(drop=True), use_container_width=True, hide_index=True)

# -------------------- Analyses croisées (TOP N) --------------------
st.subheader("🔁 Analyses croisées (TOP) — tables par défaut")

tab_agence, tab_real, tab_prod, tab_client = st.tabs([
    "Agence sélectionnée", "Réalisateur sélectionné", "Production sélectionnée", "Client sélectionné"
])

with tab_agence:
    ag_list = sorted(dfp["Agence"].dropna().unique())
    if ag_list:
        ag_sel = st.selectbox("Choisir une agence", ag_list, key="ag_top")
        sub = dfp[dfp["Agence"] == ag_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} productions (pour cette agence)**")
            st.dataframe(top_df(sub, "Production", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} réalisateurs (pour cette agence)**")
            st.dataframe(top_df(sub, "Réalisateur", top_n), use_container_width=True, hide_index=True)
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
            st.dataframe(top_df(sub, "Production", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} agences (avec ce réalisateur)**")
            st.dataframe(top_df(sub, "Agence", top_n), use_container_width=True, hide_index=True)
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
            st.dataframe(top_df(sub, "Agence", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} réalisateurs (ayant travaillé avec cette production)**")
            st.dataframe(top_df(sub, "Réalisateur", top_n), use_container_width=True, hide_index=True)
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
            st.dataframe(top_df(sub, "Agence", top_n), use_container_width=True, hide_index=True)
        with colB:
            st.markdown(f"**Top {top_n} productions (pour ce client)**")
            st.dataframe(top_df(sub, "Production", top_n), use_container_width=True, hide_index=True)
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

def compare_block(dfA, dfB, colname, label, n: int, key="cmp"):
    def clean_labels(s: pd.Series) -> pd.Series:
        s = s.astype(str).str.strip()
        s = s.replace({"": "Inconnu", "nan": "Inconnu", "None": "Inconnu"})
        return s

    colA = clean_labels(dfA[colname].fillna("Inconnu"))
    colB = clean_labels(dfB[colname].fillna("Inconnu"))

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
compare_block(dfa, dfb, top_choice, label_map[top_choice], n=top_n, key=f"cmp_{top_choice}")