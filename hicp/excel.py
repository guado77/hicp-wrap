"""
Excel storico e di aggiornamento.

Fogli per area: indici grezzi e destagionalizzati come VALORI (in blu, sono dati di fonte);
ribasatura, m/m, a/a e 3m/3m come FORMULE (in nero), cosi' il foglio si ricalcola se un
dato viene corretto o aggiunto a mano. Riepilogo e Potere d'acquisto leggono i fogli area
con formule. Proiezioni, distribuzione, sottostanti e salari sono calcoli del motore
(valori), dichiarati come tali nel foglio Leggimi.
"""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as col

from . import config

F = "Arial"
BLU_DATO = Font(name=F, size=12, color="0000FF")
NERO = Font(name=F, size=12, color="000000")
TESTATA = Font(name=F, size=12, bold=True, color="FFFFFF")
TITOLO = Font(name=F, size=16, bold=True, color="08306B")
GRASSETTO = Font(name=F, size=12, bold=True)
FONDO = PatternFill("solid", fgColor="08306B")
FONDO2 = PatternFill("solid", fgColor="DCE6F1")
BORDO = Border(bottom=Side(style="thin", color="999999"))
PCT = '0.0%;-0.0%;0.0%'
NUM = '0.00'
MESE = 'mmm yyyy'

COLONNE = ["Indice fonte", "Base gen20=100", "m/m", "a/a", "Indice SA", "3m/3m ann."]


def _testata(ws, riga, c, testo, larghezza=None):
    x = ws.cell(riga, c, testo)
    x.font, x.fill = TESTATA, FONDO
    x.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    if larghezza:
        ws.column_dimensions[col(c)].width = larghezza
    return x


def _foglio_area(wb, area, a):
    ws = wb.create_sheet(area)
    ws["A1"] = f"{config.AREE[area]} - indici e variazioni"
    ws["A1"].font = TITOLO
    ws["A2"] = "Blu = dato di fonte; nero = formula. Variazioni in %, 3m/3m su serie destagionalizzata."
    ws["A2"].font = Font(name=F, size=11, italic=True)
    misure = list(a["misure"].keys())
    mesi = sorted(set().union(*[set(m["nsa"].index) for m in a["misure"].values()]))
    mesi = [p for p in mesi if p >= pd.Period("2015-01", freq="M")]
    r0 = 5
    riga_di = {p: r0 + i for i, p in enumerate(mesi)}
    r_base = riga_di.get(pd.Period(config.BASE_INDICI, freq="M"))
    _testata(ws, 4, 1, "Mese", 12)
    for i, p in enumerate(mesi):
        c = ws.cell(r0 + i, 1, p.to_timestamp().to_pydatetime())
        c.number_format, c.font = MESE, NERO
    mappa = {}
    for j, mis in enumerate(misure):
        m = a["misure"][mis]
        c0 = 2 + j * 6
        nome = config.MISURE.get(mis, mis)
        if mis == "cpi_headline":
            nome = f"CPI nazionale - {config.CPI_NAZIONALE.get(area, '')}"
        ws.merge_cells(start_row=3, start_column=c0, end_row=3, end_column=c0 + 5)
        _testata(ws, 3, c0, nome)
        for k, t in enumerate(COLONNE):
            _testata(ws, 4, c0 + k, t, 12)
        L = {k: col(c0 + k) for k in range(6)}
        for p, r in riga_di.items():
            v = m["nsa"].get(p)
            if v is not None and not pd.isna(v):
                ws.cell(r, c0, round(float(v), 4)).font = BLU_DATO
            if m["sa"] is not None:
                vs = m["sa"].get(p)
                if vs is not None and not pd.isna(vs):
                    x = ws.cell(r, c0 + 4, round(float(vs), 4))
                    x.font = BLU_DATO if "BCE" in m["fonte_sa"] else NERO
            if r_base:
                ws.cell(r, c0 + 1, f'=IF(ISNUMBER({L[0]}{r}),{L[0]}{r}/{L[0]}${r_base}*100,"")')
            if r - 1 >= r0:
                ws.cell(r, c0 + 2, f'=IF(AND(ISNUMBER({L[0]}{r}),ISNUMBER({L[0]}{r - 1})),'
                                    f'{L[0]}{r}/{L[0]}{r - 1}-1,"")')
            if r - 12 >= r0:
                ws.cell(r, c0 + 3, f'=IF(AND(ISNUMBER({L[0]}{r}),ISNUMBER({L[0]}{r - 12})),'
                                    f'{L[0]}{r}/{L[0]}{r - 12}-1,"")')
            if r - 5 >= r0:
                ws.cell(r, c0 + 5, f'=IF(COUNT({L[4]}{r - 5}:{L[4]}{r})=6,'
                                    f'(AVERAGE({L[4]}{r - 2}:{L[4]}{r})/AVERAGE({L[4]}{r - 5}:{L[4]}{r - 3}))^4-1,"")')
            for k, fmt in [(0, NUM), (1, NUM), (2, PCT), (3, PCT), (4, NUM), (5, PCT)]:
                ws.cell(r, c0 + k).number_format = fmt
                if k in (1, 2, 3, 5):
                    ws.cell(r, c0 + k).font = NERO
        ultimo = m["nsa"].dropna().index[-1]
        mappa[mis] = {"colonne": L, "ultima_riga": riga_di[ultimo], "riga_base": r_base,
                      "riga_2024": riga_di.get(pd.Period("2024-01", freq="M"))}
    ws.freeze_panes = "B5"
    ws.row_dimensions[3].height = 34
    ws.row_dimensions[4].height = 34
    return mappa


