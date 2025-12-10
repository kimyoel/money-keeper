from __future__ import annotations

from .pipeline_pages import run_page_pipeline


def main() -> None:
    """단일 케이스를 돌려보는 수동 테스트 엔트리 포인트."""
    case_input = {
        "case_id": "demo-freelancer-loan",
        "topic": "프리랜서/지인 간 채무",
        "relationship": "지인",
        "amount": "150만원",
        "situation": "프리랜서로 일한 뒤 대금을 받지 못한 상황",
        "goal": "채권 회수 가이드와 상담 CTA 제안",
    }

    result = run_page_pipeline(case_input, test_lenient=True)
    print("status:", result.get("status"))
    print("rounds:", result.get("rounds"))
    print("approved(loop):", result.get("approved"))
    print("final_gate:", result.get("final_gate"))


if __name__ == "__main__":
    main()

