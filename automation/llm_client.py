from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:  # 선택적으로 .env 로드
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    load_dotenv = None  # type: ignore

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("openai 패키지를 설치하세요: pip install openai") from exc


def call_llm_json(
    *,
    model: str,
    system_prompt: str,
    user_content: Union[dict, str],
    temperature: Optional[float] = None,
    top_p: float = 1.0,
    max_output_tokens: int = 2048,
    reasoning_effort: Optional[str] = None,
    debug_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    OpenAI Chat Completions v1 호출을 공통 처리하고 JSON 응답을 dict로 반환한다.

    Args:
        model: 호출할 모델명.
        system_prompt: system 역할 프롬프트.
        user_content: user 메시지 콘텐츠(dict는 JSON 문자열로 직렬화).
        temperature: 샘플링 온도.
        top_p: 토큰 확률 상한.
        max_output_tokens: 최대 출력 토큰 수 (새 API에서는 max_completion_tokens).
        reasoning_effort: gpt-5.1 계열 reasoning_effort 옵션 (예: "high").

    Returns:
        dict: LLM이 반환한 JSON 파싱 결과.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)

    user_message = (
        json.dumps(user_content, ensure_ascii=False)
        if isinstance(user_content, dict)
        else str(user_content)
    )

    # response_format=json_object 사용 시 "json" 단어를 명시적으로 포함
    json_hint = (
        "\n\n[FORMAT] 모든 응답은 JSON 형식이어야 하며, 다른 텍스트를 포함하지 마십시오."
        " 반드시 json으로만 응답하십시오."
    )
    system_prompt = system_prompt + json_hint

    # user 메시지에도 포맷 힌트를 추가
    if isinstance(user_content, dict):
        user_content = {
            **user_content,
            "_format": "respond with pure JSON only, no extra text.",
        }

    params: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "top_p": top_p,
        # 최신 Chat Completions API는 max_completion_tokens를 사용한다.
        "max_completion_tokens": max_output_tokens,
        "response_format": {"type": "json_object"},
    }
    if temperature is not None:
        params["temperature"] = temperature
    if reasoning_effort is not None:
        params["reasoning_effort"] = reasoning_effort

    try:
        response = client.chat.completions.create(**params)
    except Exception as exc:
        # 일부 모델은 temperature 커스터마이즈를 지원하지 않아 에러를 낼 수 있음.
        if "temperature" in str(exc).lower() and "unsupported" in str(exc).lower():
            params.pop("temperature", None)
            response = client.chat.completions.create(**params)
        else:
            raise

    # 디버그용 raw response + usage 요약 저장
    if debug_path:
        debug_file = Path(debug_path)
        debug_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            debug_file.write_text(response.model_dump_json(indent=2), encoding="utf-8")
        except Exception:
            debug_file.write_text(json.dumps(response, default=str, ensure_ascii=False), encoding="utf-8")

        # usage 요약 별도 파일(.usage.json)
        usage = getattr(response, "usage", None)
        summary = None
        if usage:
            def _to_jsonable(obj: Any) -> Any:
                if obj is None:
                    return None
                if isinstance(obj, (str, int, float, bool)):
                    return obj
                if isinstance(obj, dict):
                    return {k: _to_jsonable(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [_to_jsonable(v) for v in obj]
                # pydantic-like objects
                if hasattr(obj, "model_dump"):
                    return obj.model_dump()
                # generic fallback
                return str(obj)

            summary = {
                "completion_tokens": _to_jsonable(getattr(usage, "completion_tokens", None)),
                "prompt_tokens": _to_jsonable(getattr(usage, "prompt_tokens", None)),
                "total_tokens": _to_jsonable(getattr(usage, "total_tokens", None)),
                "completion_tokens_details": _to_jsonable(getattr(usage, "completion_tokens_details", None)),
                "prompt_tokens_details": _to_jsonable(getattr(usage, "prompt_tokens_details", None)),
                "finish_reason": _to_jsonable(getattr(response.choices[0], "finish_reason", None)),
            }
        summary_path = debug_file.with_suffix(".usage.json")
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    message = response.choices[0].message
    # parsed 필드가 있으면 우선 사용
    parsed_payload = getattr(message, "parsed", None)
    if parsed_payload is not None:
        if parsed_payload == {} or parsed_payload == []:
            raise ValueError("LLM 응답(parsed)이 비어 있습니다.")
        return parsed_payload

    content = message.content or ""
    if not content.strip():
        raise ValueError("LLM 응답이 비어 있습니다.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 응답을 JSON으로 파싱하지 못했습니다: {content}") from exc

    # 빈 객체/배열은 실패로 간주해 상위에서 처리할 수 있도록 에러를 던진다.
    if parsed == {} or parsed == []:
        raise ValueError(f"LLM 응답이 비어 있습니다: {parsed}")

    return parsed

