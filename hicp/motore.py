"""Motore: legge l'archivio e produce i risultati per Excel, PDF e commento."""
import pandas as pd

from . import aggrega, calcoli, config, distribuzione, potere, proiezioni


def _misura(arch, area, mis):
    nsa = arch.serie(area, mis)
    if nsa is None or nsa.dropna().empty:
        return None
    nsa = nsa.dropna()
    sa = arch.serie(area, mis, sa=True)
    fonte_sa = arch.fonte(area, mis, sa=True) if sa is not None else ""
    if sa is not None and sa.dropna().index[-1] < nsa.index[-1]:
        sa = None                      # destagionalizzata pubblicata ma ferma a mesi prima: non usabile
    if sa is None:
        sa = calcoli.destagionalizza(nsa)
        fonte_sa = "destagionalizzazione interna (STL)" if sa is not None else "non disponibile"
    idx = calcoli.ribasa(nsa, config.BASE_INDICI)
    return {
        "nome": config.MISURE.get(mis, mis), "fonte": arch.fonte(area, mis),
        "nsa": nsa, "sa": sa, "fonte_sa": fonte_sa,
        "indice": idx if idx is not None else nsa,
        "mm": calcoli.var_m(nsa), "aa": calcoli.var_a(nsa),
        "mom": calcoli.mom_3m3m(sa) if sa is not None else None,
    }


def _riepilogo(m):
    t = m["nsa"].index[-1]
    g = lambda s: None if s is None or t not in s.index or pd.isna(s[t]) else float(s[t])  # noqa: E731
    prec = t - 1
    return {
        "ultimo": str(t), "indice": g(m["indice"]), "mm": g(m["mm"]), "aa": g(m["aa"]),
        "aa_prec": None if prec not in m["aa"].index or pd.isna(m["aa"][prec]) else float(m["aa"][prec]),
        "mom": g(m["mom"]) if m["mom"] is not None else None,
        "potere": potere.confronto_livelli(m["indice"], t),
    }


def calcola(arch, evento=None):
    flag = aggrega.carica_flag_bce()
    ris = {"evento": evento or {}, "aree": {}, "ultimo": str(arch.ultimo_periodo())}
    for area in config.AREE:
        misure = [m for m in config.MISURE if m in arch.misure(area)]
        misure += [m for m in arch.misure(area) if m not in misure and not m.startswith("bce_")]
        if not misure:
            continue
        a = {"misure": {}, "riepilogo": {}, "proiezioni": {}}
        for mis in misure:
            m = _misura(arch, area, mis)
            if m is None:
                continue
            a["misure"][mis] = m
            a["riepilogo"][mis] = _riepilogo(m)
            if len(m["nsa"]) >= 72:
                a["proiezioni"][mis] = proiezioni.scenari(m["nsa"], m["sa"])

        # ------------------------------------------------ voci elementari
        voci, pesi = arch.voci(area), arch.pesi(area)
        if voci is not None and pesi is not None:
            ins = aggrega.insiemi(voci.columns, flag)
            ric = {k: aggrega.aggrega(voci, pesi, v) for k, v in ins.items()}
            a["ricostruite"] = {k: s for k, s in ric.items() if s is not None}
            a["verifica"] = {
                "tutte vs HICP generale": aggrega.confronta(ric.get("tutte"), arch.serie(area, "hicp_headline")),
                "HICPX vs core": aggrega.confronta(ric.get("hicpx"), arch.serie(area, "hicp_core")),
            }
            tassi = distribuzione.tassi_annui(voci)
            ult = tassi.dropna(how="all").index[-1]
            a["voci_ultimo"] = str(ult)
            a["distribuzione_macro"] = distribuzione.distribuzione(
                tassi, pesi, ult, gruppo=lambda v: aggrega.macro_categoria(v, flag))
            a["distribuzione_divisioni"] = distribuzione.distribuzione(
                tassi, pesi, ult, gruppo=lambda v: config.DIVISIONI.get(v[:2], v[:2]))
            a["storico_quote"] = distribuzione.storico_quote(tassi, pesi)
            a["troncate"] = distribuzione.serie_troncate(tassi, pesi)
            a["pesi_macro"] = aggrega.pesi_macro(pesi, ult.year, flag)
            a["n_voci"] = {k: len(v) for k, v in ins.items()}
            # voci con l'inflazione annua piu' alta e piu' bassa (per il commento)
            w = aggrega._pesi_anno(pesi, ult.year)
            tv = pd.DataFrame({"a/a %": tassi.loc[ult], "peso per mille": w}).dropna(subset=["a/a %"])
            tv["macro"] = [aggrega.macro_categoria(v, flag) for v in tv.index]
            tv["divisione"] = [config.DIVISIONI.get(v[:2], v[:2]) for v in tv.index]
            tv["fascia"] = tv["a/a %"].map(distribuzione.fascia_di)
            tv["descrizione (BCE)"] = [flag.get(v, {}).get("voce", "") for v in tv.index]
            tv["domestica"] = [("si" if flag[v]["domestica"] else "no") if v in flag else "" for v in tv.index]
            tv["supercore"] = [("si" if flag[v]["supercore"] else "no") if v in flag else "" for v in tv.index]
            tv.index.name = "Voce"
            a["voci_tabella"] = tv.sort_values("a/a %", ascending=False)
            r = tassi.loc[ult].dropna().sort_values()
            a["voci_estreme"] = {"alte": r.tail(8)[::-1].round(1).to_dict(), "basse": r.head(5).round(1).to_dict()}

            # taratura contro le misure BCE pubblicate (area euro)
            if area == "EA":
                tar = {}
                for bce, nostra in config.BCE_CONFRONTO.items():
                    uff = arch.serie(area, bce)
                    if uff is None:
                        continue
                    # in archivio le misure BCE sono TASSI ANNUI (%), come le pubblica la BCE
                    if nostra in a["troncate"].columns:
                        nostro = a["troncate"][nostra]
                    elif nostra in a["ricostruite"]:
                        nostro = calcoli.var_a(a["ricostruite"][nostra])
                    else:
                        continue
                    d = (nostro - uff).dropna().tail(24)
                    tar[bce] = None if d.empty else {"mesi": len(d), "scarto_medio": float(d.mean()),
                                                     "scarto_max_ass": float(d.abs().max()),
                                                     "ultimo": float(d.iloc[-1])}
                a["taratura_bce"] = tar
                a["serie_bce"] = {m: arch.serie(area, m) for m in arch.misure(area) if m.startswith("bce_")}

        # ------------------------------------------------------ salari
        h = a["misure"].get("hicp_headline")
        if h is not None:
            a["salari"] = potere.salari_reali(arch.salari(area), h["nsa"])
        ris["aree"][area] = a
    return ris
