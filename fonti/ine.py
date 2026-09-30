"""
Lettore INE (API Tempus3). Codici verificati nella fase 1b (30/9/2026).

Nel dato anticipato l'INE pubblica solo le VARIAZIONI, non l'indice: per il mese della stima
preliminare si usa la variazione mensile, applicata poi all'indice Eurostat in aggiorna.py.
"""
import pandas as pd

from .comune import get

BASE = "https://servicios.ine.es/wstempus/js/ES"

INDICI = {"IPC290751": "cpi_headline"}                        # IPC generale, indice
# variazioni mensili (%) usate per estendere l'ultimo mese (stima preliminare)
VAR_MENSILI = {
    "IPC290752": "cpi_headline",
    "IPCA8092": "hicp_headline",
    "IPCA9235": "hicp_energia",
    "IPCA9238": "hicp_servizi",
    "IPCA16282": "hicp_alimentari",
}


def _serie(cod, n=400):
    d = get(f"{BASE}/DATOS_SERIE/{cod}", params={"nult": n}, timeout=90).json()
    out = {}
    for x in d.get("Data", []):
        if x.get("Valor") is None or not x.get("Anyo") or not x.get("FK_Periodo"):
            continue
        m = int(x["FK_Periodo"])
        if 1 <= m <= 12:
            out[f"{int(x['Anyo'])}-{m:02d}"] = float(x["Valor"])
    return out


def scarica(log=print):
    righe, var = [], []
    for cod, mis in INDICI.items():
        try:
            s = _serie(cod)
            righe += [("ES", mis, 0, t, v, f"INE {cod}") for t, v in s.items()]
            log(f"[ine] {cod} {mis}: {len(s)} mesi, ultimo {max(s) if s else '-'}")
        except Exception as e:  # noqa: BLE001
            log(f"[ine] {cod}: {e}")
    for cod, mis in VAR_MENSILI.items():
        try:
            s = _serie(cod, 6)
            var += [("ES", mis, t, v, f"INE {cod}") for t, v in s.items()]
            log(f"[ine] {cod} var. mensile {mis}: ultimo {max(s) if s else '-'}")
        except Exception as e:  # noqa: BLE001
            log(f"[ine] {cod}: {e}")
    return (pd.DataFrame(righe, columns=["area", "misura", "sa", "data", "valore", "fonte"]),
            pd.DataFrame(var, columns=["area", "misura", "data", "var_mensile", "fonte"]))