def _riepilogo(wb, ris, mappe):
    ws = wb.create_sheet("Riepilogo", 1)
    ws["A1"] = f"Riepilogo - ultimo dato {ris['ultimo']}"
    ws["A1"].font = TITOLO
    ws["A2"] = "Formule collegate ai fogli area: si aggiornano con i dati."
    ws["A2"].font = Font(name=F, size=11, italic=True)
    intest = ["Area", "Misura", "Mese", "Indice gen20=100", "m/m", "a/a", "3m/3m ann."]
    for k, t in enumerate(intest, start=1):
        _testata(ws, 4, k, t, [14, 46, 12, 16, 12, 12, 14][k - 1])
    r = 5
    for area, mp in mappe.items():
        for mis, info in mp.items():
            L, u = info["colonne"], info["ultima_riga"]
            nome = config.MISURE.get(mis, mis)
            ws.cell(r, 1, config.AREE[area]).font = NERO
            ws.cell(r, 2, nome).font = NERO
            ws.cell(r, 3, f"='{area}'!A{u}").number_format = MESE
            for k, (src, fmt) in enumerate([(L[1], NUM), (L[2], PCT), (L[3], PCT), (L[5], PCT)], start=4):
                c = ws.cell(r, k, f"='{area}'!{src}{u}")
                c.number_format, c.font = fmt, Font(name=F, size=12, color="008000")
            r += 1
    ws.freeze_panes = "A5"


def _potere(wb, mappe):
    ws = wb.create_sheet("Potere acquisto")
    ws["A1"] = "Potere d'acquisto contro gennaio 2020 e gennaio 2024"
    ws["A1"].font = TITOLO
    ws["A2"] = ("Prezzi = aumento dell'indice; Potere = variazione del potere d'acquisto; "
                "100 euro = valore oggi di 100 euro della data base. Formule sui fogli area.")
    ws["A2"].font = Font(name=F, size=11, italic=True)
    intest = ["Area", "Misura", "Prezzi da gen20", "Potere da gen20", "100 euro gen20",
              "Prezzi da gen24", "Potere da gen24", "100 euro gen24"]
    for k, t in enumerate(intest, start=1):
        _testata(ws, 4, k, t, [14, 46, 15, 15, 15, 15, 15, 15][k - 1])
    r = 5
    for area, mp in mappe.items():
        for mis, info in mp.items():
            L, u, b20, b24 = info["colonne"], info["ultima_riga"], info["riga_base"], info["riga_2024"]
            if not b20:
                continue
            ws.cell(r, 1, config.AREE[area]).font = NERO
            ws.cell(r, 2, config.MISURE.get(mis, mis)).font = NERO
            x = f"'{area}'!{L[0]}"
            formule = [f"={x}{u}/{x}{b20}-1", f"={x}{b20}/{x}{u}-1", f"=100*{x}{b20}/{x}{u}"]
            if b24:
                formule += [f"={x}{u}/{x}{b24}-1", f"={x}{b24}/{x}{u}-1", f"=100*{x}{b24}/{x}{u}"]
            for k, fo in enumerate(formule, start=3):
                c = ws.cell(r, k, fo)
                c.number_format = NUM if k in (5, 8) else PCT
                c.font = Font(name=F, size=12, color="008000")
            r += 1
    ws.freeze_panes = "C5"


