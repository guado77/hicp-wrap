# hicp-wrap

Wrap sull'inflazione nell'area euro: Eurostat, BCE, Istat, Destatis, INSEE, INE.
Uscite: PDF a caratteri grandi + Excel storico, sulla chat privata Telegram.

## Stato

- Fase 1 - esplorazione delle fonti: esplora_fonti.py (workflow "fase 1 - esplora fonti")
- Motore, Excel, PDF, commento: FATTI, provati su dati sintetici (workflow "prova motore")
- Fase 2a - lettori Eurostat e BCE: FATTI (fonti/eurostat.py, fonti/bce.py, aggiorna.py).
  Bastano per far girare il wrap su dati veri per EA, IT, DE, FR, ES (HICP e salari).
- Fase 1b - sonda mirata su Istat, BCE HICP, INSEE, INE, Destatis: FATTA
- Fase 2b - lettori Istat (NIC, fondo, carrello, frequenze, retribuzioni), INSEE (IPCH, IPC,
  salari), INE (IPC, IPCA), Destatis (VPI, HVPI): FATTI, con le stime preliminari
- Fase 3 - uscita automatica: FATTA (feriali 12:30 e 15:30, pubblica solo se c'e' un mese nuovo)
- DA FARE: testo dei comunicati degli istituti dentro il commento di Opus
- Fase 3 - calendario delle uscite, avvio automatico a ogni dato preliminare e definitivo: DA FARE

## Stime preliminari

Se Istat, INSEE, INE o Destatis hanno gia' il mese successivo all'ultimo Eurostat, la loro
variazione mensile viene applicata all'indice Eurostat e il mese compare con "p" nel PDF.
Quando Eurostat pubblica quel mese, il dato ufficiale sostituisce la stima.

## Attenzione con GitHub Desktop

Il bot salva l'archivio nel repo a ogni giro: prima di un tuo commit fai sempre Fetch/Pull,
altrimenti il push viene rifiutato.

## Come si pubblica con dati veri

Actions > "aggiorna e pubblica" > Run workflow. Scarica Eurostat e BCE, fonde con l'archivio
in dati/storico (le revisioni sovrascrivono, se una fonte non risponde restano i dati vecchi),
genera PDF ed Excel, li manda sulla chat privata e salva l'archivio nel repo.

## Come si prova il motore

Actions > "prova motore (dati sintetici)" > Run workflow.
Arrivano sulla chat privata il PDF e l'Excel costruiti su dati INVENTATI (lo dice la copertina).
Servono a giudicare impaginazione, grafici, tabelle e fogli, non i numeri.

## Struttura

- main.py - programma principale (--esempio, --senza-commento, --invia, --evento)
- genera_esempio.py - archivio sintetico nello stesso formato di quello vero
- hicp/archivio.py - formato unico dei dati (serie, voci, pesi, salari)
- hicp/calcoli.py - ribasatura gen 2020 = 100, m/m, a/a, 3m/3m, destagionalizzazione di ripiego
- hicp/proiezioni.py - sei scenari a fine anno ed effetto base
- hicp/aggrega.py - aggregazione HICP concatenata; domestica, importata, Supercore
- hicp/distribuzione.py - fasce di inflazione, medie troncate, mediana ponderata
- hicp/potere.py - potere d'acquisto e salari reali
- hicp/motore.py - mette insieme tutto
- hicp/grafici.py, hicp/pdf.py, hicp/excel.py - uscite
- hicp/commento.py - pacchetto dati e commento con Opus (variabile ANTHROPIC_MODEL)
- dati/classificazione_bce_2026.csv - Tabella 4 del BCE Statistics Paper n. 54

## Secret

TELEGRAM_BOT_TOKEN, TELEGRAM_PREVIEW_CHAT_ID; per il commento ANTHROPIC_API_KEY.
Destatis, se il catalogo non si apre come ospite: DESTATIS_USER e DESTATIS_PASS.
