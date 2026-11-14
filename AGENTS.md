# AGENTS.md - sendable

Project: cricket ball tracker (release, bounce, bat/pad impact, post-hit path, LBW, slow-motion replay). Tools live in tools/annotator/.

RULES
1. Do only the task given; edit only the files the task names.
2. For anything touching more than 3 files, write a short plan first.
3. Never delete or rename files or rewrite git history. Never delete videos or labels.
4. results.json changes are additive only; bump schema_version when adding fields.
5. No hard-coded absolute paths (no D:\). Use pathlib and environment variables.
6. Do not download models or data; do not commit videos, model weights or secrets.
7. Tests and manual checks: set LABELS_DIR and ANNOTATOR_LIBRARY_DIR to temp folders; never write to eval/labels or the real library; delete test data afterwards; paste `git status --short` at the end (nothing under eval/).
8. Run the relevant tests (pytest, npm test, npm run build) before reporting.
9. If you are not sure about something, say so. Do not invent results or file contents.
10. End every task with a REPORT: files changed, how to run, test output, open problems.
11. Never stop, restart or repoint the running servers on ports 8765 and 5173; for tests use other ports and temp LABELS_DIR.
