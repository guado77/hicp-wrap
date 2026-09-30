"""
Commento con Claude Opus.

Il modello riceve due cose separate:
- PACCHETTO DATI: i numeri calcolati dal motore. Sono gli UNICI numeri citabili.
- COMUNICATI: il testo dei comunicati degli istituti (Istat, Destatis, INSEE, INE, Eurostat),
  per riprendere come ciascuno legge il proprio dato. Servono a spiegare, non a dare numeri.
"""
import json
import os

import pandas as pd
import requests

from . import config

MODELLO = os.environ.get("ANTHROPIC_MODEL", "").strip() or "claude-opus-4-8"

ISTRUZIONI = """Sei un economista che scrive il commento mensile sull'inflazione nell'area euro
per un analista finanziario esperto. Scrivi in italiano, prosa densa e precisa, niente elenchi puntati.

REGOLE SUI NUMERI
- Cita SOLO numeri presenti nel PACCHETTO DATI. Non arrotondare in modo diverso, non inventare.
- I comunicati degli istituti servono a riprendere la LORO lettura del dato (quali voci hanno spinto,
  quali frenato, come descrivono il trend). Puoi citare le loro spiegazioni, non i loro numeri se non
  coincidono con il pacchetto.
- Se un'informazione manca, non supplirla: scrivi che il dato non e' disponibile.

STRUTTURA (usa esattamente questi titoli, ciascuno preceduto da "## ")
## Il dato appena uscito
Cosa e' uscito (paese, preliminare o definitivo), variazioni mensile e annua, confronto col mese
prima, e cosa dice l'istituto che lo pubblica.
## Momentum e direzione del trend
3m/3m annualizzato contro variazione annua: se il momentum sta sopra l'annua il trend accelera,
se sta sotto rallenta. Distingui headline e core, e paese per paese.
## Dove si sta allargando l'inflazione
Distribuzione delle voci per fasce (per peso e per numero), voci piu' calde, e per l'Italia
carrello della spesa e acquisti ad alta, media e bassa frequenza. Di' quali categorie mostrano
piu' contagio e cosa vuol dire per la spesa delle famiglie.
## Energia, alimentari, trasporti, servizi
Un paragrafo per categoria, confrontando i paesi.
## Inflazione sottostante
Domestica contro importata, Supercore, medie troncate e mediana. Per l'area euro richiama la
taratura sulle serie BCE; per i paesi ricorda che sono ricostruzioni con i flag BCE.
## Potere d'acquisto e salari
Cosa valgono oggi 100 euro di gennaio 2020 e di gennaio 2024, e se i salari hanno recuperato.
## Fine anno: scenari ed effetto base
Leggi gli scenari: la distanza fra 'Neutro 1 anno' e gli altri misura quanto conta l'effetto base.
Di' quale scenario e' coerente con il momentum attuale e dove porterebbe l'inflazione a fine orizzonte.

Mai raccomandazioni di investimento."""


