"""
Proiezioni dell'inflazione annua a fine anno sotto sei scenari, ed effetto base.

Tutti gli scenari proiettano il livello dell'indice GREZZO mese per mese e ne ricavano
la variazione annua: e' cosi' che l'effetto base entra da solo nel calcolo, perche'
la variazione annua di ogni mese futuro dipende anche dal mese dell'anno prima che esce.

- momentum:    la crescita destagionalizzata degli ultimi 3 mesi resta costante; il
               percorso viene poi rimesso in stagionalita' con i fattori stagionali medi
               degli ultimi 3 anni.
- neutro_1a:   ogni mese futuro ripete la variazione mensile dello stesso mese dell'anno
               prima -> la variazione annua resta invariata (riferimento neutro).
- neutro_3a/5a e mediana_5a: variazione mensile tipica di quel mese di calendario, media
               o mediana degli ultimi 3/5 anni. La mediana assorbe anni anomali (2022).
- obiettivo_2: crescita destagionalizzata coerente con il 2% annuo, rimessa in stagionalita'.
"""
import numpy as np
import pandas as pd

from .calcoli import fattori_stagionali


def orizzonte(ultimo):
    """Fino a dicembre dell'anno in corso; dall'ultimo dato di novembre o dicembre si va
    a dicembre dell'anno dopo, altrimenti la proiezione avrebbe uno o zero mesi."""
    anno = ultimo.year + (1 if ultimo.month >= 11 else 0)
    fine = pd.Period(f"{anno}-12", freq="M")
    return pd.period_range(ultimo + 1, fine, freq="M")


def _mm_tipica(mm, mese, anno_rif, ultimo, anni, funzione):
    vals = []
    for j in range(1, anni + 1):
        p = pd.Period(year=anno_rif - j, month=mese, freq="M")
        if p <= ultimo and p in mm.index and not pd.isna(mm[p]):
            vals.append(float(mm[p]))
    if not vals:
        return 1.0
    return float(np.exp(np.mean(np.log(vals)))) if funzione == "media" else float(np.median(vals))


def scenari(nsa, sa):
    nsa = nsa.dropna()
    t = nsa.index[-1]
    futuri = orizzonte(t)
    mm = nsa / nsa.shift(1)

    livelli = {}
    # scenari basati sulle variazioni mensili passate
    for nome, anni, funz in [("neutro_3a", 3, "media"), ("neutro_5a", 5, "media"),
                             ("mediana_5a", 5, "mediana")]:
        x, liv = float(nsa[t]), {}
        for p in futuri:
            x *= _mm_tipica(mm, p.month, p.year, t, anni, funz)
            liv[p] = x
        livelli[nome] = liv

    # neutro_1a: ripete la variazione dello stesso mese dell'anno prima (anche se proiettato)
    percorso = nsa.copy()
    liv = {}
    for p in futuri:
        a, b = p - 12, p - 13
        rap = percorso[a] / percorso[b] if a in percorso.index and b in percorso.index else 1.0
        x = float(percorso[p - 1]) * rap
        percorso[p] = x
        liv[p] = x
    livelli["neutro_1a"] = liv

    # momentum e 2%: crescita destagionalizzata costante, poi rimessa in stagionalita'
    if sa is not None and t in sa.index and (t - 3) in sa.index:
        f = fattori_stagionali(nsa, sa.reindex(nsa.index))
        g_mom = float((sa[t] / sa[t - 3]) ** (1 / 3))
        for nome, g in [("momentum", g_mom), ("obiettivo_2", 1.02 ** (1 / 12))]:
            livelli[nome] = {p: float(nsa[t]) * g ** h * f[p.month] / f[t.month]
                             for h, p in enumerate(futuri, start=1)}
        momentum_ann = (g_mom ** 12 - 1) * 100
    else:
        momentum_ann = None

    ordine = ["momentum", "neutro_1a", "neutro_3a", "neutro_5a", "mediana_5a", "obiettivo_2"]
    lv = pd.DataFrame({k: livelli[k] for k in ordine if k in livelli})
    lv.index = pd.PeriodIndex(lv.index, freq="M")

    yoy = {}
    for k in lv.columns:
        s = pd.concat([nsa, lv[k]])
        yoy[k] = ((s / s.shift(12) - 1) * 100).reindex(futuri)
    yoy = pd.DataFrame(yoy)

    base = pd.DataFrame({
        "var_mensile_anno_prima": [(float(mm[p - 12]) - 1) * 100 if (p - 12) in mm.index and (p - 12) <= t
                                   else np.nan for p in futuri],
    }, index=futuri)
    return {
        "ultimo": t, "fine": futuri[-1], "livelli": lv, "yoy": yoy,
        "a_fine": {k: float(yoy[k].iloc[-1]) for k in yoy.columns},
        "effetto_base": base,
        "momentum_ann": momentum_ann,
        "yoy_ultimo": float((nsa[t] / nsa[t - 12] - 1) * 100) if (t - 12) in nsa.index else None,
    }
