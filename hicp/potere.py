"""Potere d'acquisto: prezzi contro gennaio 2020 e gennaio 2024, e salari reali."""
import numpy as np
import pandas as pd

from . import config


def confronto_livelli(idx, ultimo):
    """Per ogni base: aumento dei prezzi, perdita di potere d'acquisto, valore di 100 euro."""
    out = {}
    if idx is None or ultimo not in idx.index:
        return out
    for nome, per in config.BASI_CONFRONTO.items():
        b = pd.Period(per, freq="M")
        if b not in idx.index or pd.isna(idx[b]):
            continue
        rap = float(idx[ultimo] / idx[b])
        out[nome] = {"prezzi": (rap - 1) * 100, "potere": (1 / rap - 1) * 100, "cento_euro": 100 / rap}
    return out


def _prezzi_a_frequenza(prezzi, freq):
    if freq == "Q":
        p = prezzi.copy()
        q = p.groupby(p.index.asfreq("Q")).agg(["mean", "count"])
        return q.loc[q["count"] == 3, "mean"]       # solo trimestri completi
    return prezzi


def salari_reali(salari, prezzi):
    """
    salari: dict misura -> {'serie','freq','tipo','fonte'} (dall'archivio)
    prezzi: indice dei prezzi mensile (HICP generale)
    Restituisce dict misura -> {'tabella': DataFrame, 'cumulato': {base: {...}}, 'freq', 'fonte'}
    """
    out = {}
    for mis, d in salari.items():
        s, freq, tipo = d["serie"].dropna(), d["freq"], d["tipo"]
        p = _prezzi_a_frequenza(prezzi.dropna(), freq)
        lag = 4 if freq == "Q" else 12
        infl = (p / p.shift(lag) - 1) * 100
        if tipo == "livello":
            nom = (s / s.shift(lag) - 1) * 100
        else:
            nom = s
        tab = pd.DataFrame({"salari_nominali": nom, "prezzi": infl}).dropna()
        tab["salari_reali"] = ((1 + tab["salari_nominali"] / 100) / (1 + tab["prezzi"] / 100) - 1) * 100
        cum = {}
        if tipo == "livello":
            for nome, per in config.BASI_CONFRONTO.items():
                b = pd.Period(per, freq="M").asfreq(freq)
                comuni = s.index.intersection(p.index)
                if b not in comuni or comuni.empty:
                    continue
                u = comuni[-1]
                w = s[u] / s[b]
                pr = p[u] / p[b]
                cum[nome] = {"fino_a": str(u), "salari": (w - 1) * 100, "prezzi": (pr - 1) * 100,
                             "reale": (w / pr - 1) * 100}
        out[mis] = {"tabella": tab, "cumulato": cum, "freq": freq, "fonte": d["fonte"], "tipo": tipo}
    return out
