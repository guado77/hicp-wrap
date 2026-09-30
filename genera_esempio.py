"""
Genera un archivio SINTETICO nello stesso formato che scriveranno i lettori delle fonti,
per provare motore, Excel e PDF senza rete. I numeri NON sono dati veri.

Uso: python genera_esempio.py [cartella]   (default: dati/esempio)
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hicp import aggrega, calcoli, config  # noqa: E402

RNG = np.random.default_rng(7)
MESI = pd.period_range("2014-12", "2026-08", freq="M")

ALIMENTARI = ["011100", "011200", "011300", "011400", "011500", "011600", "011700", "011800",
              "011900", "012100", "012200", "012300", "021100", "021200", "021300", "023000"]
ENERGIA = ["045100", "045200", "045300", "045400", "045500", "072200"]

# inflazione annua di fondo per categoria e anno (%)
PROFILO = {
    "Servizi":          {2015: 1.2, 2016: 1.1, 2017: 1.4, 2018: 1.4, 2019: 1.5, 2020: 1.0, 2021: 1.5,
                         2022: 3.5, 2023: 4.9, 2024: 4.0, 2025: 3.3, 2026: 3.0, 2027: 3.0},
    "Beni industriali": {2015: 0.3, 2016: 0.4, 2017: 0.4, 2018: 0.3, 2019: 0.3, 2020: 0.2, 2021: 1.5,
                         2022: 4.6, 2023: 5.0, 2024: 0.9, 2025: 0.6, 2026: 0.5, 2027: 0.5},
    "Alimentari":       {2015: 1.0, 2016: 0.9, 2017: 1.6, 2018: 2.1, 2019: 1.8, 2020: 2.3, 2021: 1.5,
                         2022: 9.0, 2023: 11.0, 2024: 2.3, 2025: 2.8, 2026: 2.6, 2027: 2.5},
    "Energia":          {2015: -6.8, 2016: -5.1, 2017: 4.9, 2018: 6.4, 2019: 1.1, 2020: -6.8, 2021: 13.0,
                         2022: 37.0, 2023: -2.0, 2024: -1.5, 2025: -0.5, 2026: 2.0, 2027: 2.0},
}
SCALA = {"EA": 1.0, "IT": 1.15, "DE": 1.05, "FR": 0.8, "ES": 1.1}

STAGIONE_SALDI = np.array([-12, -3, 8, 4, 1, 0, -12, -4, 8, 6, 2, 2], float)
STAGIONE_ESTATE = np.array([-6, -5, -3, 0, 2, 6, 12, 14, -2, -5, -6, -7], float)


def stagionalita(voce):
    if voce.startswith(("031", "032")):
        s = STAGIONE_SALDI
    elif voce in ("098000", "112000", "073300", "073400"):
        s = STAGIONE_ESTATE
    elif voce.startswith("0116") or voce.startswith("0117"):
        s = np.array([1, 1, 0, -1, -2, -2, -1, 0, 1, 1, 1, 1], float)
    else:
        return np.zeros(12)
    return (s - s.mean()) / 100.0


def tasso_annuo(cat, periodo, area, extra):
    p = PROFILO[cat]
    x = periodo.year + (periodo.month - 6.5) / 12.0
    a = int(np.floor(x))
    w = x - a
    r = p.get(a, p[2027]) * (1 - w) + p.get(a + 1, p[2027]) * w
    if r > 2.5:
        r = 2.5 + (r - 2.5) * SCALA[area]
    return r + extra


def genera_area(area, flag):
    voci = list(flag) + ALIMENTARI + ENERGIA
    idx, pesi = {}, {}
    for v in voci:
        cat = aggrega.macro_categoria(v, flag)
        extra = RNG.normal(0, 1.2 if cat != "Energia" else 3.0)
        st = stagionalita(v)
        liv, x = [], 100.0
        for p in MESI:
            r = tasso_annuo(cat, p, area, extra)
            x *= (1 + r / 100) ** (1 / 12) * np.exp(RNG.normal(0, 0.004 if cat != "Energia" else 0.02))
            liv.append(x * np.exp(st[p.month - 1]))
        idx[v] = liv
        if v in flag:
            base = flag[v]["peso"] * 0.71 * 10
        elif v in ALIMENTARI:
            base = 190 / len(ALIMENTARI)
        else:
            base = 100 / len(ENERGIA)
        pesi[v] = max(base * RNG.uniform(0.6, 1.4), 0.05)
    df = pd.DataFrame(idx, index=MESI)
    anni = range(2015, 2027)
    tot = sum(pesi.values())
    pw = pd.DataFrame({a: {v: w / tot * 1000 * RNG.uniform(0.95, 1.05) for v, w in pesi.items()}
                       for a in anni}).T
    return df, pw


def main(cartella):
    os.makedirs(cartella, exist_ok=True)
    flag = aggrega.carica_flag_bce()
    import csv
    with open(aggrega.FILE_BCE, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            flag[r["codice"]]["peso"] = max(float(r["peso_hicpx_2026"]), 0.05)

    serie, voci_rows, pesi_rows, salari_rows = [], [], [], []

    def metti(area, mis, s, sa=0, fonte="SINTETICO"):
        for p, x in s.dropna().items():
            serie.append((area, mis, sa, str(p), round(float(x), 4), fonte))

    for area in config.AREE:
        df, pw = genera_area(area, flag)
        for v in df.columns:
            for p, x in df[v].items():
                voci_rows.append((area, v, str(p), round(float(x), 4)))
        for anno, riga in pw.iterrows():
            for v, w in riga.items():
                pesi_rows.append((area, anno, v, round(float(w), 3)))
        cat = {v: aggrega.macro_categoria(v, flag) for v in df.columns}
        insiemi = {
            "hicp_headline": list(df.columns),
            "hicp_core": [v for v in df.columns if cat[v] in ("Servizi", "Beni industriali")],
            "hicp_ex_energia": [v for v in df.columns if cat[v] != "Energia"],
            "hicp_beni": [v for v in df.columns if cat[v] != "Servizi"],
            "hicp_servizi": [v for v in df.columns if cat[v] == "Servizi"],
            "hicp_alimentari": [v for v in df.columns if cat[v] == "Alimentari"],
            "hicp_energia": [v for v in df.columns if cat[v] == "Energia"],
            "hicp_trasporti": [v for v in df.columns if v.startswith("07")],
        }
        if area == "IT":
            insiemi.update({
                "istat_fondo": insiemi["hicp_core"] + ALIMENTARI[9:],
                "istat_carrello": ALIMENTARI + ["056100", "131200"],
                "istat_alta": ALIMENTARI + ["072200", "073200", "111100", "097200"],
                "istat_media": ["031200", "032100", "045100", "045200", "083400", "131300", "094600"],
                "istat_bassa": ["071100", "051100", "053100", "081300", "081200", "098000"],
            })
        agg = {}
        for mis, cod in insiemi.items():
            s = aggrega.aggrega(df, pw, cod)
            agg[mis] = s
            metti(area, mis, s, fonte="Eurostat (SINTETICO)" if mis.startswith("hicp") else "Istat (SINTETICO)")
        if area != "EA":
            cpi = agg["hicp_headline"] * np.exp(np.cumsum(RNG.normal(0, 0.0007, len(agg["hicp_headline"]))))
            metti(area, "cpi_headline", cpi, fonte=f"{config.CPI_NAZIONALE[area]} (SINTETICO)")
        if area in ("EA", "IT"):                 # serie destagionalizzate "BCE"
            for mis in ["hicp_headline", "hicp_core", "hicp_servizi", "hicp_beni", "hicp_energia",
                        "hicp_alimentari", "hicp_ex_energia"]:
                sa = calcoli.destagionalizza(agg[mis])
                metti(area, mis, sa, sa=1, fonte="BCE Data Portal (SINTETICO)")
        if area == "EA":
            from hicp import distribuzione
            tr = distribuzione.serie_troncate(distribuzione.tassi_annui(df), pw)
            for k in ["troncata10", "troncata25", "troncata30", "troncata50", "mediana"]:
                metti(area, f"bce_{k}", tr[k] + RNG.normal(0, 0.05, len(tr)), fonte="BCE (SINTETICO)")
            ins = aggrega.insiemi(df.columns, flag)
            for k in ["domestica"]:
                s = calcoli.var_a(aggrega.aggrega(df, pw, ins[k]))
                metti(area, f"bce_{k}", s + RNG.normal(0, 0.08, len(s)), fonte="BCE (SINTETICO)")

        # salari: redditi per dipendente trimestrali (livello), piu' tracker BCE (yoy) e Istat mensile
        q = pd.period_range("2015Q1", "2026Q2", freq="Q")
        x, lv = 100.0, []
        for p in q:
            g = {2021: 3.5, 2022: 4.5, 2023: 5.3, 2024: 4.5, 2025: 3.6, 2026: 3.2}.get(p.year, 1.8)
            g *= {"IT": 0.75, "DE": 1.1, "FR": 0.9, "ES": 1.0, "EA": 1.0}[area]
            if p == pd.Period("2020Q2", freq="Q"):
                g = -8
            if p == pd.Period("2020Q3", freq="Q"):
                g = 12
            x *= (1 + g / 100) ** 0.25 * np.exp(RNG.normal(0, 0.002))
            lv.append(x)
        for p, v in zip(q, lv):
            salari_rows.append((area, "compensation_per_employee", "Q", str(p), round(v, 3), "livello",
                                "Eurostat (SINTETICO)"))
        if area == "EA":
            for p in q[q >= pd.Period("2022Q1", freq="Q")]:
                salari_rows.append((area, "bce_wage_tracker", "Q", str(p),
                                    round({2022: 3.0, 2023: 4.6, 2024: 4.7, 2025: 3.2, 2026: 2.6}[p.year], 2),
                                    "yoy", "BCE (SINTETICO)"))
        if area == "IT":
            x = 100.0
            for p in MESI[1:]:
                g = {2022: 1.1, 2023: 3.0, 2024: 3.4, 2025: 3.0, 2026: 2.8}.get(p.year, 0.7)
                x *= (1 + g / 100) ** (1 / 12)
                salari_rows.append((area, "istat_retribuzioni_contrattuali", "M", str(p), round(x, 3),
                                    "livello", "Istat (SINTETICO)"))

    pd.DataFrame(serie, columns=["area", "misura", "sa", "data", "valore", "fonte"]).to_csv(
        os.path.join(cartella, "serie.csv"), index=False)
    pd.DataFrame(voci_rows, columns=["area", "voce", "data", "indice"]).to_csv(
        os.path.join(cartella, "voci.csv"), index=False)
    pd.DataFrame(pesi_rows, columns=["area", "anno", "voce", "peso"]).to_csv(
        os.path.join(cartella, "pesi.csv"), index=False)
    pd.DataFrame(salari_rows, columns=["area", "misura", "freq", "periodo", "valore", "tipo", "fonte"]).to_csv(
        os.path.join(cartella, "salari.csv"), index=False)
    print(f"archivio sintetico in {cartella}: {len(serie)} righe serie, {len(voci_rows)} righe voci")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join("dati", "esempio"))
