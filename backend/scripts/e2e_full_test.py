"""端到端测试：示例 PDF 简历 + 示例 JD 全流程（虚构数据）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPORT = Path(__file__).resolve().parent / "e2e_report.json"

JD_TEXT = """管培之星项目旨在储备优秀的金融科技复合人才，涵盖AI产品、AI应用、研究、市场、投资交易、商务等方向。

工作职责：
负责AI驱动的互联网产品全生命周期管理，深入挖掘用户需求，主导功能开发与体验优化。
1、开展用户调研、竞品分析与数据挖掘；
2、梳理现有产品功能与业务流程，提出改进方案并推动落地；
3、协同技术、设计、测试等多部门，保障产品高质量交付；
4、协助市场、运营等团队，推动产品推广与用户增长。

任职资格：
1、2027届本科及以上学历毕业生，理工科背景优先；
2、对金融科技及互联网产品有浓厚兴趣；
3、具有股票、期货、基金等金融投资理财经验者优先；
4、具备良好的沟通协调能力与团队合作精神。"""

RESUME_PLAIN = """示例候选人
手机：10000000000 | 邮箱：candidate@example.com | 上海
求职意向：产品经理 / 管培生

教育经历
示例大学 | 计算机学院 | 本科 | 2023.09 - 2027.06
主修课程：数据结构、机器学习、数据库系统、软件工程
GPA：3.6/4.0

实习经历
示例科技公司 | 产品实习生 | 2025.06 - 至今
1. 参与新产品立项，开展用户调研与竞品分析，输出需求优先级清单
2. 撰写 PRD 与原型，协同研发、设计推进迭代上线
3. 跟踪核心指标，参与 A/B 测试与体验优化

示例数据公司 | 数据分析实习生 | 2024.09 - 2025.05
1. 搭建业务数据看板，使用 Python/SQL 完成取数与分析
2. 输出周报月报，支持运营与产品决策
3. 参与用户分群项目，熟悉基础增长分析方法

项目经历
校园投资社 | 成员 | 2024.09 - 至今
开展基金与股票模拟投资练习，撰写市场复盘报告

