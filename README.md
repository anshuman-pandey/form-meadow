# Form Meadow · development checkout

A focused open-source alternative to Tally, in preparation: forms, a response inbox, and CSV export. **This is a tested storage component, not a finished or published product.**

## Run the current component

Python 3.10+; no third-party packages required.

```sh
python3 -m unittest discover -s tests -v
python3 demo.py
```

The disposable demo creates a form, opens it, submits synthetic data, reads the inbox and prints CSV. It never listens on a port or retains personal data. The `Forms` Python API stores real libraries in a SQLite file supplied by its caller.

Implemented: text, email, single-choice and explicit consent fields; required-field validation; closed-by-default forms; immutable question versions; stale-edit/submission detection; idempotent retries; persisted inbox; and CSV export with spreadsheet-formula escaping. CSV uses one row per answer, retaining each response's original label and version. Do not claim legal compliance from the existence of a consent checkbox.

Still required: authenticated owner interface, public respondent route with request limits, polished builder/inbox, six interface languages, browser acceptance, real screenshots, install/deployment instructions and owner launch handoff. The storage API has **no authorization layer** and must not be exposed directly over HTTP. No payments, uploads, conditional logic, email delivery, AI, or feature parity with Tally is claimed.

See [scope and distribution](docs/SCOPE.md). MIT licensed. Publication needs the owner's separate product-specific go-ahead.
