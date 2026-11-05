import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_labels_dir(tmp_path, monkeypatch):
    """
    Ensure every single test isolates LABELS_DIR to a temporary directory,
    guaranteeing that test runs never create or modify files in eval/labels/.
    """
    labels_tmp = tmp_path / "eval_labels"
    labels_tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LABELS_DIR", str(labels_tmp))
    return labels_tmp