专业技能
产品：用户调研、PRD、原型设计、跨部门协作
数据：Python、SQL、Excel、基础统计分析
语言：英语 CET-6"""


def make_pdf(path: Path) -> None:
    try:
        from fpdf import FPDF
    except ImportError:
        raise SystemExit("请先安装 fpdf2: pip install fpdf2")

    font_path = Path(r"C:\Windows\Fonts\simhei.ttf")
    if not font_path.exists():
        font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    if not font_path.exists():
        raise SystemExit("未找到中文字体")

    pdf = FPDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.add_font("cn", "", str(font_path))
    pdf.set_font("cn", size=10)
    w = pdf.w - pdf.l_margin - pdf.r_margin
    for line in RESUME_PLAIN.splitlines():
        if line.strip():
            pdf.multi_cell(w, 6, line)
        else:
            pdf.ln(2)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def api_json(
    client: httpx.Client, method: str, path: str, payload: dict, timeout: float = 180
) -> dict:
    r = client.request(method, f"{BASE}{path}", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not data.get("success", True) and data.get("error"):
        raise RuntimeError(f"{path} failed: {data['error']}")
    return data


def post_json(client: httpx.Client, path: str, payload: dict, timeout: float = 180) -> dict:
    return api_json(client, "POST", path, payload, timeout)


def main() -> int:
    report: dict = {"steps": [], "issues": [], "passed": True}
    pdf_path = FIXTURES / "sample_resume.pdf"
    kb_path = Path(__file__).resolve().parents[2] / "knowledge" / "简历数据库.example.md"
    knowledge = kb_path.read_text(encoding="utf-8")

    print("=== 1. 生成测试 PDF ===")
    make_pdf(pdf_path)
    report["steps"].append({"step": "create_pdf", "path": str(pdf_path), "size": pdf_path.stat().st_size})

    with httpx.Client() as client:
        print("=== 2. 解析简历 ===")
        t0 = time.time()
        with pdf_path.open("rb") as f:
            r = client.post(
                f"{BASE}/api/parse-resume",
                files={"file": ("sample_resume.pdf", f, "application/pdf")},
                timeout=300,
            )
        r.raise_for_status()
        parsed = r.json()
        if not parsed.get("success"):
            report["issues"].append(f"parse-resume: {parsed}")
            report["passed"] = False
            _save(report)
            return 1
        session_id = parsed["data"]["session_id"]
        md = parsed["data"]["markdown"]
        report["steps"].append({
            "step": "parse_resume",
            "session_id": session_id,
            "elapsed_s": round(time.time() - t0, 1),
            "md_chars": len(md),
        })
        print(f"  session={session_id}, chars={len(md)}")

        print("=== 3. 保存知识库 ===")
        kb = api_json(
            client, "PUT", "/api/knowledge-base",
            {"session_id": session_id, "content": knowledge},
        )
        report["steps"].append({"step": "knowledge_base", "has_photo": kb["data"].get("has_photo")})

        print("=== 4. JD 分析 ===")
        t0 = time.time()
        jd = post_json(client, "/api/analyze-jd", {"session_id": session_id, "jd_text": JD_TEXT})
        analysis = jd["data"]["analysis"]
        report["steps"].append({
            "step": "analyze_jd",
            "elapsed_s": round(time.time() - t0, 1),
            "role": analysis.get("role"),
            "keywords": analysis.get("keywords", [])[:12],
        })

        print("=== 5. 匹配度分析 ===")
        t0 = time.time()
        match_resp = post_json(client, "/api/analyze-match", {"session_id": session_id})
        match = match_resp["data"]["match"]
        report["steps"].append({
            "step": "analyze_match",
            "elapsed_s": round(time.time() - t0, 1),
            "overall_score": match.get("overall_score"),
        })

        print("=== 6. 生成修改建议 ===")
        t0 = time.time()
        sug_resp = post_json(
            client,
            "/api/generate-suggestions",
            {"session_id": session_id, "knowledge_base": knowledge},
            timeout=300,
        )
        suggestions = sug_resp["data"]["suggestions"]
        density = sug_resp["data"].get("density", {})
        report["steps"].append({
            "step": "generate_suggestions",
            "elapsed_s": round(time.time() - t0, 1),
            "count": len(suggestions),
            "density": density,
        })

        print("=== 7. 接受建议（跳过 delete/structure）===")
        accepted, rejected = 0, 0
        current_md = md
        sparse = (density or {}).get("status") == "sparse"
        for s in suggestions:
            if s["type"] in ("delete",) or (sparse and s["type"] == "structure"):
                post_json(
                    client,
                    "/api/update-suggestion-status",
                    {"session_id": session_id, "suggestion_id": s["id"], "status": "rejected"},
                )
                rejected += 1
                continue
            resp = post_json(
                client,
                "/api/update-suggestion-status",
                {"session_id": session_id, "suggestion_id": s["id"], "status": "accepted"},
            )
            if resp["data"].get("current_markdown"):
                current_md = resp["data"]["current_markdown"]
            accepted += 1
        report["steps"].append({
            "step": "accept_suggestions",
            "accepted": accepted,
            "rejected": rejected,
            "md_chars_after": len(current_md),
        })

        print("=== 8. 定稿 ===")
        t0 = time.time()
        try:
            fin = post_json(client, "/api/finalize-resume", {"session_id": session_id}, timeout=300)
            validation = fin["data"].get("validation", {})
            final_md = fin["data"].get("markdown", "")
            report["steps"].append({
                "step": "finalize",
                "elapsed_s": round(time.time() - t0, 1),
                "validation": validation,
                "final_chars": len(final_md),
            })
            (FIXTURES / "sample_final_resume.md").write_text(final_md, encoding="utf-8")
        except httpx.HTTPStatusError as e:
            body = e.response.json() if e.response.content else {}
            report["issues"].append(f"finalize failed: {body.get('detail', e)}")
            report["passed"] = False
            _save(report)
            return 1

        print("=== 9. 导出 PDF ===")
        t0 = time.time()
        exp_r = client.post(
            f"{BASE}/api/export-pdf",
            json={"session_id": session_id, "mode": "standard"},
            timeout=120,
        )
        exp_r.raise_for_status()
        out_pdf = FIXTURES / f"sample_export_{session_id[:8]}.pdf"
        out_pdf.write_bytes(exp_r.content)
        report["steps"].append({
            "step": "export_pdf",
            "elapsed_s": round(time.time() - t0, 1),
            "size_bytes": len(exp_r.content),
        })

        checks = _evaluate(analysis, match, suggestions, fin["data"])
        report["checks"] = checks
        if not all(c["ok"] for c in checks):
            report["passed"] = False

    _save(report)
    return 0 if report["passed"] else 1


def _evaluate(analysis, match, suggestions, finalize_data) -> list:
    checks = []
    checks.append({
        "name": "jd_keywords",
        "ok": len(analysis.get("keywords", [])) >= 3,
    })
    checks.append({
        "name": "match_score",
        "ok": 30 <= match.get("overall_score", 0) <= 95,
    })
    checks.append({
        "name": "suggestions",
        "ok": len(suggestions) >= 1,
    })
    checks.append({
        "name": "finalize_page",
        "ok": bool(finalize_data.get("validation", {}).get("page_passed")),
    })
    return checks


def _save(report: dict) -> None:
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
