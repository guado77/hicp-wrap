"""
Lettore Eurostat (API statistics 1.0, JSON-stat), classificazione ECOICOP v2.

Codici verificati nella fase 1 (30/9/2026):
- prc_hicp_minr  indici mensili, dimensione coicop18, unita' I25 (2025=100), storia dal 1996
- prc_hicp_iw    pesi per voce, per mille, annuali
- aggregati speciali: TOTAL, TOT_X_NRG_FOOD, TOT_X_NRG, GD, SERV, FOOD, NRG; trasporti = CP07
- voci elementari: classi a 4 cifre 'CPdddd' -> codice interno a 6 cifre 'dddd00'
  (stesso formato della tabella BCE: CP0411 <-> 041100)
- salari: namq_10_a10 (D1, redditi da lavoro dipendente) / namq_10_a10_e (SAL_DC, dipendenti)
"""
import pandas as pd

from .comune import a_blocchi, get, jsonstat_righe

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
GEO = {"EA": ["EA", "EA21", "EA20"], "IT": ["IT"], "DE": ["DE"], "FR": ["FR"], "ES": ["ES"]}
GEO_CN = {"EA": ["EA20", "EA", "EA21"], "IT": ["IT"], "DE": ["DE"], "FR": ["FR"], "ES": ["ES"]}

AGGREGATI = {
    "TOTAL": "hicp_headline", "TOT_X_NRG_FOOD": "hicp_core", "TOT_X_NRG": "hicp_ex_energia",
    "GD": "hicp_beni", "SERV": "hicp_servizi", "FOOD": "hicp_alimentari", "NRG": "hicp_energia",
    "CP07": "hicp_trasporti",
}
DAL = "2000-01"


def _dati(dataset, params):
    x = get(f"{BASE}/{dataset}", params=params, timeout=180)
    return list(jsonstat_righe(x.json()))


def _con_geo(area, dataset, params, geo_lista=GEO):
    ultimo = None
    for g in geo_lista[area]:
        try:
            righe = _dati(dataset, params + [("geo", g)])
            if righe:
                return g, righe
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise RuntimeError(f"{dataset} {area}: nessun codice geo ha risposto ({ultimo})")


def classi_disponibili(area):
    """Elenco dei codici coicop18 a 4 cifre (classi) presenti per l'area."""
    geo, righe = _con_geo(area, "prc_hicp_minr", [("unit", "I25"), ("lastTimePeriod", "1")])
    return geo, sorted({r["coicop18"] for r in righe if r["coicop18"].startswith("CP") and len(r["coicop18"]) == 6})


def voce_interna(cod):
    return cod[2:6] + "00"


def aggregati(area):
    geo, righe = _con_geo(area, "prc_hicp_minr",
                          [("unit", "I25"), ("sinceTimePeriod", DAL)] + [("coicop18", c) for c in AGGREGATI])
    out = [(area, AGGREGATI[r["coicop18"]], 0, r["time"], r["valore"], f"Eurostat prc_hicp_minr {geo}")
           for r in righe if r["coicop18"] in AGGREGATI]
    return pd.DataFrame(out, columns=["area", "misura", "sa", "data", "valore", "fonte"])


def voci(area, classi):
    out = []
    for blocco in a_blocchi(classi, 60):
        geo, righe = _con_geo(area, "prc_hicp_minr",
                              [("unit", "I25"), ("sinceTimePeriod", DAL)] + [("coicop18", c) for c in blocco])
        out += [(area, voce_interna(r["coicop18"]), r["time"], r["valore"]) for r in righe]
    return pd.DataFrame(out, columns=["area", "voce", "data", "indice"])


def pesi(area, classi):
    out = []
    for blocco in a_blocchi(classi, 60):
        geo, righe = _con_geo(area, "prc_hicp_iw",
                              [("sinceTimePeriod", "2000")] + [("coicop18", c) for c in blocco])
        out += [(area, int(str(r["time"])[:4]), voce_interna(r["coicop18"]), r["valore"]) for r in righe]
    return pd.DataFrame(out, columns=["area", "anno", "voce", "peso"])


def salari(area):
    """Redditi da lavoro dipendente per dipendente, trimestrale (livello). Si prova la correzione
    stagionale e di calendario, poi le altre: non tutti i paesi pubblicano la stessa."""
    d1 = dip = None
    for adj in ["SCA", "SA", "CA", "NSA"]:
        try:
            _, d1 = _con_geo(area, "namq_10_a10", [("unit", "CP_MEUR"), ("s_adj", adj), ("nace_r2", "TOTAL"),
                                                   ("na_item", "D1"), ("sinceTimePeriod", "2000-Q1")], GEO_CN)
            _, dip = _con_geo(area, "namq_10_a10_e", [("unit", "THS_PER"), ("s_adj", adj), ("nace_r2", "TOTAL"),
                                                      ("na_item", "SAL_DC"), ("sinceTimePeriod", "2000-Q1")], GEO_CN)
            break
        except Exception:  # noqa: BLE001
            d1 = dip = None
    if not d1 or not dip:
        raise RuntimeError("nessuna correzione stagionale disponibile")
    a = {r["time"]: r["valore"] for r in d1}
    b = {r["time"]: r["valore"] for r in dip}
    out = [(area, "compensation_per_employee", "Q", t.replace("-", ""), a[t] / b[t] * 1000, "livello",
            "Eurostat namq_10_a10 D1 / namq_10_a10_e SAL_DC")
           for t in sorted(a) if t in b and b[t]]
    return pd.DataFrame(out, columns=["area", "misura", "freq", "periodo", "valore", "tipo", "fonte"])


def scarica_tutto(aree, log=print):
    serie, vv, pp, ss = [], [], [], []
    for area in aree:
        try:
            geo, classi = classi_disponibili(area)
            log(f"[eurostat] {area} ({geo}): {len(classi)} classi a 4 cifre")
            serie.append(aggregati(area))
            vv.append(voci(area, classi))
            pp.append(pesi(area, classi))
            log(f"[eurostat] {area}: aggregati {len(serie[-1])} righe, voci {len(vv[-1])}, pesi {len(pp[-1])}")
        except Exception as e:  # noqa: BLE001
            log(f"[eurostat] {area}: ERRORE {type(e).__name__}: {e}")
        try:
            ss.append(salari(area))
            log(f"[eurostat] {area}: salari {len(ss[-1])} trimestri")
        except Exception as e:  # noqa: BLE001
            log(f"[eurostat] {area}: salari non disponibili ({e})")
    cat = lambda xs: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame()  # noqa: E731
    return cat(serie), cat(vv), cat(pp), cat(ss)