def _valori(wb, nome, blocchi, nota):
    """blocchi: lista di (titolo, DataFrame) scritti uno sotto l'altro."""
    ws = wb.create_sheet(nome)
    ws["A1"] = nome
    ws["A1"].font = TITOLO
    ws["A2"] = nota
    ws["A2"].font = Font(name=F, size=11, italic=True)
    r = 4
    for titolo, df in blocchi:
        if df is None or df.empty:
            continue
        ws.cell(r, 1, titolo).font = Font(name=F, size=13, bold=True, color="08306B")
        r += 1
        _testata(ws, r, 1, df.index.name or "")
        for k, c in enumerate(df.columns, start=2):
            _testata(ws, r, k, str(c))
        r += 1
        for idx, riga in df.iterrows():
            x = ws.cell(r, 1, idx.to_timestamp().to_pydatetime() if isinstance(idx, pd.Period) and idx.freqstr == "M"
                        else str(idx))
            x.font = NERO
            if isinstance(idx, pd.Period) and idx.freqstr == "M":
                x.number_format = MESE
            for k, v in enumerate(riga.values, start=2):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                num = isinstance(v, (int, float)) and not isinstance(v, bool)
                c = ws.cell(r, k, round(float(v), 4) if num else v)
                c.font = NERO
                if num:
                    c.number_format = '0.00'
            r += 1
        r += 2
    ws.column_dimensions["A"].width = 28
    for k in range(2, 16):
        ws.column_dimensions[col(k)].width = 15
    return ws


