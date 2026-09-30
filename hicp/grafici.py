"""Grafici matplotlib a caratteri grandi, alto contrasto, per il PDF."""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from . import config  # noqa: E402

COLORI = ["#08306B", "#D95F02", "#000000", "#1B7837", "#B2182B", "#6A3D9A", "#8C6D31"]
COLORI_AREA = {"EA": "#000000", "IT": "#1B7837", "DE": "#B2182B", "FR": "#08306B", "ES": "#D95F02"}
COLORI_FASCE = ["#67000D", "#D6604D", "#F4A582", "#92C5DE", "#2166AC"]
COLORI_SCENARI = {"momentum": "#B2182B", "neutro_1a": "#000000", "neutro_3a": "#08306B",
                  "neutro_5a": "#6A3D9A", "mediana_5a": "#1B7837", "obiettivo_2": "#8C6D31"}

plt.rcParams.update({
    "font.size": 15, "axes.titlesize": 18, "axes.labelsize": 15, "xtick.labelsize": 14,
    "ytick.labelsize": 14, "legend.fontsize": 14, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#BBBBBB", "grid.linewidth": 0.8, "lines.linewidth": 2.8,
    "figure.dpi": 150, "savefig.dpi": 170, "axes.titlelocation": "left",
})

_MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _fmt_data(x, _):
    d = mdates.num2date(x)
    return str(d.year) if d.month == 1 else f"{_MESI[d.month - 1]}\n{d.year % 100:02d}"


_date_it = FuncFormatter(_fmt_data)

_virgola = FuncFormatter(lambda x, _: f"{x:g}".replace(".", ","))


class Grafici:
    def __init__(self, cartella):
        self.cartella = cartella
        os.makedirs(cartella, exist_ok=True)
        self.n = 0

    def _salva(self, fig, nome):
        self.n += 1
        p = os.path.join(self.cartella, f"{self.n:03d}_{nome}.png")
        fig.savefig(p, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return p

    @staticmethod
    def _ts(s, dal):
        s = s.dropna()
        x = s.index.to_timestamp(how="end").normalize() if s.index.freqstr.startswith("Q") \
            else s.index.to_timestamp()
        tieni = x >= pd.Timestamp(dal)
        return x[tieni], s.values[tieni]

    def _base(self, titolo, altezza=5.2, zero=True):
        fig, ax = plt.subplots(figsize=(10, altezza))
        ax.set_title(titolo)
        ax.yaxis.set_major_formatter(_virgola)
        loc = mdates.AutoDateLocator(minticks=4, maxticks=8)
        ax.xaxis.set_major_locator(loc)
        ax.xaxis.set_major_formatter(_date_it)
        if zero:
            ax.axhline(0, color="#000000", linewidth=1.0)
        return fig, ax

    def _legenda(self, ax, ncol=3):
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=ncol, frameon=False)

    # ------------------------------------------------------------------
    def linee(self, serie, titolo, nome, dal="2019-01", obiettivo=True, colori=None, ncol=3):
        """serie: dict etichetta -> Series (tassi in %)."""
        fig, ax = self._base(titolo)
        for i, (lab, s) in enumerate(serie.items()):
            if s is None:
                continue
            x, y = self._ts(s, dal)
            ax.plot(x, y, label=lab, color=(colori or {}).get(lab, COLORI[i % len(COLORI)]))
        if obiettivo:
            ax.axhline(2, color="#555555", linestyle="--", linewidth=1.6)
        ax.set_ylabel("%")
        self._legenda(ax, ncol)
        return self._salva(fig, nome)

    def proiezioni(self, aa, pro, titolo, nome):
        fig, ax = self._base(titolo, altezza=5.6, zero=False)
        t = pro["ultimo"]
        x, y = self._ts(aa, str(t - 23))
        ax.plot(x, y, color="#000000", linewidth=3.4, label="Dato osservato")
        for k in pro["yoy"].columns:
            s = pd.concat([aa[[t]], pro["yoy"][k]])
            ax.plot(s.index.to_timestamp(), s.values, linestyle="--", linewidth=2.6,
                    color=COLORI_SCENARI.get(k), label=config.SCENARI_BREVI[k])
        ax.axhline(2, color="#555555", linestyle=":", linewidth=1.4)
        ax.set_ylabel("% a/a")
        self._legenda(ax, 4)
        return self._salva(fig, nome)

    def barre_orizzontali(self, valori, titolo, nome, unita="%"):
        """valori: dict etichetta -> numero."""
        et = list(valori.keys())[::-1]
        v = [valori[k] for k in et]
        fig, ax = plt.subplots(figsize=(10, 0.62 * len(et) + 1.6))
        ax.set_title(titolo)
        ax.barh(et, v, color=["#B2182B" if x > 0 else "#2166AC" for x in v])
        for i, x in enumerate(v):
            ax.text(x, i, f"  {x:+.1f}{unita}".replace(".", ","), va="center",
                    ha="left" if x >= 0 else "right", fontsize=14, fontweight="bold")
        ax.xaxis.set_major_formatter(_virgola)
        ax.grid(axis="y", visible=False)
        m = max(abs(x) for x in v) if v else 1
        ax.set_xlim(min(0, min(v)) - 0.25 * m, max(0, max(v)) + 0.3 * m)
        return self._salva(fig, nome)

    def fasce_per_area(self, quote, titolo, nome):
        """quote: dict area -> {fascia: %} (ponderate)."""
        aree = list(quote.keys())[::-1]
        fig, ax = plt.subplots(figsize=(10, 0.8 * len(aree) + 2.2))
        ax.set_title(titolo)
        sinistra = [0.0] * len(aree)
        for (fascia, _, _), col in zip(config.FASCE, COLORI_FASCE):
            v = [quote[a].get(fascia, 0.0) for a in aree]
            ax.barh(aree, v, left=sinistra, color=col, label=fascia, edgecolor="white")
            for i, (s0, x) in enumerate(zip(sinistra, v)):
                if x >= 7:
                    ax.text(s0 + x / 2, i, f"{x:.0f}", ha="center", va="center", fontsize=13,
                            color="white" if col in ("#67000D", "#D6604D", "#2166AC") else "black",
                            fontweight="bold")
            sinistra = [s + x for s, x in zip(sinistra, v)]
        ax.set_xlim(0, 100)
        ax.set_xlabel("% del paniere (per peso)")
        ax.grid(axis="y", visible=False)
        self._legenda(ax, 5)
        return self._salva(fig, nome)

    def fasce_storico(self, df, titolo, nome, dal="2019-01"):
        df = df[df.index >= pd.Period(dal, freq="M")]
        fig, ax = plt.subplots(figsize=(10, 5.4))
        ax.set_title(titolo)
        ax.stackplot(df.index.to_timestamp(), *[df[f] for f, _, _ in config.FASCE],
                     labels=[f for f, _, _ in config.FASCE], colors=COLORI_FASCE)
        ax.set_ylim(0, 100)
        ax.set_ylabel("% del paniere")
        self._legenda(ax, 5)
        return self._salva(fig, nome)

    def salari_prezzi(self, dati, titolo, nome):
        """dati: dict etichetta -> Series indice (base = 100)."""
        fig, ax = self._base(titolo, zero=False)
        for i, (lab, s) in enumerate(dati.items()):
            ax.plot(s.index.to_timestamp(), s.values, label=lab, color=COLORI[i % len(COLORI)])
        ax.axhline(100, color="#555555", linestyle="--", linewidth=1.4)
        ax.set_ylabel("indice")
        self._legenda(ax, 2)
        return self._salva(fig, nome)
