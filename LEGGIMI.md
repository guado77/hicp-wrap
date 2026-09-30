# hicp-wrap — fase 1

Cosa fa: interroga i cataloghi di Eurostat, BCE, Istat, INE, INSEE e Destatis e scrive
quali dataset e codici esistono davvero. Non scarica ancora le serie storiche.

## Come si lancia (nessuna riga di comando)

1. Su GitHub crea il repository privato **hicp-wrap**.
2. Clonalo con GitHub Desktop in C:\GitHub\hicp-wrap.
3. Copia dentro tutto il contenuto di questo zip, poi fai Commit e Push da GitHub Desktop.
4. Settings > Secrets and variables > Actions: aggiungi TELEGRAM_BOT_TOKEN e
   TELEGRAM_PREVIEW_CHAT_ID (gli stessi degli altri wrap).
5. Scheda Actions > "fase 1 - esplora fonti" > Run workflow.

Il rapporto arriva sulla chat privata (rapporto_fonti.md + zip di dettaglio) ed è
anche negli artifact del run. Mandamelo così com'è.

## Destatis

Se nel rapporto la sezione Destatis dice che nessuna credenziale ha aperto il catalogo:
registrazione gratuita su genesis.destatis.de, poi secret DESTATIS_USER e DESTATIS_PASS
(oppure DESTATIS_TOKEN se il profilo ti dà un token) e rilancia.

## File

- esplora_fonti.py — le sonde, una per istituto, isolate fra loro
- dati/classificazione_bce_2026.csv — Tabella 4 del Statistics Paper BCE n. 54:
  118 voci HICPX con flag domestica/Supercore, peso 2026 e quota di import
- .github/workflows/esplora-fonti.yml — avvio manuale
