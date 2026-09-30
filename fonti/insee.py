"""
Lettore INSEE (BDM SDMX, api.insee.fr/series/BDM, senza chiave).

Verificato nella fase 1b (30/9/2026):
- IPCH base 2025, ensemble, mensile: idbank 011812231 (contiene gia' il provvisorio del mese)
- salari: indice dei salari mensili di base, ensemble, trimestrale: idbank 010562695 (T2 2017 = 100)
- IPC-2025 (CPI nazionale): la risposta completa e' troppo grande (HTTP 413) -> si cerca la serie
  'Ensemble' per chiave, leggendo prima la struttura del dataflow.
"""
import re

import pandas as pd

from .comune import get

BASE = "https://api.insee.fr/series/BDM"
IPCH = "011812231"
SMB = "010562695"


def _obs(testo):
    """Ogni <Obs .../>: attributi letti in qualunque ordine."""
    out = {}
    for m in re.finditer(r"<(?:\w+:)?Obs\b([^>]*)/?>", testo):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        t, v = a.get("TIME_PERIOD"), a.get("OBS_VALUE")
        if t and v not in (None, "", "NaN"):
            out[t] = float(v)
    return out


def serie_idbank(idbank, dal="2000-01"):
    x = get(f"{BASE}/data/SERIES_BDM/{idbank}", params={"startPeriod": dal}, timeout=120)
    return _obs(x.text)


def trova_ipc(log=print):
    """idbank dell'IPC 'Ensemble' mensile, base 2025, cercato per chiave."""
    x = get(f"{BASE}/datastructure/FR1/IPC-2025", timeout=120)
    dims = re.findall(r'<(?:\w+:)?Dimension\b[^>]*\bid="([^"]+)"[^>]*\bposition="(\d+)"', x.text)
    if not dims:
        dims = [(d, str(i)) for i, d in enumerate(re.findall(r'<(?:\w+:)?Dimension\b[^>]*\bid="([^"]+)"', x.text), 1)]
    ordine = [d for d, _ in sorted(dims, key=lambda t: int(t[1]))]
    valori = {"FREQ": "M", "COICOP2018": "00", "NATURE": "INDICE", "REF_AREA": "FE"}
    chiave = ".".join(valori.get(d, "") for d in ordine)
    log(f"[insee] IPC-2025 dimensioni {ordine}, chiave '{chiave}'")
    y = get(f"{BASE}/data/IPC-2025/{chiave}", params={"lastNObservations": 1}, timeout=180)
    cand = []
    for m in re.finditer(r"<Series\b([^>]*)>", y.text):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        t = a.get("TITLE_FR", "")
        if "Ensemble" in t and "France" in t and "hors" not in t.lower():
            cand.append((len(t), a.get("IDBANK"), t))
    cand.sort()
    if cand:
        log(f"[insee] IPC scelto {cand[0][1]}: {cand[0][2][:140]}")
        return cand[0][1]
    log("[insee] IPC 'Ensemble' non trovato")
    return None


def scarica(log=print):
    righe, sal = [], []
    try:
        s = serie_idbank(IPCH)
        righe += [("FR", "hicp_headline_naz", 0, t, v, f"INSEE {IPCH}") for t, v in s.items()]
        log(f"[insee] IPCH {IPCH}: {len(s)} mesi, ultimo {max(s) if s else '-'}")
    except Exception as e:  # noqa: BLE001
        log(f"[insee] IPCH: {e}")
    try:
        idb = trova_ipc(log)
        if idb:
            s = serie_idbank(idb)
            righe += [("FR", "cpi_headline", 0, t, v, f"INSEE {idb}") for t, v in s.items()]
            log(f"[insee] IPC {idb}: {len(s)} mesi, ultimo {max(s) if s else '-'}")
    except Exception as e:  # noqa: BLE001
        log(f"[insee] IPC: {e}")
    try:
        s = serie_idbank(SMB, "2000-Q1")
        sal += [("FR", "insee_salaire_mensuel_base", "Q", t.replace("-", ""), v, "livello", f"INSEE {SMB}")
                for t, v in s.items()]
        log(f"[insee] salari {SMB}: {len(s)} trimestri")
    except Exception as e:  # noqa: BLE001
        log(f"[insee] salari: {e}")
    return (pd.DataFrame(righe, columns=["area", "misura", "sa", "data", "valore", "fonte"]),
            pd.DataFrame(sal, columns=["area", "misura", "freq", "periodo", "valore", "tipo", "fonte"]))
