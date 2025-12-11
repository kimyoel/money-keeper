from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from .html_and_deploy import run_html_and_deploy
from .pipeline_pages import run_page_pipeline

# 한 번 실행 시 status='todo' 케이스 중 최대 max_cases_per_run개를 처리합니다. (기본 10개)

CASES_FILE = Path("cases.jsonl")
LOGS_DIR = Path("logs")
DEPLOY_FAIL_LOG = LOGS_DIR / "deploy_failures.jsonl"


def load_cases(path: Path = CASES_FILE) -> Iterable[dict]:
    """cases.jsonl에서 케이스를 읽어온다."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def run_all_cases(test_lenient: bool = False, max_cases_per_run: int = 10) -> List[Dict]:
    """
    상태가 todo인 케이스를 순차 처리하고 결과를 반환한다.
    approved_for_publish일 때만 html_and_deploy를 호출한다.
    """
    cases = list(load_cases())
    results = []
    before_fail_count = count_failures()
    processed = 0
    for case in cases:
        if processed >= max_cases_per_run:
            break
        if case.get("status") not in (None, "todo"):
            continue
        case_id = case.get("case_id") or "case"
        pipeline_result = run_page_pipeline(case, test_lenient=test_lenient)
        status = pipeline_result.get("status")
        case["status"] = status
        case["last_run_at"] = pipeline_result.get("last_run_at") or pipeline_result.get("timestamp") or None
        deploy_result = None
        if status == "approved_for_publish":
            deploy_result = run_html_and_deploy(case_id, pipeline_result.get("draft", {}))
            pipeline_result["deploy"] = deploy_result
        elif status and status.startswith("blocked"):
            # 배포는 호출하지 않음
            pass
        case["deploy"] = deploy_result
        results.append(pipeline_result)
        processed += 1

    # 새 deploy 실패가 생겼으면 코드 디버거를 실행
    after_fail_count = count_failures()
    if after_fail_count > before_fail_count:
        # TODO: deploy_failures.jsonl를 바탕으로 자동 디버거를 돌리고 싶으면
        # run_code_debugger(limit=3)를 다시 활성화하고, LLM 빈 응답/에러를 try/except로 감싸서
        # cron 실행을 방해하지 않도록 보완할 것.
        # run_code_debugger(limit=3)

    save_cases(cases)
    return results


def count_failures() -> int:
    if not DEPLOY_FAIL_LOG.exists():
        return 0
    return sum(1 for line in DEPLOY_FAIL_LOG.read_text(encoding="utf-8").splitlines() if line.strip())


def save_cases(cases: Iterable[dict], path: Path = CASES_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # 테스트 모드에서 lenient 승인 활성화
    outputs = run_all_cases(test_lenient=True)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))

