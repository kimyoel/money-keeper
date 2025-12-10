from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .config import (
    CASE_GEN_MAX_COMPLETION_TOKENS,
    CASE_GEN_MODEL,
    KEYWORD_MAX_COMPLETION_TOKENS,
    KEYWORD_MODEL,
)
from .llm_client import call_llm_json
from .serp_client import fetch_serp

# 한 번 실행 시 대략 len(DEFAULT_SEEDS) * DEFAULT_N_KEYWORDS_PER_SEED * DEFAULT_N_CASES_PER_KEYWORD 개의 케이스를 생성합니다.
CASES_FILE = Path("cases.jsonl")

DEFAULT_SEEDS = [
    "프리랜서 미수금",
    "지인에게 빌려준 돈 못 받음",
    "카톡으로만 빌려준 돈",
]
DEFAULT_N_KEYWORDS_PER_SEED = 4
DEFAULT_N_CASES_PER_KEYWORD = 2

__all__ = [
    "load_cases",
    "save_cases",
    "generate_keywords_from_seed",
    "generate_cases_from_keyword",
    "append_new_cases_from_seeds",
    "DEFAULT_SEEDS",
    "DEFAULT_N_KEYWORDS_PER_SEED",
    "DEFAULT_N_CASES_PER_KEYWORD",
]


def _extract_list(obj, candidate_keys: tuple[str, ...]) -> list:
    """LLM 응답에서 리스트를 안전하게 추출한다."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in candidate_keys:
            if key in obj:
                value = obj[key]
                if not isinstance(value, list):
                    raise ValueError(f"{key} 값이 배열이 아닙니다.")
                return value
        return [obj]
    raise ValueError("LLM 응답이 배열이나 객체가 아닙니다.")


def load_cases(path: Path | str = CASES_FILE) -> List[dict]:
    """cases.jsonl을 읽어 리스트로 반환한다."""
    p = Path(path)
    if not p.exists():
        return []
    cases: List[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def save_cases(cases: Iterable[dict], path: Path | str = CASES_FILE) -> None:
    """케이스 리스트를 JSONL로 저장한다."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")


def generate_keywords_from_seed(seed: str, max_keywords: int = 10) -> List[dict]:
    """
    씨앗 키워드와 실제 SERP 데이터를 LLM에 전달해 롱테일 키워드 배열을 생성한다.
    각 원소: { "keyword": str, "intent": str, "score": float }
    """
    serp_data = fetch_serp(seed)

    user_content = {
        "seed": seed,
        "serp": serp_data,
        "instructions": (
            f"아래 seed와 실제 검색 결과(SERP)를 보고, 실제로 사람들이 많이 칠 법한 롱테일 검색어를 "
            f"최소 3개 이상, 최대 {max_keywords}개까지 뽑아라.\n"
            '형식: [{"keyword": str, "intent": str, "score": float}, ...]\n'
            "- keyword: 사용자가 실제로 입력할 법한 자연스러운 검색어\n"
            "- intent: 사용자가 이 검색으로 알고 싶어하는 것의 요약\n"
            "- score: 0~1, 우리 랜딩으로 끌고 올 가치(의도 선명도 + 전환 가능성)\n"
            "- 반드시 JSON 배열 리터럴만 반환하고([ {...}, {...} ]), 최상위에 객체(result 등)를 두지 말 것.\n"
            "- 단일 객체 하나만 반환하지 말 것."
        ),
    }

    def _call_keyword_llm():
        return call_llm_json(
            model=KEYWORD_MODEL,
            system_prompt=(
                "너는 한국어 SERP 기반 롱테일 키워드 플래너다. "
                "최상위 JSON 배열만 반환하고, 단일 객체나 result 키로 감싸지 말아라."
            ),
            user_content=user_content,
            max_output_tokens=KEYWORD_MAX_COMPLETION_TOKENS,
            debug_path="logs/debug/llm_raw_keyword_planner.json",
            reasoning_effort="medium",
        )

    result = _extract_list(_call_keyword_llm(), ("result", "results", "keywords", "items"))
    if len(result) < 2:
        retry = _extract_list(_call_keyword_llm(), ("result", "results", "keywords", "items"))
        result = retry
    return result[:max_keywords]


