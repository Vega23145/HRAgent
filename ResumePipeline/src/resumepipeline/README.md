# resume-pipeline

Mail in -> a MongoDB document + a resume file out, tied together by one key.

```
IMAP unseen -> parse MIME -> attachment text -> clean + strip contacts -> Gemini (schema-forced) -> store
 mail.py        mail.py       reader.py          textprep.py              gemini.py + schema.py    pipeline.py
```

## Output
- MongoDB doc, `_id = <key>`: `email`, `body`, `contact`, `resume_file`, `resume{skills, experience, education, ...}`
- `<RESUME_DIR>/<key>.pdf|.docx|.tex|.latex|`: the original attachment, same `<key>`
- no MONGO_URI? the JSON goes to `<OUT_DIR>/<key>.json` instead
- token usage is logged per resume, not stored

## No orphans
1. Gemini runs first (failure persists nothing) 2. file written atomically 3. record saved;
if that fails the file is deleted. A crash between 2 and 3 is cleaned up by the
startup sweep (`--reconcile` runs it alone): files with no record, older than 10 min,
named like `<16 hex>.pdf|docx|tex|latex`, are removed. Records whose file is missing are reported,
and restored automatically if the same mail is seen again (no Gemini call).

## Run
```
uv sync
set -a && . ./.env && set +a
uv run -m hragent.parsing_engine.resume_pipeline                  # once
uv run -m hragent.parsing_engine.resume_pipeline --loop 60        # every minute
uv run -m hragent.parsing_engine.resume_pipeline --eml mail.eml   # try a saved email, no IMAP
uv run -m hragent.parsing_engine.resume_pipeline --reconcile     # only sync files <-> records
```

## Test (offline)
```
uv run pytest src/hragent/parsing_engine/tests
```
