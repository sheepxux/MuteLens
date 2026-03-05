"""
Mutelens - LLM Evaluator
================================
使用 LLM 对文章进行语义层面的多维度评分。
支持 OpenAI 兼容 API（OpenAI / DeepSeek / Moonshot / 通义千问等）。
"""

import json
import os
from dataclasses import dataclass

import httpx

LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "60"))

MAX_CONTENT_CHARS = 8000


@dataclass
class LLMDimensionResult:
    score: float
    reasoning: str


@dataclass
class LLMEvaluation:
    d1_original_insight: LLMDimensionResult
    d2_argument_quality: LLMDimensionResult
    d3_information_density: LLMDimensionResult
    d4_forward_looking: LLMDimensionResult
    d5_analytical_depth: LLMDimensionResult
    d6_source_credibility: LLMDimensionResult
    summary: str


EVALUATION_PROMPT = """你是一位严格且专业的文章质量评测专家。你的任务是对给定文章进行客观、深入的多维度评分。

## 评分原则
- 你是一位严苛的评审，不轻易给高分
- 7 分以上代表真正优秀，9 分以上极为罕见
- 大多数普通文章应在 4-6 分区间
- 纯搬运、注水、PR 稿应在 2-4 分区间
- 评分必须有明确依据，不能含糊

## 文章信息
标题: {title}
来源: {domain}

正文:
{content}

## 评分维度（每个维度 1-10 分）

### D1: 原创洞见 (Original Insight)
- 文章是否提出了独特的观点、框架或认知连接？
- 读者能否从中获得别处难以获得的信息或启发？
- 是简单转述/聚合已有信息，还是有真正的增量贡献？
参考: 1-3 = 纯搬运/常识重述; 4-6 = 有一定解读但缺乏新意; 7-8 = 有明确原创观点或独特角度; 9-10 = 开创性的框架/观点/发现

### D2: 论证质量 (Argument Quality)
- 核心观点是否有充分的证据/数据/逻辑支撑？
- 推理链是否完整、逻辑是否自洽？
- 是否考虑了反面论点和边界条件？
参考: 1-3 = 无论证或逻辑混乱; 4-6 = 有基本论证但不够严密; 7-8 = 论证充分、逻辑清晰; 9-10 = 论证极其严密，多角度验证

### D3: 信息密度 (Information Density)
- 单位篇幅内的有效信息量如何？
- 数据、事实、引用的质量（而非仅数量）如何？
- 是否简洁有力，还是冗长注水？
参考: 1-3 = 大量注水/重复/空洞; 4-6 = 信息量中等; 7-8 = 信息密集，几乎没有废话; 9-10 = 每段都有高价值信息

### D4: 前瞻性 (Forward-Looking)
- 是否识别了尚未成为主流共识的趋势或方向？
- 对未来的预判是否有逻辑支撑（而非空洞预测）？
- 是否帮助读者理解"接下来会发生什么"？
参考: 1-3 = 纯回顾性/无前瞻内容; 4-6 = 有一些前瞻但缺乏深度; 7-8 = 有清晰的前瞻性分析; 9-10 = 识别了他人尚未注意的趋势

### D5: 内容深度 (Analytical Depth)
- 分析是否触及问题的本质和底层机制？
- 是否超越表面现象，揭示因果关系和系统性规律？
- 是否有多层次的思考（what → why → so what）？
参考: 1-3 = 仅描述表面事实; 4-6 = 有一定分析但停留中层; 7-8 = 深入到底层机制/因果; 9-10 = 多层次系统性分析

### D6: 信源可信度 (Source Credibility)
- 引用的信息来源是否可靠、可追溯？
- 关键声明是否可独立验证？
- 作者是否有明显的偏见或利益冲突？
参考: 1-3 = 无来源或来源不可靠; 4-6 = 部分有来源但不够充分; 7-8 = 主要声明有可靠来源; 9-10 = 所有关键声明都有高质量可验证来源

## 输出格式
请严格按以下 JSON 格式输出，不要添加任何其他内容：
{{"d1_original_insight":{{"score":0,"reasoning":"<一句话>"}},"d2_argument_quality":{{"score":0,"reasoning":"<一句话>"}},"d3_information_density":{{"score":0,"reasoning":"<一句话>"}},"d4_forward_looking":{{"score":0,"reasoning":"<一句话>"}},"d5_analytical_depth":{{"score":0,"reasoning":"<一句话>"}},"d6_source_credibility":{{"score":0,"reasoning":"<一句话>"}},"summary":"<2-3 句话总体评价，指出核心优势和不足>"}}"""


def _truncate_content(content: str) -> str:
    if len(content) <= MAX_CONTENT_CHARS:
        return content
    return content[:MAX_CONTENT_CHARS] + "\n\n[... 内容已截断]"


def _parse_llm_response(text: str) -> LLMEvaluation:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    data = json.loads(cleaned)

    def _extract(key: str) -> LLMDimensionResult:
        d = data.get(key, {})
        score = float(d.get("score", 5))
        score = max(1.0, min(10.0, score))
        return LLMDimensionResult(score=round(score, 1), reasoning=str(d.get("reasoning", "")))

    return LLMEvaluation(
        d1_original_insight=_extract("d1_original_insight"),
        d2_argument_quality=_extract("d2_argument_quality"),
        d3_information_density=_extract("d3_information_density"),
        d4_forward_looking=_extract("d4_forward_looking"),
        d5_analytical_depth=_extract("d5_analytical_depth"),
        d6_source_credibility=_extract("d6_source_credibility"),
        summary=str(data.get("summary", "")),
    )


async def evaluate_article(title: str, content: str, domain: str) -> LLMEvaluation:
    if not LLM_API_KEY:
        raise ValueError(
            "未配置 LLM API Key。请在 backend/.env 文件中设置 LLM_API_KEY。"
        )

    truncated = _truncate_content(content)
    prompt = EVALUATION_PROMPT.format(
        title=title,
        domain=domain,
        content=truncated,
    )

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1024,
            },
        )
        resp.raise_for_status()
        result = resp.json()

    text = result["choices"][0]["message"]["content"]
    return _parse_llm_response(text)
