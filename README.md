# Rendiment de l'equip

App de Streamlit per avaluar el rendiment de l'equip i de cada jugadora a
partir de dades de la FCBQ, i recomanar exercicis quan es cau per sota dels
llindars marcats per l'entrenador.

## Estructura

- `extraction.py` — extracció de dades del partit (mateixa API que Micki Analítica)
- `metrics.py` — càlcul de %2, %3, %TL, +/- i Pearson (minuts vs +/- per minut)
- `app.py` — interfície Streamlit (sidebar, taula amb marcatge, pestanya d'exercicis)
- `data/exercicis.xlsx` — biblioteca d'exercicis (edita aquest fitxer per afegir-ne)

## ⚠️ Abans d'executar

Els mòduls `extraction.py` i `metrics.py` tenen comentaris `TODO` on he hagut
d'endevinar noms de camps del JSON de la FCBQ (jugada, tipus_tir, equip_anotador...)
perquè no tinc accés al teu codi exacte de Micki Analítica. Verifica'ls contra
la teva extracció actual, o millor encara, substitueix `fetch_match_raw` i
`parse_match_moves` per una crida directa a les teves funcions ja existents.

## Posar-ho en un repositori nou de GitHub

Des d'aquesta carpeta:

```bash
git init
git add .
git commit -m "Primera versió: app de rendiment i exercicis"
git branch -M main
git remote add origin https://github.com/<el-teu-usuari>/manresa-metrics.git
git push -u origin main
```

Si encara no has creat el repositori a GitHub, fes-ho primer a
github.com/new (nom suggerit: `manresa-metrics`, pot ser privat).

## Desplegar a Streamlit Cloud

1. Vés a share.streamlit.io i connecta el repositori.
2. Branch: `main`, arxiu principal: `app.py`.
3. Recorda tornar a pujar `data/exercicis.xlsx` actualitzat quan afegeixis exercicis nous.

## Ús

1. Introdueix la URL o l'ID d'un partit, o diversos (un per línia), a la barra lateral. Els percentatges de tir, el +/- i el Pearson s'acumulen automàticament de tots els partits carregats.
2. Ajusta els llindars mínims de %2, %3 i %TL.
3. Prem "Calcula".
4. A "Resum" veuràs les cel·les en vermell per sota del llindar i el Pearson
   de gestió de minuts. A "Exercicis" veuràs els exercicis recomanats per a
   cada mancança detectada.
