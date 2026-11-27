\# CLAUDE.md – NesheiMedia Guide



\## Om prosjektet

NesheiMedia Bibelen – en omfattende mørk-modus HTML-guide for videoproduksjon.

Hostet på GitHub Pages: https://regularivar.github.io/NesheiMedia-guide/



\## Filstruktur

\- index.html – hovedfil, skal holdes lean

\- images/ – alle bilder lagres her

\- README.md – prosjektbeskrivelse



\## Tekniske regler

\- All kode i én index.html – ikke opprett separate CSS/JS-filer

\- Bilder lagres alltid i images/-mappen

\- Mørk modus design – behold eksisterende fargepalett

\- Ikke bryt eksisterende kapittelstruktur



\## Aktive skills

\- superpowers – alltid aktiv

\- frontend-design – aktiv ved UI-arbeid

\- code-review – aktiv ved kodegjennomgang



\## Eier

\- Ivar Nesheim, TV-editor ved NRK og frilanser via NesheiMedia

\- Kommunikasjon: norsk bokmål, direkte og konsist

\- Ikke kom med uoppfordrede forslag

\- Følg planen vi er i gang med




## Oppdatering – påvirker også vault og Assist

Teksten i index.html speiler vault-filene i `bibelen/`, og Assist (KUNNSKAP + BIBEL-chat) bygges fra denne index.html. Endrer du innhold her, følg sjekklisten:

`B:\50.06_AI TOOLS\OBSIDIAN_VAULT\wiki\workflow\NesheiMedia-guide\OPPDATERING-SJEKKLISTE.md`

Kort: rett `bibelen/*.md` → `node tools/build-from-md.js` → push → i assist-app: `node scripts/build-kunnskap.js`, øk CACHE i sw.js + test, kjør tester, push.

**Seksjonene i index.html er generert** fra `bibelen/*.md` (siden 2026-11-27). Ikke rediger dem for hånd. Skall, CSS, JS, forside og dashboard redigeres fortsatt i index.html. Widgets ligger i `partials/`. Markdown-formatet står i vaulten: `wiki/workflow/NesheiMedia-guide/PLAN-md-til-nettside.md`.
Verktøy: `tools/build-from-md.js` (bygg, `--check`), `tools/verify_roundtrip.py ORIGINAL.html BYGGET.html` (sammenligner seksjoner), `tools/md_migrate.py` (engangsmigrering, brukt 2026-11-27).
