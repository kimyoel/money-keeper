"""
사이트 카탈로그 관리 모듈.
- pages.json 관리 (update_pages_json)
- sitemap.xml 생성 (build_sitemap)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

# 기본 base URL (Netlify 배포 주소)
DEFAULT_BASE_URL = "https://gentle-yeot-a0c73f.netlify.app"


def load_pages_json(public_dir: Path | str) -> List[Dict[str, Any]]:
    """public/pages.json을 읽어 리스트로 반환한다."""
    p = Path(public_dir) / "pages.json"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_pages_json(public_dir: Path | str, pages: List[Dict[str, Any]]) -> Path:
    """pages 리스트를 public/pages.json에 저장한다."""
    p = Path(public_dir) / "pages.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    return p


def update_pages_json(
    public_dir: Path | str,
    page_meta: Dict[str, Any],
) -> Path:
    """
    랜딩 생성 시 {slug, title, category, created_at, ...}를 public/pages.json에 append/merge.
    중복 slug는 최신으로 덮어쓴다.
    
    page_meta 필수 필드:
    - slug: 페이지 슬러그 (예: "freelancer-design-90")
    - title: 페이지 제목
    - category: 카테고리 (예: "프리랜서 · 소액")
    - created_at: ISO 형식 날짜 (없으면 자동 생성)
    
    선택 필드:
    - description: 설명
    - updated_at: 업데이트 시간 (없으면 자동 생성)
    """
    public_path = Path(public_dir)
    pages = load_pages_json(public_path)
    
    slug = page_meta.get("slug")
    if not slug:
        raise ValueError("page_meta에 slug가 필수입니다.")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # 기존 페이지 찾기
    existing_idx = None
    for i, p in enumerate(pages):
        if p.get("slug") == slug:
            existing_idx = i
            break
    
    # 새 페이지 메타 생성
    new_entry = {
        "slug": slug,
        "title": page_meta.get("title", slug),
        "category": page_meta.get("category", "기타"),
        "description": page_meta.get("description", ""),
        "created_at": page_meta.get("created_at", now),
        "updated_at": now,
    }
    
    if existing_idx is not None:
        # 기존 항목 업데이트 (created_at은 유지)
        old_created = pages[existing_idx].get("created_at", now)
        new_entry["created_at"] = old_created
        pages[existing_idx] = new_entry
    else:
        # 새로 추가
        pages.append(new_entry)
    
    return save_pages_json(public_path, pages)


def build_sitemap(
    public_dir: Path | str,
    base_url: str = DEFAULT_BASE_URL,
) -> Path:
    """
    public/pages.json 기준으로 public/sitemap.xml을 재생성한다.
    """
    public_path = Path(public_dir)
    pages = load_pages_json(public_path)
    
    # base_url 끝에 슬래시 제거
    base_url = base_url.rstrip("/")
    
    # XML 네임스페이스 설정
    nsmap = {
        "": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    
    # sitemap.xml 수동 생성 (ElementTree는 namespace 처리가 제한적이라 문자열로 생성)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    
    urls = []
    
    # 메인 페이지 (index.html)
    urls.append({
        "loc": f"{base_url}/",
        "lastmod": now,
        "changefreq": "weekly",
        "priority": "1.0",
    })
    
    # 상황별 가이드 목록 페이지
    urls.append({
        "loc": f"{base_url}/index.html",
        "lastmod": now,
        "changefreq": "weekly",
        "priority": "0.9",
    })
    
    # pages.json의 각 페이지
    for page in pages:
        slug = page.get("slug", "")
        if not slug:
            continue
        
        updated = page.get("updated_at") or page.get("created_at") or now
        # ISO 형식을 sitemap 형식으로 변환
        if "T" in updated:
            lastmod = updated[:19] + "+00:00"
        else:
            lastmod = now
            
        urls.append({
            "loc": f"{base_url}/{slug}.html",
            "lastmod": lastmod,
            "changefreq": "monthly",
            "priority": "0.64",
        })
    
    # XML 생성
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9',
        '        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">',
    ]
    
    for url in urls:
        xml_lines.extend([
            "  <url>",
            f"    <loc>{url['loc']}</loc>",
            f"    <lastmod>{url['lastmod']}</lastmod>",
            f"    <changefreq>{url['changefreq']}</changefreq>",
            f"    <priority>{url['priority']}</priority>",
            "  </url>",
        ])
    
    xml_lines.append("</urlset>")
    
    sitemap_path = public_path / "sitemap.xml"
    sitemap_path.write_text("\n".join(xml_lines), encoding="utf-8")
    
    return sitemap_path


def copy_static_files_to_public(
    root_dir: Path | str,
    public_dir: Path | str,
) -> List[Path]:
    """
    루트 디렉토리의 정적 파일들을 public 디렉토리로 복사한다.
    대상: robots.txt, google*.html, naver*.html 등 검증 파일
    
    Note: sitemap.xml은 build_sitemap()으로 생성하므로 복사하지 않음
    """
    import shutil
    
    root_path = Path(root_dir)
    public_path = Path(public_dir)
    public_path.mkdir(parents=True, exist_ok=True)
    
    copied = []
    
    # 복사할 파일 패턴
    patterns = [
        "robots.txt",
        "google*.html",
        "naver*.html",
        "qr.png",
    ]
    
    # 루트 index.html을 calculator.html로 복사
    root_index = root_path / "index.html"
    if root_index.is_file():
        dst = public_path / "calculator.html"
        shutil.copy2(root_index, dst)
        # calculator.html 내 링크 수정 (./public/index.html -> ./index.html)
        content = dst.read_text(encoding="utf-8")
        content = content.replace("./public/index.html", "./index.html")
        dst.write_text(content, encoding="utf-8")
        copied.append(dst)
    
    for pattern in patterns:
        for src in root_path.glob(pattern):
            if src.is_file():
                dst = public_path / src.name
                shutil.copy2(src, dst)
                copied.append(dst)
    
    return copied


def extract_page_meta_from_page_json(page_json: dict) -> Dict[str, Any]:
    """
    pipeline_pages에서 생성된 page_json에서 pages.json용 메타 정보를 추출한다.
    """
    meta = page_json.get("meta", {})
    content = page_json.get("content", {})
    hero = content.get("hero", {})
    
    # category 추출: meta.category 또는 hero.headline에서 추론
    category = meta.get("category", "")
    if not category:
        # 제목에서 추론 시도
        title = meta.get("title", "")
        if "프리랜서" in title:
            category = "프리랜서"
        elif "지인" in title or "친구" in title:
            category = "지인 · 대여금"
        elif "중고" in title or "사기" in title:
            category = "중고거래 · 사기"
        elif "연인" in title or "헤어" in title:
            category = "연인 · 대여금"
        elif "직장" in title or "동료" in title:
            category = "직장 · 대여금"
        elif "건설" in title or "일용" in title:
            category = "건설 · 일용직"
        elif "폐업" in title or "체불" in title:
            category = "폐업 · 임금체불"
        elif "마케팅" in title or "용역" in title:
            category = "마케팅 · 용역비"
        elif "출판" in title or "외주" in title:
            category = "출판 · 소액 체불"
        elif "서비스" in title or "청소" in title:
            category = "서비스 · 소액 분쟁"
        else:
            category = "기타"
    
    return {
        "slug": meta.get("slug", ""),
        "title": meta.get("title", ""),
        "category": category,
        "description": meta.get("description", hero.get("subheadline", "")),
    }


if __name__ == "__main__":
    # 테스트용 실행
    import sys
    
    public_dir = Path(__file__).parent.parent / "public"
    root_dir = Path(__file__).parent.parent
    
    # 정적 파일 복사
    copied = copy_static_files_to_public(root_dir, public_dir)
    print(f"복사된 파일: {[str(p) for p in copied]}")
    
    # 테스트 페이지 추가
    test_meta = {
        "slug": "test-page",
        "title": "테스트 페이지",
        "category": "테스트",
        "description": "테스트용 페이지입니다.",
    }
    update_pages_json(public_dir, test_meta)
    
    # sitemap 생성
    sitemap_path = build_sitemap(public_dir)
    print(f"sitemap 생성됨: {sitemap_path}")

