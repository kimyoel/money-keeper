from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
DEPLOY_FAIL_LOG = LOGS_DIR / "deploy_failures.jsonl"


def log_deploy_failure(entry: Dict[str, Any]) -> None:
    """deploy 실패를 logs/deploy_failures.jsonl에 기록한다."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with DEPLOY_FAIL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def render_html(page_json: dict) -> str:
    """
    page_json을 HTML 문자열로 렌더링한다.
    """
    content = page_json.get("content", {})
    meta = page_json.get("meta", {})
    hero = content.get("hero", {})
    sections = content.get("sections", [])
    faq = content.get("faq", [])
    disclaimer = content.get("disclaimer", {})

    sections_html = "".join(
        f"""
      <section class="section" id="{s.get('id','')}">
        <h2>{s.get('title','')}</h2>
        <p>{s.get('body','')}</p>
      </section>
        """
        for s in sections
    )

    faq_items = "".join(
        f"""
        <details>
          <summary>{q.get('question','')}</summary>
          <div>{q.get('answer','')}</div>
        </details>
        """
        for q in faq
    )

    disclaimer_legal = disclaimer.get("legal", "이 페이지는 일반 정보 제공이며, 개별 사건에 대한 법률 자문이나 결과 보장이 아닙니다.")
    disclaimer_privacy = disclaimer.get("privacy", "제공된 정보는 관련 법령과 내부 정책에 따라 필요한 범위에서만 안전하게 처리됩니다.")

    html = f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>{meta.get('title','')}</title>
  <meta name="description" content="{meta.get('description','')}" />
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <div class="site-shell">
    <header class="site-header">
      <a class="brand" href="./index.html"><span>💸</span>떼인 돈 계산기</a>
      <a class="ghost-link" href="../index.html">메인 계산기</a>
    </header>

    <div class="breadcrumb-wrap">
      <div class="breadcrumb">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.172 3 10.172V20a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1v-4h4v4a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1v-9.828l-9-7Z"/>
        </svg>
        <a href="../index.html">홈</a>
        <span class="breadcrumb-sep">›</span>
        <a href="./index.html">상황별 미수금 가이드</a>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current breadcrumb-ellipsis">{meta.get('title','')}</span>
      </div>
    </div>

    <section class="hero">
      <h1>{hero.get('headline','')}</h1>
      <p class="subtitle">{hero.get('subheadline','')}</p>
      <p class="intro">{hero.get('intro','')}</p>
    </section>

    {sections_html}

    <section class="section">
      <h2>FAQ</h2>
      <div class="mb-4 rounded-md bg-gray-50 border border-gray-200 px-3 py-2 text-xs text-gray-600">
        ※ 아래 답변들은 실제 사례들을 바탕으로 정리한 <strong>일반적인 안내</strong>입니다.<br>
        개별 사건에 그대로 적용되지는 않을 수 있고, 구체적인 결론은 사실관계·증거·법원 판단에 따라 달라질 수 있습니다.
      </div>
      <div class="faq">
        {faq_items}
      </div>
      <p class="mt-4 text-xs text-gray-500">
        ※ 이 Q&A는 실제 상담을 대신하는 것이 아니라, 비슷한 상황에서 많이 나오는 질문을 정리한 일반적인 안내입니다.
      </p>
    </section>

    <section class="section">
      <h2>떼인 돈 계산기로 금액 확인하기</h2>
      <p>원금과 약정일을 넣어 지연손해금을 계산해 두면 요구액을 명확히 정리할 수 있습니다. 금액을 확인한 뒤 내용증명이나 지급명령 서류를 준비할지 검토해 보세요.</p>
      <a class="cta" href="../index.html">떼인 돈 계산기 열기</a>
      <div class="notice-box">
        이 계산기는 입력하신 값을 기준으로 한 <strong>참고용 시뮬레이션</strong>입니다.<br />
        실제 소송·집행 결과와 다를 수 있으며, 최종 판단은 법률 전문가와 상의해 주세요.
      </div>
    </section>

    <section class="section" aria-label="상황 정리 키트 안내">
      <h2 class="section-title">비슷한 일이 반복될 때를 대비해, 셀프 정리 키트를 준비 중입니다</h2>
      <p class="text-sm text-gray-700">
        이 페이지와 계산기로 이번 사건을 한 번 정리해 보셨다면, 앞으로 비슷한 상황이 생겨도 같은 틀로 정리할 수 있도록 돕는 '셀프 정리 키트'를 준비하고 있습니다.
      </p>
      <ul class="mt-3 text-sm text-gray-700 space-y-1">
        <li>• 사건 요약 & 타임라인 한 장 템플릿</li>
        <li>• 증거·자료 체크리스트</li>
        <li>• 관계·상황별 연락 예시문 모음</li>
        <li>• 전문가 상담이 더 나을 수 있는지 점검하는 레드 라인 체크리스트</li>
      </ul>
      <p class="mt-2 text-xs text-gray-500">
        레드 라인 체크리스트는 형사 가능성, 고액·복잡한 분쟁, 다수 피해자가 얽힌 경우처럼 전문가 상담이 더 안전할 수 있는 상황을 스스로 점검해 보는 표입니다. 키트는 준비 중이며, 출시 알림은 결과 화면에서 신청하실 수 있습니다.
      </p>
    </section>

    <section class="section" id="disclaimer" aria-label="면책 및 법령 안내">
      <h2>면책 및 법령 안내</h2>
      <p class="text-sm text-gray-700">{disclaimer_legal}</p>
      <p class="text-xs text-gray-600 mt-2">{disclaimer_privacy}</p>
    </section>

    <p class="footer">본 페이지의 안내는 일반적인 절차를 정리한 것으로, 개별 사건에 대한 법률 자문이 아닙니다.</p>
    <p class="footer" style="font-size:12px;color:#6b7280;">※ 본 서비스는 일반 정보 제공 및 계산 예시일 뿐, 개별 사건에 대한 법률 자문이 아닙니다. 실제 대응은 법률 전문가와 상의해 절차를 결정해 주세요.</p>
  </div>
</body>
</html>
""".strip()
    return html


