from __future__ import annotations

from .pipeline_cases import (
    DEFAULT_N_CASES_PER_KEYWORD,
    DEFAULT_N_KEYWORDS_PER_SEED,
    DEFAULT_SEEDS,
    append_new_cases_from_seeds,
)
from .run_all import run_all_cases


def run_full_cycle(
    seeds: list[str] | None = None,
    n_keywords_per_seed: int | None = None,
    n_cases_per_keyword: int | None = None,
    max_cases_per_run: int = 10,
) -> None:
    """
    1) seeds / n_keywords_per_seed / n_cases_per_keyword에 값이 없으면
       pipeline_cases에서 정의한 DEFAULT_* 상수 값을 사용합니다.
    2) append_new_cases_from_seeds(...)를 호출해 cases.jsonl에 todo 케이스를 추가합니다.
    3) 그 다음 run_all_cases(max_cases_per_run=max_cases_per_run)를 호출해
       방금 추가된 todo 케이스를 포함해 최대 max_cases_per_run개를 처리합니다.
    """
    seeds = seeds or DEFAULT_SEEDS
    n_keywords_per_seed = n_keywords_per_seed or DEFAULT_N_KEYWORDS_PER_SEED
    n_cases_per_keyword = n_cases_per_keyword or DEFAULT_N_CASES_PER_KEYWORD

    append_new_cases_from_seeds(
        seeds=seeds,
        n_keywords_per_seed=n_keywords_per_seed,
        n_cases_per_keyword=n_cases_per_keyword,
    )

    run_all_cases(max_cases_per_run=max_cases_per_run)


if __name__ == "__main__":
    run_full_cycle()

