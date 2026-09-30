"""
PDF a caratteri grandi: corpo 16 pt, tabelle 13 pt, testo allineato a sinistra,
alto contrasto, grafici a tutta larghezza con testo ingrandito.
"""
import os

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import config
from .calcoli import var_a
from .grafici import COLORI_AREA, Grafici

BLU = colors.HexColor("#08306B")
GRIGIO = colors.HexColor("#EFEFEF")
LARGHEZZA = A4[0] - 3.2 * cm

S = {
    "titolo": ParagraphStyle("titolo", fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=BLU),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=25, textColor=BLU,
                         spaceBefore=6, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.black,
                         spaceBefore=12, spaceAfter=6),
    "corpo": ParagraphStyle("corpo", fontName="Helvetica", fontSize=12.5, leading=17, alignment=TA_LEFT,
                            spaceAfter=7),
    "nota": ParagraphStyle("nota", fontName="Helvetica", fontSize=10.5, leading=14, alignment=TA_LEFT,
                           textColor=colors.HexColor("#222222"), spaceAfter=6),
    "cella": ParagraphStyle("cella", fontName="Helvetica", fontSize=11, leading=13.5),
    "cella_b": ParagraphStyle("cella_b", fontName="Helvetica-Bold", fontSize=11, leading=13.5,
                              textColor=colors.white),
    "avviso": ParagraphStyle("avviso", fontName="Helvetica-Bold", fontSize=13, leading=17,
                             textColor=colors.HexColor("#B2182B"), spaceAfter=8),
}


def f(x, d=1, segno=False):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "n.d."
    if round(x, d) == 0:
        x = 0.0
    t = f"{x:+.{d}f}" if segno and x != 0 else f"{x:.{d}f}"
    return t.replace(".", ",")


def tabella(righe, larghezze=None, prima_sx=True):
    dati = [[Paragraph(str(c), S["cella_b"] if i == 0 else S["cella"]) for c in r] for i, r in enumerate(righe)]
    n = len(righe[0])
    if larghezze is None:
        prima = 0.34 if n > 2 else 0.6
        larghezze = [LARGHEZZA * prima] + [LARGHEZZA * (1 - prima) / (n - 1)] * (n - 1)
    t = Table(dati, colWidths=larghezze, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), BLU),
          ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#888888")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i in range(2, len(righe), 2):
        st.append(("BACKGROUND", (0, i), (-1, i), GRIGIO))
    t.setStyle(TableStyle(st))
    return t


def img(p, larghezza=LARGHEZZA):
    from PIL import Image as PImg
    w, h = PImg.open(p).size
    return Image(p, width=larghezza, height=larghezza * h / w)


def _piede(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 11)
    canvas.drawString(1.6 * cm, 1.0 * cm, "Inflazione area euro - wrap")
    canvas.drawRightString(A4[0] - 1.6 * cm, 1.0 * cm, f"pagina {doc.page}")
    canvas.restoreState()


def _nome_mese(p):
    mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
            "settembre", "ottobre", "novembre", "dicembre"]
    p = pd.Period(p, freq="M")
    return f"{mesi[p.month - 1]} {p.year}"


def _mese_breve(p, prel=False):
    if not p:
        return "n.d."
    m = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
    q = pd.Period(p, freq="M")
    return f"{m[q.month - 1]} {q.year % 100:02d}" + (" p" if prel else "")


