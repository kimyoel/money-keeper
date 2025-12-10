from __future__ import annotations

import os
import requests

SERP_API_KEY = os.getenv("SERP_API_KEY")
SERP_API_ENDPOINT = os.getenv("SERP_API_ENDPOINT")  # 예: https://api.serpapi.com/search


def fetch_serp(query: str, num: int = 10, lang: str = "ko", country: str = "kr") -> dict:
    """
    검색 API를 호출해 정규화된 SERP 데이터를 반환한다.
    반환 예시:
    {
      "top_results": [{"title":..., "snippet":..., "url":...}, ...],
      "related_searches": [...],
      "people_also_ask": [...]
    }
    """
    if not SERP_API_KEY or not SERP_API_ENDPOINT:
        raise RuntimeError("SERP_API_KEY 또는 SERP_API_ENDPOINT 환경변수가 설정되지 않았습니다.")

    params = {
        "q": query,
        "num": num,
        "hl": lang,
        "gl": country,
        "api_key": SERP_API_KEY,
    }
    resp = requests.get(SERP_API_ENDPOINT, params=params, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    top_results = [
        {
            "title": item.get("title"),
            "snippet": item.get("snippet") or item.get("description"),
            "url": item.get("link") or item.get("url"),
        }
        for item in raw.get("organic_results", [])[:num]
    ]

    related = raw.get("related_searches", [])
    people_also_ask = [p.get("question") for p in raw.get("people_also_ask", []) if p.get("question")]

    return {
        "top_results": top_results,
        "related_searches": related,
        "people_also_ask": people_also_ask,
    }

