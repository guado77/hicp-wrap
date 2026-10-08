"""Consumi e tetti delle chiamate al modello (razionalizzazione dei wrap, 8/10/2026).

Tre cose, uguali in tutti i repo dei wrap:

1. registra(): ogni chiamata stampa nel log del run UNA riga
       [consumi] wrap=<nome> fase=<scheda|sintesi|...> modello=<id> in=<n> out=<n> ragion=<n> cache=<n> tot=<n>
   Il wrap-monitor legge i log della settimana e ne fa la classifica dei costi
   (consumi_settimana.py). Nessun file da committare, nessun secret in piu'.
   Il nome del wrap e' quello del workflow (GITHUB_WORKFLOW) se non indicato.

2. taglia(): tetto ai caratteri mandati al modello (25.000 di default,
   TETTO_CARATTERI per cambiarlo). Se il testo e' piu' lungo tiene l'attacco
   (abstract, introduzione: 60%) e la coda (conclusioni: 40%), che e' dove sta
   il succo di un paper o di un documento ufficiale.

3. modello() e sforzo(): due livelli. Le schede dei singoli documenti usano il
   ragionamento "low" (il ragionamento si paga come testo in uscita ed e' la
   voce piu' cara); le sintesi e le letture finali "medium". Il modello resta
   Grok 4.7 per entrambi: le varianti "fast" sull'API costano di piu' (verificato
   sulla documentazione xAI l'8/10/2026). Si cambiano con le variabili
   MODELLO_SCHEDE / MODELLO_SINTESI / SFORZO_SCHEDE / SFORZO_SINTESI.
"""
from __future__ import annotations

import os

TETTO = int(os.environ.get("TETTO_CARATTERI", "25000"))


def modello(fase: str = "scheda", predefinito: str = "grok-4.7") -> str:
    nome = "MODELLO_SCHEDE" if fase == "scheda" else "MODELLO_SINTESI"
    return (os.environ.get(nome) or "").strip() or predefinito


def sforzo(fase: str = "scheda") -> str:
    if fase == "scheda":
        return (os.environ.get("SFORZO_SCHEDE") or "low").strip()
    return (os.environ.get("SFORZO_SINTESI") or "medium").strip()


def taglia(testo: str, tetto: int | None = None) -> str:
    """Testo entro il tetto: attacco (60%) + coda (40%) con un segno di taglio."""
    tetto = tetto or TETTO
    if not testo or len(testo) <= tetto:
        return testo or ""
    testa = int(tetto * 0.6)
    coda = tetto - testa - 60
    return (testo[:testa].rstrip() + "\n\n[... parte centrale omessa per brevita' ...]\n\n"
            + testo[-coda:].lstrip())


def comprimi_schede(testo: str, sep: str = "\n\n=====\n\n", tetto: int | None = None,
                    minimo: int = 1500) -> str:
    """Per le SINTESI: il tetto si ripartisce fra le schede invece di tagliare
    nel mezzo (che farebbe sparire le schede centrali). Ogni scheda tiene
    l'attacco (titolo, domanda, risultati), almeno `minimo` caratteri."""
    tetto = tetto or TETTO
    if not testo or len(testo) <= tetto:
        return testo or ""
    pezzi = testo.split(sep)
    quota = max(minimo, tetto // max(1, len(pezzi)))
    return sep.join(p if len(p) <= quota else p[:quota].rstrip() + " [...]" for p in pezzi)


def _num(d, *chiavi) -> int:
    for k in chiavi:
        v = d.get(k) if isinstance(d, dict) else getattr(d, k, None)
        if isinstance(v, (int, float)):
            return int(v)
    return 0


def registra(usage, modello_usato: str = "", fase: str = "", wrap: str | None = None) -> None:
    """usage: il campo 'usage' della risposta (dict JSON o oggetto dell'SDK)."""
    try:
        if usage is None:
            return
        if not isinstance(usage, dict) and hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        ingresso = _num(usage, "prompt_tokens", "input_tokens")
        uscita = _num(usage, "completion_tokens", "output_tokens")
        det_out = (usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}) \
            if isinstance(usage, dict) else {}
        det_in = (usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}) \
            if isinstance(usage, dict) else {}
        ragion = _num(det_out, "reasoning_tokens") or _num(usage, "reasoning_tokens")
        cache = _num(det_in, "cached_tokens")
        totale = _num(usage, "total_tokens") or (ingresso + uscita)
        nome = (wrap or os.environ.get("CONSUMI_WRAP") or os.environ.get("GITHUB_WORKFLOW") or "locale")
        nome = nome.replace(" ", "_")
        fase = (str(fase or "-").replace(" ", "_") or "-")[:30]
        print(f"[consumi] wrap={nome} fase={fase} modello={modello_usato or '-'} "
              f"in={ingresso} out={uscita} ragion={ragion} cache={cache} tot={totale}", flush=True)
    except Exception as e:                                            # noqa: BLE001
        print(f"[consumi] non registrato: {e}", flush=True)
