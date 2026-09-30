"""Configurazione del motore: aree, misure, etichette, fasce, date di confronto."""

AREE = {
    "EA": "Area euro",
    "IT": "Italia",
    "DE": "Germania",
    "FR": "Francia",
    "ES": "Spagna",
}

# Misure aggregate. Le prime otto esistono per tutte le aree (Eurostat, stessa metodologia);
# le misure nazionali e quelle Istat compaiono solo dove l'archivio le contiene.
MISURE = {
    "hicp_headline": "HICP generale",
    "hicp_core": "Core (escl. energia, alimentari, alcol e tabacchi)",
    "hicp_ex_energia": "Al netto degli energetici",
    "hicp_beni": "Beni",
    "hicp_servizi": "Servizi",
    "hicp_alimentari": "Alimentari (incl. alcol e tabacchi)",
    "hicp_energia": "Energia",
    "hicp_trasporti": "Trasporti",
    "cpi_headline": "CPI nazionale generale",
    "istat_fondo": "Istat - componente di fondo",
    "istat_carrello": "Istat - carrello della spesa",
    "istat_alta": "Istat - acquisti ad alta frequenza",
    "istat_media": "Istat - acquisti a media frequenza",
    "istat_bassa": "Istat - acquisti a bassa frequenza",
}

# Nome del CPI nazionale per area
CPI_NAZIONALE = {"IT": "NIC (Istat)", "DE": "VPI (Destatis)", "FR": "IPC (INSEE)", "ES": "IPC (INE)"}

# Misure sottostanti ricostruite dal motore sulle voci elementari
SOTTOSTANTI = {
    "domestica": "Domestica (voci HICPX a basso import, flag BCE)",
    "importata": "Importata (voci HICPX non domestiche)",
    "supercore": "Supercore (voci cicliche, flag BCE)",
    "non_supercore": "Non Supercore (voci HICPX acicliche)",
    "troncata10": "Media troncata 10%",
    "troncata25": "Media troncata 25%",
    "troncata30": "Media troncata 30%",
    "troncata50": "Media troncata 50%",
    "troncata75": "Media troncata 75%",
    "mediana": "Mediana ponderata",
}

# Serie BCE pubblicate (solo area euro) con cui tarare le ricostruzioni: nome in archivio -> sottostante
# (la Supercore BCE fino a dic 2025 usa il metodo 2018: si mostra ma non si usa per tarare,
#  perche' i nostri flag sono quelli del metodo 2026)
BCE_CONFRONTO = {
    "bce_troncata10": "troncata10",
    "bce_troncata25": "troncata25",
    "bce_troncata30": "troncata30",
    "bce_troncata50": "troncata50",
    "bce_mediana": "mediana",
    "bce_domestica": "domestica",
}

# Fasce di inflazione annua per la distribuzione delle voci (estremi in %)
FASCE = [
    ("oltre 5%", 5.0, None),
    ("3-5%", 3.0, 5.0),
    ("2-3%", 2.0, 3.0),
    ("1,5-2%", 1.5, 2.0),
    ("sotto 1,5%", None, 1.5),
]

# Date di confronto per il potere d'acquisto
BASI_CONFRONTO = {"gen 2020": "2020-01", "gen 2024": "2024-01"}
BASE_INDICI = "2020-01"          # tutti gli indici ribasati a gennaio 2020 = 100

SCENARI = {
    "momentum": "Momentum ultimi 3 mesi costante",
    "neutro_1a": "Stesse var. mensili dell'anno prima (a/a invariato)",
    "neutro_3a": "Media var. mensili stesso mese, ultimi 3 anni",
    "neutro_5a": "Media var. mensili stesso mese, ultimi 5 anni",
    "mediana_5a": "Mediana var. mensili stesso mese, ultimi 5 anni",
    "obiettivo_2": "Dinamica coerente con il 2% annuo",
}

SCENARI_BREVI = {"momentum": "Momentum", "neutro_1a": "Neutro 1 anno", "neutro_3a": "Media 3 anni",
                 "neutro_5a": "Media 5 anni", "mediana_5a": "Mediana 5 anni", "obiettivo_2": "2%"}

# Macro-categorie delle voci elementari (ECOICOP v2, 6 cifre)
ENERGIA_PREFISSI = ("0451", "0452", "0453", "0454", "0455", "0722")
ALIMENTARI_PREFISSI = ("01", "02")
ALIMENTARI_SERVIZI = ("013000", "022000")      # servizi dentro le divisioni 01-02: stanno nell'HICPX

DIVISIONI = {
    "01": "Alimentari e bevande analcoliche", "02": "Alcolici e tabacchi",
    "03": "Abbigliamento e calzature", "04": "Abitazione e utenze",
    "05": "Mobili e articoli per la casa", "06": "Salute", "07": "Trasporti",
    "08": "Informazione e comunicazione", "09": "Ricreazione, sport e cultura",
    "10": "Istruzione", "11": "Ristorazione e alloggio",
    "12": "Assicurazioni e servizi finanziari", "13": "Cura della persona e altri",
}

SALARI_NOMI = {
    "compensation_per_employee": "Redditi per dipendente (Eurostat)",
    "insee_salaire_mensuel_base": "Salario mensile di base (INSEE)",
    "istat_retribuzioni_contrattuali": "Retribuzioni contrattuali (Istat)",
    "bce_wage_tracker": "Wage tracker BCE",
    "bce_salari_negoziali": "Salari negoziali BCE",
}

MACRO = ["Alimentari", "Energia", "Beni industriali", "Servizi"]
