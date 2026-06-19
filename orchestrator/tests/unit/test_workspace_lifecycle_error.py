"""T041: workspace start 失败 → status=error + error_message 写入（FR-018）。

纯函数 apply_start_result 测试：compose up 失败（returncode!=0/stderr）→
status 转 error + error_message 保留 stderr 摘要；成功 → status=running +
error_message 清空（避免历史错误残留）。compose_runner 零改动（FR-019）。
"""
from types import SimpleNamespace

from orchestrator.services.compose_runner import ComposeResult
from orchestrator.services.workspace_lifecycle import apply_start_result


def _ws(status: str = "starting", error_message: str | None = None) -> SimpleNamespace:
    """轻量 workspace 替身（仅关注 status / error_message 两字段）。"""
    return SimpleNamespace(status=status, error_message=error_message)


def test_start_success_sets_running_and_clears_error():
    """成功：starting → running，且历史 error_message 被清空。"""
    ws = _ws(status="starting", error_message="历史错误")
    apply_start_result(ws, ComposeResult(success=True, returncode=0))
    assert ws.status == "running"
    assert ws.error_message is None  # 成功必须清空历史错误


def test_start_failure_sets_error_and_records_stderr():
    """失败：starting → error，error_message 含 stderr 摘要（FR-018）。"""
    ws = _ws(status="starting")
    result = ComposeResult(success=False, returncode=1, stderr="Bind for 0.0.0.0:8100 failed: port is already allocated")
    apply_start_result(ws, result)
    assert ws.status == "error"
    assert ws.error_message is not None
    assert "port is already allocated" in ws.error_message


def test_start_failure_with_empty_stderr_still_records_message():
    """失败但 stderr 空：仍写 error_message（非 None，便于前端展示）。"""
    ws = _ws(status="starting")
    apply_start_result(ws, ComposeResult(success=False, returncode=1, stderr=""))
    assert ws.status == "error"
    assert ws.error_message is not None
    assert ws.error_message != ""


def test_start_failure_truncates_long_stderr():
    """stderr 过长截断（防 TEXT 列虽无硬限但前端展示可控）。"""
    ws = _ws(status="starting")
    long_stderr = "x" * 5000
    apply_start_result(ws, ComposeResult(success=False, returncode=1, stderr=long_stderr))
    assert ws.status == "error"
    assert ws.error_message is not None
    assert len(ws.error_message) <= 2000
