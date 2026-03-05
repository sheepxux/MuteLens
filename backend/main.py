"""
Mutelens - FastAPI Backend v3.1
================================
基于 LLM 的文章质量多维度评测 API + 认证徽章系统。
流程: 提取文章 → Veto Gate 预检 → LLM 语义评估 → 加权评分 → 存储 & 返回结果。
"""

import os
import traceback

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from article_fetcher import fetch_article
from scorer_engine import veto_gate, compute_score, create_vetoed_result
from llm_evaluator import evaluate_article
from badge_store import save_evaluation, get_evaluation
from badge_svg import generate_badge_svg

SITE_URL = os.getenv("SITE_URL", "https://mute-lens.vercel.app")

app = FastAPI(
    title="Mutelens API",
    description="基于 LLM 的文章质量多维度评测引擎 + 认证徽章系统",
    version="3.1.0",
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
    dimensions: list[dict]
    weights: dict[str, float]
    analysis_summary: str
    badge_id: str


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Mutelens", "version": "3.1"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_article_endpoint(req: AnalyzeRequest):
    """分析文章 URL，返回基于 LLM 的多维度评分 + 认证徽章 ID。"""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    try:
        article = fetch_article(url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"文章提取失败: {str(e)}")

    if not article.content or len(article.content.strip()) < 30:
        raise HTTPException(
            status_code=422,
            detail="无法提取有效文章内容，请检查 URL 是否正确",
        )

    vetoed, veto_reason = veto_gate(article.title, article.content)
    if vetoed:
        result = create_vetoed_result(veto_reason)
    else:
        try:
            llm_eval = await evaluate_article(
                title=article.title,
                content=article.content,
                domain=article.domain,
            )
            result = compute_score(llm_eval)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"LLM 评估失败: {str(e)}。请检查 API 配置或稍后重试。",
            )

    content_preview = article.content[:500] + ("..." if len(article.content) > 500 else "")

    dimensions_list = [
        {
            "key": d.key,
            "label": d.label,
            "labelEn": d.label_en,
            "score": d.score,
            "maxScore": d.max_score,
            "description": d.description,
            "weight": d.weight,
        }
        for d in result.dimensions
    ]

    badge_id = save_evaluation(
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
        dimensions=dimensions_list,
        weights=result.weights,
        analysis_summary=result.analysis_summary,
    )

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
        dimensions=dimensions_list,
        weights=result.weights,
        analysis_summary=result.analysis_summary,
        badge_id=badge_id,
    )


# ─── Badge Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/badge/{badge_id}")
async def get_badge_svg(
    badge_id: str,
    style: str = Query("flat", regex="^(flat|seal)$"),
):
    """Return an SVG certification badge image."""
    evaluation = get_evaluation(badge_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Badge not found")

    svg = generate_badge_svg(
        score=evaluation.overall_score,
        grade=evaluation.grade,
        title=evaluation.title,
        style=style,
    )

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/verify/{badge_id}")
async def verify_badge(badge_id: str):
    """Return full evaluation data for verification."""
    evaluation = get_evaluation(badge_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {
        "badge_id": evaluation.badge_id,
        "url": evaluation.url,
        "domain": evaluation.domain,
        "title": evaluation.title,
        "author": evaluation.author,
        "published": evaluation.published,
        "cover_image": evaluation.cover_image,
        "word_count": evaluation.word_count,
        "language": evaluation.language,
        "overall_score": evaluation.overall_score,
        "grade": evaluation.grade,
        "vetoed": evaluation.vetoed,
        "veto_reason": evaluation.veto_reason,
        "dimensions": evaluation.dimensions,
        "weights": evaluation.weights,
        "analysis_summary": evaluation.analysis_summary,
        "created_at": evaluation.created_at,
        "badge_url": f"{SITE_URL}/api/badge/{evaluation.badge_id}",
        "verify_url": f"{SITE_URL}/verify/{evaluation.badge_id}",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
