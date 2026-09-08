"""
Extracció de dades de partit — còpia fidel de la lògica de fetch_and_parse()
del teu app.py actual (multi-URL/referer fallback + detecció dinàmica de camps).
"""

import urllib.request
import json
import re
import pandas as pd

API_BASE = "https://msstats.optimalwayconsulting.com/v1/fcbq/getJsonWithMatchMoves/{match_id}?currentSeason=true"


def extract_match_id(text: str):
    m = re.search(r"/([a-f0-9]{24})(?:\?|$)", text)
    if m:
        return m.group(1)
    if re.match(r"^[a-f0-9]{24}$", text.strip()):
        return text.strip()
    return None


def fetch_and_parse(match_id: str) -> pd.DataFrame:
    urls_a_provar = [
        API_BASE.format(match_id=match_id),
        API_BASE.format(match_id=match_id).replace("currentSeason=true", "currentSeason=false"),
        f"https://msstats.optimalwayconsulting.com/v1/fcbq/getJsonWithMatchMoves/{match_id}",
    ]
    referers = [
        f"https://www.basquetcatala.cat/competicions-anteriors/resultat/estadistiques/2025/{match_id}",
        f"https://www.basquetcatala.cat/estadistiques/2025/{match_id}",
        f"https://www.basquetcatala.cat/estadistiques/2024/{match_id}",
        "https://www.basquetcatala.cat/",
    ]
    data = None
    for url in urls_a_provar:
        for referer in referers:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0", "Accept": "application/json",
                    "Referer": referer})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                if data:
                    break
            except Exception:
                continue
        if data:
            break
    if not data:
        raise Exception("No s'ha pogut obtenir dades de l'API")

    if isinstance(data, list):
        data = {"moves": data}
    raw = data.get("moves") or data.get("matchMoves") or data.get("playByPlay") or []
    if not raw:
        for v in data.values():
            if isinstance(v, list) and len(v) > 3:
                raw = v
                break

    camp_equip, camp_jugador, camp_accio = "idTeam", "actorName", "move"
    camp_dorsal, camp_score, camp_period = "actorShirtNumber", "score", "period"
    if raw and isinstance(raw[0], dict):
        primer = raw[0]
        for c in ["idTeam", "teamId", "id_team", "idEquip", "equipId", "team_id", "idequip"]:
            if c in primer:
                camp_equip = c; break
        for c in ["actorName", "playerName", "jugador", "actor_name", "name", "player"]:
            if c in primer:
                camp_jugador = c; break
        for c in ["move", "action", "accio", "moveText", "actionText", "description"]:
            if c in primer:
                camp_accio = c; break
        for c in ["actorShirtNumber", "shirtNumber", "dorsal", "shirt_number", "number"]:
            if c in primer:
                camp_dorsal = c; break
        for c in ["score", "marcador", "scoreText", "currentScore"]:
            if c in primer:
                camp_score = c; break
        for c in ["period", "quart", "quarter", "cuarto"]:
            if c in primer:
                camp_period = c; break

    rows = []
    for i, play in enumerate(raw):
        if not isinstance(play, dict):
            continue
        mn, sc = play.get("min", ""), play.get("sec", "")
        temps = f"{int(mn):02d}:{int(sc):02d}" if mn != "" and sc != "" else str(mn)
        move = play.get(camp_accio, "")
        punts = 3 if "Cistella de 3" in move else (
            2 if "Cistella de 2" in move else (
                1 if ("Cistella de 1" in move or "Tir lliure convertit" in move) else 0))
        rows.append({
            "num": i + 1, "quart": play.get(camp_period, ""), "temps": temps,
            "min_num": float(mn) + float(sc) / 60 if mn != "" else 0,
            "idEquip": str(play.get(camp_equip, "")), "dorsal": play.get(camp_dorsal, ""),
            "jugador": play.get(camp_jugador, ""), "accio": move,
            "marcador": play.get(camp_score, ""), "punts": punts,
        })
    return pd.DataFrame(rows)


def _keep_real_teams(df_partit: pd.DataFrame) -> pd.DataFrame:
    """Alguns esdeveniments del play-by-play (inici/fi de període, salts,
    incidències) poden portar un idEquip que no és cap dels dos equips reals
    del partit. Ens quedem només amb els dos idEquip amb més jugades —
    els altres (equips 'fantasma' sense tirs de veritat) es descarten."""
    if df_partit.empty:
        return df_partit
    ids_reals = df_partit["idEquip"].value_counts().head(2).index.tolist()
    return df_partit[df_partit["idEquip"].isin(ids_reals)]


def extract_matches(match_ids: list) -> pd.DataFrame:
    """Extreu i concatena diversos partits (per finestres de N jornades)."""
    frames = []
    for mid in match_ids:
        df = fetch_and_parse(mid)
        df["match_id"] = mid
        df = _keep_real_teams(df)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
