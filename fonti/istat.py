"""
Lettore Istat (esploradati SDMX, formato jsondata). Dataflow verificati nella fase 1b (30/9/2026):

- 167_745_DF_DCSP_NIC1B2025_1  NIC mensili dal 2026, base 2025 - principali dati
- 167_745_DF_DCSP_NIC1B2025_2  NIC mensili dal 2026, base 2025 - tipologie di prodotto
- 167_744_DF_DCSP_NIC1B2015_1  NIC mensili 2016-2025, base 2015 - principali dati
- 167_744_DF_DCSP_NIC1B2015_2  NIC mensili 2016-2025, base 2015 - tipologie di prodotto
- 155_318_DF_DCSC_RETRCONTR1C_4 retribuzioni contrattuali, base 2021

Le serie si riconoscono dalle ETICHETTE (indice generale, componente di fondo, carrello,
alta/media/bassa frequenza), non da codici indovinati: il log stampa cosa e' stato scelto.
Raccordo base 2015 -> base 2025: si divide la serie vecchia per la sua media 2025 e si
moltiplica per 100, che e' la definizione del coefficiente di raccordo Istat.

VINCOLO: al massimo 5 richieste al minuto, oltre scatta un blocco di 1-2 giorni. Pausa di 15 s
fra una chiamata e l'altra.
"""
import re
import time

import pandas as pd

from .comune import get

BASE = "https://esploradati.istat.it/SDMXWS/rest/data"
PAUSA = 15

REGOLE = [  # (misura, parole che devono esserci, parole che non devono esserci) - italiano e inglese
    ("cpi_headline", [r"indice generale|all[- ]items|overall index"],
     [r"tabacc", r"netto", r"escl", r"\bex\b", r"excluding", r"net of", r"tobacco", r"--"]),
    ("istat_fondo", [r"componente di fondo|netto degli energetici e degli alimentari freschi|"
                     r"excluding energy and (unprocessed|fresh) food|core"], [r"--"]),
    ("istat_carrello", [r"carrello|cura della casa e della persona|household and personal care|"
                        r"grocery|shopping basket"], []),
    ("istat_alta", [r"alta frequenza|high[- ]frequency"], []),
    ("istat_media", [r"media frequenza|medium[- ]frequency"], []),
    ("istat_bassa", [r"bassa frequenza|low[- ]frequency"], []),
]


def _jsondata(flusso, dal):
    x = get(f"{BASE}/IT1,{flusso},1.0/all", params={"startPeriod": dal, "format": "jsondata"},
            timeout=300, tentativi=2, pausa=PAUSA, headers={"Accept-Language": "it"})
    js = x.json()
    if "data" in js:                                   # SDMX-JSON 2.0
        ds, st = js["data"]["dataSets"][0], js["data"]["structures"][0]
    else:                                              # SDMX-JSON 1.0
        ds, st = js["dataSets"][0], js["structure"]
    dser = st["dimensions"]["series"]
    tempi = [str(v.get("id")).replace("-M", "-") for v in st["dimensions"]["observation"][0]["values"]]
    out = []
    for chiave, s in ds.get("series", {}).items():
        idx = [int(i) for i in chiave.split(":")]
        etich = {d["id"]: (d["values"][i].get("id"), d["values"][i].get("name", "")) for d, i in zip(dser, idx)}
        # territorio: si tiene solo l'Italia (codice IT); province e regioni escono qui
        terr = [c for dim, (c, _) in etich.items() if re.search(r"REF_AREA|ITTER|TERR", dim, re.I)]
        if terr and terr[0] != "IT":
            continue
        obs = {tempi[int(k)]: v[0] for k, v in s.get("observations", {}).items() if v and v[0] is not None}
        out.append((etich, obs))
    return out


def _testo(etich):
    return " | ".join(str(n) for _, n in etich.values()).lower()


