#!/usr/bin/env python3
"""Build index.html from the assessment guidebook markdown.

Usage: python3 build.py
"""

import re
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
SRC = ROOT / "04_学習評価ガイドブック_3観点実践.md"
DST = ROOT / "index.html"


def slugify(text: str) -> str:
    """Generate a URL-friendly slug from a heading."""
    text = re.sub(r"[#*`>]+", "", text).strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[/\\:?\"<>|]", "", text)
    return text


def extract_toc(md_text: str):
    """Extract H2 headings as the primary TOC, with H3 as sub-items."""
    toc = []
    in_code = False
    for line in md_text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m2 = re.match(r"^##\s+(.+)$", line)
        m3 = re.match(r"^###\s+(.+)$", line)
        if m2:
            title = m2.group(1).strip()
            if title == "目次":
                continue
            toc.append({"level": 2, "title": title, "slug": slugify(title), "children": []})
        elif m3 and toc:
            title = m3.group(1).strip()
            toc[-1]["children"].append({"level": 3, "title": title, "slug": slugify(title)})
    return toc


def render_toc_html(toc):
    parts = ['<nav class="toc-nav" aria-label="目次">']
    parts.append('<div class="toc-title">目次</div>')
    parts.append('<ol class="toc-list">')
    for item in toc:
        parts.append(
            f'<li class="toc-item toc-l2"><a href="#{item["slug"]}" data-target="{item["slug"]}">{item["title"]}</a>'
        )
        if item["children"]:
            parts.append('<ol class="toc-sublist">')
            for child in item["children"]:
                parts.append(
                    f'<li class="toc-item toc-l3"><a href="#{child["slug"]}" data-target="{child["slug"]}">{child["title"]}</a></li>'
                )
            parts.append("</ol>")
        parts.append("</li>")
    parts.append("</ol>")
    parts.append("</nav>")
    return "\n".join(parts)


def add_anchor_ids(html: str) -> str:
    """Inject id attributes onto h2 and h3 tags using their text as the slug."""
    import html as html_lib

    def repl(match):
        tag = match.group(1)
        inner = match.group(2)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        # Decode HTML entities so slug matches the TOC slug derived from raw md.
        plain = html_lib.unescape(plain)
        slug = slugify(plain)
        return f'<{tag} id="{slug}">{inner}</{tag}>'

    html = re.sub(r"<(h[23])>(.*?)</\1>", repl, html, flags=re.DOTALL)
    return html


def split_combined_callouts(html: str) -> str:
    """Split blockquotes that contain both 【不適切な例】 and 【ふさわしい例】.

    Markdown often merges consecutive blockquotes (separated only by blank
    `>` lines) into a single <blockquote>. We re-split them here and assign
    the bad/good callout classes.
    """
    pattern = re.compile(
        r'<blockquote>(.*?)</blockquote>',
        re.DOTALL,
    )

    def repl(match):
        inner = match.group(1)
        has_bad = '【不適切な例】' in inner
        has_good = '【ふさわしい例】' in inner
        if has_bad and has_good:
            # Split at the 【ふさわしい例】 paragraph boundary
            split_re = re.compile(
                r'(?=<p[^>]*><strong>【ふさわしい例】)'
            )
            parts = split_re.split(inner, maxsplit=1)
            if len(parts) == 2:
                bad_part, good_part = parts
                return (
                    f'<blockquote class="callout callout-bad">{bad_part.strip()}</blockquote>\n'
                    f'<blockquote class="callout callout-good">{good_part.strip()}</blockquote>'
                )
        elif has_bad:
            return f'<blockquote class="callout callout-bad">{inner.strip()}</blockquote>'
        elif has_good:
            return f'<blockquote class="callout callout-good">{inner.strip()}</blockquote>'
        return match.group(0)

    return pattern.sub(repl, html)


def strip_first_toc(html: str) -> str:
    """Remove the manually written TOC block (between the H1 and 序章)."""
    # The markdown has "## 目次" then a list, then "---". Remove that section.
    pattern = r'<h2>目次</h2>.*?<hr\s*/?>'
    return re.sub(pattern, "", html, count=1, flags=re.DOTALL)


