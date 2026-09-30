"""
hicp-wrap - programma principale.

  python main.py --esempio                 prova completa su dati sintetici (senza rete)
  python main.py                           usa l'archivio vero in dati/storico
  opzioni: --senza-commento  --invia  --evento "Istat, stima preliminare settembre"

Uscite in uscita/: inflazione-AAAA-MM.pdf e inflazione-AAAA-MM.xlsx
Con --invia li manda sulla chat privata Telegram (TELEGRAM_BOT_TOKEN, TELEGRAM_PREVIEW_CHAT_ID).
"""
import argparse
import json
import os
import sys

import requests

from hicp import commento, excel, motore, pdf
from hicp.archivio import Archivio


def invia(percorsi, didascalia):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_PREVIEW_CHAT_ID", "").strip()
    if not tok or not chat:
        print("[telegram] non configurato")
        return
    for p in percorsi:
        with open(p, "rb") as f:
            x = requests.post(f"https://api.telegram.org/bot{tok}/sendDocument", timeout=180,
                              data={"chat_id": chat, "caption": didascalia}, files={"document": f})
        print(f"[telegram] {os.path.basename(p)}: HTTP {x.status_code}")


NOMI = {"EA": "area euro", "IT": "Italia", "DE": "Germania", "FR": "Francia", "ES": "Spagna"}
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


def descrivi(nov, prel):
    """Titolo dell'uscita: 'stima preliminare di settembre 2026: Italia, Spagna; ...'."""
    gruppi = {}
    for k, mese in nov.items():
        area, mis = k.split("|")
        tipo = "stima preliminare" if prel.get(k) else ("CPI nazionale" if mis == "cpi_headline" else "HICP")
        gruppi.setdefault((tipo, mese), set()).add(NOMI.get(area, area))
    parti = []
    for (tipo, mese), aree in sorted(gruppi.items(), key=lambda t: (t[0][1], t[0][0]), reverse=True):
        y, m = mese.split("-")
        parti.append(f"{tipo} di {MESI[int(m) - 1]} {y}: {', '.join(sorted(aree))}")
    return "; ".join(parti)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esempio", action="store_true")
    ap.add_argument("--archivio", default=os.path.join("dati", "storico"))
    ap.add_argument("--uscita", default="uscita")
    ap.add_argument("--senza-commento", action="store_true")
    ap.add_argument("--invia", action="store_true")
    ap.add_argument("--evento", default="")
    ap.add_argument("--solo-se-nuovo", action="store_true", help="esce senza pubblicare se non ci sono dati nuovi")
    a = ap.parse_args()

    avviso = None
    cartella = a.archivio
    if a.esempio:
        import genera_esempio
        cartella = os.path.join("dati", "esempio")
        genera_esempio.main(cartella)
        avviso = "PROVA SU DATI SINTETICI - I NUMERI NON SONO DATI VERI"
    if not os.path.exists(os.path.join(cartella, "serie.csv")):
        sys.exit(f"archivio vuoto: {cartella}")

    if not a.esempio:
        pn = os.path.join(cartella, "novita.json")
        info = json.load(open(pn, encoding="utf-8")) if os.path.exists(pn) else {}
        nov, prel = info.get("nuovi", {}), info.get("preliminare", {})
        if a.solo_se_nuovo and not nov:
            print("nessun dato nuovo: niente da pubblicare")
            return
        if not a.evento and nov:
            a.evento = descrivi(nov, prel)

    ris = motore.calcola(Archivio(cartella), evento={"descrizione": a.evento} if a.evento else None)
    nome = f"inflazione-{ris['ultimo']}"
    os.makedirs(a.uscita, exist_ok=True)
    with open(os.path.join(a.uscita, "pacchetto_dati.json"), "w", encoding="utf-8") as f:
        json.dump(commento.pacchetto(ris), f, ensure_ascii=False, indent=1, default=str)

    testo = None if a.senza_commento else commento.scrivi(ris)
    pl = os.path.join(cartella, "log_fonti.txt")
    if not a.esempio and os.path.exists(pl):
        with open(pl, "a", encoding="utf-8") as f:
            f.write(f"\n[commento] {'saltato (--senza-commento)' if a.senza_commento else commento.ESITO}\n")
    p_pdf = pdf.costruisci(ris, os.path.join(a.uscita, nome + ".pdf"), commento=testo,
                           cartella_grafici=os.path.join(a.uscita, "grafici"), avviso=avviso)
    p_xls = excel.costruisci(ris, os.path.join(a.uscita, nome + ".xlsx"))
    print(f"scritti {p_pdf} e {p_xls}")
    if a.invia:
        allegati = [p_pdf, p_xls]
        pl = os.path.join(cartella, "log_fonti.txt")
        if not a.esempio and os.path.exists(pl):
            allegati.append(pl)                       # diagnostica delle fonti, utile nelle prime settimane
        invia(allegati, f"Inflazione area euro - {a.evento or ris['ultimo']}"[:1000])


if __name__ == "__main__":
    main()
