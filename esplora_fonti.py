"""
hicp-wrap - FASE 1: esplorazione delle fonti.

Non scarica ancora serie storiche: interroga i cataloghi di ciascun istituto
e scrive in esito/ quali dataset, codici e profondita' storiche esistono
davvero, cosi' la mappa delle serie si costruisce su codici verificati e non
su codici ricordati.

Fonti: Eurostat, BCE (Data Portal), Istat, INE, INSEE, Destatis.
Uscita: esito/rapporto_fonti.md + file di dettaglio (json/csv) + esito.zip,
inviato sulla chat privata Telegram se i secret sono presenti.

Ogni sonda e' isolata: se una fonte non risponde lo si scrive nel rapporto
e si passa alla successiva.
"""
import csv
import io
import json
import os
import re
import shutil
import time
import traceback

import requests

OUT = "esito"
TIMEOUT = 90
HDR = {"User-Agent": "Mozilla/5.0 (hicp-wrap; esplorazione fonti statistiche)"}
PAESI = ["IT", "DE", "FR", "ES"]

os.makedirs(OUT, exist_ok=True)
_righe = []


def r(s=""):
    print(s, flush=True)
    _righe.append(s)


def salva(nome, obj):
    p = os.path.join(OUT, nome)
    with open(p, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    return p


def get(url, **kw):
    h = dict(HDR)
    h.update(kw.pop("headers", {}))
    return requests.get(url, headers=h, timeout=kw.pop("timeout", TIMEOUT), **kw)


def sonda(titolo):
    """Decoratore: isola ogni sonda e registra l'esito nel rapporto."""
    def deco(fn):
        def wrap():
            r(f"\n## {titolo}\n")
            t0 = time.time()
            try:
                fn()
                r(f"\n_durata {time.time() - t0:.0f}s_")
            except Exception as e:  # noqa: BLE001
                r(f"**ERRORE**: {type(e).__name__}: {e}")
                r("```\n" + traceback.format_exc()[-1500:] + "\n```")
        return wrap
    return deco


def flussi_sdmx(xml):
    """Estrae (id, nome) dai Dataflow di un messaggio SDMX-ML 2.1."""
    out = []
    for m in re.finditer(r"<(?:\w+:)?Dataflow\b([^>]*)>(.*?)</(?:\w+:)?Dataflow>", xml, re.S):
        attr, corpo = m.group(1), m.group(2)
        mid = re.search(r'\bid="([^"]+)"', attr)
        if not mid:
            continue
        nomi = dict(re.findall(r'<(?:\w+:)?Name[^>]*xml:lang="(\w+)"[^>]*>(.*?)</(?:\w+:)?Name>', corpo, re.S))
        ver = re.search(r'\bversion="([^"]+)"', attr)
        out.append({"id": mid.group(1), "versione": ver.group(1) if ver else "",
                    "nome_en": nomi.get("en", ""), "nome_it": nomi.get("it", ""),
                    "nome_fr": nomi.get("fr", ""), "nome_de": nomi.get("de", "")})
    return out


def filtra(lista, parole, campi=("id", "nome_en", "nome_it", "nome_fr", "nome_de")):
    parole = [p.lower() for p in parole]
    return [x for x in lista if any(p in str(x.get(c, "")).lower() for c in campi for p in parole)]


# ----------------------------------------------------------------- EUROSTAT
EST = "https://ec.europa.eu/eurostat/api/dissemination"


def jsonstat_riassunto(js):
    dims = js.get("id", [])
    out = {"dimensioni": {}}
    for d in dims:
        cat = js["dimension"][d]["category"]
        idx = cat.get("index", {})
        codici = sorted(idx, key=lambda k: idx[k]) if isinstance(idx, dict) else list(idx)
        out["dimensioni"][d] = {"n": len(codici), "codici": codici}
    return out


@sonda("Eurostat - catalogo HICP e salari")
def eurostat():
    x = get(f"{EST}/sdmx/2.1/dataflow/ESTAT/all/latest?detail=allstubs", timeout=180)
    r(f"catalogo dataflow: HTTP {x.status_code}, {len(x.content) // 1024} kB")
    x.raise_for_status()
    tutti = flussi_sdmx(x.text)
    hicp = [f for f in tutti if "HICP" in f["id"].upper()]
    salva("eurostat_dataflow_hicp.json", hicp)
    r(f"dataflow totali {len(tutti)}, con HICP nel codice: {len(hicp)}\n")
    r("| codice | nome |\n|---|---|")
    for f in hicp:
        r(f"| {f['id']} | {f['nome_en'][:90]} |")

    # campione di ogni dataset HICP: dimensioni, codici, ultimo periodo, profondita'
    dettaglio = {}
    r("\n### Struttura dei dataset HICP (campione Italia)\n")
    for f in hicp[:40]:
        cod = f["id"].lower()
        try:
            y = get(f"{EST}/statistics/1.0/data/{cod}", params={"geo": "IT", "lastTimePeriod": 1})
            if y.status_code != 200:
                r(f"- {cod}: HTTP {y.status_code}")
                continue
            info = jsonstat_riassunto(y.json())
            dimcoicop = next((d for d in info["dimensioni"] if "coicop" in d.lower()), None)
            ultimo = info["dimensioni"].get("time", {}).get("codici", ["?"])[-1]
            prof = ""
            if dimcoicop:
                primo = info["dimensioni"][dimcoicop]["codici"][0]
                par = {"geo": "IT", dimcoicop: primo}
                if "unit" in info["dimensioni"]:
                    par["unit"] = info["dimensioni"]["unit"]["codici"][0]
                z = get(f"{EST}/statistics/1.0/data/{cod}", params=par)
                if z.status_code == 200:
                    t = jsonstat_riassunto(z.json())["dimensioni"].get("time", {}).get("codici", [])
                    if t:
                        prof = f", storia {t[0]} -> {t[-1]} ({len(t)} periodi, serie {primo})"
            dims = ", ".join(f"{d}={v['n']}" for d, v in info["dimensioni"].items())
            r(f"- **{cod}**: ultimo {ultimo}; {dims}{prof}")
            if dimcoicop:
                cc = info["dimensioni"][dimcoicop]["codici"]
                r(f"  - codici {dimcoicop} (primi 12): {', '.join(cc[:12])}")
            if "unit" in info["dimensioni"]:
                r(f"  - unit: {', '.join(info['dimensioni']['unit']['codici'])}")
            dettaglio[cod] = info
            time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            r(f"- {cod}: errore {type(e).__name__}: {e}")
    salva("eurostat_struttura_hicp.json", dettaglio)

    # aggancio alla classificazione BCE: i codici a 6 cifre del paper esistono?
    bce = [row["codice"] for row in csv.DictReader(open("dati/classificazione_bce_2026.csv", encoding="utf-8"), delimiter=";")]
    r("\n### Aggancio voci della tabella BCE ai codici Eurostat\n")
    for cod, info in dettaglio.items():
        dimc = next((d for d in info["dimensioni"] if "coicop" in d.lower()), None)
        if not dimc:
            continue
        codici = info["dimensioni"][dimc]["codici"]
        norm = {re.sub(r"\D", "", c): c for c in codici}
        trovati = [b for b in bce if b in norm or b.rstrip("0") in norm or b[:4] in norm]
        r(f"- {cod}: {len(trovati)}/{len(bce)} voci BCE riconoscibili fra {len(codici)} codici")

    # salari e costo del lavoro
    r("\n### Salari e costo del lavoro\n")
    for cod in ["namq_10_gdp", "namq_10_a10", "namq_10_a10_e", "lc_lci_r2_q", "ei_lmlc_q"]:
        try:
            y = get(f"{EST}/statistics/1.0/data/{cod}", params={"geo": "IT", "lastTimePeriod": 1})
            if y.status_code != 200:
                r(f"- {cod}: HTTP {y.status_code}")
                continue
            info = jsonstat_riassunto(y.json())
            ult = info["dimensioni"].get("time", {}).get("codici", ["?"])[-1]
            dims = "; ".join(f"{d}: {', '.join(v['codici'][:8])}{'...' if v['n'] > 8 else ''}"
                             for d, v in info["dimensioni"].items() if d not in ("geo", "time", "freq"))
            r(f"- **{cod}** ultimo {ult} - {dims}")
        except Exception as e:  # noqa: BLE001
            r(f"- {cod}: errore {e}")
    altri = filtra(tutti, ["compensation", "labour cost", "wage"])
    salva("eurostat_dataflow_salari.json", altri)
    r(f"\nAltri dataflow su salari/costo del lavoro: {len(altri)} (in eurostat_dataflow_salari.json)")


# ---------------------------------------------------------------------- BCE
ECB = "https://data-api.ecb.europa.eu/service"
PAROLE_SOTTOSTANTE = ["supercore", "domestic", "trimmed", "median", "pcci", "persistent",
                      "excluding", "cyclical", "import", "seasonally", "hicpx", "core"]


def ecb_csv(chiave, **par):
    par = {"format": "csvdata", **par}
    x = get(f"{ECB}/data/{chiave}", params=par, timeout=180)
    if x.status_code != 200:
        return x.status_code, []
    return 200, list(csv.DictReader(io.StringIO(x.text)))


@sonda("BCE Data Portal - HICP destagionalizzato, misure sottostanti, salari")
def bce():
    x = get(f"{ECB}/dataflow", timeout=120)
    r(f"catalogo dataflow: HTTP {x.status_code}")
    x.raise_for_status()
    flussi = flussi_sdmx(x.text)
    salva("bce_dataflow.json", flussi)
    utili = filtra(flussi, ["icp", "inflation", "price", "wage", "compensation", "negotiat",
                            "tracker", "labour", "underlying"])
    r(f"dataflow totali {len(flussi)}, pertinenti {len(utili)}\n")
    r("| codice | nome |\n|---|---|")
    for f in utili:
        r(f"| {f['id']} | {f['nome_en'][:90]} |")

    # tutte le serie ICP area euro (ultima osservazione) con titolo
    st, righe = ecb_csv("ICP/M.U2....", lastNObservations=1)
    r(f"\n### ICP area euro: HTTP {st}, {len(righe)} serie")
    if righe:
        campi = list(righe[0].keys())
        r(f"colonne: {', '.join(campi)}")
        salva("bce_icp_U2.csv", _csv(righe))
        tit = next((c for c in campi if c.upper() == "TITLE"), None)
        chiave = next((c for c in campi if c.upper() == "KEY"), campi[0])
        voci = {}
        for w in righe:
            t = (w.get(tit) or "") if tit else ""
            item = w.get("ICP_ITEM", "")
            testo = f"{t} {item}".lower()
            if any(p in testo for p in PAROLE_SOTTOSTANTE) or not item[:1].isdigit():
                voci[w[chiave]] = f"{t[:110]} | {w.get('TIME_PERIOD', '')} = {w.get('OBS_VALUE', '')}"
        r(f"\nserie con voce non numerica o parole chiave (misure speciali/sottostanti): {len(voci)}\n")
        for k in sorted(voci)[:250]:
            r(f"- `{k}` {voci[k]}")
        adj = {}
        for w in righe:
            adj[w.get("ADJUSTMENT", "?")] = adj.get(w.get("ADJUSTMENT", "?"), 0) + 1
        r(f"\nserie per codice di aggiustamento (N=grezze, S/Y=destagionalizzate): {adj}")

    # destagionalizzate per paese
    for p in PAESI:
        st, righe = ecb_csv(f"ICP/M.{p}....", lastNObservations=1)
        if not righe:
            r(f"\n- {p}: HTTP {st}, nessuna serie")
            continue
        sa = [w for w in righe if w.get("ADJUSTMENT") not in ("N", None, "")]
        voci_sa = sorted({w.get("ICP_ITEM", "") for w in sa})
        r(f"\n- **{p}**: {len(righe)} serie ICP, destagionalizzate {len(sa)}; voci SA: {', '.join(voci_sa[:40])}")
        salva(f"bce_icp_{p}.csv", _csv(righe))
        time.sleep(1)

    # salari: flussi con 'wage' o 'negotiat' nel nome - campione area euro
    r("\n### Salari (campione)\n")
    for f in filtra(flussi, ["wage", "negotiat", "compensation", "tracker"], campi=("id", "nome_en")):
        st, righe = ecb_csv(f["id"], lastNObservations=1)
        if st != 200:
            r(f"- {f['id']}: HTTP {st}")
            continue
        salva(f"bce_{f['id']}.csv", _csv(righe))
        aree = sorted({w.get("REF_AREA", "") for w in righe})
        r(f"- **{f['id']}** ({f['nome_en'][:60]}): {len(righe)} serie; aree: {', '.join(aree[:30])}")
        time.sleep(1)
    for k in ["STS/Q.U2.N.INWR.000000.3.ANR"]:
        st, righe = ecb_csv(k, lastNObservations=4)
        r(f"- salari negoziali {k}: HTTP {st}, " + ", ".join(f"{w.get('TIME_PERIOD')}={w.get('OBS_VALUE')}" for w in righe))


def _csv(righe):
    if not righe:
        return ""
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=list(righe[0].keys()), extrasaction="ignore")
    w.writeheader()
    w.writerows(righe)
    return s.getvalue()


