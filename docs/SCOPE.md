# Scope and acceptance

Queue: OpenIntake. Working name: Form Meadow. On 15 November 2026, GitHub `form-meadow in:name` returned five fuzzy matches and no exact repository-name match; quoted web search did not surface an exact software match. Preliminary screening only, not trademark clearance.

Tally's [official FAQ](https://tally.so/help/faq) documents response export through the Submissions tab and Download CSV. Checked 15 November 2026. Our intended comparable workflow is deliberately smaller: build a form → publish its respondent page → submit validated answers → view an authenticated inbox → export CSV. Tally provides many capabilities not planned here; do not claim full parity or that all Tally workflows are paid.

The core preserves immutable schemas with each submission. Revision conflicts fail visibly. Closing a form prevents new responses; retrying a previously accepted identical request returns its original receipt. CSV exports escape formula-looking text while retaining original data in SQLite. Original field labels stay with old answers after edits.

Next: owner authentication separated from respondent access; request size/rate limits; response deletion/retention; public-route errors without inbox leakage; a visual builder, inbox and preview; English/German/Spanish/Japanese/Simplified and Traditional Chinese UI. Test publish → submit in separate browser context → owner inbox → CSV, close/reopen, required fields, stale revisions, unauthorized access and mobile layout. Do not publish a text-only repository as a completed storefront.

Distribution preparation: create a reproducible workshop-registration example with synthetic responses and a real builder-to-CSV recording. The adoption entry point should be a concrete “self-host a simple Tally-style signup form” guide, with a candid feature table. A useful deployment recipe can be offered upstream only after compatible installation and current contribution policy are verified. No external submission, listing acceptance or social publication is claimed.
