"""Tests for run_batch --hand-from-labels (per-clip TRACKER_BATTER_HAND)."""
from __future__ import annotations

from run_batch import clip_subprocess_env, parse_args


def test_flag_off_returns_batch_env_unchanged() -> None:
    base = {"TRACKER_BATTER_HAND": "right", "A": "1"}
    assert clip_subprocess_env(base, {"batter_hand": "left"}, False) is base
    assert clip_subprocess_env(None, {"batter_hand": "left"}, False) is None


def test_hand_from_label_overrides_batch_value() -> None:
    base = {"TRACKER_BATTER_HAND": "right", "A": "1"}
    env = clip_subprocess_env(base, {"batter_hand": "left"}, True)
    assert env["TRACKER_BATTER_HAND"] == "left" and env["A"] == "1"
    assert base["TRACKER_BATTER_HAND"] == "right"  # batch env not mutated
    assert clip_subprocess_env(base, {"batter_hand": "Right"}, True)["TRACKER_BATTER_HAND"] == "right"


def test_null_hand_unsets_variable() -> None:
    base = {"TRACKER_BATTER_HAND": "right"}
    assert "TRACKER_BATTER_HAND" not in clip_subprocess_env(base, {"batter_hand": None}, True)
    assert "TRACKER_BATTER_HAND" not in clip_subprocess_env(base, {}, True)


def test_without_batch_env_copies_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("SOME_MARKER_VAR", "x")
    env = clip_subprocess_env(None, {"batter_hand": "right"}, True)
    assert env["SOME_MARKER_VAR"] == "x" and env["TRACKER_BATTER_HAND"] == "right"


def test_cli_flag_parses() -> None:
    assert parse_args(["--run-name", "r", "--hand-from-labels"]).hand_from_labels is True
    assert parse_args(["--run-name", "r"]).hand_from_labels is False
