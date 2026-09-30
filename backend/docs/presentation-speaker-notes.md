# Panel presentation speaker notes (10 minutes)

The companion `panel-presentation.pdf` is a seven-slide deck. Target 8 minutes for the walkthrough and reserve 2 minutes for Q&A.

## Before the demo
- Start backend and frontend; sign in with an HR account.
- Confirm a prepared job brief and a candidate with source-linked evidence exist.
- Keep the Admin evaluation page available only if a labeled dataset and completed run are ready; never imply metrics exist without labels.

## Timed run of show

| Time | Action |
| --- | --- |
| 00:00-00:40 | Explain evidence-led recruiter decision support.
| 00:40-01:45 | Walk the architecture diagram from ingestion through retrieval, ranking, and evaluation.
| 01:45-02:30 | Show job brief creation, including file upload, then open Search.
| 02:30-05:40 | Run a prepared query; inspect shortlist, score/fallback status, requirement states, evidence, and compare.
| 05:40-06:50 | Show how relevance and skill labels produce ranking/classification/grounding metrics. State the dataset size and limits accurately.
| 06:50-07:35 | Explain hybrid retrieval, fallback behavior, traceability, and remaining provider/data limits.
| 07:35-08:00 | Recap and invite questions.
| 08:00-10:00 | Q&A.

## Demo query template

Use a role already represented in the loaded corpus. Example: `Find a Python and SQL engineer with production data-pipeline experience; prefer cloud deployment experience.` Pick a known resume and verify every example claim against the displayed source evidence. Do not quote invented scores or metrics.
