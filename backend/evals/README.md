# 选岗 Copilot 评测 harness

针对 DeepSeek tool-calling 选岗 Copilot 的回归评测，防止「改了 prompt / 工具，模型就不调正确工具」的静默退化。

## 两层结构

| 层 | 文件 | 需要 key？ | 需要 deepeval？ | 作用 |
|---|---|---|---|---|
| 离线 plumbing | `tests/test_copilot_eval_offline.py` | 否 | 否 | mock DeepSeek，验证 runner 正确捕获 `tools_used` / GenUI 区块（管线本身）。随主测试套件常驻运行。 |
| 工具正确性（live） | `evals/test_copilot_tooluse.py` | 是 | 是 | 用真实 DeepSeek 跑黄金集，`ToolCorrectnessMetric` 评判模型是否调用了期望工具。 |

`ToolCorrectnessMetric` 不传 `available_tools` 时是**纯确定性**匹配，不调用任何评判 LLM——
所以评测本身**零 token**；token 只花在「让被测 Copilot 真实决定调哪些工具」这一步。

## 运行

```bash
cd backend
pip install -r requirements-dev.txt          # 含 deepeval

# 1) 离线 plumbing（任何时候都能跑，无需 key）
python -m pytest tests/test_copilot_eval_offline.py -v

# 2) live 工具正确性（需有效 DEEPSEEK_API_KEY）
#    缺 deepeval → 整文件跳过；缺/失效 key → live 用例跳过；接线测试始终运行
python -m pytest evals/test_copilot_tooluse.py -v

#    可选：留痕到 Confident AI 仪表盘
deepeval test run evals/test_copilot_tooluse.py
```

> 评测对 DeepSeek 的鉴权/网络故障（如 401/超时）按「跳过」处理，只有「选错工具」才判失败。

## 数据与扩展

- 固定数据集在 `evals/golden_dataset.py`：`FIXTURE_JOBS` / `FIXTURE_RESUME` / `FIXTURE_PREFS` 保证可复现；
  `GOLDENS` 列出每条 `input` 与 `expected_tools`（只列「必须命中」的工具，模型多调无害工具不算错）。
- 加新用例：往 `GOLDENS` 追加一个 `Golden(id, input, expected_tools, expected_block_types)` 即可。
- runner（`evals/runner.py`）通过注入固定 `CopilotContext` 驱动 `_stream_with_tools`，与线上数据隔离。

## 进阶（可选）

回复质量评测（`GEval` / 答案相关性）需要评判 LLM。你只有 DeepSeek key，可实现一个
`DeepEvalBaseLLM` 适配器（用 `app.services.llm_client`）作为 judge 再启用——会产生 token，按需开启。
