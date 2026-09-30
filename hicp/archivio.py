"""
Archivio in formato unico, indipendente dalle fonti.

I lettori delle fonti (fase 2) scrivono qui; il motore legge solo da qui.
Quattro file CSV in una cartella:

  serie.csv   area, misura, sa, data (AAAA-MM), valore, fonte
              indici aggregati; sa=1 per le serie destagionalizzate pubblicate (BCE)
  voci.csv    area, voce (codice ECOICOP v2 a 6 cifre), data, indice
  pesi.csv    area, anno, voce, peso (per mille)
  salari.csv  area, misura, freq (M/Q), periodo (AAAA-MM o AAAA-Qn), valore, tipo (livello/yoy), fonte
"""
import os

import pandas as pd


class Archivio:
    def __init__(self, cartella):
        self.cartella = cartella
        self._serie = self._leggi("serie.csv", {"area": str, "misura": str, "data": str, "fonte": str})
        self._voci = self._leggi("voci.csv", {"area": str, "voce": str, "data": str})
        self._pesi = self._leggi("pesi.csv", {"area": str, "voce": str})
        self._salari = self._leggi("salari.csv", {"area": str, "misura": str, "periodo": str,
                                                  "freq": str, "tipo": str, "fonte": str})

    def _leggi(self, nome, tipi):
        p = os.path.join(self.cartella, nome)
        if not os.path.exists(p):
            return pd.DataFrame()
        return pd.read_csv(p, dtype=tipi)

    # ------------------------------------------------------------ aggregati
    def misure(self, area, sa=False):
        s = self._serie
        if s.empty:
            return []
        m = s[(s["area"] == area) & (s["sa"] == int(sa))]["misura"].unique().tolist()
        return m

    def serie(self, area, misura, sa=False):
        s = self._serie
        if s.empty:
            return None
        x = s[(s["area"] == area) & (s["misura"] == misura) & (s["sa"] == int(sa))]
        if x.empty:
            return None
        out = pd.Series(x["valore"].astype(float).values,
                        index=pd.PeriodIndex(x["data"], freq="M"), name=misura).sort_index()
        return out[~out.index.duplicated(keep="last")]

    def fonte(self, area, misura, sa=False):
        s = self._serie
        x = s[(s["area"] == area) & (s["misura"] == misura) & (s["sa"] == int(sa))]
        return "" if x.empty else str(x["fonte"].iloc[-1])

    # ------------------------------------------------------ voci elementari
    def voci(self, area):
        v = self._voci
        if v.empty:
            return None
        x = v[v["area"] == area]
        if x.empty:
            return None
        w = x.pivot_table(index="data", columns="voce", values="indice", aggfunc="last")
        w.index = pd.PeriodIndex(w.index, freq="M")
        return w.sort_index()

    def pesi(self, area):
        p = self._pesi
        if p.empty:
            return None
        x = p[p["area"] == area]
        if x.empty:
            return None
        return x.pivot_table(index="anno", columns="voce", values="peso", aggfunc="last").sort_index()

    # --------------------------------------------------------------- salari
    def salari(self, area):
        s = self._salari
        if s.empty:
            return {}
        x = s[s["area"] == area]
        out = {}
        for (mis, freq, tipo), g in x.groupby(["misura", "freq", "tipo"]):
            idx = pd.PeriodIndex(g["periodo"], freq="Q" if freq == "Q" else "M")
            out[mis] = {"serie": pd.Series(g["valore"].astype(float).values, index=idx).sort_index(),
                        "freq": freq, "tipo": tipo, "fonte": str(g["fonte"].iloc[-1])}
        return out

    def ultimo_periodo(self):
        s = self._serie
        return None if s.empty else pd.Period(s["data"].max(), freq="M")
