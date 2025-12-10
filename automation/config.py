"""
파이프라인에서 사용하는 LLM/파라미터 상수 정의.
"""

WRITER_MODEL = "gpt-5-mini"
REVIEWER_MODEL = "gpt-5-mini"
FIXER_MODEL = "gpt-5-mini"
FINAL_GATE_MODEL = "gpt-5.1"
CODE_DEBUG_MODEL = "gpt-5.1"

# Writer 출력 길이 상한 (completion 토큰)
WRITER_MAX_COMPLETION_TOKENS = 8000
# Reviewer/Fixer 출력 길이 상한 (completion 토큰)
REVIEWER_MAX_COMPLETION_TOKENS = 8000
FIXER_MAX_COMPLETION_TOKENS = 8000
# Final gate 출력 길이 상한 (completion 토큰)
FINAL_GATE_MAX_COMPLETION_TOKENS = 8000

# 키워드/케이스 생성용 모델 및 토큰 한도
KEYWORD_MODEL = "gpt-5-mini"
CASE_GEN_MODEL = "gpt-5-mini"
KEYWORD_MAX_COMPLETION_TOKENS = 8000
CASE_GEN_MAX_COMPLETION_TOKENS = 8000

# Reviewer ↔ Fixer 루프 최대 반복 수
MAX_ROUNDS = 3

