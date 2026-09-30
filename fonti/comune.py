"""Funzioni comuni ai lettori delle fonti."""
import itertools
import time

import requests

HDR = {"User-Agent": "Mozilla/5.0 (hicp-wrap; statistiche ufficiali)"}


def get(url, params=None, timeout=120, tentativi=3, pausa=10, **kw):
    """GET con pochi tentativi e pausa crescente. Solleva l'ultima eccezione."""
    ultimo = None
    for i in range(tentativi):
        try:
            x = requests.get(url, params=params, headers={**HDR, **kw.pop("headers", {})}, timeout=timeout, **kw)
            if x.status_code == 200:
                return x
            ultimo = RuntimeError(f"HTTP {x.status_code} su {x.url[:200]}: {x.text[:200]}")
            if x.status_code in (400, 404):
                break
        except requests.RequestException as e:
            ultimo = e
        time.sleep(pausa * (i + 1))
    raise ultimo


def jsonstat_righe(js):
    """
    Converte un dataset JSON-stat 2.0 (formato Eurostat) in righe dict {dimensione: codice, 'valore': x}.
    'value' puo' essere lista o dizionario indice -> valore.
    """
    ids, size = js["id"], js["size"]
    codici = []
    for d in ids:
        idx = js["dimension"][d]["category"]["index"]
        if isinstance(idx, dict):
            codici.append([k for k, _ in sorted(idx.items(), key=lambda kv: kv[1])])
        else:
            codici.append(list(idx))
    val = js.get("value", {})
    if isinstance(val, list):
        coppie = ((i, v) for i, v in enumerate(val) if v is not None)
    else:
        coppie = ((int(i), v) for i, v in val.items() if v is not None)
    passi = [1] * len(size)
    for k in range(len(size) - 2, -1, -1):
        passi[k] = passi[k + 1] * size[k + 1]
    for i, v in coppie:
        riga, resto = {}, i
        for d, p, c in zip(ids, passi, codici):
            riga[d] = c[resto // p]
            resto %= p
        riga["valore"] = float(v)
        yield riga


def a_blocchi(lista, n):
    it = iter(lista)
    while True:
        b = list(itertools.islice(it, n))
        if not b:
            return
        yield b
