"""
Mutelens - FastAPI Backend
================================
提供文章分析 API，接收 URL，返回多维度评分结果。
"""

import traceback
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from article_fetcher import fetch_article
from scorer_engine import score_article

app = FastAPI(
    title="Mutelens API",
    description="文章质量多维度评测引擎",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: str


class AnalyzeResponse(BaseModel):
    url: str
    domain: str
    title: str
    author: str
    published: str
    cover_image: str
    word_count: int
    language: str
    content_preview: str
    overall_score: float
    grade: str
    vetoed: bool
    veto_reason: str
    content_type: str
    content_type_label: str
    dimensions: list[dict]
    intermediate: dict[str, float]
    analysis_summary: str


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Mutelens"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_article(req: AnalyzeRequest):
    """分析文章 URL，返回多维度评分。"""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 1. 提取文章
    try:
        article = fetch_article(url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"文章提取失败: {str(e)}",
        )

    if not article.content or len(article.content.strip()) < 30:
        raise HTTPException(
            status_code=422,
            detail="无法提取有效文章内容，请检查 URL 是否正确",
        )

    # 2. 评分
    try:
        result = score_article(
            title=article.title,
            content=article.content,
            domain=article.domain,
            published=article.published,
            source_type=article.source_type,
            source_tier=article.source_tier,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"评分引擎错误: {str(e)}",
        )

    # 3. 构造响应
    content_preview = article.content[:500] + ("..." if len(article.content) > 500 else "")

    dimensions_list = [
        {
            "key": d.key,
            "label": d.label,
            "labelEn": d.label_en,
            "score": d.score,
            "maxScore": d.max_score,
            "description": d.description,
        }
        for d in result.dimensions
    ]

    return AnalyzeResponse(
        url=article.url,
        domain=article.domain,
        title=article.title,
        author=article.author,
        published=article.published,
        cover_image=article.cover_image,
        word_count=article.word_count,
        language=article.language,
        content_preview=content_preview,
        overall_score=result.overall_score,
        grade=result.grade,
        vetoed=result.vetoed,
        veto_reason=result.veto_reason,
        content_type=result.content_type,
        content_type_label=result.content_type_label,
        dimensions=dimensions_list,
        intermediate=result.intermediate,
        analysis_summary=result.analysis_summary,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
