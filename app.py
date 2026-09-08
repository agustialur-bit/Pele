import streamlit as st
import pandas as pd
import os

from extraction import extract_matches, extract_match_id
from metrics import player_shooting_table, team_shooting_row, plus_minus_per_player, coaching_pearson

APP_DIR = os.path.dirname(os.path.abspath(__file__))
EXERCICIS_PATH = os.path.join(APP_DIR, "data", "exercicis.xlsx")

st.set_page_config(page_title="Rendiment de l'equip", layout="wide")

# ---------- Sidebar ----------
st.sidebar.header("Partit(s)")
match_input_raw = st.sidebar.text_area(
    "URL(s) o ID(s) de partit (un per línia)",
    help="Pots posar-ne un o diversos per analitzar una franja.",
)

st.sidebar.header("Llindars mínims de l'entrenador")
min_2 = st.sidebar.number_input("% tir de 2 mínim", 0, 100, 40)
min_3 = st.sidebar.number_input("% tir de 3 mínim", 0, 100, 30)
min_tl = st.sidebar.number_input("% tirs lliures mínim", 0, 100, 65)

run = st.sidebar.button("Calcula")

if "player_table" not in st.session_state:
    st.session_state.player_table = None
if "team_names" not in st.session_state:
    st.session_state.team_names = {}

if run and match_input_raw.strip():
    linies = [l.strip() for l in match_input_raw.strip().split("\n") if l.strip()]
    match_ids = [extract_match_id(l) or l for l in linies]

    with st.spinner("Extraient dades..."):
        try:
            df_moves = extract_matches(match_ids)
            equips_ids = [e for e in df_moves["idEquip"].unique() if e]

            player_table = player_shooting_table(df_moves)
            team_rows = [team_shooting_row(df_moves, eid) for eid in equips_ids]
            pm_table = plus_minus_per_player(df_moves)
            r, p = coaching_pearson(pm_table)

            st.session_state.player_table = player_table
            st.session_state.team_rows = team_rows
            st.session_state.pm_table = pm_table
            st.session_state.pearson = (r, p)
            st.session_state.df_moves = df_moves
            st.session_state.equips_ids = equips_ids
            # Noms per defecte: primer equip que apareix = Local, segon = Visitant
            # (mateixa convenció que la teva app actual). Si n'hi ha més (diversos
            # rivals en partits diferents), es numeren.
            visitants_n = 0
            for i, eid in enumerate(equips_ids):
                if eid in st.session_state.team_names:
                    continue
                if i == 0:
                    st.session_state.team_names[eid] = "Equip Local"
                else:
                    visitants_n += 1
                    st.session_state.team_names[eid] = (
                        "Equip Visitant" if visitants_n == 1 else f"Equip Visitant {visitants_n}")
        except Exception as e:
            st.sidebar.error(f"Error carregant el partit: {e}")

if st.session_state.player_table is not None:
    with st.sidebar.expander("Noms dels equips"):
        for eid in st.session_state.get("equips_ids", []):
            st.session_state.team_names[eid] = st.text_input(
                f"Nom per {eid[:8]}...", value=st.session_state.team_names.get(eid, eid[:8]),
                key=f"name_{eid}")

tab_resum, tab_exercicis = st.tabs(["Resum", "Exercicis"])


def highlight_below(val, threshold):
    if pd.isna(val):
        return ""
    return "background-color: #f0997b; color: #4A1B0C" if val < threshold else ""


def style_column(styler, col, threshold):
    """Compatible amb pandas antic (Styler.applymap) i nou (Styler.map)."""
    fn = lambda v: highlight_below(v, threshold)
    if hasattr(styler, "map"):
        return styler.map(fn, subset=[col])
    return styler.applymap(fn, subset=[col])


def build_full_table():
    ft = pd.concat(
        [st.session_state.player_table, pd.DataFrame(st.session_state.team_rows)],
        ignore_index=True,
    )
    ft["Equip"] = ft["idEquip"].map(st.session_state.team_names).fillna(ft["idEquip"])
    return ft


