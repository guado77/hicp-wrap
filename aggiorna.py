"""
Aggiorna l'archivio dati/storico dalle fonti e dice se c'e' qualcosa di nuovo.

- I dati scaricati si FONDONO con quelli gia' in archivio: le revisioni sovrascrivono,
  e se una fonte non risponde restano i dati della volta precedente (niente buchi).
- Scrive dati/storico/novita.json con i mesi nuovi per area e fonte; main.py lo usa
  per decidere se pubblicare e per il titolo dell'uscita.

Uso: python aggiorna.py
"""
import json
import os
import sys

import pandas as pd

from fonti import bce, eurostat

CARTELLA = os.path.join("dati", "storico")
AREE = ["EA", "IT", "DE", "FR", "ES"]
CHIAVI = {
    "serie.csv": ["area", "misura", "sa", "data"],
    "voci.csv": ["area", "voce", "data"],
    "pesi.csv": ["area", "anno", "voce"],
    "salari.csv": ["area", "misura", "periodo"],
}


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


def ultimi(serie):
    """Ultimo mese per area delle misure headline (una per fonte)."""
    if serie is None or serie.empty:
        return {}
    x = serie[(serie["misura"].isin(["hicp_headline", "cpi_headline"])) & (serie["sa"].astype(str) == "0")]
    return {f"{r.area}|{r.misura}": r.data for r in x.groupby(["area", "misura"])["data"].max().reset_index()
            .itertuples()}


def main():
    os.makedirs(CARTELLA, exist_ok=True)
    p_serie = os.path.join(CARTELLA, "serie.csv")
    prima = ultimi(pd.read_csv(p_serie, dtype=str)) if os.path.exists(p_serie) else {}

    s_eu, v_eu, p_eu, sal_eu = eurostat.scarica_tutto(AREE)
    try:
        s_bce, sal_bce = bce.scarica()
    except Exception as e:  # noqa: BLE001
        print(f"[bce] ERRORE {e}")
        s_bce, sal_bce = pd.DataFrame(), pd.DataFrame()

    serie = fondi("serie.csv", pd.concat([s_eu, s_bce], ignore_index=True))
    fondi("voci.csv", v_eu)
    fondi("pesi.csv", p_eu)
    fondi("salari.csv", pd.concat([sal_eu, sal_bce], ignore_index=True))

    dopo = ultimi(serie)
    nuovi = {k: v for k, v in dopo.items() if prima.get(k) != v}
    with open(os.path.join(CARTELLA, "novita.json"), "w", encoding="utf-8") as f:
        json.dump({"prima": prima, "dopo": dopo, "nuovi": nuovi}, f, ensure_ascii=False, indent=1)
    print(f"ultimi mesi: {dopo}")
    print(f"NOVITA': {nuovi if nuovi else 'nessuna'}")
    if serie is None or serie.empty:
        sys.exit("archivio vuoto: nessuna fonte ha risposto")


if __name__ == "__main__":
    main()