def _r(x, d=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return round(float(x), d)


def pacchetto(ris):
    out = {"evento": ris.get("evento"), "ultimo_mese": ris["ultimo"], "aree": {}}
    for area, a in ris["aree"].items():
        x = {"nome": config.AREE[area], "misure": {}, "proiezioni_fine_orizzonte": {}}
        for mis, r in a["riepilogo"].items():
            x["misure"][config.MISURE.get(mis, mis)] = {
                "m/m %": _r(r["mm"]), "a/a %": _r(r["aa"]), "a/a mese prima %": _r(r["aa_prec"]),
                "3m/3m annualizzato %": _r(r["mom"]),
                "potere d'acquisto": {b: {"prezzi +%": _r(v["prezzi"], 1), "valore oggi di 100 euro": _r(v["cento_euro"], 1)}
                                      for b, v in r["potere"].items()},
            }
        for mis, p in a["proiezioni"].items():
            x["proiezioni_fine_orizzonte"][config.MISURE.get(mis, mis)] = {
                "fino a": str(p["fine"]),
                **{config.SCENARI_BREVI[k]: _r(v) for k, v in p["a_fine"].items()}}
        if a.get("distribuzione_macro"):
            x["distribuzione_voci_%_per_peso"] = {g: {f: _r(v, 1) for f, v in d["peso"].items()}
                                                   for g, d in a["distribuzione_macro"].items()}
            x["distribuzione_voci_%_per_numero_totale"] = {f: _r(v, 1) for f, v in
                                                           a["distribuzione_macro"]["Totale"]["n"].items()}
            x["voci_piu_calde_a/a"] = a["voci_estreme"]["alte"]
            sq = a["storico_quote"]
            if len(sq) > 3:
                x["quota_paniere_oltre_3%_oggi_e_3_mesi_fa"] = [
                    _r(sq.iloc[-1]["oltre 5%"] + sq.iloc[-1]["3-5%"], 1),
                    _r(sq.iloc[-4]["oltre 5%"] + sq.iloc[-4]["3-5%"], 1)]
        if a.get("ricostruite"):
            x["sottostanti_a/a %"] = {}
            for k, s in a["ricostruite"].items():
                if k in ("domestica", "importata", "supercore", "non_supercore"):
                    aa = (s / s.shift(12) - 1) * 100
                    x["sottostanti_a/a %"][config.SOTTOSTANTI[k].split(" (")[0]] = {
                        "oggi": _r(aa.iloc[-1]), "3 mesi fa": _r(aa.iloc[-4])}
            t = a["troncate"]
            if not t.empty:
                x["troncate_e_mediana_a/a %"] = {config.SOTTOSTANTI[k]: _r(t[k].iloc[-1]) for k in t.columns}
            x["ricostruzione"] = "misura BCE" if area == "EA" else "ricostruzione con flag BCE dell'area euro"
        if a.get("taratura_bce"):
            x["taratura_su_serie_BCE_scarto_medio_pp"] = {k: _r(v["scarto_medio"]) for k, v in
                                                         a["taratura_bce"].items() if v}
        sal = {}
        for mis, d in (a.get("salari") or {}).items():
            t = d["tabella"]
            if t.empty:
                continue
            sal[mis] = {"periodo": str(t.index[-1]), "salari nominali a/a %": _r(t["salari_nominali"].iloc[-1]),
                        "salari reali a/a %": _r(t["salari_reali"].iloc[-1]),
                        "cumulato da gen 2020": {k: _r(v, 1) for k, v in d["cumulato"].get("gen 2020", {}).items()
                                                 if k != "fino_a"}}
        if sal:
            x["salari"] = sal
        out["aree"][area] = x
    return out


ESITO = ""


def scrivi(ris, comunicati=None):
    """Restituisce il testo del commento, oppure None se il modello non risponde."""
    chiave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    global ESITO
    if not chiave:
        ESITO = "ANTHROPIC_API_KEY assente nei secret del repo"
        print(f"[commento] {ESITO}")
        return None
    dati = json.dumps(pacchetto(ris), ensure_ascii=False, indent=1)
    com = "\n\n".join(f"--- {c['fonte']} - {c['titolo']} ---\n{c['testo'][:12000]}" for c in (comunicati or []))
    messaggio = f"PACCHETTO DATI (unici numeri citabili):\n{dati}\n\nCOMUNICATI DEGLI ISTITUTI:\n{com or '(nessuno)'}"
    try:
        x = requests.post("https://api.anthropic.com/v1/messages", timeout=600, headers={
            "x-api-key": chiave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODELLO, "max_tokens": 8000, "system": ISTRUZIONI,
                  "messages": [{"role": "user", "content": messaggio}]})
        if x.status_code != 200:
            ESITO = f"modello {MODELLO}: HTTP {x.status_code} {x.text[:300]}"
            print(f"[commento] {ESITO}")
            return None
        ESITO = f"ok, modello {MODELLO}"
        return "".join(b.get("text", "") for b in x.json().get("content", []) if b.get("type") == "text")
    except Exception as e:  # noqa: BLE001
        ESITO = f"modello {MODELLO}: {type(e).__name__}: {e}"
        print(f"[commento] {ESITO}")
        return None