def costruisci(ris, percorso, commento=None, cartella_grafici="uscita/grafici", avviso=None):
    G = Grafici(cartella_grafici)
    aree = ris["aree"]
    st = []
    ev = ris.get("evento") or {}

    # --------------------------------------------------------------- copertina
    st.append(Paragraph("Inflazione nell'area euro", S["titolo"]))
    st.append(Spacer(1, 6))
    sott = f"Dati aggiornati a {_nome_mese(ris['ultimo'])}"
    if ev:
        sott += f" - uscita: {ev.get('descrizione', '')}"
    st.append(Paragraph(sott, S["h2"]))
    if avviso:
        st.append(Paragraph(avviso, S["avviso"]))
    st.append(Spacer(1, 8))
    righe = [["Area", "Mese", "a/a", "m/m", "Core a/a", "3m/3m", "Fine anno*"]]
    for a, x in aree.items():
        h, c = x["riepilogo"].get("hicp_headline", {}), x["riepilogo"].get("hicp_core", {})
        pr = x["proiezioni"].get("hicp_headline", {}).get("a_fine", {})
        righe.append([config.AREE[a], _mese_breve(h.get("ultimo"), h.get("preliminare")), f(h.get("aa")),
                      f(h.get("mm"), segno=True), f(c.get("aa")), f(h.get("mom")),
                      f"{f(pr.get('momentum'))} / {f(pr.get('neutro_1a'))}"])
    st.append(tabella(righe, [LARGHEZZA * 0.19, LARGHEZZA * 0.15] + [LARGHEZZA * 0.11] * 4 +
                      [LARGHEZZA * 0.22]))
    st.append(Paragraph("Valori in %, HICP. Mese con p = stima preliminare dell'istituto nazionale, "
                        "applicata all'ultimo indice Eurostat. Momentum = variazione della media degli ultimi 3 mesi sui 3 "
                        "precedenti, annualizzata, su serie destagionalizzata. *Inflazione annua a fine "
                        "orizzonte: scenario momentum / scenario con variazione annua invariata.", S["nota"]))
    st.append(img(G.linee({config.AREE[a]: x["misure"]["hicp_headline"]["aa"] for a, x in aree.items()
                           if "hicp_headline" in x["misure"]},
                          "HICP generale, variazione annua %", "paesi_headline",
                          colori={config.AREE[a]: COLORI_AREA[a] for a in aree})))

    # ---------------------------------------------------------------- commento
    st.append(PageBreak())
    st.append(Paragraph("Commento", S["h1"]))
    if commento:
        for par in [p.strip() for p in commento.split("\n\n") if p.strip()]:
            if par.startswith("## "):
                st.append(Paragraph(par[3:], S["h2"]))
            else:
                st.append(Paragraph(par.replace("\n", " "), S["corpo"]))
    else:
        st.append(Paragraph("Commento non disponibile in questa edizione.", S["corpo"]))

    # ------------------------------------------------------- confronto paesi
    st.append(PageBreak())
    st.append(Paragraph("Confronto fra paesi", S["h1"]))
    for mis, tit in [("hicp_core", "Core"), ("hicp_servizi", "Servizi")]:
        st.append(img(G.linee({config.AREE[a]: x["misure"][mis]["aa"] for a, x in aree.items()
                               if mis in x["misure"]}, f"{tit}, variazione annua %", f"paesi_{mis}",
                              colori={config.AREE[a]: COLORI_AREA[a] for a in aree})))
    st.append(PageBreak())
    st.append(Paragraph("Momentum: 3 mesi su 3 mesi annualizzato", S["h1"]))
    st.append(img(G.linee({config.AREE[a]: x["misure"]["hicp_headline"]["mom"] for a, x in aree.items()
                           if x["misure"].get("hicp_headline", {}).get("mom") is not None},
                          "HICP generale, 3m/3m annualizzato % (destagionalizzato)", "paesi_mom",
                          dal="2022-01", colori={config.AREE[a]: COLORI_AREA[a] for a in aree})))
    st.append(img(G.linee({config.AREE[a]: x["misure"]["hicp_core"]["mom"] for a, x in aree.items()
                           if x["misure"].get("hicp_core", {}).get("mom") is not None},
                          "Core, 3m/3m annualizzato % (destagionalizzato)", "paesi_mom_core",
                          dal="2022-01", colori={config.AREE[a]: COLORI_AREA[a] for a in aree})))

    # --------------------------------------------------------------- per area
    for a, x in aree.items():
        st.append(PageBreak())
        st.append(Paragraph(config.AREE[a], S["h1"]))
        righe = [["Misura", "Mese", "Indice 2020=100", "m/m", "a/a", "a/a mese prec.", "3m/3m ann."]]
        for mis, r in x["riepilogo"].items():
            nome = config.MISURE.get(mis, mis)
            if mis == "cpi_headline":
                nome = f"CPI nazionale - {config.CPI_NAZIONALE.get(a, '')}"
            righe.append([nome, _mese_breve(r["ultimo"], r.get("preliminare")), f(r["indice"]),
                          f(r["mm"], segno=True), f(r["aa"]), f(r["aa_prec"]), f(r["mom"])])
        st.append(tabella(righe, [LARGHEZZA * 0.29, LARGHEZZA * 0.12, LARGHEZZA * 0.14] + [LARGHEZZA * 0.1125] * 4))
        fonti_sa = sorted({m["fonte_sa"] for m in x["misure"].values() if m.get("fonte_sa")})
        st.append(Paragraph("p = stima preliminare. Destagionalizzazione: "
                            f"{'; '.join(fonti_sa)}.", S["nota"]))
        comp = {config.MISURE[m]: x["misure"][m]["aa"] for m in
                ["hicp_headline", "hicp_core", "hicp_servizi", "hicp_beni"] if m in x["misure"]}
        st.append(img(G.linee(comp, f"{config.AREE[a]}: componenti, variazione annua %", f"{a}_comp", ncol=2)))
        comp = {config.MISURE[m]: x["misure"][m]["aa"] for m in
                ["hicp_alimentari", "hicp_energia", "hicp_trasporti"] if m in x["misure"]}
        st.append(img(G.linee(comp, f"{config.AREE[a]}: alimentari, energia, trasporti, a/a %", f"{a}_vol",
                              ncol=2)))
        istat = {config.MISURE[m]: x["misure"][m]["aa"] for m in
                 ["istat_carrello", "istat_alta", "istat_media", "istat_bassa"] if m in x["misure"]}
        if istat:
            st.append(img(G.linee(istat, "Italia: carrello e frequenza d'acquisto, a/a %", f"{a}_istat",
                                  ncol=2)))
        h = x["misure"]["hicp_headline"]
        mom = {"a/a": h["aa"], "3m/3m annualizzato": h["mom"]}
        if "hicp_core" in x["misure"]:
            mom["Core 3m/3m annualizzato"] = x["misure"]["hicp_core"]["mom"]
        st.append(img(G.linee(mom, f"{config.AREE[a]}: variazione annua e momentum", f"{a}_mom", dal="2022-01")))

        # proiezioni
        if x["proiezioni"]:
            pr0 = next(iter(x["proiezioni"].values()))
            sc = list(config.SCENARI)
            righe = [["Misura", "a/a oggi"] + ["Mom.", "Neutro 1a", "Media 3a", "Media 5a", "Med. 5a", "2%"]]
            for mis in ["hicp_headline", "hicp_core", "hicp_servizi", "hicp_beni", "hicp_alimentari",
                        "hicp_energia", "cpi_headline", "istat_carrello"]:
                p = x["proiezioni"].get(mis)
                if p is None:
                    continue
                nome = config.MISURE.get(mis, mis).split(" (")[0]
                righe.append([nome, f(p["yoy_ultimo"])] + [f(p["a_fine"].get(k)) for k in sc])
            st.append(KeepTogether([
                Paragraph(f"Proiezioni a {_nome_mese(pr0['fine'])}", S["h2"]),
                tabella(righe, [LARGHEZZA * 0.24, LARGHEZZA * 0.1] + [LARGHEZZA * 0.11] * 6),
                Paragraph("Inflazione annua % alla fine dell'orizzonte in ciascuno scenario. Neutro 1a: "
                          "stesse variazioni mensili dell'anno prima (a/a invariato). Media/mediana: "
                          "variazione tipica di ciascun mese di calendario. La mediana a 5 anni "
                          "assorbe gli anni anomali come il 2022.", S["nota"])]))
            p = x["proiezioni"]["hicp_headline"]
            st.append(img(G.proiezioni(h["aa"], p, f"{config.AREE[a]}: HICP generale, scenari a fine orizzonte",
                                       f"{a}_proiez")))
            righe = [["Mese", "Var. mensile che esce (anno prima)"] + ["a/a " + k for k in ["momentum", "neutro 5a"]]]
            for per in p["yoy"].index:
                righe.append([_nome_mese(per), f(p["effetto_base"].loc[per, "var_mensile_anno_prima"], 2, True),
                              f(p["yoy"].loc[per].get("momentum")), f(p["yoy"].loc[per].get("neutro_5a"))])
            st.append(KeepTogether([Paragraph("Effetto base: le variazioni mensili che escono dal confronto annuo",
                                              S["h2"]),
                                    tabella(righe, [LARGHEZZA * 0.28, LARGHEZZA * 0.36, LARGHEZZA * 0.18,
                                                    LARGHEZZA * 0.18]),
                                    Paragraph("Una variazione mensile alta che esce dal confronto abbassa "
                                              "l'inflazione annua a parità di dinamica corrente, e viceversa.",
                                              S["nota"])]))

    # ------------------------------------------------------ focus categorie
    st.append(PageBreak())
    st.append(Paragraph("Focus: energia, alimentari, trasporti, servizi", S["h1"]))
    for mis in ["hicp_energia", "hicp_alimentari", "hicp_trasporti", "hicp_servizi"]:
        st.append(img(G.linee({config.AREE[a]: x["misure"][mis]["aa"] for a, x in aree.items()
                               if mis in x["misure"]}, f"{config.MISURE[mis]}, a/a %", f"focus_{mis}",
                              obiettivo=False, colori={config.AREE[a]: COLORI_AREA[a] for a in aree})))

    # --------------------------------------------------------- distribuzione
    st.append(PageBreak())
    st.append(Paragraph("Quanto è diffusa l'inflazione", S["h1"]))
    st.append(Paragraph("Voci elementari del paniere divise per fascia di inflazione annua. La quota per "
                        "peso dice quanta parte della spesa delle famiglie sta in ciascuna fascia; la quota "
                        "per numero quanto è esteso il contagio fra i prodotti.", S["corpo"]))
    quote = {config.AREE[a]: x["distribuzione_macro"]["Totale"]["peso"] for a, x in aree.items()
             if x.get("distribuzione_macro")}
    if quote:
        st.append(img(G.fasce_per_area(quote, "Quota del paniere per fascia di inflazione annua", "fasce_aree")))
        for a, x in aree.items():
            d = x.get("distribuzione_macro")
            if not d:
                continue
            righe = [["Gruppo (voci)"] + [f0 for f0, _, _ in config.FASCE]]
            for g in ["Totale"] + config.MACRO:
                if g in d:
                    righe.append([f"{g} ({d[g]['voci']})"] + [f(d[g]["peso"][f0], 0) for f0, _, _ in config.FASCE])
            righe.append([f"Totale per numero ({d['Totale']['voci']})"] +
                         [f(d["Totale"]["n"][f0], 0) for f0, _, _ in config.FASCE])
            st.append(KeepTogether([Paragraph(f"{config.AREE[a]} - {_nome_mese(x['voci_ultimo'])} "
                                              "(% per peso)", S["h2"]),
                                    tabella(righe, [LARGHEZZA * 0.3] + [LARGHEZZA * 0.14] * 5)]))
        for a in ["EA", "IT"]:
            if a in aree and not aree[a]["storico_quote"].empty:
                st.append(img(G.fasce_storico(aree[a]["storico_quote"],
                                              f"{config.AREE[a]}: quota del paniere per fascia nel tempo",
                                              f"{a}_fasce_storico")))

    # ---------------------------------------------------------- sottostanti
    st.append(PageBreak())
    st.append(Paragraph("Inflazione sottostante: domestica, importata, ciclica", S["h1"]))
    st.append(Paragraph("Domestica e Supercore sono aggregate con i flag voce per voce del BCE Statistics "
                        "Paper n. 54 (2026). Per l'area euro sono la stessa misura della BCE; per i singoli "
                        "paesi sono una ricostruzione: flag stimati sull'area euro applicati alle voci "
                        "nazionali.", S["corpo"]))
    for a, x in aree.items():
        r = x.get("ricostruite")
        if not r:
            continue
        ss = {config.SOTTOSTANTI[k].split(" (")[0]: var_a(r[k]) for k in
              ["domestica", "importata", "supercore", "non_supercore"] if k in r}
        st.append(img(G.linee(ss, f"{config.AREE[a]}: domestica, importata, Supercore, a/a %", f"{a}_sott",
                              ncol=2)))
    righe = [["Area"] + ["Tronc. 10%", "25%", "30%", "50%", "75%", "Mediana"]]
    for a, x in aree.items():
        t = x.get("troncate")
        if t is None or t.empty:
            continue
        u = t.iloc[-1]
        righe.append([config.AREE[a]] + [f(u[k]) for k in ["troncata10", "troncata25", "troncata30",
                                                            "troncata50", "troncata75", "mediana"]])
    st.append(KeepTogether([Paragraph("Medie troncate e mediana ponderata (a/a %)", S["h2"]), tabella(righe),
                            Paragraph("Troncata X%: si toglie X/2% del peso in ciascuna coda della "
                                      "distribuzione delle variazioni annue delle voci.", S["nota"])]))
    tar = aree.get("EA", {}).get("taratura_bce")
    if tar:
        righe = [["Serie BCE", "Mesi", "Scarto medio", "Scarto max", "Ultimo"]]
        for k, v in tar.items():
            if v:
                righe.append([k, str(v["mesi"]), f(v["scarto_medio"], 2, True), f(v["scarto_max_ass"], 2),
                              f(v["ultimo"], 2, True)])
        st.append(KeepTogether([Paragraph("Taratura: nostre ricostruzioni contro le serie BCE (area euro)",
                                          S["h2"]), tabella(righe),
                                Paragraph("Scarti in punti percentuali sulla variazione annua, ultimi 24 mesi. "
                                          "Scarti piccoli = metodo tarato: vale anche per le misure che la "
                                          "BCE non pubblica (troncate 25/50/75, ricostruzioni per paese).",
                                          S["nota"])]))

    # ------------------------------------------------------- potere d'acquisto
    st.append(PageBreak())
    st.append(Paragraph("Potere d'acquisto", S["h1"]))
    for base in config.BASI_CONFRONTO:
        righe = [["Misura"] + [config.AREE[a] for a in aree]]
        for mis in ["hicp_headline", "hicp_alimentari", "hicp_energia", "hicp_servizi", "hicp_trasporti",
                    "istat_carrello"]:
            riga = [config.MISURE[mis].split(" (")[0]]
            presente = False
            for a, x in aree.items():
                pw = x["riepilogo"].get(mis, {}).get("potere", {}).get(base)
                riga.append(f(pw["cento_euro"], 1) if pw else "-")
                presente |= pw is not None
            if presente:
                righe.append(riga)
        st.append(KeepTogether([Paragraph(f"Quanto valgono oggi 100 euro di {base}", S["h2"]),
                                tabella(righe, [LARGHEZZA * 0.25] + [LARGHEZZA * 0.75 / len(aree)] * len(aree))]))
    st.append(img(G.barre_orizzontali(
        {config.AREE[a]: x["riepilogo"]["hicp_headline"]["potere"]["gen 2020"]["prezzi"] for a, x in aree.items()
         if "gen 2020" in x["riepilogo"]["hicp_headline"]["potere"]},
        "Aumento dei prezzi da gennaio 2020 (HICP generale)", "potere_2020")))

    righe = [["Area", "Misura salari", "Fino a", "Salari", "Prezzi", "Salari reali"]]
    curve = {}
    for a, x in aree.items():
        for mis, d in (x.get("salari") or {}).items():
            c = d["cumulato"].get("gen 2020")
            if c:
                righe.append([config.AREE[a], config.SALARI_NOMI.get(mis, mis.replace("_", " ")), c["fino_a"], f(c["salari"], 1, True),
                              f(c["prezzi"], 1, True), f(c["reale"], 1, True)])
            if mis == "compensation_per_employee" and d["tipo"] == "livello":
                tab = d["tabella"]
                curve[config.AREE[a]] = tab["salari_reali"]
    if len(righe) > 1:
        st.append(KeepTogether([Paragraph("Salari contro prezzi, variazione cumulata da inizio 2020 (%)", S["h2"]),
                                tabella(righe, [LARGHEZZA * 0.14, LARGHEZZA * 0.3, LARGHEZZA * 0.13] +
                                        [LARGHEZZA * 0.143] * 3)]))
    if curve:
        st.append(img(G.linee(curve, "Salari reali per dipendente, variazione annua %", "salari_reali",
                              obiettivo=False, colori={config.AREE[a]: COLORI_AREA[a] for a in aree})))

    # ------------------------------------------------------------------- note
    st.append(PageBreak())
    st.append(Paragraph("Note di metodo e fonti", S["h1"]))
    note = [
        "Indici: tutti ribasati a gennaio 2020 = 100. Dal gennaio 2026 l'HICP usa la classificazione "
        "ECOICOP versione 2 e la base 2025 = 100; lo storico delle sottocomponenti è preso interamente "
        "dalla serie ricalcolata, per evitare salti artificiali.",
        "Momentum: media degli ultimi 3 mesi sui 3 precedenti, annualizzata, sempre su serie "
        "destagionalizzata (BCE dove pubblicata, altrimenti destagionalizzazione interna STL, dichiarata "
        "nella pagina di ciascuna area).",
        "Scenari: si proietta il livello dell'indice grezzo mese per mese, così la variazione annua di ogni "
        "mese futuro incorpora da sola l'effetto base.",
        "Distribuzione: voci elementari ECOICOP v2 a 6 cifre con i pesi dell'anno; fasce sulla variazione "
        "annua dell'ultimo mese.",
        "Domestica e Supercore: flag del BCE Statistics Paper n. 54 (2026), Tabella 4; soglia di import 12%, "
        "composizione costante.",
    ]
    for n in note:
        st.append(Paragraph(n, S["corpo"]))
    istituti = set()
    for x in aree.values():
        for m in x["misure"].values():
            t = (m.get("fonte") or "").replace("stima preliminare ", "")
            istituti.add(t.split(" ")[0])
    st.append(Paragraph("Fonti: " + ", ".join(sorted(i for i in istituti if i)) + "; BCE Data Portal; "
                        "stime preliminari degli istituti nazionali dove indicato con p.", S["nota"]))

    os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)
    doc = SimpleDocTemplate(percorso, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.8 * cm,
                            title="Inflazione area euro", author="hicp-wrap")
    doc.build(st, onFirstPage=_piede, onLaterPages=_piede)
    return percorso