# -------------------------------------------------------------------- ISTAT
@sonda("Istat - catalogo esploradati (una sola chiamata: limite 5 query/minuto)")
def istat():
    x = get("https://esploradati.istat.it/SDMXWS/rest/dataflow/IT1", timeout=180)
    r(f"catalogo dataflow: HTTP {x.status_code}, {len(x.content) // 1024} kB")
    x.raise_for_status()
    flussi = flussi_sdmx(x.text)
    salva("istat_dataflow.json", flussi)
    utili = filtra(flussi, ["prezzi al consumo", "consumer price", "nic", "foi", "ipca",
                            "armonizz", "harmonised", "retribuz", "wage", "frequenza", "carrello"])
    r(f"dataflow totali {len(flussi)}, pertinenti {len(utili)}\n")
    r("| codice | versione | nome |\n|---|---|---|")
    for f in utili:
        r(f"| {f['id']} | {f['versione']} | {(f['nome_it'] or f['nome_en'])[:100]} |")


# ---------------------------------------------------------------------- INE
@sonda("INE - operazioni e tabelle (API Tempus3)")
def ine():
    base = "https://servicios.ine.es/wstempus/js/ES"
    x = get(f"{base}/OPERACIONES_DISPONIBLES")
    r(f"operazioni: HTTP {x.status_code}")
    x.raise_for_status()
    ops = x.json()
    salva("ine_operaciones.json", ops)
    utili = [o for o in ops if re.search(r"precios de consumo|IPC|salari|coste laboral",
                                         f"{o.get('Nombre', '')} {o.get('Codigo', '')}", re.I)]
    r(f"operazioni totali {len(ops)}, pertinenti {len(utili)}\n")
    for o in utili:
        r(f"- **{o.get('Codigo')}** (Id {o.get('Id')}): {o.get('Nombre')}")
    tabelle = {}
    for o in utili[:8]:
        y = get(f"{base}/TABLAS_OPERACION/{o.get('Id')}")
        if y.status_code != 200:
            r(f"  - tabelle {o.get('Codigo')}: HTTP {y.status_code}")
            continue
        tt = y.json()
        tabelle[o.get("Codigo")] = tt
        r(f"\n  Tabelle di {o.get('Codigo')} ({len(tt)}):")
        for t in tt[:40]:
            r(f"  - Id {t.get('Id')}: {t.get('Nombre')}")
        time.sleep(0.5)
    salva("ine_tablas.json", tabelle)


