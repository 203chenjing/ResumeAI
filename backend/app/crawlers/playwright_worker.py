"""独立子进程运行 Playwright（规避 Windows uvicorn asyncio 限制）。"""
from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.buffer.write(b'{"error":"missing url"}')
        return 1

    url = sys.argv[1]
    user_agent = sys.argv[2] if len(sys.argv) > 2 else "ResumeAI-Crawler/1.0"
    wait_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 2500
    timeout_ms = int(sys.argv[4]) if len(sys.argv) > 4 else 60000
    wait_until = sys.argv[5] if len(sys.argv) > 5 else "networkidle"
    mode = sys.argv[6] if len(sys.argv) > 6 else "fetch"

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=user_agent)
            try:
                try:
                    page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if wait_ms > 0:
                    page.wait_for_timeout(wait_ms)

                if mode == "nowcoder":
                    from app.crawlers.parsers import parse_nowcoder_schedule

                    jobs = parse_nowcoder_schedule(page, json.loads(sys.argv[7]))
                    out = {"jobs": [j.__dict__ if hasattr(j, "__dict__") else j for j in jobs]}
                    # JobPosting is dataclass
                    from dataclasses import asdict

                    out = {"jobs": [asdict(j) for j in jobs]}
                elif mode == "yingjiesheng":
                    from dataclasses import asdict
                    from app.crawlers.parsers import parse_yingjiesheng_list

                    jobs = parse_yingjiesheng_list(page, json.loads(sys.argv[7]))
                    out = {"jobs": [asdict(j) for j in jobs]}
                elif mode == "bytedance":
                    from dataclasses import asdict
                    from app.crawlers.parsers import parse_bytedance_campus

                    jobs = parse_bytedance_campus(page, json.loads(sys.argv[7]))
                    out = {"jobs": [asdict(j) for j in jobs]}
                else:
                    out = {"url": page.url, "html": page.content(), "text": page.inner_text("body")}
            finally:
                browser.close()
        payload = json.dumps(out, ensure_ascii=False)
        sys.stdout.buffer.write(payload.encode("utf-8"))
        return 0
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        sys.stderr.buffer.write(err.encode("utf-8"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
