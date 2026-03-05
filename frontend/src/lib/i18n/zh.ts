const zh = {
  // Header
  "header.tagPill": "Article Intelligence Engine",

  // Hero
  "hero.title.line1": "消除信息噪音",
  "hero.title.line2": "的标志",
  "hero.subtitle":
    "输入任意文章链接，AI 从原创洞见、论证质量、前瞻性等 6 个核心维度深度评测。通过认证的文章可获得 MuteLens 权威徽章。",

  // Feature cards
  "feature.llm.title": "六维度 AI 深度评测",
  "feature.llm.desc": "基于大语言模型语义理解，超越关键词统计，从原创性、论证力、前瞻性等核心维度全面透视文章价值",
  "feature.gate.title": "多层级智能审查机制",
  "feature.gate.desc": "前置噪音过滤引擎精准拦截标题党、广告软文与情绪操控，确保进入评测的每一篇内容都值得被认真对待",
  "feature.forward.title": "前沿价值发现引擎",
  "feature.forward.desc": "优先识别具有原创洞见与前瞻视野的内容，让真正引领行业方向的声音脱颖而出",

  // URL Input
  "input.placeholder": "粘贴文章链接，开始分析...",
  "input.analyze": "分析",
  "input.newArticle": "分析新文章",

  // Loading
  "loading.step1": "正在获取文章内容...",
  "loading.step2": "解析文章结构与元数据...",
  "loading.step3": "AI 正在深度阅读全文...",
  "loading.step4": "评估原创洞见与论证质量...",
  "loading.step5": "分析前瞻性与内容深度...",
  "loading.step6": "生成综合评测报告...",

  // Error
  "error.title": "分析失败",

  // Platform logos
  "platforms.title": "支持分析来源",

  // Score Dashboard
  "dashboard.overallLabel": "综合评分 / 100",
  "dashboard.vetoTitle": "Veto Gate 否决",
  "dashboard.dimensionsTitle": "6 维度详细评分",
  "dashboard.weightsTitle": "权重分布",
  "dashboard.noTitle": "未提取到标题",
  "dashboard.words": "词",

  // Grades
  "grade.S": "必读级",
  "grade.A": "优秀",
  "grade.B+": "良好",
  "grade.B": "中上",
  "grade.C": "一般",
  "grade.D": "偏低",
  "grade.F": "不推荐",

  // Dimensions
  "dim.d1": "原创洞见",
  "dim.d2": "论证质量",
  "dim.d3": "信息密度",
  "dim.d4": "前瞻性",
  "dim.d5": "内容深度",
  "dim.d6": "信源可信度",

  // Badge / Embed
  "badge.title": "认证徽章",
  "badge.description": "将此徽章嵌入到你的文章中，展示 MuteLens 权威认证",
  "badge.html": "HTML 嵌入代码",
  "badge.markdown": "Markdown 嵌入代码",
  "badge.copied": "已复制！",
  "badge.copy": "复制",
  "badge.preview": "预览",
  "badge.verifyPage": "验证页面",

  // Verify page
  "verify.title": "MuteLens 认证验证",
  "verify.evaluated": "评测时间",
  "verify.authentic": "此文章已通过 MuteLens AI 深度评测认证",
  "verify.notFound": "未找到该评测记录",
  "verify.backHome": "返回首页",

  // Footer
  "footer.tagline": "MuteLens · 消除信息噪音的标志",
  "footer.credit.prefix": "由",
  "footer.credit.suffix": "设计开发",
} as const;

export type TranslationKey = keyof typeof zh;
export default zh;