# -------------------------------------------------------------------- INSEE
@sonda("INSEE - catalogo BDM (SDMX)")
def insee():
    candidati = ["https://api.insee.fr/series/BDM/dataflow/FR1/all",
                 "https://api.insee.fr/series/BDM/V1/dataflow/FR1/all",
                 "https://bdm.insee.fr/series/sdmx/dataflow/FR1/all"]
    flussi, usato = [], None
    for u in candidati:
        try:
            x = get(u, timeout=120)
            r(f"- {u}: HTTP {x.status_code}")
            if x.status_code == 200:
                flussi = flussi_sdmx(x.text)
                if flussi:
                    usato = u
                    break
        except Exception as e:  # noqa: BLE001
            r(f"- {u}: errore {type(e).__name__}")
    if not flussi:
        r("**nessun endpoint INSEE ha restituito il catalogo**")
        return
    r(f"\nendpoint valido: {usato}")
    salva("insee_dataflow.json", flussi)
    utili = filtra(flussi, ["ipc", "ipch", "prix-conso", "prix a la consommation",
                            "prix à la consommation", "consumer price", "salaire", "smb", "wage"])
    r(f"dataflow totali {len(flussi)}, pertinenti {len(utili)}\n")
    r("| codice | nome |\n|---|---|")
    for f in utili:
        r(f"| {f['id']} | {(f['nome_fr'] or f['nome_en'])[:100]} |")