def generate_cases_from_keyword(keyword_record: dict, n_cases: int = 3) -> List[dict]:
    """
    keyword+intent를 받아 n_cases개의 케이스 dict 배열 생성.
    각 케이스:
    { case_id, seed, keyword, topic, relationship, amount, situation, goal,
      status="todo", created_at, last_run_at=None }
    """
    seed = keyword_record.get("seed")
    keyword = keyword_record.get("keyword")
    intent = keyword_record.get("intent", "")
    system_prompt = (
        "너는 pSEO 랜딩 케이스를 생성하는 도우미다. "
        "검색 키워드로 유입될 법한 현실적인 상황(n_cases개)을 JSON 배열로 만들어라. "
        "각 항목은 case_id(간단 slug), seed, keyword, topic, relationship, amount, situation, goal, "
        "status='todo', created_at ISO8601, last_run_at=None 필드를 포함한다. "
        "최소 2개 이상 케이스를 생성하고, 최상위 JSON 배열 리터럴로만 반환하며 result 키로 감싸지 말아라. "
        "관계/역할을 표현할 때 '클라이언트' 대신 문맥에 맞는 한국어(의뢰인, 고객, 거래 상대방, 지인, 회사, 스타트업, 법인 등)를 사용하라. "
        "금액(amount)은 seed/SERP 맥락에서 자연스러운 청구액만 사용하고, 변호사 수임료·소송 비용·성공보수·인지대·송달료 등 법률 비용을 새로 만들지 마라. "
        "지연이자·손해배상은 '추가 청구 가능성' 수준으로만 언급하고, 회수율/성공률/승소 가능성 같은 표현은 사용하지 말라."
    )
    payload = {
        "seed": seed,
        "keyword": keyword,
        "intent": intent,
        "n_cases": n_cases,
    }
    def _call_case_llm():
        return call_llm_json(
            model=CASE_GEN_MODEL,
            system_prompt=system_prompt,
            user_content=payload,
            max_output_tokens=CASE_GEN_MAX_COMPLETION_TOKENS,
            debug_path="logs/debug/llm_raw_case_gen.json",
        )

    result = _extract_list(_call_case_llm(), ("cases", "result", "results", "items"))
    if len(result) < 2:
        retry = _extract_list(_call_case_llm(), ("cases", "result", "results", "items"))
        result = retry

    # timezone-aware UTC 시간으로 기록해 DeprecationWarning을 방지
    now = datetime.now(timezone.utc).isoformat()
    cases: List[dict] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        item.setdefault("status", "todo")
        item.setdefault("created_at", now)
        item.setdefault("last_run_at", None)
        cases.append(item)
    return cases


def append_new_cases_from_seeds(
    seeds: list[str],
    n_keywords_per_seed: int = 5,
    n_cases_per_keyword: int = 2,
    cases_path: Path | str = CASES_FILE,
) -> List[dict]:
    """
    seeds 리스트를 받아 keyword→case를 생성한 뒤 기존 cases.jsonl에 추가 저장한다.
    """
    existing = load_cases(cases_path)
    new_cases: List[dict] = []
    for seed in seeds:
        kw_list = generate_keywords_from_seed(seed, max_keywords=n_keywords_per_seed)
        # kw_list 원소에 seed를 추가해 downstream이 참조 가능하도록 한다.
        for kw in kw_list:
            kw["seed"] = seed
            cases = generate_cases_from_keyword(kw, n_cases=n_cases_per_keyword)
            new_cases.extend(cases)
    combined = existing + new_cases
    save_cases(combined, cases_path)
    return combined


if __name__ == "__main__":
    append_new_cases_from_seeds(
        seeds=DEFAULT_SEEDS,
        n_keywords_per_seed=DEFAULT_N_KEYWORDS_PER_SEED,
        n_cases_per_keyword=DEFAULT_N_CASES_PER_KEYWORD,
    )

