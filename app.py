
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
    # si beaucoup de NaT, tenter conversion FR -> EN
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

def top_df(df: pd.DataFrame, col: str, n: int) -> pd.DataFrame:
    s = df[col].value_counts().head(n).reset_index()
    s.index = s.index + 1  # Démarre à 1
    s.index.name = "Rang"
    s = s.rename(columns={"index": col, col: "Nombre"})
    return s

# -------------------- Sidebar: source + TOP size --------------------
st.sidebar.header("Paramètres")
mode = st.sidebar.radio("Source des données", ["Par défaut (fichier-clean)", "Uploader un fichier clean (.csv/.xlsx)"])
top_n = st.sidebar.selectbox("Taille du TOP", [5, 10, 20, 50], index=1)

# -------------------- Chargement des données --------------------
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

st.caption(f"Source: {source_label} — {len(df)} lignes après nettoyage — TOP {top_n}")

# -------------------- Filtre de période --------------------
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

# -------------------- TOPS (tables par défaut) --------------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("🏆 Top clients")
    top_clients = top_df(dfp, "Client", top_n)
    st.dataframe(top_clients, use_container_width=True)
    if st.checkbox("📊 Voir le graphique (clients)", key="chart_clients"):
        st.bar_chart(top_clients.set_index(top_clients.columns[0])["Nombre"])

    st.subheader("🏆 Top productions")
    top_prods = top_df(dfp, "Production", top_n)
    st.dataframe(top_prods, use_container_width=True)
    if st.checkbox("📊 Voir le graphique (productions)", key="chart_prods"):
        st.bar_chart(top_prods.set_index(top_prods.columns[0])["Nombre"])

with c2:
    st.subheader("🏆 Top agences")
    top_ag = top_df(dfp, "Agence", top_n)
    st.dataframe(top_ag, use_container_width=True)
    if st.checkbox("📊 Voir le graphique (agences)", key="chart_agences"):
        st.bar_chart(top_ag.set_index(top_ag.columns[0])["Nombre"])

    st.subheader("🏆 Top réalisateurs")
    top_real = top_df(dfp, "Réalisateur", top_n)
    st.dataframe(top_real, use_container_width=True)
    if st.checkbox("📊 Voir le graphique (réalisateurs)", key="chart_reals"):
        st.bar_chart(top_real.set_index(top_real.columns[0])["Nombre"])

# -------------------- Timeline (chart par défaut, table en option) --------------------
st.subheader("📈 Répartition mensuelle")
timeline = dfp.groupby(dfp["Date de sortie"].dt.to_period("M")).size().reset_index(name="Nombre")
timeline["Mois"] = timeline["Date de sortie"].dt.to_timestamp()
timeline_show = timeline[["Mois", "Nombre"]].sort_values("Mois")

fig = px.bar(timeline_show, x="Mois", y="Nombre")
st.plotly_chart(fig, use_container_width=True)
if st.checkbox("📄 Voir les données (timeline)", key="table_timeline"):
    tshow = timeline_show.copy()
    tshow.index = tshow.index + 1
    tshow.index.name = "Rang"
    st.dataframe(tshow, use_container_width=True)

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
            p = top_df(sub, "Production", top_n)
            st.dataframe(p, use_container_width=True)
            if st.checkbox("📊 Graphique (prod pour agence)", key="chart_ag_prod"):
                st.bar_chart(p.set_index(p.columns[0])["Nombre"])
        with colB:
            st.markdown(f"**Top {top_n} réalisateurs (pour cette agence)**")
            r = top_df(sub, "Réalisateur", top_n)
            st.dataframe(r, use_container_width=True)
            if st.checkbox("📊 Graphique (réals pour agence)", key="chart_ag_real"):
                st.bar_chart(r.set_index(r.columns[0])["Nombre"])

with tab_real:
    r_list = sorted(dfp["Réalisateur"].dropna().unique())
    if r_list:
        r_sel = st.selectbox("Choisir un réalisateur", r_list, key="real_top")
        sub = dfp[dfp["Réalisateur"] == r_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} productions (avec ce réalisateur)**")
            p = top_df(sub, "Production", top_n)
            st.dataframe(p, use_container_width=True)
            if st.checkbox("📊 Graphique (prod pour réal)", key="chart_real_prod"):
                st.bar_chart(p.set_index(p.columns[0])["Nombre"])
        with colB:
            st.markdown(f"**Top {top_n} agences (avec ce réalisateur)**")
            a = top_df(sub, "Agence", top_n)
            st.dataframe(a, use_container_width=True)
            if st.checkbox("📊 Graphique (agences pour réal)", key="chart_real_ag"):
                st.bar_chart(a.set_index(a.columns[0])["Nombre"])

with tab_prod:
    p_list = sorted(dfp["Production"].dropna().unique())
    if p_list:
        p_sel = st.selectbox("Choisir une production", p_list, key="prod_top")
        sub = dfp[dfp["Production"] == p_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} agences (ayant travaillé avec cette production)**")
            a = top_df(sub, "Agence", top_n)
            st.dataframe(a, use_container_width=True)
            if st.checkbox("📊 Graphique (agences pour prod)", key="chart_prod_ag"):
                st.bar_chart(a.set_index(a.columns[0])["Nombre"])
        with colB:
            st.markdown(f"**Top {top_n} réalisateurs (ayant travaillé avec cette production)**")
            r = top_df(sub, "Réalisateur", top_n)
            st.dataframe(r, use_container_width=True)
            if st.checkbox("📊 Graphique (réals pour prod)", key="chart_prod_real"):
                st.bar_chart(r.set_index(r.columns[0])["Nombre"])

with tab_client:
    c_list = sorted(dfp["Client"].dropna().unique())
    if c_list:
        c_sel = st.selectbox("Choisir un client", c_list, key="client_top")
        sub = dfp[dfp["Client"] == c_sel]
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**Top {top_n} agences (pour ce client)**")
            a = top_df(sub, "Agence", top_n)
            st.dataframe(a, use_container_width=True)
            if st.checkbox("📊 Graphique (agences pour client)", key="chart_client_ag"):
                st.bar_chart(a.set_index(a.columns[0])["Nombre"])
        with colB:
            st.markdown(f"**Top {top_n} productions (pour ce client)**")
            p = top_df(sub, "Production", top_n)
            st.dataframe(p, use_container_width=True)
            if st.checkbox("📊 Graphique (productions pour client)", key="chart_client_prod"):
                st.bar_chart(p.set_index(p.columns[0])["Nombre"])

# -------------------- Mode comparaison --------------------
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
    ta = dfA[colname].value_counts().head(n).rename("Période A")
    tb = dfB[colname].value_counts().head(n).rename("Période B")
    comp = pd.concat([ta, tb], axis=1).fillna(0).astype(int)
    comp.index = range(1, len(comp) + 1)  # Rang à partir de 1
    comp.index.name = "Rang"
    comp["Δ (B-A)"] = comp["Période B"] - comp["Période A"]
    st.markdown(f"**{label} (TOP {n})**")
    st.dataframe(comp, use_container_width=True)
    if st.checkbox("📊 Voir le graphique", key=f"{key}_chart"):
        st.bar_chart(comp[["Période A", "Période B"]])

label_map = {"Client": "Top clients", "Agence": "Top agences", "Production": "Top productions", "Réalisateur": "Top réalisateurs"}
compare_block(dfa, dfb, top_choice, label_map[top_choice], n=top_n, key=f"cmp_{top_choice}")