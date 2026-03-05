import type { TranslationKey } from "./zh";

const en: Record<TranslationKey, string> = {
  // Header
  "header.tagPill": "Article Intelligence Engine",

  // Hero
  "hero.title.line1": "The Mark of Cutting",
  "hero.title.line2": "Through the Noise",
  "hero.subtitle":
    "Paste any article URL. AI evaluates across 6 core dimensions — originality, argument quality, forward-looking vision, and more. Certified articles earn the MuteLens badge.",

  // Feature cards
  "feature.llm.title": "6-Dimension AI Evaluation",
  "feature.llm.desc": "LLM-powered semantic analysis beyond surface metrics — evaluating originality, argument rigor, and forward-looking vision at depth",
  "feature.gate.title": "Multi-Layer Integrity Screen",
  "feature.gate.desc": "Precision noise-filtering engine intercepts clickbait, advertorials, and emotional manipulation before evaluation begins",
  "feature.forward.title": "Frontier Value Discovery",
  "feature.forward.desc": "Prioritizes content with genuine original insight and forward-looking vision — surfacing the voices that lead",

  // URL Input
  "input.placeholder": "Paste an article URL to analyze...",
  "input.analyze": "Analyze",
  "input.newArticle": "Analyze another",

  // Loading
  "loading.step1": "Fetching article content...",
  "loading.step2": "Parsing structure and metadata...",
  "loading.step3": "AI is reading the full article...",
  "loading.step4": "Evaluating originality and argument quality...",
  "loading.step5": "Analyzing forward-looking insights and depth...",
  "loading.step6": "Generating evaluation report...",

  // Error
  "error.title": "Analysis Failed",

  // Platform logos
  "platforms.title": "Supported Sources",

  // Score Dashboard
  "dashboard.overallLabel": "Overall Score / 100",
  "dashboard.vetoTitle": "Veto Gate Rejected",
  "dashboard.dimensionsTitle": "6-Dimension Breakdown",
  "dashboard.weightsTitle": "Weight Distribution",
  "dashboard.noTitle": "Title not extracted",
  "dashboard.words": "words",

  // Grades
  "grade.S": "Must Read",
  "grade.A": "Excellent",
  "grade.B+": "Good",
  "grade.B": "Above Average",
  "grade.C": "Average",
  "grade.D": "Below Average",
  "grade.F": "Not Recommended",

  // Dimensions
  "dim.d1": "Original Insight",
  "dim.d2": "Argument Quality",
  "dim.d3": "Information Density",
  "dim.d4": "Forward-Looking",
  "dim.d5": "Analytical Depth",
  "dim.d6": "Source Credibility",

  // Badge / Embed
  "badge.title": "Certification Badge",
  "badge.description": "Embed this badge in your article to showcase MuteLens certification",
  "badge.html": "HTML Embed",
  "badge.markdown": "Markdown Embed",
  "badge.copied": "Copied!",
  "badge.copy": "Copy",
  "badge.preview": "Preview",
  "badge.verifyPage": "Verification Page",

  // Verify page
  "verify.title": "MuteLens Certification",
  "verify.evaluated": "Evaluated on",
  "verify.authentic": "This article has been evaluated and certified by MuteLens AI",
  "verify.notFound": "Evaluation record not found",
  "verify.backHome": "Back to Home",

  // Footer
  "footer.tagline": "MuteLens · The Mark of Cutting Through the Noise",
  "footer.credit.prefix": "Built by",
  "footer.credit.suffix": "",
};

export default en;
