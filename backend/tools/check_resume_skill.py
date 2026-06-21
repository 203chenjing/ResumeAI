"""简历 Markdown 格式自检器。

检查项目（来自 SKILL.md 的 Quality Checklist）：
- 实习经历前有 `---` 分隔线，无空行
- 相关技能前有 `---` 分隔线，无空行
- 相关技能恰好 4 条单行有序项，标签为 工作技能/数据技能/AI技能/语言能力
- `## 实习经历` 区块只用有序列表（1./2./3.），不用 `-` 或 `*`
- 不含 `求职优势`/`求职摘要`/`个人总结` 等总结块
- 每段实习经历 ≤ 5 条 numbered item

用法：
    python check_resume_skill.py input.md
    python check_resume_skill.py input.md --markdown-only
"""
import argparse
import re
import sys
from pathlib import Path


def check(md_path: Path) -> list[str]:
    issues: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 1. 分隔线检查
    if re.search(r"\n\s*\n---\s*\n## 实习经历", text) or "---\n## 实习经历" not in text:
        if "## 实习经历" in text and "---\n## 实习经历" not in text:
            issues.append("实习经历前未紧贴 `---` 分隔线")
    if "## 相关技能" in text and "---\n## 相关技能" not in text:
        issues.append("相关技能前未紧贴 `---` 分隔线")

    # 2. 总结块检查
    forbidden_sections = ["求职优势", "求职摘要", "个人总结"]
    for s in forbidden_sections:
        if re.search(rf"#+\s*{s}", text):
            issues.append(f"包含禁止的总结块: {s}")

    # 3. 实习经历区块只用有序列表
    if "## 实习经历" in text:
        exp_block = text.split("## 实习经历", 1)[1]
        if "## 相关技能" in exp_block:
            exp_block = exp_block.split("## 相关技能", 1)[0]
        for ln in exp_block.split("\n"):
            stripped = ln.lstrip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                issues.append("实习经历区块出现 `-` 或 `*` 无序列表")
                break

    # 4. 相关技能 = 4 条单行有序项
    if "## 相关技能" in text:
        skill_block = text.split("## 相关技能", 1)[1]
        skill_lines = [
            ln for ln in skill_block.split("\n")
            if re.match(r"^\d+\.\s+\*\*(工作技能|数据技能|AI技能|语言能力)\*\*", ln.strip())
        ]
        if len(skill_lines) != 4:
            issues.append(f"相关技能应为 4 条单行有序项，实际 {len(skill_lines)} 条")
        expected_labels = ["工作技能", "数据技能", "AI技能", "语言能力"]
        for i, ln in enumerate(skill_lines):
            m = re.match(r"^\d+\.\s+\*\*([^*]+)\*\*", ln.strip())
            if m and i < 4 and m.group(1) != expected_labels[i]:
                issues.append(f"相关技能第 {i+1} 项标签应为 `{expected_labels[i]}`，实际 `{m.group(1)}`")

    # 5. 每段实习经历 ≤ 5 个 numbered item
    if "## 实习经历" in text:
        block = text.split("## 实习经历", 1)[1]
        if "## 相关技能" in block:
            block = block.split("## 相关技能", 1)[0]
        chunks = re.split(r"\n\*\*[^*]+\*\*\s+[^\n]*\n", block)
        for chunk in chunks[1:]:
            cnt = len(re.findall(r"^\d+\.\s", chunk, flags=re.MULTILINE))
            if cnt > 5:
                issues.append(f"某段实习经历有 {cnt} 条编号项，应 ≤ 5")
                break

    return issues


def main():
    parser = argparse.ArgumentParser(description="简历 Markdown 格式自检")
    parser.add_argument("input", type=Path)
    parser.add_argument("--markdown-only", action="store_true", help="只检查 markdown，不调用 PDF")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    issues = check(args.input)
    if issues:
        print("Skill check: failed.")
        for i in issues:
            print(f"  - {i}")
        sys.exit(2)
    print("Skill check: passed.")


if __name__ == "__main__":
    main()
