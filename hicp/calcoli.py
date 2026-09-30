"""Calcoli di base sulle serie mensili di indici (PeriodIndex mensile)."""
import numpy as np
import pandas as pd


def ribasa(s, base="2020-01"):
    """Indice con il mese base = 100. Se il mese base manca restituisce None."""
    b = pd.Period(base, freq="M")
    if s is None or b not in s.index or pd.isna(s[b]) or s[b] == 0:
        return None
    return s / s[b] * 100.0


def var_m(s):
    """Variazione mensile in %."""
    return (s / s.shift(1) - 1.0) * 100.0


def var_a(s):
    """Variazione annua in % (stesso mese dell'anno prima)."""
    return (s / s.shift(12) - 1.0) * 100.0


def mom_3m3m(sa):
    """
    Momentum: media degli ultimi 3 mesi sui 3 precedenti, annualizzata, in %.
    Va calcolato su serie DESTAGIONALIZZATA: sui grezzi misura la stagionalita'.
    """
    m3 = sa.rolling(3).mean()
    return ((m3 / m3.shift(3)) ** 4 - 1.0) * 100.0


def destagionalizza(s):
    """
    Destagionalizzazione di ripiego (STL robusta sul logaritmo, periodo 12), usata solo
    quando la BCE non pubblica la serie destagionalizzata. Restituisce la serie SA
    oppure None se la storia e' troppo corta (meno di 4 anni completi).
    """
    from statsmodels.tsa.seasonal import STL

    x = s.dropna()
    if len(x) < 48:
        return None
    y = np.log(x.astype(float))
    y.index = y.index.to_timestamp()
    res = STL(y, period=12, robust=True, seasonal=13).fit()
    sa = np.exp(y - res.seasonal)
    sa.index = x.index
    # stessa scala dei grezzi: medie annue uguali
    return sa * (x.mean() / sa.mean())


def fattori_stagionali(nsa, sa, anni=3):
    """
    Fattore stagionale medio per mese di calendario (NSA/SA) sugli ultimi 'anni' anni.
    Restituisce dict mese(1-12) -> fattore.
    """
    r = (nsa / sa).dropna()
    if r.empty:
        return {m: 1.0 for m in range(1, 13)}
    ultimo_anno = r.index.max().year
    r = r[r.index.year > ultimo_anno - anni - 1]
    f = r.groupby(r.index.month).mean()
    return {m: float(f.get(m, 1.0)) for m in range(1, 13)}


def ultimo_valido(s):
    s = s.dropna() if s is not None else None
    if s is None or s.empty:
        return None, None
    return s.index[-1], float(s.iloc[-1])


def valore_a(s, periodo):
    if s is None:
        return None
    p = pd.Period(periodo, freq="M")
    if p in s.index and not pd.isna(s[p]):
        return float(s[p])
    return None
