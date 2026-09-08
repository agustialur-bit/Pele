import streamlit as st
import pandas as pd

from extraction import extract_matches, extract_match_id
from metrics import player_shooting_table, team_shooting_row, plus_minus_per_player, coaching_pearson

st.set_page_config(page_title="Rendiment de l'equip", layout="wide")

# ---------- Sidebar ----------
st.sidebar.header("Partit(s)")
match_input_raw = st.sidebar.text_area(
    "URL(s) o ID(s) de partit (un per línia)",
    help="Igual que a l'app actual: pots posar-ne un o diversos per analitzar una franja.",
)

st.sidebar.header("Llindars mínims de l'entrenador")
min_2 = st.sidebar.number_input("% tir de 2 mínim", 0, 100, 40)
min_3 = st.sidebar.number_input("% tir de 3 mínim", 0, 100, 30)
min_tl = st.sidebar.number_input("% tirs lliures mínim", 0, 100, 65)

run = st.sidebar.button("Calcula")

if "player_table" not in st.session_state:
    st.session_state.player_table = None

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
        except Exception as e:
            st.sidebar.error(f"Error carregant el partit: {e}")

tab_resum, tab_exercicis = st.tabs(["Resum", "Exercicis"])


def highlight_below(val, threshold):
    if pd.isna(val):
        return ""
    return "background-color: #f0997b; color: #4A1B0C" if val < threshold else ""


with tab_resum:
    st.subheader("Percentatges de tir")

    if st.session_state.player_table is not None:
        full_table = pd.concat(
            [st.session_state.player_table, pd.DataFrame(st.session_state.team_rows)],
            ignore_index=True,
        )

        styled = full_table.style.applymap(lambda v: highlight_below(v, min_2), subset=["%2"]) \
                                   .applymap(lambda v: highlight_below(v, min_3), subset=["%3"]) \
                                   .applymap(lambda v: highlight_below(v, min_tl), subset=["%TL"])
        st.dataframe(styled, use_container_width=True)

        st.subheader("+/- per jugadora")
        st.dataframe(st.session_state.pm_table, use_container_width=True)

        r, p = st.session_state.pearson
        st.subheader("Gestió de l'entrenador (Pearson)")
        st.metric("Correlació minuts vs +/- per minut", r if r == r else "n/a")
        if p == p:
            st.caption(f"p-valor: {p} (significatiu si < 0.05)")
        st.caption(
            "Un valor proper a +1 indica que qui més minuts juga és qui més "
            "rendiment aporta. Proper a 0 o negatiu suggereix un possible "
            "desajust entre minutatge i rendiment."
        )
    else:
        st.info("Introdueix un o més partits a la barra lateral i prem 'Calcula'.")

with tab_exercicis:
    st.subheader("Exercicis recomanats")

    if st.session_state.player_table is None:
        st.info("Calcula primer les dades a la pestanya Resum.")
    else:
        try:
            exercicis_df = pd.read_excel("data/exercicis.xlsx")
        except FileNotFoundError:
            st.warning("No s'ha trobat data/exercicis.xlsx. Afegeix el fitxer al repositori.")
            exercicis_df = pd.DataFrame(columns=["exercici", "url", "tags"])

        deficiencies = []
        full_table = pd.concat(
            [st.session_state.player_table, pd.DataFrame(st.session_state.team_rows)],
            ignore_index=True,
        )
        for _, row in full_table.iterrows():
            if row["%2"] is not None and row["%2"] < min_2:
                deficiencies.append(("tir_2", row["jugadora"]))
            if row["%3"] is not None and row["%3"] < min_3:
                deficiencies.append(("tir_3", row["jugadora"]))
            if row["%TL"] is not None and row["%TL"] < min_tl:
                deficiencies.append(("tirs_lliures", row["jugadora"]))

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
