"""
Aggregazione delle voci elementari con la formula HICP: Laspeyres concatenato
annualmente sul dicembre dell'anno precedente, pesi dell'anno in corso.
Serve a ricostruire domestica/importata, Supercore/non Supercore per ciascun paese
e a verificare la ricostruzione contro gli aggregati ufficiali.
"""
import csv
import os

import numpy as np
import pandas as pd

from . import config

_QUI = os.path.dirname(os.path.abspath(__file__))
FILE_BCE = os.path.join(_QUI, "..", "dati", "classificazione_bce_2026.csv")


def carica_flag_bce(percorso=FILE_BCE):
    with open(percorso, encoding="utf-8") as f:
        righe = list(csv.DictReader(f, delimiter=";"))
    return {r["codice"]: {"domestica": r["domestica"] == "1", "supercore": r["supercore"] == "1",
                          "aggregato": r["aggregato"], "voce": r["voce"],
                          "quota_import": float(r["quota_import"])} for r in righe}


def macro_categoria(voce, flag):
    """Alimentari / Energia / Beni industriali / Servizi, secondo le convenzioni HICP."""
    if voce.startswith(config.ENERGIA_PREFISSI):
        return "Energia"
    if voce.startswith(config.ALIMENTARI_PREFISSI) and voce not in config.ALIMENTARI_SERVIZI:
        return "Alimentari"
    f = flag.get(voce)
    if f:
        return "Servizi" if f["aggregato"] == "Services" else "Beni industriali"
    return "Non classificata"


def insiemi(voci_disponibili, flag):
    """Insiemi di voci per le misure ricostruite."""
    hicpx = [v for v in voci_disponibili if v in flag]
    return {
        "domestica": [v for v in hicpx if flag[v]["domestica"]],
        "importata": [v for v in hicpx if not flag[v]["domestica"]],
        "supercore": [v for v in hicpx if flag[v]["supercore"]],
        "non_supercore": [v for v in hicpx if not flag[v]["supercore"]],
        "hicpx": hicpx,
        "tutte": list(voci_disponibili),
    }


def _pesi_anno(pesi, anno):
    if anno in pesi.index:
        return pesi.loc[anno]
    prec = [a for a in pesi.index if a <= anno]
    return pesi.loc[max(prec)] if prec else None


def aggrega(voci, pesi, codici, base="2020-01"):
    """
    Indice aggregato delle voci 'codici'. Una voce che manca in un mese dell'anno
    esce dall'aggregato per TUTTO quell'anno (niente cambi di composizione a meta' anno).
    Restituisce la serie ribasata (base = 100) oppure None.
    """
    cols = [c for c in codici if c in voci.columns and c in pesi.columns]
    if not cols:
        return None
    v = voci[cols]
    anni = sorted(set(v.index.year))
    livello = {}
    for anno in anni:
        dic = pd.Period(f"{anno - 1}-12", freq="M")
        if dic not in v.index:
            continue
        w = _pesi_anno(pesi[cols], anno)
        if w is None:
            continue
        mesi = [p for p in v.index if p.year == anno]
        blocco = v.loc[mesi]
        ok = [c for c in cols if w.get(c, 0) > 0 and not pd.isna(v.at[dic, c]) and blocco[c].notna().all()]
        if not ok:
            continue
        if not livello:
            livello[dic] = 100.0
        if dic not in livello:
            continue
        rel = blocco[ok].div(v.loc[dic, ok])
        ww = w[ok].astype(float)
        agg = (rel * ww).sum(axis=1) / ww.sum()
        for p, x in agg.items():
            livello[p] = livello[dic] * float(x)
    if not livello:
        return None
    s = pd.Series(livello).sort_index()
    s.index = pd.PeriodIndex(s.index, freq="M")
    b = pd.Period(base, freq="M")
    return s / s[b] * 100.0 if b in s.index else s


def confronta(ricostruita, ufficiale, mesi=24):
    """Scarto sulla variazione annua fra ricostruzione e serie ufficiale, ultimi 'mesi'."""
    if ricostruita is None or ufficiale is None:
        return None
    a = (ricostruita / ricostruita.shift(12) - 1) * 100
    b = (ufficiale / ufficiale.shift(12) - 1) * 100
    d = (a - b).dropna().tail(mesi)
    if d.empty:
        return None
    return {"mesi": int(len(d)), "scarto_medio": float(d.mean()),
            "scarto_max_ass": float(d.abs().max()), "ultimo": float(d.iloc[-1])}


def pesi_macro(pesi, anno, flag):
    w = _pesi_anno(pesi, anno)
    out = {}
    for v, x in w.items():
        if pd.isna(x):
            continue
        k = macro_categoria(v, flag)
        out[k] = out.get(k, 0.0) + float(x)
    tot = sum(out.values()) or np.nan
    return {k: x / tot * 100 for k, x in out.items()}