def save_html(page_id: str, html: str, output_dir: Path | str = "public") -> Path:
    """HTML을 파일로 저장한다."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{page_id}.html"
    target.write_text(html, encoding="utf-8")
    return target


def deploy_stub(page_path: Path) -> Tuple[bool, str]:
    """
    배포 스텁. 실제 배포 로직(git push/Netlify/CI 등)은 추후 구현.
    Returns: (success, message)
    """
    # TODO: 실제 배포/CI 훅 연동
    return True, "deploy stub success"


def git_commit_and_push(message: str) -> None:
    """public 디렉터리 변경을 커밋/푸시한다."""
    cmds = [
        ["git", "add", "public"],
        ["git", "commit", "-m", message],
        ["git", "push"],
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git command failed: {cmd}, stderr={proc.stderr}")


def run_html_and_deploy(case_id: str, page_json: dict) -> Dict[str, Any]:
    """
    HTML 렌더 → 저장 → 배포(스텁)까지 수행하고, 실패 시 deploy_failures.jsonl에 기록.
    """
    timestamp = datetime.utcnow().isoformat()
    try:
        html = render_html(page_json)
        path = save_html(case_id, html)
        success, message = deploy_stub(path)
        if not success:
            raise RuntimeError(message)
        # git commit/push
        git_commit_and_push(f"auto: publish {case_id}")
        return {"status": "success", "path": str(path), "message": message}
    except Exception as exc:  # pragma: no cover
        entry = {
            "case_id": case_id,
            "error_type": "deploy_failed",
            "stage": "deploy_stub",
            "error_message": str(exc),
            "stacktrace": "",
            "timestamp": timestamp,
        }
        log_deploy_failure(entry)
        return {"status": "failed", "error": str(exc)}

