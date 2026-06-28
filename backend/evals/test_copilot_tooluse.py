"""选岗 Copilot 工具调用正确性 live 评测（deepeval ToolCorrectnessMetric，确定性、零 token）。

运行条件（缺一即整文件跳过）：
- 安装 deepeval（`pip install -r requirements-evals.txt`）
- 设置 DEEPSEEK_API_KEY（评测会真实调用 DeepSeek 让模型决定调哪些工具）

运行方式：
    cd backend
    python -m pytest evals/test_copilot_tooluse.py -v        # 普通 pytest 即可（metric 为确定性）
    # 或留痕到 Confident AI：deepeval test run evals/test_copilot_tooluse.py

说明：ToolCorrectnessMetric 不传 available_tools 时为纯确定性匹配（不调用任何评判 LLM），
因此评测本身不产生 token；token 仅花在「让被测 Copilot 真实决定调哪些工具」这一步。
"""
import os

import httpx
import pytest

# 某些 deepeval 版本在 import 时会探测 OPENAI_API_KEY；这里给个占位避免噪声。
os.environ.setdefault("OPENAI_API_KEY", "dummy")

deepeval = pytest.importorskip("deepeval", reason="deepeval 未安装，跳过 live 评测")
from deepeval.metrics import ToolCorrectnessMetric  # noqa: E402
from deepeval.test_case import LLMTestCase, ToolCall  # noqa: E402

from app.config import settings  # noqa: E402
from evals.golden_dataset import GOLDENS  # noqa: E402
from evals.runner import run_copilot  # noqa: E402

_HAS_KEY = bool(settings.deepseek_api_key) and settings.deepseek_api_key != "DEMO_KEY"

# 命中率阈值：期望工具被命中的比例（默认非严格匹配，允许模型多调无害工具）。
TOOL_THRESHOLD = 0.99


def test_tool_correctness_metric_wiring():
    """不需要 key/不调用模型：验证 deepeval API 接线正确（CI 在装了 deepeval 时守护）。"""
    good = LLMTestCase(
        input="北京后端实习",
        actual_output="字节跳动后端实习",
        tools_called=[ToolCall(name="search_jobs")],
        expected_tools=[ToolCall(name="search_jobs")],
    )
    metric = ToolCorrectnessMetric(threshold=TOOL_THRESHOLD)
    metric.measure(good)
    assert metric.score >= TOOL_THRESHOLD

    bad = LLMTestCase(
        input="最适合我的岗位",
        actual_output="...",
        tools_called=[ToolCall(name="get_preferences")],
        expected_tools=[ToolCall(name="rerank_by_resume")],
    )
    metric2 = ToolCorrectnessMetric(threshold=TOOL_THRESHOLD)
    metric2.measure(bad)
    assert metric2.score < TOOL_THRESHOLD


@pytest.mark.skipif(not _HAS_KEY, reason="未配置 DEEPSEEK_API_KEY，跳过 live 评测")
@pytest.mark.parametrize("golden", GOLDENS, ids=[g.id for g in GOLDENS])
def test_tool_correctness(golden):
    try:
        res = run_copilot(golden.input)
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        # DeepSeek 鉴权/网络故障属环境问题，跳过而非判失败（只有「选错工具」才算评测失败）。
        pytest.skip(f"DeepSeek 调用失败（环境问题，非评测失败）：{e}")

    test_case = LLMTestCase(
        input=golden.input,
        actual_output=res.reply or "(no reply)",
        tools_called=[ToolCall(name=n) for n in res.tool_names] or [ToolCall(name="<none>")],
        expected_tools=[ToolCall(name=n) for n in golden.expected_tools],
    )

    metric = ToolCorrectnessMetric(threshold=TOOL_THRESHOLD)
    metric.measure(test_case)

    assert metric.score >= TOOL_THRESHOLD, (
        f"[{golden.id}] 期望工具 {golden.expected_tools}，实际 {res.tool_names}，"
        f"score={metric.score:.2f} reason={metric.reason}"
    )

    # 附加确定性断言：期望的 GenUI 区块类型应出现
    for bt in golden.expected_block_types:
        assert bt in res.block_types, (
            f"[{golden.id}] 期望产出区块 {bt}，实际 {res.block_types}"
        )
