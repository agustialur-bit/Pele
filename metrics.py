"""
Càlculs sobre el DataFrame de jugades (mateix esquema que fetch_and_parse):
%2, %3, %TL per jugadora i equip, +/- via intervals reals Entra/Surt,
i el Pearson minuts-jugats vs +/--per-minut (la mateixa idea que el teu ROT,
aquí sense escalar a 0-10).
"""

import pandas as pd
from scipy.stats import pearsonr

MINS_PER_QUART = 10  # com al teu app.py (quarts de 10 minuts)

PAT_2A = "Cistella de 2|Intent fallat de 2|fallat de 2"
PAT_2M = "Cistella de 2"
PAT_3A = "Cistella de 3|Intent fallat de 3|fallat de 3"
PAT_3M = "Cistella de 3"
PAT_TLA = "Cistella de 1|Intent fallat de 1"
PAT_TLM = "Cistella de 1"


def _pct(df, pat_attempt, pat_made):
    intents = df["accio"].str.contains(pat_attempt, case=False, na=False).sum()
    encerts = df["accio"].str.contains(pat_made, case=False, na=False).sum()
    return round(100 * encerts / intents, 1) if intents else None


def player_shooting_table(df_moves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for jugadora, g in df_moves.groupby("jugador"):
        if not jugadora or str(jugadora) in ("", "nan"):
            continue
        eq_id = g["idEquip"].mode().iloc[0] if not g["idEquip"].mode().empty else ""
        rows.append({
            "jugadora": jugadora,
            "idEquip": eq_id,
            "%2": _pct(g, PAT_2A, PAT_2M),
            "%3": _pct(g, PAT_3A, PAT_3M),
            "%TL": _pct(g, PAT_TLA, PAT_TLM),
        })
    return pd.DataFrame(rows)


def team_shooting_row(df_moves: pd.DataFrame, id_equip: str) -> dict:
    g = df_moves[df_moves["idEquip"] == id_equip]
    return {"jugadora": "EQUIP", "idEquip": id_equip, "%2": _pct(g, PAT_2A, PAT_2M),
            "%3": _pct(g, PAT_3A, PAT_3M), "%TL": _pct(g, PAT_TLA, PAT_TLM)}


def _t_abs(row):
    """Converteix quart + min_num (comptador enrere dins del quart) a minut
    absolut de partit, exactament com al teu app.py."""
    q = int(row["quart"]) if row["quart"] != "" else 1
    m = float(row["min_num"])
    t = (q - 1) * MINS_PER_QUART + (MINS_PER_QUART - m if m <= MINS_PER_QUART else m)
    return max(0, min(t, q * MINS_PER_QUART))


def build_intervals(df_partit: pd.DataFrame) -> dict:
    """Retorna {jugadora: [(t_ini, t_fi, idEquip), ...]} a partir dels
    esdeveniments Entra al camp / Surt del camp, mateixa lògica que
    get_intervals_jugadores() del teu app.py.

    IMPORTANT: df_partit ha de contenir jugades d'UN SOL partit (la columna
    'num' es reinicia a cada partit, així que barrejar-los aquí donaria
    intervals sense sentit). Per diversos partits, usa build_intervals_multi.
    """
    intervals = {}
    en_pista = {}

    for jug in df_partit["jugador"].unique():
        if not jug or str(jug) in ("", "nan"):
            continue
        dj = df_partit[df_partit["jugador"] == jug].sort_values("num")
        if dj.empty:
            continue
        primer = dj.iloc[0]
        primer_acc = str(primer.get("accio", ""))
        if "Surt" in primer_acc and "camp" in primer_acc:
            en_pista[jug] = ((int(primer.get("quart", 1)) - 1) * MINS_PER_QUART,
                              str(primer.get("idEquip", "")))

    for _, row in df_partit.sort_values("num").iterrows():
        jug = row.get("jugador", "")
        if not jug or str(jug) in ("", "nan"):
            continue
        accio = str(row.get("accio", ""))
        q = int(row.get("quart", 1)) if row.get("quart", "") != "" else 1
        t = _t_abs(row)
        eq_id = str(row.get("idEquip", ""))

        if "Entra al camp" in accio:
            en_pista[jug] = (t, eq_id)
        elif "Surt del camp" in accio:
            ti, ei = en_pista.pop(jug, ((q - 1) * MINS_PER_QUART, eq_id))
            if t > ti:
                intervals.setdefault(jug, []).append((ti, t, ei))
        elif "Final de període" in accio:
            fi = q * MINS_PER_QUART
            for j, (ti, ei) in list(en_pista.items()):
                if fi > ti:
                    intervals.setdefault(j, []).append((ti, fi, ei))
            en_pista = {}

    fi_partit = df_partit["quart"].max() * MINS_PER_QUART if not df_partit.empty else 40
    for j, (ti, ei) in en_pista.items():
        if fi_partit > ti:
            intervals.setdefault(j, []).append((ti, fi_partit, ei))

    return intervals


def plus_minus_per_player(df_moves: pd.DataFrame) -> pd.DataFrame:
    """+/- i minuts jugats per jugadora, ACUMULATS de tots els partits
    carregats. Processa cada match_id per separat (num i quart es
    reinicien a cada partit) i després suma els resultats entre partits."""
    acumulat = {}  # jugadora -> {"minuts": x, "+/-": y, "eq_id": z}

    match_ids = df_moves["match_id"].unique() if "match_id" in df_moves.columns else [None]
    for mid in match_ids:
        df_partit = df_moves[df_moves["match_id"] == mid] if mid is not None else df_moves
        intervals = build_intervals(df_partit)
        df_t = df_partit.copy()
        df_t["t_abs"] = df_t.apply(_t_abs, axis=1)

        for jug, ivs in intervals.items():
            if not ivs:
                continue
            eq_id = ivs[0][2]
            rival_ids = [e for e in df_partit["idEquip"].unique() if e != eq_id]
            rival_id = rival_ids[0] if rival_ids else None

            minuts = sum(tf - ti for ti, tf, _ in ivs)
            pf = pc = 0
            for ti, tf, ei in ivs:
                finestra = df_t[(df_t["t_abs"] >= ti) & (df_t["t_abs"] <= tf)]
                pf += int(finestra[finestra["idEquip"] == ei]["punts"].sum())
                if rival_id:
                    pc += int(finestra[finestra["idEquip"] == rival_id]["punts"].sum())

            acc = acumulat.setdefault(jug, {"minuts": 0.0, "+/-": 0})
            acc["minuts"] += minuts
            acc["+/-"] += (pf - pc)

    rows = [{"jugadora": jug, "minuts": round(v["minuts"], 1), "+/-": v["+/-"]}
            for jug, v in acumulat.items()]
    return pd.DataFrame(rows)


def coaching_pearson(plus_minus_df: pd.DataFrame):
    """
    Pearson entre minuts jugats i +/- per minut de cada jugadora — la mateixa
    idea que el teu ROT index (5*(rho+1)/10), aquí retornat com a r brut.
    Retorna (r, p_valor). Cal un mínim de 3 jugadores amb minuts > 0.
    """
    df = plus_minus_df[plus_minus_df["minuts"] > 0].copy()
    if len(df) < 3:
        return (float("nan"), float("nan"))
    df["pm_per_min"] = df["+/-"] / df["minuts"]
    if df["minuts"].std() == 0 or df["pm_per_min"].std() == 0:
        return (float("nan"), float("nan"))
    r, p = pearsonr(df["minuts"], df["pm_per_min"])
    return (round(r, 3), round(p, 3))