# ----------------------------------------------------------------- DESTATIS
@sonda("Destatis - GENESIS-Online (API 2020)")
def destatis():
    base = "https://www-genesis.destatis.de/genesisWS/rest/2020"
    tok = os.environ.get("DESTATIS_TOKEN", "").strip()
    usr = os.environ.get("DESTATIS_USER", "").strip()
    pwd = os.environ.get("DESTATIS_PASS", "").strip()
    credenziali = []
    if tok:
        credenziali.append(("token", tok, ""))
    if usr:
        credenziali.append(("utente", usr, pwd))
    credenziali.append(("ospite GAST", "GAST", "GAST"))
    for etichetta, u, p in credenziali:
        for sel in ["61111*", "61121*"]:
            dati = {"selection": sel, "area": "all", "pagelength": "200", "language": "de"}
            try:
                x = requests.post(f"{base}/catalogue/tables", data=dati, timeout=TIMEOUT,
                                  headers={**HDR, "username": u, "password": p,
                                           "Content-Type": "application/x-www-form-urlencoded"})
                modo = "POST"
                if x.status_code != 200 or '"Code":0' not in x.text.replace(" ", ""):
                    x2 = get(f"{base}/catalogue/tables", params={**dati, "username": u, "password": p})
                    if x2.status_code == 200:
                        x, modo = x2, "GET"
                js = x.json() if x.headers.get("content-type", "").startswith("application/json") else {}
                stato = js.get("Status", {})
                lista = js.get("List") or []
                r(f"- {etichetta} {modo} {sel}: HTTP {x.status_code}, stato {stato.get('Code')} "
                  f"'{str(stato.get('Content', ''))[:120]}', tabelle {len(lista)}")
                if lista:
                    salva(f"destatis_{sel.strip('*')}.json", lista)
                    for t in lista[:30]:
                        r(f"  - {t.get('Code')}: {str(t.get('Content', ''))[:100]}")
            except Exception as e:  # noqa: BLE001
                r(f"- {etichetta} {sel}: errore {type(e).__name__}: {e}")
        if any(f.startswith("destatis_") for f in os.listdir(OUT)):
            r(f"\ncredenziali funzionanti: **{etichetta}**")
            return
    r("\n**nessuna credenziale ha aperto il catalogo**: serve registrazione gratuita su "
      "genesis.destatis.de e i secret DESTATIS_USER / DESTATIS_PASS (o DESTATIS_TOKEN)")


