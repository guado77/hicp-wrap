"""
hicp-wrap - FASE 1b: sonda mirata sui buchi lasciati dalla fase 1.

- Istat: il catalogo completo e' andato in timeout (180 s). Si chiede la versione
  leggera (allstubs) con attesa lunga, e si prova anche il vecchio endpoint sdmx.istat.it.
- BCE: il dataflow ICP si ferma a dic 2025; si cerca la chiave del nuovo dataflow HICP
  e si elencano tutte le serie area euro e Italia.
- INSEE: elenco delle serie (idbank e titolo) di IPC-2025, IPCH-2025, SALAIRES-ACEMO-2017.
- INE: elenco delle serie delle tabelle IPC/IPCA ECOICOP v2, ultimo periodo di ciascuna,
  e ricerca dell'indicatore anticipato (flash).
- Destatis: di nuovo, con i secret DESTATIS_USER / DESTATIS_PASS se presenti.

Uscita: esito2/rapporto_fonti_2.md + dettagli, inviati sulla chat privata.
"""
import csv
import io
import os
import re
import shutil
import time

import requests

import esplora_fonti as e1

e1.OUT = "esito2"
os.makedirs(e1.OUT, exist_ok=True)
r, salva, sonda, get = e1.r, e1.salva, e1.sonda, e1.get


@sonda("Istat - catalogo leggero")
def istat():
    for url in ["https://esploradati.istat.it/SDMXWS/rest/dataflow/IT1/all/latest?detail=allstubs",
                "https://esploradati.istat.it/SDMXWS/rest/dataflow/IT1?detail=allstubs",
                "https://sdmx.istat.it/SDMXWS/rest/dataflow/IT1?detail=allstubs"]:
        t0 = time.time()
        try:
            x = get(url, timeout=600)
            r(f"- {url}: HTTP {x.status_code}, {len(x.content) // 1024} kB, {time.time() - t0:.0f}s")
            if x.status_code != 200:
                continue
            flussi = e1.flussi_sdmx(x.text)
            if not flussi:
                continue
            salva("istat_dataflow.json", flussi)
            utili = e1.filtra(flussi, ["prezzi al consumo", "consumer price", "nic", "foi", "ipca", "armonizz",
                                       "harmonised", "retribuz", "frequenza", "carrello", "contractual"])
            r(f"\ndataflow totali {len(flussi)}, pertinenti {len(utili)}\n")
            r("| codice | versione | nome |\n|---|---|---|")
            for f in utili:
                r(f"| {f['id']} | {f['versione']} | {(f['nome_it'] or f['nome_en'])[:110]} |")
            return
        except Exception as ex:  # noqa: BLE001
            r(f"- {url}: {type(ex).__name__} dopo {time.time() - t0:.0f}s")
        time.sleep(20)                         # limite Istat: 5 richieste al minuto


@sonda("BCE - nuovo dataflow HICP")
def bce_hicp():
    base = "https://data-api.ecb.europa.eu/service/data"
    trovato = None
    for n in range(3, 10):
        chiave = "HICP/M.U2" + "." * n
        x = get(f"{base}/{chiave}", params={"format": "csvdata", "lastNObservations": 1}, timeout=180)
        r(f"- {chiave}: HTTP {x.status_code}")
        if x.status_code == 200 and x.text.strip():
            trovato = n
            break
    if trovato is None:
        return
    for area in ["U2", "IT", "DE", "FR", "ES"]:
        chiave = f"HICP/M.{area}" + "." * trovato
        x = get(f"{base}/{chiave}", params={"format": "csvdata", "lastNObservations": 1}, timeout=180)
        righe = list(csv.DictReader(io.StringIO(x.text))) if x.status_code == 200 else []
        salva(f"bce_hicp_{area}.csv", x.text if righe else "")
        if not righe:
            r(f"\n- {area}: HTTP {x.status_code}, nessuna serie")
            continue
        campi = list(righe[0].keys())
        adj = {}
        for w in righe:
            adj[w.get("ADJUSTMENT", "?")] = adj.get(w.get("ADJUSTMENT", "?"), 0) + 1
        date = sorted({w.get("TIME_PERIOD", "") for w in righe})
        r(f"\n### {area}: {len(righe)} serie; aggiustamento {adj}; ultimi periodi {date[-3:]}")
        if area == "U2":
            r(f"colonne: {', '.join(campi)}")
        speciali = [w for w in righe if w.get("ADJUSTMENT") not in ("N", None, "")
                    or re.search(r"trim|median|supercore|domestic|import|pcci|persistent|cyclical",
                                 (w.get("TITLE") or "").lower())]
        for w in speciali[:120]:
            r(f"- `{w['KEY']}` {(w.get('TITLE') or '')[:100]} | {w.get('TIME_PERIOD')} = {w.get('OBS_VALUE')}")
        time.sleep(1)