def costruisci(ris, percorso):
    wb = Workbook()
    ws = wb.active
    ws.title = "Leggimi"
    righe = [
        ("Inflazione area euro - storico e foglio di aggiornamento", TITOLO),
        (f"Ultimo dato: {ris['ultimo']}", GRASSETTO),
        ("", NERO),
        ("Fogli EA, IT, DE, FR, ES: indici di fonte (blu) e trasformazioni (formule, nero):", NERO),
        ("  base gennaio 2020 = 100, variazione mensile, annua, 3m/3m annualizzato su serie destagionalizzata.", NERO),
        ("  Indice SA in blu = pubblicato dalla BCE; in nero = destagionalizzazione interna (STL).", NERO),
        ("Riepilogo e Potere acquisto: formule che leggono i fogli area (verde).", NERO),
        ("Proiezioni, Distribuzione, Sottostanti, Salari, Voci: calcoli del motore (valori).", NERO),
        ("", NERO),
        ("Per correggere o aggiungere un dato: scrivilo nella colonna 'Indice fonte' del foglio area;", NERO),
        ("le formule della riga e il Riepilogo si aggiornano da soli.", NERO),
    ]
    for i, (t, fnt) in enumerate(righe, start=1):
        ws.cell(i, 1, t).font = fnt
    ws.column_dimensions["A"].width = 110

    mappe = {}
    for area, a in ris["aree"].items():
        mappe[area] = _foglio_area(wb, area, a)
    _riepilogo(wb, ris, mappe)
    _potere(wb, mappe)

    # proiezioni
    blocchi = []
    for area, a in ris["aree"].items():
        tab = pd.DataFrame({config.MISURE.get(m, m): {"a/a oggi": p["yoy_ultimo"], **{config.SCENARI_BREVI[k]: v
                            for k, v in p["a_fine"].items()}} for m, p in a["proiezioni"].items()}).T
        tab.index.name = "Misura"
        if not tab.empty:
            fine = next(iter(a["proiezioni"].values()))["fine"]
            blocchi.append((f"{config.AREE[area]} - inflazione annua % a {fine} per scenario", tab))
        p = a["proiezioni"].get("hicp_headline")
        if p:
            t = p["yoy"].rename(columns=config.SCENARI_BREVI)
            t.insert(0, "Var. mensile che esce (anno prima)", p["effetto_base"]["var_mensile_anno_prima"])
            t.index.name = "Mese"
            blocchi.append((f"{config.AREE[area]} - HICP generale: percorso a/a % ed effetto base", t))
    _valori(wb, "Proiezioni", blocchi, "Scenari: " + "; ".join(f"{config.SCENARI_BREVI[k]} = {v}"
                                                                for k, v in config.SCENARI.items()))

    # distribuzione
    blocchi = []
    for area, a in ris["aree"].items():
        d = a.get("distribuzione_macro")
        if not d:
            continue
        for tipo, lab in [("peso", "per peso"), ("n", "per numero di voci")]:
            t = pd.DataFrame({g: v[tipo] for g, v in d.items()}).T
            t.index.name = "Gruppo"
            blocchi.append((f"{config.AREE[area]} - {a['voci_ultimo']} - quota % delle voci per fascia, {lab}", t))
        dv = a.get("distribuzione_divisioni") or {}
        t = pd.DataFrame({g: v["peso"] for g, v in dv.items() if g != "Totale"}).T
        t.index.name = "Divisione"
        blocchi.append((f"{config.AREE[area]} - per divisione ECOICOP, quota % per peso", t))
        sq = a.get("storico_quote")
        if sq is not None and not sq.empty:
            sq = sq.copy()
            sq.index.name = "Mese"
            blocchi.append((f"{config.AREE[area]} - storico quota % del paniere per fascia (per peso)", sq))
    _valori(wb, "Distribuzione", blocchi, "Fasce sulla variazione annua delle voci elementari ECOICOP v2.")

    # sottostanti
    blocchi = []
    for area, a in ris["aree"].items():
        r = a.get("ricostruite") or {}
        t = pd.DataFrame({config.SOTTOSTANTI.get(k, k): (s / s.shift(12) - 1) * 100 for k, s in r.items()
                          if k in ("domestica", "importata", "supercore", "non_supercore")})
        tr = a.get("troncate")
        if tr is not None and not tr.empty:
            t = t.join(tr.rename(columns=config.SOTTOSTANTI), how="outer")
        for k, s in (a.get("serie_bce") or {}).items():
            t[f"BCE pubblicata: {k}"] = s
        t = t[t.index >= pd.Period("2016-01", freq="M")].dropna(how="all")
        t.index.name = "Mese"
        blocchi.append((f"{config.AREE[area]} - misure sottostanti, a/a %", t))
    _valori(wb, "Sottostanti", blocchi, "Domestica/Supercore con i flag del BCE Statistics Paper 54; "
                                        "troncate e mediana sulle variazioni annue delle voci.")

    # salari
    blocchi = []
    for area, a in ris["aree"].items():
        for mis, d in (a.get("salari") or {}).items():
            t = d["tabella"].copy()
            t.index = t.index.astype(str)
            t.index.name = "Periodo"
            blocchi.append((f"{config.AREE[area]} - {mis} ({d['fonte']}), variazioni annue %", t))
    _valori(wb, "Salari", blocchi, "Salari reali = (1 + salari nominali) / (1 + prezzi) - 1; "
                                   "prezzi HICP generale, medie trimestrali per le serie trimestrali.")
    blocchi = [(f"{config.AREE[area]} - voci elementari a {a['voci_ultimo']}, ordinate per inflazione annua",
                a["voci_tabella"]) for area, a in ris["aree"].items() if a.get("voci_tabella") is not None]
    ws = _valori(wb, "Voci", blocchi, "Una riga per voce ECOICOP v2: variazione annua, peso, fascia, flag BCE.")
    ws.column_dimensions["F"].width = 60
    wb.calculation.fullCalcOnLoad = True
    wb.save(percorso)
    return percorso
