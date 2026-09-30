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
        nov = json.load(open(pn, encoding="utf-8")).get("nuovi", {}) if os.path.exists(pn) else {}
        if a.solo_se_nuovo and not nov:
            print("nessun dato nuovo: niente da pubblicare")
            return
        if not a.evento and nov:
            a.evento = "nuovi dati: " + ", ".join(f"{k.split('|')[0]} {v}" for k, v in sorted(nov.items()))

    ris = motore.calcola(Archivio(cartella), evento={"descrizione": a.evento} if a.evento else None)
    nome = f"inflazione-{ris['ultimo']}"
    os.makedirs(a.uscita, exist_ok=True)
    with open(os.path.join(a.uscita, "pacchetto_dati.json"), "w", encoding="utf-8") as f:
        json.dump(commento.pacchetto(ris), f, ensure_ascii=False, indent=1, default=str)

    testo = None if a.senza_commento else commento.scrivi(ris)
    p_pdf = pdf.costruisci(ris, os.path.join(a.uscita, nome + ".pdf"), commento=testo,
                           cartella_grafici=os.path.join(a.uscita, "grafici"), avviso=avviso)
    p_xls = excel.costruisci(ris, os.path.join(a.uscita, nome + ".xlsx"))
    print(f"scritti {p_pdf} e {p_xls}")
    if a.invia:
        invia([p_pdf, p_xls], f"Inflazione area euro - {a.evento or ris['ultimo']}")


if __name__ == "__main__":
    main()