@sonda("INSEE - serie di IPC-2025, IPCH-2025, SALAIRES-ACEMO-2017")
def insee():
    for flusso in ["IPC-2025", "IPCH-2025", "SALAIRES-ACEMO-2017"]:
        url = f"https://api.insee.fr/series/BDM/data/{flusso}"
        try:
            x = get(url, params={"lastNObservations": 1}, timeout=240)
        except Exception as ex:  # noqa: BLE001
            r(f"- {flusso}: {type(ex).__name__}")
            continue
        serie = []
        for m in re.finditer(r"<Series\b([^>]*)>(.*?)</Series>", x.text, re.S):
            attr = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            obs = re.findall(r'<Obs\b[^>]*TIME_PERIOD="([^"]+)"[^>]*OBS_VALUE="([^"]*)"', m.group(2))
            attr["ULTIMO"] = obs[-1][0] if obs else ""
            attr["VALORE"] = obs[-1][1] if obs else ""
            serie.append(attr)
        r(f"\n### {flusso}: HTTP {x.status_code}, {len(serie)} serie")
        if not serie:
            r(x.text[:500])
            continue
        campi = sorted({k for s in serie for k in s})
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=campi)
        w.writeheader()
        w.writerows(serie)
        salva(f"insee_{flusso}.csv", buf.getvalue())
        r(f"attributi: {', '.join(campi)}")
        chiave_tit = next((c for c in campi if c.upper().startswith("TITLE_FR")), None)
        scelte = [s for s in serie if chiave_tit and re.search(
            r"ensemble|hors tabac|alimentation|énergie|energie|services|produits manufacturés|sous-jacent|"
            r"salaire mensuel de base", s.get(chiave_tit, ""), re.I)]
        for s in scelte[:60]:
            r(f"- idbank {s.get('IDBANK')}: {s.get(chiave_tit, '')[:120]} | {s['ULTIMO']} = {s['VALORE']}")
        time.sleep(1)


@sonda("INE - serie delle tabelle IPC/IPCA ECOICOP v2 e indicatore anticipato")
def ine():
    base = "https://servicios.ine.es/wstempus/js/ES"
    ops = get(f"{base}/OPERACIONES_DISPONIBLES").json()
    for o in ops:
        if re.search(r"adelant|avance|flash|IPC", f"{o.get('Nombre', '')} {o.get('Codigo', '')}", re.I):
            r(f"- operazione {o.get('Codigo')} (Id {o.get('Id')}): {o.get('Nombre')}")
    tabelle = {"IPC general y grupos": [76125, 76144, 79181, 24077], "IPC clases": [76127],
               "IPC ponderaciones clases": [76158], "IPCA general y grupos": [67256, 67261, 76102, 79188],
               "IPCA clases": [67258, 76104, 79187], "IPCA grupos especiales": [79189, 67260],
               "IPC tasa general": [76134], "IPC grupos especiales": [76133]}
    for nome, ids in tabelle.items():
        for tid in ids:
            try:
                d = get(f"{base}/DATOS_TABLA/{tid}", params={"nult": 1}, timeout=120).json()
            except Exception as ex:  # noqa: BLE001
                r(f"- {nome} {tid}: {type(ex).__name__}")
                continue
            ult = {((s.get("Data") or [{}])[-1].get("Anyo"), (s.get("Data") or [{}])[-1].get("FK_Periodo"))
                   for s in d[:5]} if d else set()
            r(f"\n### {nome} - tabella {tid}: {len(d)} serie, ultimo (anno, periodo) {ult}")
            salva(f"ine_tabla_{tid}.json", d[:400])
            for s in d[:25]:
                dd = (s.get("Data") or [{}])[-1]
                r(f"- {s.get('COD')}: {s.get('Nombre', '')[:110]} | {dd.get('Anyo')}-{dd.get('FK_Periodo')} = "
                  f"{dd.get('Valor')}")
            time.sleep(0.5)


@sonda("Destatis - GENESIS con credenziali")
def destatis():
    usr, pwd = os.environ.get("DESTATIS_USER", "").strip(), os.environ.get("DESTATIS_PASS", "").strip()
    tok = os.environ.get("DESTATIS_TOKEN", "").strip()
    if not (usr or tok):
        r("**secret DESTATIS_USER / DESTATIS_PASS (o DESTATIS_TOKEN) assenti**: registrazione gratuita su "
          "https://www-genesis.destatis.de, poi aggiungili ai secret del repo")
        return
    base = "https://www-genesis.destatis.de/genesisWS/rest/2020"
    h = {"username": tok or usr, "password": "" if tok else pwd}
    x = requests.post(f"{base}/helloworld/logincheck", headers={**e1.HDR, **h}, timeout=60)
    r(f"- logincheck: HTTP {x.status_code} {x.text[:200]}")
    for sel in ["61111*", "61121*", "62321*"]:
        x = requests.post(f"{base}/catalogue/tables", headers={**e1.HDR, **h}, timeout=90,
                          data={"selection": sel, "area": "all", "pagelength": "100", "language": "de"})
        try:
            js = x.json()
        except Exception:  # noqa: BLE001
            r(f"- {sel}: HTTP {x.status_code} {x.text[:200]}")
            continue
        lista = js.get("List") or []
        r(f"\n### {sel}: HTTP {x.status_code}, stato {js.get('Status')}, tabelle {len(lista)}")
        for t in lista[:40]:
            r(f"- {t.get('Code')}: {str(t.get('Content', ''))[:110]}")


if __name__ == "__main__":
    r("# hicp-wrap - fase 1b: sonda mirata")
    r(f"eseguito {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    for s in [bce_hicp, insee, ine, destatis, istat]:
        s()
    salva("rapporto_fonti_2.md", "\n".join(e1._righe))
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_PREVIEW_CHAT_ID", "").strip()
    if tok and chat:
        z = shutil.make_archive("esito_fonti_2", "zip", e1.OUT)
        for p in [os.path.join(e1.OUT, "rapporto_fonti_2.md"), z]:
            with open(p, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{tok}/sendDocument", timeout=120,
                              data={"chat_id": chat, "caption": "hicp-wrap - fase 1b"}, files={"document": f})