def _scegli(serie, log, flusso):
    """Tiene solo gli indici (non le variazioni), territorio Italia, e applica le regole."""
    buone = []
    for etich, obs in serie:
        t = _testo(etich)
        if re.search(r"variaz|tendenzial|congiuntural|peso|pesi", t):
            continue
        if re.search(r"\b(nord|centro|sud|isole|regione|provinc)", t):
            continue
        buone.append((t, obs))
    scelte = {}
    for mis, si, no in REGOLE:
        cand = [(len(t), t, obs) for t, obs in buone if obs
                and all(re.search(p, t) for p in si) and not any(re.search(p, t) for p in no)]
        if cand:
            cand.sort(key=lambda c: c[0])
            scelte[mis] = cand[0][2]
            log(f"[istat] {flusso} {mis} <- '{cand[0][1][:150]}' ({len(cand[0][2])} mesi)")
    con_dati = sum(1 for _, o in buone if o)
    log(f"[istat] {flusso}: {len(serie)} serie Italia, {len(buone)} indici, {con_dati} con osservazioni")
    if not scelte:
        log(f"[istat] {flusso}: nessuna regola soddisfatta. Etichette (ultima parte): "
            + " || ".join(t[-90:] for t, o in buone[:25] if o))
    return scelte


def _raccorda(vecchia, nuova):
    """Porta la serie base 2015 in base 2025 (media 2025 = 100) e la unisce alla nuova."""
    v = {t: x for t, x in vecchia.items() if t[:4].isdigit()}
    anno = [x for t, x in v.items() if t.startswith("2025")]
    if len(anno) < 12:
        return dict(nuova)
    k = 100.0 / (sum(anno) / len(anno))
    out = {t: x * k for t, x in v.items()}
    out.update(nuova)
    return out


def scarica(log=print):
    righe, sal = [], []
    risultati = {}
    for coppia in [("167_744_DF_DCSP_NIC1B2015_1", "167_745_DF_DCSP_NIC1B2025_1"),
                   ("167_744_DF_DCSP_NIC1B2015_2", "167_745_DF_DCSP_NIC1B2025_2")]:
        parti = []
        for flusso, dal in zip(coppia, ["2016-01", "2026-01"]):
            try:
                parti.append(_scegli(_jsondata(flusso, dal), log, flusso))
            except Exception as e:  # noqa: BLE001
                log(f"[istat] {flusso}: {type(e).__name__}: {str(e)[:200]}")
                parti.append({})
            time.sleep(PAUSA)
        vecchie, nuove = parti
        for mis in set(vecchie) | set(nuove):
            if mis in risultati:
                continue
            risultati[mis] = _raccorda(vecchie.get(mis, {}), nuove.get(mis, {}))
    for mis, s in risultati.items():
        righe += [("IT", mis, 0, t, float(v), "Istat NIC (base 2025, raccordata)") for t, v in s.items()
                  if re.match(r"^\d{4}-\d{2}$", t)]
    # IPCA Istat: serve solo per la stima preliminare dell'HICP italiano (ultimi mesi)
    try:
        time.sleep(PAUSA)
        ipca = _scegli(_jsondata("168_761", "2024-01"), log, "168_761 IPCA")
        if "cpi_headline" in ipca:
            righe += [("IT", "hicp_headline_naz", 0, t, float(v), "Istat IPCA 168_761")
                      for t, v in ipca["cpi_headline"].items() if re.match(r"^\d{4}-\d{2}$", t)]
    except Exception as e:  # noqa: BLE001
        log(f"[istat] IPCA 168_761: {type(e).__name__}: {str(e)[:200]}")
    try:
        time.sleep(PAUSA)
        for etich, obs in _jsondata("155_318_DF_DCSC_RETRCONTR1C_4", "2016-01"):
            t = _testo(etich)
            if "indic" in t and re.search(r"totale economia|totale", t) and "per dipendente" in t \
                    and not re.search(r"variaz|ora", t):
                sal += [("IT", "istat_retribuzioni_contrattuali", "M", p, float(v), "livello",
                         "Istat retribuzioni contrattuali (base 2021)") for p, v in obs.items()
                        if re.match(r"^\d{4}-\d{2}$", p)]
                log(f"[istat] retribuzioni <- '{t[:150]}' ({len(obs)} mesi)")
                break
        else:
            log("[istat] retribuzioni: serie 'totale economia per dipendente' non riconosciuta")
    except Exception as e:  # noqa: BLE001
        log(f"[istat] retribuzioni: {type(e).__name__}: {str(e)[:200]}")
    return (pd.DataFrame(righe, columns=["area", "misura", "sa", "data", "valore", "fonte"]),
            pd.DataFrame(sal, columns=["area", "misura", "freq", "periodo", "valore", "tipo", "fonte"]))
