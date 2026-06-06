# familyblocker-lists

Remote lists and GitHub Actions automation for FamilyBlocker.

## Files used by the browser extension

- `blocked_keywords.txt`
- `blocked_titles.txt`

## Management files

- `blocked_titles_manual.txt`: manually trusted blocked titles.
- `blocked_titles_auto.txt`: generated automatically.
- `blocked_titles_by_genre.txt`: generated review file grouped by Wikidata genre code.
- `blocked_titles_sources.tsv`: generated source map: title -> genre codes.
- `blocked_titles_allowlist.txt`: suppresses specific automatically imported titles.
- `blocked_genres_enabled.txt`: strict genre list enabled by default.
- `blocked_genres_disabled.txt`: Q codes to disable entire automatic genres.

## Logic

`blocked_titles.txt = blocked_titles_manual.txt + auto titles from enabled genres - blocked_titles_allowlist.txt`

Manual titles always win.

## Run manually

Actions -> Update blocked titles -> Run workflow