# ---------------------------------------------------- CLASSIFICAZIONE BCE
@sonda("Controllo classificazione BCE (Tabella 4, Statistics Paper 54)")
def classificazione():
    rr = list(csv.DictReader(open("dati/classificazione_bce_2026.csv", encoding="utf-8"), delimiter=";"))
    dom = [x for x in rr if x["domestica"] == "1"]
    sc = [x for x in rr if x["supercore"] == "1"]
    w = lambda xs: sum(float(x["peso_hicpx_2026"]) for x in xs)  # noqa: E731
    r(f"voci {len(rr)} (atteso 118), domestiche {len(dom)} (atteso 53), Supercore {len(sc)} (atteso 29)")
    r(f"peso domestiche {w(dom):.1f}% (paper 56,5% con pesi 2025), Supercore {w(sc):.1f}% (paper 37,5%)")


def invia_telegram():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_PREVIEW_CHAT_ID", "").strip()
    if not tok or not chat:
        print("Telegram non configurato: esito solo negli artifact")
        return
    zipf = shutil.make_archive("esito_fonti", "zip", OUT)
    for p, cap in [(os.path.join(OUT, "rapporto_fonti.md"), "hicp-wrap - fase 1: rapporto fonti"),
                   (zipf, "dettaglio completo (json/csv)")]:
        with open(p, "rb") as f:
            x = requests.post(f"https://api.telegram.org/bot{tok}/sendDocument",
                              data={"chat_id": chat, "caption": cap}, files={"document": f}, timeout=120)
        print(f"Telegram {os.path.basename(p)}: HTTP {x.status_code}")


if __name__ == "__main__":
    r("# hicp-wrap - fase 1: esplorazione delle fonti")
    r(f"eseguito {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    for s in [classificazione, eurostat, bce, istat, ine, insee, destatis]:
        s()
    salva("rapporto_fonti.md", "\n".join(_righe))
    invia_telegram()