with tab_resum:
    st.subheader("Percentatges de tir")

    if st.session_state.player_table is not None:
        full_table = build_full_table()

        equip_opcions = ["Tots"] + sorted(full_table["Equip"].unique().tolist())
        equip_sel = st.selectbox("Filtra per equip", equip_opcions, key="filtre_equip")
        taula_mostrada = full_table if equip_sel == "Tots" else full_table[full_table["Equip"] == equip_sel]
        taula_mostrada = taula_mostrada[["jugadora", "Equip", "%2", "%3", "%TL"]]

        styled = taula_mostrada.style
        for col, threshold in [("%2", min_2), ("%3", min_3), ("%TL", min_tl)]:
            styled = style_column(styled, col, threshold)
        styled = styled.format({"%2": "{:.1f}", "%3": "{:.1f}", "%TL": "{:.1f}"}, na_rep="Sense tirs")
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.subheader("+/- per jugadora")
        pm_display = st.session_state.pm_table.copy()
        pm_display["Equip"] = pm_display["idEquip"].map(st.session_state.team_names).fillna(pm_display["idEquip"])
        st.dataframe(pm_display[["jugadora", "Equip", "minuts", "+/-"]], use_container_width=True, hide_index=True)

        st.subheader("Gestió de l'entrenador (Pearson)")
        equip_pearson_opcions = sorted(pm_display["Equip"].unique().tolist())
        equip_pearson_sel = st.selectbox(
            "Equip a analitzar", equip_pearson_opcions, key="filtre_equip_pearson",
            help="El Pearson i la gràfica només tenen sentit calculats dins d'un mateix equip.")
        pm_equip = pm_display[pm_display["Equip"] == equip_pearson_sel]
        r, p = coaching_pearson(pm_equip)

        st.metric(f"Correlació minuts vs +/- per minut — {equip_pearson_sel}", r if r == r else "n/a")
        if p == p:
            st.caption(f"p-valor: {p} (significatiu si < 0.05)")
        st.caption(
            "Un valor proper a +1 indica que qui més minuts juga és qui més "
            "rendiment aporta. Proper a 0 o negatiu suggereix un possible "
            "desajust entre minutatge i rendiment."
        )

        pm_chart = pm_equip[pm_equip["minuts"] > 0].copy()
        if not pm_chart.empty:
            pm_chart["+/- per min"] = (pm_chart["+/-"] / pm_chart["minuts"]).round(3)
            st.caption(f"{equip_pearson_sel} — minuts jugats (x) vs +/- per minut (y), cada punt una jugadora.")
            st.scatter_chart(pm_chart, x="minuts", y="+/- per min")
        else:
            st.info(f"No hi ha prou minuts registrats per a {equip_pearson_sel}.")

        st.markdown("**% acumulats per equip**")
        equip_pct = full_table[full_table["jugadora"] == "EQUIP"][["Equip", "%2", "%3", "%TL"]]
        st.dataframe(
            equip_pct.style.format({"%2": "{:.1f}", "%3": "{:.1f}", "%TL": "{:.1f}"}, na_rep="Sense tirs"),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Introdueix un o més partits a la barra lateral i prem 'Calcula'.")

with tab_exercicis:
    st.subheader("Exercicis recomanats")

    if st.session_state.player_table is None:
        st.info("Calcula primer les dades a la pestanya Resum.")
    else:
        try:
            exercicis_df = pd.read_excel(EXERCICIS_PATH)
        except FileNotFoundError:
            st.warning(
                f"No s'ha trobat el fitxer a `{EXERCICIS_PATH}`. "
                "Comprova que `data/exercicis.xlsx` estigui pujat al repositori de GitHub "
                "(no dins .gitignore, i amb aquest nom exacte i majúscules/minúscules)."
            )
            pujat = st.file_uploader("O puja'l aquí temporalment", type="xlsx", key="up_exercicis")
            exercicis_df = pd.read_excel(pujat) if pujat else pd.DataFrame(columns=["exercici", "url", "tags"])

        deficiencies = []
        full_table = build_full_table()
        for _, row in full_table.iterrows():
            qui = row["Equip"] if row["jugadora"] == "EQUIP" else row["jugadora"]
            if row["%2"] is not None and row["%2"] < min_2:
                deficiencies.append(("tir_2", qui))
            if row["%3"] is not None and row["%3"] < min_3:
                deficiencies.append(("tir_3", qui))
            if row["%TL"] is not None and row["%TL"] < min_tl:
                deficiencies.append(("tirs_lliures", qui))

        if not deficiencies:
            st.success("Cap jugadora ni l'equip estan per sota dels llindars marcats.")
        else:
            for tag, qui in deficiencies:
                st.markdown(f"**{qui} — mancança: {tag.replace('_', ' ')}**")
                matches = exercicis_df[exercicis_df["tags"].str.contains(tag, na=False)]
                if matches.empty:
                    st.write("Sense exercicis etiquetats per a aquesta mancança.")
                else:
                    for _, ex in matches.iterrows():
                        st.markdown(f"- [{ex['exercici']}]({ex['url']})")
