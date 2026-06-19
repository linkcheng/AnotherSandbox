"""T038: 状态机 + slug/volume 测试。§8.5, data-model.md §6。"""
import pytest

from orchestrator.services.workspace_lifecycle import make_slug, validate_transition, volume_path


def test_legal_transitions():
    assert validate_transition("start", "created") == "running"
    assert validate_transition("start", "stopped") == "running"
    assert validate_transition("stop", "running") == "stopped"
    assert validate_transition("pause", "running") == "paused"
    assert validate_transition("resume", "paused") == "running"
    assert validate_transition("delete", "running") == "deleted"
    assert validate_transition("delete", "stopped") == "deleted"


def test_idempotent_transition():
    # 已在目标态 → 幂等返回当前态（resume→running 已 running 则无操作）
    assert validate_transition("start", "running") == "running"
    assert validate_transition("stop", "stopped") == "stopped"
    assert validate_transition("resume", "running") == "running"


def test_illegal_transition_raises():
    with pytest.raises(ValueError):
        validate_transition("pause", "stopped")  # 只能从 running pause
    with pytest.raises(ValueError):
        validate_transition("resume", "stopped")  # 只能从 paused resume
    with pytest.raises(ValueError):
        validate_transition("start", "paused")  # 只能从 created/stopped start


def test_unknown_action_raises():
    with pytest.raises(ValueError):
        validate_transition("reboot", "running")


def test_make_slug_lowercase_and_suffix():
    slug = make_slug("Alice Dev Box")
    assert slug.startswith("alice-dev-box-")
    assert len(slug) > len("alice-dev-box-")


def test_make_slug_empty_name():
    assert make_slug("!!!").startswith("ws-")


def test_volume_path():
    assert volume_path("/data/ws", "alice-abc") == "/data/ws/alice-abc"
