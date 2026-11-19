"""纯函数单元测试：不联网，只验证结果对象与汇总渲染的行为契约。"""

import pytest

from agent_homework import Result, render, summarize


def test_summarize_counts_ok_and_failed() -> None:
    results = [
        Result("https://a", 200, True, 10.0, 100),
        Result("https://b", 404, False, 12.0, 50),
        Result("https://c", 0, False, 5000.0, error="timeout"),
    ]
    assert summarize(results, 20.0) == {
        "requested": 3,
        "ok": 1,
        "failed": 2,
        "wall_ms": 20.0,
    }


def test_render_shows_failure_reason_and_total() -> None:
    text = render([Result("https://x", 0, False, 5.0, error="timeout")], 5.0)
    assert "[timeout]" in text
    assert "完成 0/1（失败 1）" in text


def test_result_is_immutable() -> None:
    result = Result("https://x", 200, True, 1.0)
    with pytest.raises(AttributeError):
        result.url = "https://y"  # type: ignore[misc]
