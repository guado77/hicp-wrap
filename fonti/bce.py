"""
Lettore BCE Data Portal (data-api.ecb.europa.eu, formato csvdata).

Verificato nella fase 1 (30/9/2026):
- dataflow ICP (vecchia classificazione): si FERMA a dicembre 2025. Contiene per l'area euro
  medie troncate 5..50% (TRIMxx), mediana ponderata (WGTMED), Supercore metodo 2018 (SPRXEF),
  PCCI, e 13 serie destagionalizzate (ADJUSTMENT=Y). Per i paesi nessuna serie destagionalizzata.
- dataflow HICP (nuova classificazione): esiste ma la sua chiave non e' ancora nota ->
  scopri_hicp() la cerca da solo; se risponde, le sue serie sostituiscono quelle ICP.
- salari: EWT (wage tracker, anche previsivo) e INW (salari negoziali), variazioni annue.
"""
import csv
import io

import pandas as pd

from .comune import get

BASE = "https://data-api.ecb.europa.eu/service/data"

# voce BCE -> misura in archivio (tassi annui %)
SOTTOSTANTI = {"TRIM10": "bce_troncata10", "TRIM25": "bce_troncata25", "TRIM30": "bce_troncata30",
               "TRIM50": "bce_troncata50", "WGTMED": "bce_mediana", "SPRXEF": "bce_supercore_2018",
               "PCCI00": "bce_pcci", "PCCXEF": "bce_pcci_core"}
# voce BCE -> misura destagionalizzata
DESTAG = {"000000": "hicp_headline", "XEF000": "hicp_core", "XE0000": "hicp_ex_energia",
          "GOODS0": "hicp_beni", "SERV00": "hicp_servizi", "FOOD00": "hicp_alimentari", "NRGY00": "hicp_energia"}
SALARI = {
    "EWT/Q.U2.N.WT.INWS._T.4F0.GY": "bce_wage_tracker",
    "EWT/Q.U2.N.WT.INWX._T.4F0.GY": "bce_wage_tracker_senza_una_tantum",
    "INW/Q.U2.N.INWR.000000.4F0.GY.IX": "bce_salari_negoziali",
}


def _csv(chiave, **par):
    x = get(f"{BASE}/{chiave}", params={"format": "csvdata", **par}, timeout=180)
    return list(csv.DictReader(io.StringIO(x.text)))


def scopri_hicp(log=print):
    """Trova la struttura della chiave del dataflow HICP provando il numero di dimensioni."""
    for n in range(3, 10):
        chiave = "HICP/M.U2" + "." * n
        try:
            righe = _csv(chiave, lastNObservations=1)
            if righe:
                log(f"[bce] dataflow HICP: chiave con {n + 2} dimensioni, {len(righe)} serie area euro")
                return righe
        except Exception:  # noqa: BLE001
            continue
    log("[bce] dataflow HICP: struttura non trovata, si usa ICP (fino a dic 2025)")
    return []


def _serie_lunghe(chiavi, log):
    out = {}
    for k in chiavi:
        try:
            out[k] = _csv(k, startPeriod="2000-01")
        except Exception as e:  # noqa: BLE001
            log(f"[bce] {k}: {e}")
    return out


def scarica(log=print):
    serie, salari = [], []
    # 1) ICP: storia delle misure sottostanti (fino a dic 2025)
    chiavi = {f"ICP/M.U2.N.{v}.3.{'3MM' if v.startswith('PCC') else 'ANR'}": m for v, m in SOTTOSTANTI.items()}
    for k, righe in _serie_lunghe(chiavi, log).items():
        for r in righe:
            if r.get("OBS_VALUE"):
                serie.append(("EA", chiavi[k], 0, r["TIME_PERIOD"], float(r["OBS_VALUE"]), f"BCE {k}"))
    # 2) HICP nuova classificazione: se la chiave si trova, prende sottostanti e destagionalizzate
    elenco = scopri_hicp(log)
    if elenco:
        campo_voce = next((c for c in elenco[0] if c.upper() in ("ICP_ITEM", "HICP_ITEM", "ITEM")), None)
        scelte = {}
        for r in elenco:
            voce = r.get(campo_voce, "") if campo_voce else ""
            tit = (r.get("TITLE") or "").lower()
            adj = r.get("ADJUSTMENT", "N")
            if voce in SOTTOSTANTI and ("anr" in r["KEY"].lower() or "3mm" in r["KEY"].lower()):
                scelte[r["KEY"]] = SOTTOSTANTI[voce]
            elif adj in ("Y", "S") and voce in DESTAG and "inx" in r["KEY"].lower():
                scelte[r["KEY"]] = ("SA", DESTAG[voce])
            elif "domestic inflation" in tit or "low import" in tit:
                scelte[r["KEY"]] = "bce_domestica"
        log(f"[bce] HICP: {len(scelte)} serie utili")
        for k, righe in _serie_lunghe({k.replace(".", "/", 1): v for k, v in scelte.items()}, log).items():
            dest = scelte[k.replace("/", ".", 1)]
            sa, mis = (1, dest[1]) if isinstance(dest, tuple) else (0, dest)
            for r in righe:
                if r.get("OBS_VALUE"):
                    serie.append(("EA", mis, sa, r["TIME_PERIOD"], float(r["OBS_VALUE"]), f"BCE {k}"))
    # 3) salari
    for k, mis in SALARI.items():
        try:
            for r in _csv(k, startPeriod="2015-Q1"):
                if r.get("OBS_VALUE"):
                    salari.append(("EA", mis, "Q", r["TIME_PERIOD"].replace("-", ""), float(r["OBS_VALUE"]),
                                   "yoy", f"BCE {k}"))
        except Exception as e:  # noqa: BLE001
            log(f"[bce] salari {k}: {e}")
    df = pd.DataFrame(serie, columns=["area", "misura", "sa", "data", "valore", "fonte"])
    # la stessa misura puo' arrivare da ICP e da HICP: tiene l'ultima scritta (HICP) per ogni mese
    df = df.drop_duplicates(subset=["area", "misura", "sa", "data"], keep="last")
    log(f"[bce] serie {df['misura'].nunique() if not df.empty else 0}, salari {len(salari)} osservazioni")
    return df, pd.DataFrame(salari, columns=["area", "misura", "freq", "periodo", "valore", "tipo", "fonte"])
