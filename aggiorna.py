"""
Aggiorna l'archivio dati/storico dalle fonti e dice se c'e' qualcosa di nuovo.

- Eurostat: indici HICP, voci, pesi, salari per EA, IT, DE, FR, ES (spina dorsale).
- BCE: misure sottostanti, destagionalizzate area euro, wage tracker e salari negoziali.
- Istat, INSEE, INE, Destatis: CPI nazionali, misure Istat (fondo, carrello, frequenze),
  salari nazionali e STIME PRELIMINARI.
- Stima preliminare: se un istituto nazionale ha gia' il mese successivo all'ultimo di
  Eurostat, la sua variazione mensile viene applicata all'indice Eurostat e la riga e'
  marcata 'stima preliminare'. Quando Eurostat pubblica quel mese, la sua riga sostituisce
  quella stimata (la fusione tiene sempre il dato piu' recente).
- Una fonte che non risponde non cancella nulla: restano i dati della volta precedente.

Scrive dati/storico/novita.json e dati/storico/log_fonti.txt.
"""
import json
import os
import sys

import pandas as pd

from fonti import bce, destatis, eurostat, ine, insee, istat

CARTELLA = os.path.join("dati", "storico")
AREE = ["EA", "IT", "DE", "FR", "ES"]
CHIAVI = {
    "serie.csv": ["area", "misura", "sa", "data"],
    "voci.csv": ["area", "voce", "data"],
    "pesi.csv": ["area", "anno", "voce"],
    "salari.csv": ["area", "misura", "periodo"],
}
COLONNE_SERIE = ["area", "misura", "sa", "data", "valore", "fonte"]
_log = []


def log(s):
    print(s, flush=True)
    _log.append(str(s))


def fondi(nome, nuovo):
    p = os.path.join(CARTELLA, nome)
    vecchio = pd.read_csv(p, dtype=str) if os.path.exists(p) else pd.DataFrame()
    if nuovo is None or nuovo.empty:
        return vecchio
    nuovo = nuovo.astype(str)
    tutto = pd.concat([vecchio, nuovo], ignore_index=True) if not vecchio.empty else nuovo
    tutto = tutto.drop_duplicates(subset=CHIAVI[nome], keep="last").sort_values(CHIAVI[nome])
    tutto.to_csv(p, index=False)
    return tutto


def _unisci(parti):
    parti = [p for p in parti if p is not None and not p.empty]
    return pd.concat(parti, ignore_index=True) if parti else pd.DataFrame()


def ultimi(serie):
    if serie is None or serie.empty:
        return {}
    x = serie[(serie["misura"].isin(["hicp_headline", "cpi_headline"])) & (serie["sa"].astype(str) == "0")]
    return {f"{r.area}|{r.misura}": r.data for r in x.groupby(["area", "misura"])["data"].max().reset_index()
            .itertuples()}


def var_da_livelli(df, area, misura_naz):
    """Variazioni mensili % da una serie di livelli nazionale."""
    x = df[(df["area"] == area) & (df["misura"] == misura_naz)].sort_values("data")
    if x.empty:
        return {}, ""
    s = pd.Series(x["valore"].astype(float).values, index=pd.PeriodIndex(x["data"], freq="M"))
    mm = (s / s.shift(1) - 1) * 100
    return {str(p): float(v) for p, v in mm.dropna().items()}, x["fonte"].iloc[-1]


def estendi(serie, area, misura, var, fonte):
    """Aggiunge i mesi successivi all'ultimo disponibile applicando le variazioni mensili nazionali."""
    x = serie[(serie["area"] == area) & (serie["misura"] == misura) & (serie["sa"].astype(str) == "0")]
    x = x[~x["fonte"].str.contains("stima preliminare", na=False)]      # si riparte dal dato ufficiale
    if x.empty:
        return []
    x = x.sort_values("data")
    p = pd.Period(x["data"].iloc[-1], freq="M") + 1
    livello = float(x["valore"].iloc[-1])
    nuove = []
    while str(p) in var:
        livello *= 1 + var[str(p)] / 100
        nuove.append((area, misura, 0, str(p), round(livello, 4),
                      f"stima preliminare {fonte} (var. mensile applicata all'ultimo indice)"))
        log(f"[preliminare] {area} {misura} {p}: var. mensile {var[str(p)]:+.2f}% da {fonte}")
        p += 1
    return nuove


def main():
    os.makedirs(CARTELLA, exist_ok=True)
    p_serie = os.path.join(CARTELLA, "serie.csv")
    prima = ultimi(pd.read_csv(p_serie, dtype=str)) if os.path.exists(p_serie) else {}

    s_eu, v_eu, p_eu, sal_eu = eurostat.scarica_tutto(AREE, log=log)
    parti_serie, parti_sal, var_ine = [s_eu], [sal_eu], pd.DataFrame()
    fonti_naz = [("bce", lambda: bce.scarica(log=log)), ("istat", lambda: istat.scarica(log=log)),
                 ("insee", lambda: insee.scarica(log=log)), ("ine", lambda: ine.scarica(log=log)),
                 ("destatis", lambda: (destatis.scarica(log=log), pd.DataFrame()))]
    for nome, fn in fonti_naz:
        try:
            a, b = fn()
            parti_serie.append(a)
            if nome == "ine":
                var_ine = b
            else:
                parti_sal.append(b)
        except Exception as e:  # noqa: BLE001
            log(f"[{nome}] ERRORE {type(e).__name__}: {e}")

    serie = fondi("serie.csv", _unisci(parti_serie))
    fondi("voci.csv", v_eu)
    fondi("pesi.csv", p_eu)
    fondi("salari.csv", _unisci(parti_sal))

    # stime preliminari: estendono le serie oltre l'ultimo mese pubblicato
    if serie is not None and not serie.empty:
        nuove = []
        for area in ["IT", "DE", "FR"]:
            var, fonte = var_da_livelli(serie, area, "hicp_headline_naz")
            nuove += estendi(serie, area, "hicp_headline", var, fonte)
        if not var_ine.empty:
            for mis, g in var_ine.groupby("misura"):
                nuove += estendi(serie, "ES", mis, dict(zip(g["data"], g["var_mensile"].astype(float))),
                                 g["fonte"].iloc[-1])
        if nuove:
            serie = fondi("serie.csv", pd.DataFrame(nuove, columns=COLONNE_SERIE))

    dopo = ultimi(serie)
    nuovi = {k: v for k, v in dopo.items() if prima.get(k) != v}
    prel = {}
    if serie is not None and not serie.empty:
        for k, v in nuovi.items():
            area, mis = k.split("|")
            r = serie[(serie["area"] == area) & (serie["misura"] == mis) & (serie["data"] == v)
                      & (serie["sa"].astype(str) == "0")]
            prel[k] = bool(len(r)) and "stima preliminare" in str(r["fonte"].iloc[-1])
    with open(os.path.join(CARTELLA, "novita.json"), "w", encoding="utf-8") as f:
        json.dump({"prima": prima, "dopo": dopo, "nuovi": nuovi, "preliminare": prel}, f,
                  ensure_ascii=False, indent=1)
    log(f"ultimi mesi: {dopo}")
    log(f"NOVITA': {nuovi if nuovi else 'nessuna'}")
    with open(os.path.join(CARTELLA, "log_fonti.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(_log))
    if serie is None or serie.empty:
        sys.exit("archivio vuoto: nessuna fonte ha risposto")


if __name__ == "__main__":
    main()