def build():
    md_text = SRC.read_text(encoding="utf-8")

    # Strip the manually written H1 + lead block (we render our own header)
    # but keep everything from "## 序章" onward, plus the lead paragraph.

    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "attr_list", "sane_lists", "footnotes"],
    )
    body_html = md.convert(md_text)
    body_html = add_anchor_ids(body_html)
    body_html = strip_first_toc(body_html)

    toc = extract_toc(md_text)
    toc_html = render_toc_html(toc)

    # Remove the H1 that markdown generated (we have a custom header)
    body_html = re.sub(r"<h1>.*?</h1>", "", body_html, count=1, flags=re.DOTALL)

    # Markdown merges consecutive blockquotes. Split & class-tag them.
    body_html = split_combined_callouts(body_html)

    template = TEMPLATE.replace("__TOC__", toc_html).replace("__BODY__", body_html)
    DST.write_text(template, encoding="utf-8")
    print(f"wrote {DST} ({DST.stat().st_size} bytes)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>学習評価ガイドブック v3.0 ── 3観点の実践 × 評価設計を深化させる4つのフレームワーク</title>
<meta name="description" content="小・中・高の3観点評価の実践と、DOK・CRM・SRL・SAMRの4フレームワークを統合した学習評価ガイドブック。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #fafaf7;
  --fg: #18181b;
  --fg-soft: #3f3f46;
  --fg-muted: #71717a;
  --border: #e4e4e7;
  --border-soft: #f4f4f5;
  --card: #ffffff;
  --accent: #0f172a;
  --accent-2: #2563eb;
  --accent-3: #6366f1;
  --good-bg: #f0fdf4;
  --good-border: #86efac;
  --good-fg: #166534;
  --bad-bg: #fef2f2;
  --bad-border: #fca5a5;
  --bad-fg: #991b1b;
  --note-bg: #fffbeb;
  --note-border: #fcd34d;
  --code-bg: #f4f4f5;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 18px -2px rgba(15,23,42,0.06), 0 2px 6px -1px rgba(15,23,42,0.04);
  --radius: 14px;
  --radius-sm: 8px;
  --serif: 'Noto Serif JP', 'Hiragino Mincho ProN', 'Yu Mincho', serif;
  --sans: 'Inter', 'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }

body {
  font-family: var(--sans);
  color: var(--fg);
  background: var(--bg);
  line-height: 1.85;
  font-feature-settings: "palt";
  letter-spacing: 0.01em;
}

a { color: var(--accent-2); text-decoration: none; transition: color 0.15s; }
a:hover { color: var(--accent-3); text-decoration: underline; text-underline-offset: 4px; }

/* === Header === */
.site-header {
  position: relative;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%);
  color: white;
  padding: 6rem 2rem 5rem;
  overflow: hidden;
}
.site-header::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 15% 20%, rgba(99,102,241,0.25), transparent 40%),
    radial-gradient(circle at 85% 70%, rgba(37,99,235,0.18), transparent 40%);
  pointer-events: none;
}
.site-header-inner {
  position: relative;
  max-width: 880px;
  margin: 0 auto;
}
.eyebrow {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  backdrop-filter: blur(8px);
}
.site-title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: clamp(1.8rem, 4.2vw, 2.8rem);
  margin: 1.4rem 0 0.6rem;
  letter-spacing: 0.02em;
  line-height: 1.4;
}
.site-subtitle {
  font-size: 1rem;
  font-weight: 400;
  opacity: 0.85;
  max-width: 640px;
}
.site-meta {
  margin-top: 2rem;
  display: flex;
  gap: 1.2rem;
  flex-wrap: wrap;
  font-size: 0.85rem;
  opacity: 0.75;
}
.site-meta span {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.tag-row {
  margin-top: 1.6rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.tag {
  font-size: 0.75rem;
  font-weight: 500;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.18);
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  letter-spacing: 0.04em;
}

/* === Layout === */
.layout {
  max-width: 1320px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 3rem;
  padding: 3rem 2rem 6rem;
}

/* === TOC === */
.toc {
  position: sticky;
  top: 2rem;
  align-self: start;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
  font-size: 0.85rem;
  padding-right: 0.5rem;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.toc::-webkit-scrollbar { width: 6px; }
.toc::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
.toc-title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--fg-muted);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}
.toc-list, .toc-sublist {
  list-style: none;
  padding-left: 0;
}
.toc-sublist {
  margin: 0.4rem 0 0.8rem 0.7rem;
  padding-left: 0.7rem;
  border-left: 1px solid var(--border-soft);
}
.toc-item a {
  display: block;
  padding: 0.35rem 0.6rem;
  color: var(--fg-soft);
  border-radius: 5px;
  transition: all 0.15s;
  line-height: 1.5;
}
.toc-l2 > a {
  font-weight: 600;
  color: var(--fg);
  margin-top: 0.2rem;
}
.toc-l3 > a {
  font-size: 0.8rem;
  color: var(--fg-muted);
}
.toc-item a:hover {
  background: var(--border-soft);
  color: var(--accent-2);
  text-decoration: none;
}
.toc-item a.active {
  background: var(--accent-2);
  color: white;
}

