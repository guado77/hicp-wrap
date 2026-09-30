"""
Lettore Destatis (GENESIS-Online API 2020, credenziali nei secret DESTATIS_USER / DESTATIS_PASS).

Tabelle verificate nella fase 1b (30/9/2026):
- 61111-0002 Verbraucherpreisindex (VPI), Deutschland, Monate  -> CPI nazionale
- 61121-0002 Harmonisierter VPI (HVPI), Deutschland, Monate    -> per la stima preliminare dell'HICP

Il file 'ffcsv' ha intestazioni che cambiano fra tabelle: il lettore cerca da solo la colonna
dell'anno, quella del mese e quella del valore, e stampa le intestazioni nel log.
"""
import csv
import io
import os

import pandas as pd
import requests

from .comune import HDR

BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020"
MESI = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
        "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
TABELLE = {"61111-0002": "cpi_headline", "61121-0002": "hicp_headline_naz"}


def _credenziali():
    tok = os.environ.get("DESTATIS_TOKEN", "").strip()
    usr = os.environ.get("DESTATIS_USER", "").strip()
    pwd = os.environ.get("DESTATIS_PASS", "").strip()
    if tok:
        return {"username": tok, "password": ""}
    if usr:
        return {"username": usr, "password": pwd}
    return None


def _num(x):
    x = (x or "").strip().replace(".", "").replace(",", ".") if "," in (x or "") else (x or "").strip()
    try:
        return float(x)
    except ValueError:
        return None


def tabella(nome, cred, log):
    x = requests.post(f"{BASE}/data/tablefile", headers={**HDR, **cred}, timeout=180,
                      data={"name": nome, "area": "all", "format": "ffcsv", "compress": "false",
                            "startyear": "2000", "language": "de"})
    if x.status_code != 200 or ";" not in x.text[:2000]:
        raise RuntimeError(f"HTTP {x.status_code}: {x.text[:300]}")
    righe = list(csv.DictReader(io.StringIO(x.text.lstrip("\ufeff"), newline=""), delimiter=";"))
    campi = list(righe[0].keys()) if righe else []
    log(f"[destatis] {nome}: {len(righe)} righe; colonne {campi[:14]}")
    c_anno = next((c for c in campi if c.lower() in ("time", "zeit", "jahr")), None)
    c_mese = next((c for c in campi if any(str(r.get(c, "")).strip().lower() in MESI for r in righe[:30])), None)
    c_val = next((c for c in campi if c.lower() == "value"), None) or \
        next((c for c in reversed(campi) if any(_num(r.get(c)) for r in righe[:30])), None)
    out = {}
    for r in righe:
        a, m, v = str(r.get(c_anno, "")).strip()[:4], str(r.get(c_mese, "")).strip().lower(), _num(r.get(c_val))
        if a.isdigit() and m in MESI and v is not None:
            out[f"{a}-{MESI[m]:02d}"] = v
    return out


def scarica(log=print):
    cred = _credenziali()
    if not cred:
        log("[destatis] credenziali assenti: salto")
        return pd.DataFrame(columns=["area", "misura", "sa", "data", "valore", "fonte"])
    righe = []
    for nome, mis in TABELLE.items():
        try:
            s = tabella(nome, cred, log)
            righe += [("DE", mis, 0, t, v, f"Destatis {nome}") for t, v in s.items()]
            log(f"[destatis] {nome} {mis}: {len(s)} mesi, ultimo {max(s) if s else '-'}")
        except Exception as e:  # noqa: BLE001
            log(f"[destatis] {nome}: {e}")
    return pd.DataFrame(righe, columns=["area", "misura", "sa", "data", "valore", "fonte"])
