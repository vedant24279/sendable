# Annotator Engineering Standards & Testing Rules

- Manual checks must start the backend with LABELS_DIR set to a temp folder; never write to eval/labels while testing, and paste git status at the end.
- For tests and manual checks set LABELS_DIR and ANNOTATOR_LIBRARY_DIR to temp folders; never write to eval/labels or the real library while testing; delete test data afterwards; paste `git status --short` at the end (nothing under eval/).