/* === Content === */
.content {
  min-width: 0;
  font-size: 1rem;
}
.content h2, .content h3, .content h4, .content h5 {
  font-family: var(--serif);
  letter-spacing: 0.02em;
  scroll-margin-top: 2rem;
}
.content h2 {
  font-size: 1.85rem;
  font-weight: 700;
  margin-top: 4.5rem;
  margin-bottom: 1.6rem;
  padding-bottom: 0.9rem;
  border-bottom: 2px solid var(--accent);
  position: relative;
  line-height: 1.4;
}
.content h2::before {
  content: "";
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 60px;
  height: 2px;
  background: var(--accent-3);
}
.content > h2:first-child { margin-top: 0; }
.content h3 {
  font-size: 1.35rem;
  font-weight: 600;
  margin-top: 3rem;
  margin-bottom: 1.1rem;
  padding-left: 0.85rem;
  border-left: 4px solid var(--accent-2);
  line-height: 1.5;
}
.content h4 {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 2.2rem;
  margin-bottom: 0.9rem;
  color: var(--accent);
}
.content h5 {
  font-size: 1rem;
  font-weight: 700;
  margin-top: 1.6rem;
  margin-bottom: 0.7rem;
  color: var(--fg-soft);
}
.content p {
  margin: 1rem 0;
  color: var(--fg-soft);
}
.content strong {
  color: var(--fg);
  font-weight: 700;
}
.content ul, .content ol {
  margin: 1rem 0 1.2rem 1.6rem;
  color: var(--fg-soft);
}
.content li { margin: 0.4rem 0; }
.content li::marker { color: var(--accent-2); }
.content hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 4rem 0;
}

/* === Tables === */
.content table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 1.5rem 0;
  font-size: 0.9rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}
.content thead {
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}
.content th {
  text-align: left;
  font-weight: 700;
  padding: 0.85rem 1rem;
  color: var(--accent);
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  letter-spacing: 0.02em;
}
.content td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-soft);
  color: var(--fg-soft);
  vertical-align: top;
}
.content tbody tr:last-child td { border-bottom: none; }
.content tbody tr:hover { background: #fafafa; }

/* === Code === */
.content code {
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
  background: var(--code-bg);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.88em;
  color: #be123c;
}
.content pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 1.2rem 1.4rem;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin: 1.4rem 0;
  font-size: 0.85rem;
  line-height: 1.7;
  box-shadow: var(--shadow-md);
}
.content pre code {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: inherit;
}

/* === Blockquotes / Callouts === */
.content blockquote {
  margin: 1.6rem 0;
  padding: 1.2rem 1.4rem;
  background: var(--note-bg);
  border-left: 4px solid var(--note-border);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--fg-soft);
  font-size: 0.95rem;
}
.content blockquote p { margin: 0.5rem 0; color: inherit; }
.content blockquote > p:first-child { margin-top: 0; }
.content blockquote > p:last-child { margin-bottom: 0; }

.content blockquote.callout-bad {
  background: var(--bad-bg);
  border-left-color: var(--bad-border);
}
.content blockquote.callout-bad strong:first-child { color: var(--bad-fg); }
.content blockquote.callout-good {
  background: var(--good-bg);
  border-left-color: var(--good-border);
}
.content blockquote.callout-good strong:first-child { color: var(--good-fg); }

