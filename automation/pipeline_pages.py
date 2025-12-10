from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple
from uuid import uuid4

from .config import (
    FINAL_GATE_MODEL,
    FINAL_GATE_MAX_COMPLETION_TOKENS,
    FIXER_MODEL,
    FIXER_MAX_COMPLETION_TOKENS,
    MAX_ROUNDS,
    REVIEWER_MODEL,
    REVIEWER_MAX_COMPLETION_TOKENS,
    WRITER_MAX_COMPLETION_TOKENS,
    WRITER_MODEL,
)
from .llm_client import call_llm_json

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "review_logs.jsonl"
DEBUG_DIR = LOGS_DIR / "debug"


def load_prompt(path: str) -> str:
    """
    지정된 경로의 프롬프트 파일을 읽어 문자열로 반환한다.

    Args:
        path: 프롬프트 파일 경로.
    """
    prompt_path = Path(path)
    return prompt_path.read_text(encoding="utf-8")


def append_log(record: dict) -> None:
    """
    logs/review_logs.jsonl에 JSONL 형식으로 한 줄 append한다.

    Args:
        record: 로깅할 dict (case_id, approved, rounds, scores, status 등).
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_debug(case_id: str, name: str, data: dict) -> None:
    """
    디버깅용 원시 응답을 logs/debug/{case_id}.{name}.json 으로 저장한다.
    """
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{case_id}.{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def validate_writer_output(draft: dict) -> Tuple[bool, dict]:
    """
    Writer 출력이 최소 스키마/길이를 충족하는지 검증한다.
    Returns: (is_valid, issues_dict)
    """
    issues: Dict[str, Any] = {}
    try:
        hero_headline = draft.get("content", {}).get("hero", {}).get("headline", "")
        sections = draft.get("content", {}).get("sections", [])
        first_body = sections[0].get("body", "") if sections else ""
        slug = draft.get("meta", {}).get("slug", "")
        title = draft.get("meta", {}).get("title", "")
        description = draft.get("meta", {}).get("description", "")
    except Exception as exc:  # pragma: no cover
        return False, {"error": f"structure_error: {exc}"}

    if not hero_headline or len(hero_headline.strip()) < 10:
        issues["headline"] = "headline too short (<10) or missing"
    if not sections:
        issues["sections"] = "no sections"
    if len(first_body.strip()) < 50:
        issues["first_section_body"] = "first section body too short (<50) or missing"
    if not slug:
        issues["slug"] = "slug missing"
    if not title:
        issues["title"] = "title missing"
    if not description:
        issues["description"] = "description missing"

    return (len(issues) == 0, issues)


def build_fallback_draft(case_input: dict) -> dict:
    """
    Writer가 반복 실패할 때 사용하는 보수적 fallback draft.
    """
    topic = case_input.get("topic", "케이스")
    amount = case_input.get("amount", "")
    situation = case_input.get("situation", "")
    slug = case_input.get("slug") or "fallback-page"
    title = case_input.get("title") or f"{topic} 가이드"
    description = case_input.get("description") or f"{topic} 상황에 대한 기본 안내"

    hero = {
        "headline": f"{topic} 기본 안내",
        "subheadline": f"{situation or '상황에 맞는 대응 가이드'}",
        "cta": "무료 상담 신청",
    }


def validate_page_output(draft: dict) -> Tuple[bool, dict]:
    """
    Fixer/Reviewer 이후에도 사용할 수 있는 페이지 스키마 검증.
    """
    return validate_writer_output(draft)
    sections = [
        {
            "id": "overview",
            "title": "상황 개요",
            "body": f"현재 상황: {situation or '자세한 상황을 입력하세요.'} "
            f"금액: {amount or '금액 정보 없음'}. "
            "신뢰 가능한 절차에 따라 대응 방법을 안내합니다.",
        },
        {
            "id": "steps",
            "title": "대응 단계",
            "body": "1) 사실관계 정리 2) 증빙 확보 3) 전문가 상담 4) 합의/조정 또는 법적 절차 검토.",
        },
    ]
    faq = [
        {"question": "어떻게 시작하나요?", "answer": "상담을 통해 상황을 정리한 뒤 맞춤형 대응을 제안합니다."},
        {"question": "법적 위험이 있나요?", "answer": "허위 주장과 과장을 피하고, 사실 기반으로 대응합니다."},
    ]

    return {
        "content": {"hero": hero, "sections": sections, "faq": faq},
        "meta": {"slug": slug, "title": title, "description": description},
        "_fallback": True,
    }


def call_writer(case_input: dict) -> dict:
    """
    Writer 에이전트 호출.

    Args:
        case_input: 케이스 입력 데이터.

    Returns:
        dict: 예상 구조 예시
        {
          "content": {...},  # 섹션/본문/FAQ 등
          "meta": {...}      # slug, title, description 등
        }
    """
    system_prompt = load_prompt(str(PROMPTS_DIR / "writer.md"))
    result = call_llm_json(
        model=WRITER_MODEL,
        system_prompt=system_prompt,
        user_content={
            "case": case_input,
            "response_schema": {
                "required": ["content", "meta"],
                "content": "sections/body/faq 등 상세 랜딩 페이지 구조",
                "meta": "slug, title, description 등 메타데이터",
            },
        },
        temperature=0.7,
        max_output_tokens=WRITER_MAX_COMPLETION_TOKENS,
        debug_path=str(DEBUG_DIR / "llm_raw_writer.json"),
    )
    if not isinstance(result, dict):
        raise ValueError("Writer 응답이 dict 형식이 아닙니다.")

    # content/meta 누락 시 기본 스켈레톤을 채워 넣고 경고를 남긴다.
    default_content = {
        "hero": {"headline": "", "subheadline": "", "cta": ""},
        "sections": [],
        "faq": [],
    }
    default_meta = {"slug": "", "title": "", "description": ""}

    warnings = []
    if "content" not in result:
        result["content"] = default_content
        warnings.append("writer: content missing, filled with empty skeleton.")
    if "meta" not in result:
        result["meta"] = default_meta
        warnings.append("writer: meta missing, filled with empty skeleton.")

    if warnings:
        result.setdefault("_warnings", []).extend(warnings)
    return result


def call_reviewer(draft: dict, mode: str = "initial") -> dict:
    """
    Reviewer 에이전트 호출.

    Args:
        draft: 작성된 초안 데이터.
        mode: 리뷰 모드 ("initial" | "final").

    Returns:
        dict: 예상 구조 예시
        {
          "approved": bool,
          "reasons": [str, ...],
          "scores": {
            "legal": float,
            "tone": float,
            "structure": float,
            "seo": float
          },
          "fix_suggestions": [str, ...]
        }
    """
    system_prompt = load_prompt(str(PROMPTS_DIR / "reviewer.md"))
    result = call_llm_json(
        model=REVIEWER_MODEL,
        system_prompt=system_prompt,
        user_content={
            "draft": draft,
            "mode": mode,
            "response_schema": {
                "required": ["approved", "reasons", "scores", "fix_suggestions"],
                "scores": {"legal": "float", "tone": "float", "structure": "float", "seo": "float"},
                "fix_suggestions": "list of strings",
            },
        },
        temperature=0.0,
        max_output_tokens=REVIEWER_MAX_COMPLETION_TOKENS,
        debug_path=str(DEBUG_DIR / f"llm_raw_reviewer_{mode}.json"),
    )
    if not isinstance(result, dict):
        raise ValueError("Reviewer 응답이 dict 형식이 아닙니다.")
    # approved 누락 시 기본 False로 보수 처리하고, 힌트를 남긴다.
    if "approved" not in result:
        result["approved"] = False
        result.setdefault(
            "reasons",
            ["missing approved flag from reviewer response; treated as not approved."],
        )
    return result


def call_fixer(draft: dict, review_feedback: dict) -> dict:
    """
    Fixer 에이전트 호출.

    Args:
        draft: 현재 초안 데이터.
        review_feedback: 리뷰 결과 dict.

    Returns:
        dict: draft와 동일한 구조의 수정본.
    """
    system_prompt = load_prompt(str(PROMPTS_DIR / "fixer.md"))
    try:
        result = call_llm_json(
            model=FIXER_MODEL,
            system_prompt=system_prompt,
            user_content={
                "draft": draft,
                "review": review_feedback,
                "response_schema": {
                    "required": ["content", "meta"],
                    "content": "sections/body/faq 등 상세 랜딩 페이지 구조",
                    "meta": "slug, title, description 등 메타데이터",
                },
            },
            temperature=0.2,
            max_output_tokens=FIXER_MAX_COMPLETION_TOKENS,
            debug_path=str(DEBUG_DIR / "llm_raw_fixer.json"),
        )
    except Exception as exc:
        return {"_error": f"fixer_call_failed: {exc}"}

    if not isinstance(result, dict):
        return {"_error": "fixer_return_not_dict"}
    return result


def call_final_gate(draft: dict) -> dict:
    """
    최종 법·리스크 게이트 호출 (보수적 판단).

    Args:
        draft: 최종 후보 초안.

    Returns:
        dict: 예상 구조 예시
        {
          "approved": bool,
          "reasons": [str, ...],
          "risk_tags": [str, ...]
        }
    """
    base_prompt = load_prompt(str(PROMPTS_DIR / "reviewer.md"))
    gate_prompt = (
        base_prompt
        + "\n\n[최종 게이트 지침]\n"
        + "- 법적/리스크 관점에서 더 보수적으로 판단한다.\n"
        + "- 허용되지 않는 주장·과장은 모두 거부하고, 위험 태그를 식별한다."
    )
    result = call_llm_json(
        model=FINAL_GATE_MODEL,
        system_prompt=gate_prompt,
        user_content={
            "draft": draft,
            "mode": "final_gate",
            "response_schema": {
                "required": ["approved", "reasons", "risk_tags"],
                "risk_tags": "list of risk labels",
            },
        },
        temperature=0.0,
        max_output_tokens=FINAL_GATE_MAX_COMPLETION_TOKENS,
        reasoning_effort="high",
        debug_path=str(DEBUG_DIR / "llm_raw_final_gate.json"),
    )
    if not isinstance(result, dict) or "approved" not in result:
        raise ValueError("Final gate 응답에 approved 필드가 없습니다.")
    return result


def run_page_pipeline(case_input: dict, *, test_lenient: bool = False) -> dict:
    """
    Writer → Reviewer → Fixer → Reviewer 루프 후 최종 게이트까지 수행한다.

    Args:
        case_input: 케이스 입력 dict.
        test_lenient: 테스트 모드에서 승인 완화 규칙 적용 여부.

    Returns:
        dict: 최종 결과
        {
          "case": case_input,
          "draft": 최종 draft,
          "review": 마지막 loop reviewer 결과,
          "final_gate": 최종 게이트 결과 (없을 수 있음),
          "rounds": int,
          "approved": bool,              # 루프 기준 승인 여부
          "status": "approved_for_publish" | "blocked_by_loop" | "blocked_by_final_gate"
        }
    """
    case_id = str(case_input.get("case_id") or f"case-{uuid4()}")

    error_type = "none"

    writer_retry_used = False
    fallback_used = False

    # Writer 1차
    draft = call_writer(case_input)
    write_debug(case_id, "writer.try1", draft)
    valid, issues = validate_writer_output(draft)

    # Writer 2차 (retry) if invalid
    if not valid:
        writer_retry_used = True
        retry_payload = {
            "case": case_input,
            "retry_reason": "previous draft failed validation: content/meta missing or too short",
            "response_schema": {
                "required": ["content", "meta"],
                "content": "sections/body/faq 등 상세 랜딩 페이지 구조",
                "meta": "slug, title, description 등 메타데이터",
            },
        }
        draft_retry = call_llm_json(
            model=WRITER_MODEL,
            system_prompt=load_prompt(str(PROMPTS_DIR / "writer.md")),
            user_content=retry_payload,
            temperature=0.7,
            max_output_tokens=WRITER_MAX_COMPLETION_TOKENS,
            debug_path=str(DEBUG_DIR / "llm_raw_writer_retry.json"),
        )
        write_debug(case_id, "writer.try2", draft_retry)
        draft = draft_retry
        valid, issues = validate_writer_output(draft)

    # Fallback if still invalid
    if not valid:
        fallback_used = True
        draft = build_fallback_draft(case_input)
        write_debug(case_id, "writer.fallback", draft)
        valid, issues = validate_writer_output(draft)
        draft.setdefault("_warnings", []).append("writer fallback used")
        error_type = "writer_schema_error"

    # 최종적으로도 실패하면 하드 실패
    if not valid:
        error_type = "writer_hard_fail"
        status = "writer_hard_fail"
        result = {
            "case": case_input,
            "draft": draft,
            "review": None,
            "final_gate": None,
            "rounds": 0,
            "approved": False,
            "status": status,
            "issues": issues,
        }
        log_entry = {
            "case_id": case_id,
            "approved": False,
            "rounds": 0,
            "status": status,
            "scores": None,
            "error_type": error_type,
            "model_writer": WRITER_MODEL,
            "model_reviewer": REVIEWER_MODEL,
            "model_fixer": FIXER_MODEL,
            "model_final_gate": FINAL_GATE_MODEL,
        }
        append_log(log_entry)
        write_debug(case_id, "writer.validation_fail", {"issues": issues})
        return result

    if writer_retry_used and error_type == "none":
        error_type = "writer_schema_error"

    review = call_reviewer(draft, mode="initial")
    write_debug(case_id, "round0.reviewer.initial", review)
    approved = bool(review.get("approved", False))
    rounds = 0
    final_gate_review = None

    while not approved and rounds < MAX_ROUNDS:
        round_idx = rounds + 1
        fixer_result = call_fixer(draft, review)
        write_debug(case_id, f"round{round_idx}.fixer", fixer_result)

        # Fixer 실패/빈 응답 처리: 기존 draft 유지, 수동 리뷰로 종료
        fix_valid, fix_issues = validate_page_output(fixer_result) if "_error" not in fixer_result else (False, fixer_result)
        if not fix_valid:
            error_type = "fixer_invalid"
            status = "fixer_failed"
            result = {
                "case": case_input,
                "draft": draft,  # 기존 draft 유지
                "review": review,
                "final_gate": None,
                "rounds": round_idx,
                "approved": False,
                "status": status,
                "issues": fix_issues,
            }
            log_entry = {
                "case_id": case_id,
                "approved": False,
                "rounds": round_idx,
                "status": status,
                "scores": review.get("scores"),
                "error_type": error_type,
                "model_writer": WRITER_MODEL,
                "model_reviewer": REVIEWER_MODEL,
                "model_fixer": FIXER_MODEL,
                "model_final_gate": FINAL_GATE_MODEL,
            }
            append_log(log_entry)
            write_debug(case_id, f"round{round_idx}.fixer.validation_fail", {"issues": fix_issues})
            return result

        draft = fixer_result

        review = call_reviewer(draft, mode="final")
        write_debug(case_id, f"round{round_idx}.reviewer.final", review)
        approved = bool(review.get("approved", False))
        # 테스트 모드에서는 legal 점수가 높고 최소 1회 루프 후이면 승인 완화
        try:
            legal_score = float(review.get("scores", {}).get("legal", 0.0))
        except Exception:
            legal_score = 0.0
        if (
            test_lenient
            and not approved
            and legal_score >= 0.8
            and round_idx >= 1
        ):
            approved = True
            review.setdefault(
                "reasons",
                [],
            ).append("lenient test pass: legal score >= 0.8 after first round.")
        rounds += 1

    status = "blocked_by_loop"
    if approved:
        final_gate_review = call_final_gate(draft)
        write_debug(case_id, "final_gate", final_gate_review)

        final_gate_approved = bool(final_gate_review.get("approved", False))
        fix_suggestions = final_gate_review.get("fix_suggestions") or []
        safe_draft = draft  # Final Gate 전까지 검증된 안전한 버전 백업

        if not final_gate_approved:
            status = "blocked_by_final_gate"
        else:
            # 기본값은 승인
            status = "approved_for_publish"

            if fix_suggestions:
                try:
                    final_fix = call_fixer(draft, final_gate_review)
                    write_debug(case_id, "final_gate.fixer", final_fix)

                    if "_error" not in final_fix:
                        is_valid, issues = validate_page_output(final_fix)
                    else:
                        is_valid, issues = False, final_fix

                    if is_valid and "_error" not in final_fix:
                        draft = final_fix
                    else:
                        draft = safe_draft
                        status = "approved_for_publish"
                        write_debug(
                            case_id,
                            "final_gate.fixer.validation_fail",
                            {"issues": issues},
                        )
                except Exception as e:
                    draft = safe_draft
                    status = "approved_for_publish"
                    write_debug(
                        case_id,
                        "final_gate.fixer.exception",
                        {"error": str(e)},
                    )

    else:
        status = "blocked_by_final_gate"

    result = {
        "case": case_input,
        "draft": draft,
        "review": review,
        "final_gate": final_gate_review,
        "rounds": rounds,
        "approved": approved,
        "status": status,
    }

    log_entry = {
        "case_id": case_id,
        "approved": approved,
        "rounds": rounds,
        "status": status,
        "scores": review.get("scores"),
        "error_type": error_type,
        "model_writer": WRITER_MODEL,
        "model_reviewer": REVIEWER_MODEL,
        "model_fixer": FIXER_MODEL,
        "model_final_gate": FINAL_GATE_MODEL,
    }
    append_log(log_entry)

    return result

