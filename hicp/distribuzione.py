"""
Distribuzione delle voci elementari per fasce di inflazione annua (per numero e per peso),
medie troncate ponderate e mediana ponderata.
"""
import numpy as np
import pandas as pd

from . import config
from .aggrega import _pesi_anno


def tassi_annui(voci):
    return (voci / voci.shift(12) - 1.0) * 100.0


def fascia_di(r):
    for nome, lo, hi in config.FASCE:
        if (lo is None or r > lo) and (hi is None or r <= hi):
            return nome
    return None


def _riga(tassi, pesi, periodo):
    r = tassi.loc[periodo].dropna()
    w = _pesi_anno(pesi, periodo.year)
    if w is None:
        return None, None
    w = w.reindex(r.index).fillna(0.0)
    keep = w > 0
    return r[keep], w[keep].astype(float)


def distribuzione(tassi, pesi, periodo, gruppo=None):
    """
    Quote delle voci per fascia al mese 'periodo'.
    gruppo: funzione voce -> nome gruppo (es. macro-categoria). Restituisce
    {'Totale': {'n': {fascia: %}, 'peso': {fascia: %}, 'voci': N}, gruppo: {...}}
    """
    r, w = _riga(tassi, pesi, periodo)
    if r is None or r.empty:
        return {}
    df = pd.DataFrame({"r": r, "w": w})
    df["fascia"] = df["r"].map(fascia_di)
    df["gruppo"] = [gruppo(v) if gruppo else "Totale" for v in df.index]
    out = {}
    for nome, g in [("Totale", df)] + ([(k, x) for k, x in df.groupby("gruppo")] if gruppo else []):
        n = g["fascia"].value_counts(normalize=True) * 100
        p = g.groupby("fascia")["w"].sum() / g["w"].sum() * 100
        out[nome] = {"n": {f: float(n.get(f, 0.0)) for f, _, _ in config.FASCE},
                     "peso": {f: float(p.get(f, 0.0)) for f, _, _ in config.FASCE},
                     "voci": int(len(g))}
    return out


def storico_quote(tassi, pesi, dal="2019-01"):
    """Quota ponderata delle voci per fascia, mese per mese."""
    righe = {}
    for p in tassi.index:
        if p < pd.Period(dal, freq="M"):
            continue
        r, w = _riga(tassi, pesi, p)
        if r is None or r.empty:
            continue
        f = r.map(fascia_di)
        tot = w.sum()
        righe[p] = {nome: float(w[f == nome].sum() / tot * 100) for nome, _, _ in config.FASCE}
    return pd.DataFrame(righe).T.sort_index() if righe else pd.DataFrame()


def media_troncata(r, w, taglio):
    """
    Media ponderata troncata: toglie taglio/2 del peso in ciascuna coda, con pesi
    parziali per le voci a cavallo della soglia. taglio in frazione (0.10 = 10%).
    """
    o = np.argsort(r.values)
    rv, wv = r.values[o], w.values[o] / w.values.sum()
    fine = np.cumsum(wv)
    inizio = fine - wv
    a, b = taglio / 2.0, 1.0 - taglio / 2.0
    tenuto = np.clip(np.minimum(fine, b) - np.maximum(inizio, a), 0, None)
    if tenuto.sum() <= 0:
        return np.nan
    return float((rv * tenuto).sum() / tenuto.sum())


def mediana_ponderata(r, w):
    o = np.argsort(r.values)
    rv, wv = r.values[o], w.values[o] / w.values.sum()
    return float(rv[np.searchsorted(np.cumsum(wv), 0.5)])


TAGLI = {"troncata10": 0.10, "troncata25": 0.25, "troncata30": 0.30,
         "troncata50": 0.50, "troncata75": 0.75}


def serie_troncate(tassi, pesi, dal="2016-01"):
    righe = {}
    for p in tassi.index:
        if p < pd.Period(dal, freq="M"):
            continue
        r, w = _riga(tassi, pesi, p)
        if r is None or len(r) < 10:
            continue
        x = {k: media_troncata(r, w, t) for k, t in TAGLI.items()}
        x["mediana"] = mediana_ponderata(r, w)
        righe[p] = x
    return pd.DataFrame(righe).T.sort_index() if righe else pd.DataFrame()
