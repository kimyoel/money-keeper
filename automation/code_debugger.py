from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .config import CODE_DEBUG_MODEL
from .llm_client import call_llm_json

LOGS_DIR = Path("logs")
DEPLOY_FAIL_LOG = LOGS_DIR / "deploy_failures.jsonl"
REPORTS_DIR = Path("reports")


def load_recent_failures(limit: int = 5) -> List[dict]:
    """
    logs/deploy_failures.jsonl 에서 최근 실패 케이스 N개를 읽어온다.
    """
    if not DEPLOY_FAIL_LOG.exists():
        return []
    lines = DEPLOY_FAIL_LOG.read_text(encoding="utf-8").splitlines()
    lines = [l for l in lines if l.strip()]
    recent = lines[-limit:]
    return [json.loads(l) for l in recent]


def build_debug_context(failure: dict) -> dict:
    """
    실패 케이스에 대한 디버깅 컨텍스트를 구성한다.
    관련 소스 파일 내용을 포함해 LLM 분석에 넘길 수 있도록 준비한다.
    """
    files_to_load = [
        Path("automation/html_and_deploy.py"),
        Path("automation/run_all.py"),
        Path("automation/pipeline_pages.py"),
        Path("automation/config.py"),
    ]
    sources = {}
    for path in files_to_load:
        if path.exists():
            sources[str(path)] = path.read_text(encoding="utf-8")
    context = {
        "failure": failure,
        "sources": sources,
        "notes": "Focus on minimal fixes; produce short diff plans.",
    }
    return context


def call_code_debug_agent(context: dict) -> dict:
    """
    GPT-5.1 + reasoning_effort='high'로 코드 디버그 제안을 요청한다.
    """
    system_prompt = (
        "너는 배포/코드 실패를 분석하는 코드 디버거다. "
        "역할: 1) 에러 원인 요약 2) 1~2단계의 수정 계획 "
        "3) 각 단계별 수정 전/후 코드 블록(diff 요약) 제안. "
        "한 번에 많은 변경을 제안하지 말고, 작은 수정만 단계적으로 제안하라."
    )
    return call_llm_json(
        model=CODE_DEBUG_MODEL,
        system_prompt=system_prompt,
        user_content=context,
        temperature=0.0,
        max_output_tokens=1200,
        reasoning_effort="high",
    )


def write_code_debug_report(failure: dict, analysis: dict) -> Path:
    """
    code debug 리포트를 reports 디렉터리에 저장한다.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    case_id = failure.get("case_id", "unknown")
    target = REPORTS_DIR / f"code_debug_{case_id}.md"
    summary = analysis.get("summary") or analysis.get("analysis") or ""
    plan = analysis.get("plan") or analysis.get("steps") or []
    diffs = analysis.get("diffs") or analysis.get("patches") or []

    lines = [
        f"# Code Debug Report for {case_id}",
        "",
        "## Failure",
        f"- stage: {failure.get('stage')}",
        f"- error: {failure.get('error_message')}",
        "",
        "## Root Cause (LLM 추정)",
        summary if isinstance(summary, str) else json.dumps(summary, ensure_ascii=False),
        "",
        "## Plan (small, incremental)",
        json.dumps(plan, ensure_ascii=False, indent=2),
        "",
        "## Suggested Diffs",
        json.dumps(diffs, ensure_ascii=False, indent=2),
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def run_code_debugger(limit: int = 3) -> List[Path]:
    """
    최근 실패를 불러와 디버그 리포트를 생성한다.
    """
    failures = load_recent_failures(limit=limit)
    reports: List[Path] = []
    for failure in failures:
        context = build_debug_context(failure)
        analysis = call_code_debug_agent(context)
        report_path = write_code_debug_report(failure, analysis)
        reports.append(report_path)
    return reports


if __name__ == "__main__":
    reports = run_code_debugger(limit=3)
    print("generated reports:", [str(p) for p in reports])

