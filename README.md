# Mutelens v2.0

文章质量多维评测引擎 — 粘贴文章链接，自动从 10 个维度进行深度评分。

## 架构

```
frontend/   → Next.js 16 + TypeScript + Tailwind CSS + Recharts
backend/    → FastAPI + trafilatura + 自研评分引擎
```

## 快速开始

### 1. 启动后端 (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端运行在 http://localhost:8000，API 文档见 http://localhost:8000/docs

### 2. 启动前端 (Next.js)

```bash
cd frontend
npm install
npm run dev
```

前端运行在 http://localhost:3000

## 评分维度

| 维度 | 英文 | 权重范围 |
|------|------|----------|
| D1 事实密度 | Fact Density | 0.20-0.30 |
| D2 内容新颖性 | Novelty | 0.10-0.15 |
| D3 信源质量 | Source Quality | 0.15-0.25 |
| D4 时效性 | Timeliness | 0.10-0.20 |
| D5 可操作性 | Actionability | 0.10-0.20 |
| D6 标题一致性 | Title Consistency | 调节因子 P |
| D7 传播潜力 | Reach Potential | 调节因子 K |
| D8 内容深度 | Content Depth | 加分项 |
| D9 可验证度 | Verification | 加分项 |
| D10 情绪中立度 | Neutrality | 加分项 |

## 评分公式

```
B = w1*D1 + w2*D2 + w3*D3 + w4*D4 + w5*D5   (加权基础分)
P = 0.25 + 0.75 / (1 + e^(-0.8*(D6-5)))       (标题一致性调节)
K = 1 + 0.3 * tanh((D7-5)/3)                  (传播潜力调节)
V_final = sigmoid(B * P * K * depth_bonus) * 100
```

## Veto Gate

当文章命中以下条件时自动否决（分数归零）：
- 标题党关键词检测
- 广告/推销内容
- 极端情绪化表达

## API

```
POST /api/analyze
Body: { "url": "https://example.com/article" }
```

响应包含：综合评分、等级、10 维度详细评分、计算中间值、分析摘要。