/* Tables inside blockquotes need a tighter style */
.content blockquote table {
  font-size: 0.83rem;
  background: rgba(255,255,255,0.65);
}

/* === Footer === */
.site-footer {
  background: #0f172a;
  color: #94a3b8;
  padding: 3rem 2rem;
  text-align: center;
  font-size: 0.85rem;
  letter-spacing: 0.02em;
}
.site-footer strong { color: white; }
.site-footer-inner {
  max-width: 880px;
  margin: 0 auto;
}

/* === Responsive === */
@media (max-width: 980px) {
  .layout {
    grid-template-columns: 1fr;
    gap: 1rem;
    padding: 2rem 1.2rem 4rem;
  }
  .toc {
    position: static;
    max-height: none;
    margin-bottom: 2rem;
    padding: 1.4rem;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .site-header { padding: 4rem 1.4rem 3.5rem; }
  .content h2 { font-size: 1.5rem; margin-top: 3rem; }
  .content h3 { font-size: 1.2rem; }
  .content table { font-size: 0.82rem; }
  .content th, .content td { padding: 0.6rem 0.7rem; }
}

/* === Print === */
@media print {
  .toc, .site-header { display: none; }
  body { background: white; }
  .content h2 { page-break-after: avoid; }
  .content table, .content blockquote { page-break-inside: avoid; }
}

/* === Subtle entrance animation === */
@keyframes fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.site-header-inner > * { animation: fade-in 0.6s ease-out backwards; }
.site-header-inner > *:nth-child(1) { animation-delay: 0.05s; }
.site-header-inner > *:nth-child(2) { animation-delay: 0.15s; }
.site-header-inner > *:nth-child(3) { animation-delay: 0.25s; }
.site-header-inner > *:nth-child(4) { animation-delay: 0.35s; }
.site-header-inner > *:nth-child(5) { animation-delay: 0.45s; }
</style>
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <span class="eyebrow">Assessment Guidebook · v3.0</span>
    <h1 class="site-title">学習評価ガイドブック<br>3観点の実践 × 評価設計を深化させる4つのフレームワーク</h1>
    <p class="site-subtitle">小学校・中学校・高等学校の3観点評価を、DOK・認知的厳密性マトリックス・自己調整学習・SAMR×ブルーム・デジタル・タクソノミーで深化させる包括ガイド。</p>
    <div class="site-meta">
      <span>📘 約87,000字 / 1,200行</span>
      <span>🎯 小・中・高すべての校種に対応</span>
      <span>🔬 海外研究19件 + 4フレームワーク</span>
    </div>
    <div class="tag-row">
      <span class="tag">3観点評価</span>
      <span class="tag">Webb DOK</span>
      <span class="tag">Cognitive Rigor Matrix</span>
      <span class="tag">Self-Regulated Learning</span>
      <span class="tag">SAMR Model</span>
      <span class="tag">Bloom's Digital Taxonomy</span>
    </div>
  </div>
</header>

<div class="layout">
  <aside class="toc">
    __TOC__
  </aside>

  <main class="content">
    __BODY__
  </main>
</div>

<footer class="site-footer">
  <div class="site-footer-inner">
    <p><strong>Assessment Guidebook v3.0</strong></p>
    <p style="margin-top: 0.6rem;">3観点の正しい実践 × 評価設計を深化させる4つのフレームワーク（DOK / CRM / SRL / SAMR×Digital Taxonomy）</p>
    <p style="margin-top: 1.2rem; opacity: 0.6;">本ガイドブックは、教育現場での評価の質的向上を目的として作成されたものです。各学校・教科の実態に応じて適宜修正・活用してください。</p>
  </div>
</footer>

<script>
// Highlight active TOC item on scroll
(function() {
  const tocLinks = document.querySelectorAll('.toc a[data-target]');
  const targets = Array.from(tocLinks).map(a => ({
    link: a,
    el: document.getElementById(a.dataset.target)
  })).filter(t => t.el);

  function onScroll() {
    const y = window.scrollY + 120;
    let active = null;
    for (const t of targets) {
      if (t.el.offsetTop <= y) active = t;
    }
    tocLinks.forEach(a => a.classList.remove('active'));
    if (active) active.link.classList.add('active');
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();
</script>

</body>
</html>
"""


if __name__ == "__main__":
    build()
