"use client";

import dynamic from "next/dynamic";
import {
  SiArxiv,
  SiArstechnica,
  SiReddit,
  SiSubstack,
  SiGithub,
  SiTechcrunch,
  SiYcombinator,
  SiIeee,
  SiGooglenews,
  SiHuggingface,
  SiAnthropic,
  SiDeepmind,
  SiGooglescholar,
} from "react-icons/si";

const LogoLoop = dynamic(() => import("./LogoLoop"), { ssr: false });

const PLATFORMS = [
  { node: <SiArxiv />,        title: "arXiv",          href: "https://arxiv.org" },
  { node: <SiArstechnica />,  title: "Ars Technica",   href: "https://arstechnica.com" },
  { node: <SiTechcrunch />,   title: "TechCrunch",     href: "https://techcrunch.com" },
  { node: <SiHuggingface />,  title: "Hugging Face",   href: "https://huggingface.co" },
  { node: <SiAnthropic />,    title: "Anthropic",      href: "https://anthropic.com" },
  { node: <SiDeepmind />,     title: "DeepMind",       href: "https://deepmind.google" },
  { node: <SiSubstack />,     title: "Substack",       href: "https://substack.com" },
  { node: <SiReddit />,       title: "Reddit",         href: "https://reddit.com" },
  { node: <SiGithub />,       title: "GitHub",         href: "https://github.com" },
  { node: <SiYcombinator />,  title: "Hacker News",    href: "https://news.ycombinator.com" },
  { node: <SiIeee />,         title: "IEEE",           href: "https://ieee.org" },
  { node: <SiGooglenews />,   title: "Google News",    href: "https://news.google.com" },
  { node: <SiGooglescholar />,title: "Google Scholar", href: "https://scholar.google.com" },
];

export default function PlatformLogoLoop() {
  return (
    <div className="w-full py-4">
      <p className="text-center text-[10px] font-mono text-white/15 uppercase tracking-widest mb-5">
        支持分析来源
      </p>
      <div style={{ height: "32px", position: "relative", overflow: "hidden" }}>
        <LogoLoop
          logos={PLATFORMS}
          speed={55}
          direction="left"
          logoHeight={22}
          gap={52}
          pauseOnHover
          fadeOut
          fadeOutColor="#000000"
          scaleOnHover
          ariaLabel="支持分析的文章来源平台"
          style={{ color: "rgba(255,255,255,0.25)" }}
        />
      </div>
    </div>
  );
}
