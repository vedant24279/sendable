"""Tests for compare-view backend endpoints (/api/runs, /api/clips/{id}/compare)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def compare_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    labels_dir = tmp_path / "labels"
    runs_dir.mkdir()
    reports_dir.mkdir()
    labels_dir.mkdir()

    monkeypatch.setenv("EVAL_RUNS_DIR", str(runs_dir))
    monkeypatch.setenv("EVAL_REPORTS_DIR", str(reports_dir))
    monkeypatch.setenv("LABELS_DIR", str(labels_dir))

    # Older run with run_info.json
    old_run = runs_dir / "run_old"
    old_run.mkdir()
    (old_run / "run_info.json").write_text(
        json.dumps({"run_name": "run_old", "utc_time": "2026-01-01T10:00:00Z"}),
        encoding="utf-8",
    )

    # Newer run with run_info.json
    new_run = runs_dir / "run_new_2"
    new_run.mkdir()
    (new_run / "run_info.json").write_text(
        json.dumps({"run_name": "run_new_2", "utc_time": "2026-02-01T12:00:00Z"}),
        encoding="utf-8",
    )

    # Folder without run_info.json (should be ignored)
    incomplete_run = runs_dir / "incomplete"
    incomplete_run.mkdir()

    # Folder with disallowed characters (should be ignored)
    weird_run = runs_dir / "weird run!"
    weird_run.mkdir()
    (weird_run / "run_info.json").write_text(
        json.dumps({"run_name": "weird run!", "utc_time": "2026-03-01T00:00:00Z"}),
        encoding="utf-8",
    )

    # Clip results in run_new_2
    clip_dir = new_run / "c_abc123"
    clip_dir.mkdir()
    (clip_dir / "results.json").write_text(
        json.dumps(
            {
                "events": {
                    "release": {"frame": 4, "x": 111.5, "y": 222.5},
                    "bounce": {"frame": 14, "x": 333.0, "y": 444.0, "zone": "GOOD", "length_m": 6.5},
                    "impact": None,
                    "deviation": {"frame": 20, "x": 350.0, "y": 510.0},
                },
                "trajectory": [
                    {"frame": 4, "x": 111.5, "y": 222.5, "conf": 0.9, "interpolated": False},
                    {"frame": 5, "x": 120.0, "y": 240.0, "interpolated": True},
                ],
            }
        ),
        encoding="utf-8",
    )

    # Per-clip CSV for run_new_2
    csv_path = reports_dir / "run_new_2_per_clip.csv"
    headers = [
        "clip_id",
        "release_frame_error",
        "release_px_error",
        "bounce_frame_error",
        "bounce_px_error",
        "bounce_ground_error_m",
        "bounce_pitch_z_error_m",
        "deviation_frame_error",
        "deviation_px_error",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(
            {
                "clip_id": "c_abc123",
                "release_frame_error": "-1",
                "release_px_error": "12.5",
                "bounce_frame_error": "0",
                "bounce_px_error": "6.2",
                "bounce_ground_error_m": "0.312",
                "bounce_pitch_z_error_m": "0.310",
                "deviation_frame_error": "2",
                "deviation_px_error": "45.0",
            }
        )

    return {"runs_dir": runs_dir, "reports_dir": reports_dir, "headers": headers}


def test_list_runs_newest_first(compare_env) -> None:
    client = TestClient(app)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == ["run_new_2", "run_old"]


def test_compare_found_with_csv_row(compare_env) -> None:
    client = TestClient(app)
    resp = client.get("/api/clips/c_abc123/compare", params={"run": "run_new_2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["events"]["release"] == {"frame": 4, "x": 111.5, "y": 222.5}
    assert data["events"]["bounce"]["zone"] == "GOOD"
    assert data["events"]["deviation"] == {"frame": 20, "x": 350.0, "y": 510.0}
    assert len(data["trajectory"]) == 2
    assert list(data["csv_row"].keys()) == compare_env["headers"]
    assert data["csv_row"]["bounce_ground_error_m"] == "0.312"


def test_compare_missing_clip_returns_found_false(compare_env) -> None:
    client = TestClient(app)
    resp = client.get("/api/clips/c_missing/compare", params={"run": "run_new_2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False


@pytest.mark.parametrize(
    "bad_run",
    [
        "",
        "bad run",
        "run$1",
        "../secrets",
        "..\\secrets",
        "a/b",
        ".",
        "..",
    ],
)
def test_compare_rejects_bad_and_traversal_run_names(compare_env, bad_run: str) -> None:
    client = TestClient(app)
    resp = client.get("/api/clips/c_abc123/compare", params={"run": bad_run})
    assert resp.status_code == 400


def test_compare_rejects_bad_clip_id_traversal(compare_env) -> None:
    client = TestClient(app)
    resp = client.get("/api/clips/..%2Fetc/compare", params={"run": "run_new_2"})
    assert resp.status_code in (400, 404)
    resp2 = client.get("/api/clips/bad clip!/compare", params={"run": "run_new_2"})
    assert resp2.status_code == 400


def test_run_metrics_endpoint_and_validation(compare_env) -> None:
    client = TestClient(app)
    ok = client.get("/api/runs/run_new_2/metrics")
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["run"] == "run_new_2"
    assert "c_abc123" in payload["rows"]

    bad = client.get("/api/runs/bad$run/metrics")
    assert bad.status_code == 400
