"""CSCE 412 Project 5 - AI Website Builder Agent.

Run from the project root:
    python agents/website_builder.py
    python agents/website_builder.py --check

Reads outputs/requirements.json created by agent.py, calls an LLM to design
five pages, uses approved local file-writing tools, then verifies its output.
This agent DOES NOT deploy AWS resources.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
SITE = ROOT / "website"
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"
PAGES = {
    "index": "Home",
    "about": "About",
    "projects": "Projects",
    "skills": "Skills",
    "contact": "Contact",
}


def e(text: str) -> str:
    """Escape AI-created text before inserting it into HTML."""
    return html.escape(text, quote=True)


def read_requirements() -> dict:
    path = OUTPUTS / "requirements.json"
    if not path.is_file():
        raise FileNotFoundError("Missing outputs/requirements.json. Run 'python agent.py' first.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    analysis = doc.get("analysis")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("requirements"), list):
        raise ValueError("Requirements JSON is not in the starter agent's expected format")
    return analysis


def generate_site_spec(requirements: dict) -> dict:
    """Meaningful LLM task: interpret requirements and author the site content."""
    system = """You are the Website Builder Agent for a student AWS cloud deployment project.
Design the written content of a professional, five-page Cloud and HPC Engineering
portfolio website. Return ONLY JSON, no markdown and no HTML. Required JSON shape:
{
  "tagline": "short site-wide tagline",
  "pages": {
    "index": {"title":"...", "eyebrow":"...", "lead":"...",
              "sections":[{"heading":"...", "body":"..."}],
              "cards":[{"heading":"...", "body":"..."}]},
    "about":  { ... same keys ... },
    "projects": { ... same keys ... },
    "skills": { ... same keys ... },
    "contact": { ... same keys ... }
  }
}
Each page must have 2 sections and 3 cards. Content should be clear, concise,
useful, distinct across pages and fit a modern portfolio. Highlight topics such
as MPI bitonic sort, HPC performance profiling, GPU computing, distributed
systems, and cloud engineering as areas/projects, but don't invent employers,
metrics, job titles, credentials, contact details, external links, or awards.
The site's owner can review and personalize these example descriptions before
publishing. Do not claim AWS services have already been deployed or tested.
Use terminology consistent with private S3, CloudFront, Route 53, and ACM.
"""
    request = {
        "task": "Create content for a five-page responsive static portfolio website",
        "requirements_from_first_agent": requirements,
        "target_pages": list(PAGES),
    }
    response = OpenAI().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(request)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("The model returned an empty response")
    return json.loads(content)


def validate_spec(spec: dict) -> None:
    """Reject incomplete/unexpected model output before writing files."""
    if not isinstance(spec, dict) or not isinstance(spec.get("tagline"), str):
        raise ValueError("Missing tagline in AI output")
    pages = spec.get("pages")
    if not isinstance(pages, dict) or set(pages) != set(PAGES):
        raise ValueError("Expected exactly five named pages in AI output")
    for slug, data in pages.items():
        if not isinstance(data, dict):
            raise ValueError(f"{slug} must be an object")
        for field in ("title", "eyebrow", "lead"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"{slug}.{field} must be a nonempty string")
        for field, minimum in (("sections", 2), ("cards", 3)):
            items = data.get(field)
            if not isinstance(items, list) or len(items) < minimum:
                raise ValueError(f"{slug}.{field} needs at least {minimum} entries")
            for item in items:
                if not isinstance(item, dict) or any(
                    not isinstance(item.get(k), str) or not item[k].strip()
                    for k in ("heading", "body")
                ):
                    raise ValueError(f"{slug}.{field} entries need heading and body strings")


def navigation(active: str) -> str:
    links = "\n".join(
        '<a href="{}"{}>{}</a>'.format(slug + '.html', ' aria-current="page"' if slug == active else '', label)
        for slug, label in PAGES.items()
    )
    return f'''<header class="site-header">
      <a class="brand" href="index.html" aria-label="Cloud and HPC Engineering home">
        <span class="brand-mark" aria-hidden="true">◆</span> Cloud<span class="brand-accent">/</span>HPC
      </a>
      <button class="menu-toggle" id="menu-toggle" aria-label="Toggle navigation" aria-expanded="false">Menu ☰</button>
      <nav class="nav" id="main-nav" aria-label="Main navigation">{links}</nav>
      <button id="theme-toggle" class="theme-toggle" type="button" aria-label="Switch color theme">◐ Theme</button>
    </header>'''


def render_page(slug: str, data: dict, tagline: str) -> str:
    sections = "\n".join(
        f'<section class="content-section"><span class="section-number">0{i}</span>'
        f'<div><h2>{e(item["heading"])}</h2><p>{e(item["body"])}</p></div></section>'
        for i, item in enumerate(data["sections"], 1)
    )
    cards = "\n".join(
        f'<article class="feature-card"><span class="card-icon" aria-hidden="true">◆</span>'
        f'<h3>{e(item["heading"])}</h3><p>{e(item["body"])}</p></article>'
        for item in data["cards"]
    )
    active_title = PAGES[slug]
    art = {"index":"cloud-illustration.svg", "about":"network-illustration.svg", "projects":"compute-illustration.svg", "skills":"compute-illustration.svg", "contact":"network-illustration.svg"}[slug]
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{e(data['lead'][:155])}">
  <title>{e(active_title)} | Cloud &amp; HPC Engineering</title>
  <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="assets/style.css">
  <script src="assets/site.js" defer></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <div class="page-shell">
    {navigation(slug)}
    <main id="main">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow"><span class="status-dot"></span> {e(data['eyebrow'])}</p>
          <h1>{e(data['title'])}</h1>
          <p class="lead">{e(data['lead'])}</p>
          <div class="hero-actions"><a class="primary-btn" href="projects.html">Explore projects <span aria-hidden="true">↗</span></a><a class="secondary-btn" href="contact.html">Get in touch</a></div>
        </div>
        <img class="hero-art" src="assets/{art}" alt="Illustrated cloud and distributed compute network" width="460" height="360">
      </section>
      <div class="section-heading"><span>01 / OVERVIEW</span><p>{e(tagline)}</p></div>
      <div class="sections">{sections}</div>
      <div class="section-heading"><span>02 / HIGHLIGHTS</span><p>Systems, ideas, and areas of focus</p></div>
      <div class="card-grid">{cards}</div>
      <div class="page-cta"><div><h2>Build something reliable.</h2><p>Explore how cloud, automation, and performance engineering connect.</p></div><a class="primary-btn" href="contact.html">Contact <span aria-hidden="true">↗</span></a></div>
    </main>
    <footer><span>Cloud / HPC Engineering</span><span>Student project · CSCE 412</span><span>Static site · Designed for secure AWS delivery</span></footer>
  </div>
</body>
</html>'''


def render_404() -> str:
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 | Page not found</title><link rel="stylesheet" href="assets/style.css"><script src="assets/site.js" defer></script>
</head><body><div class="page-shell">'''+navigation("missing")+'''<main id="main" class="error-page">
<p class="eyebrow">404 / PAGE NOT FOUND</p><h1>Looks like this route got lost.</h1>
<p class="lead">The page you requested does not exist. Head back to the home page to keep exploring.</p>
<a class="primary-btn" href="index.html">Back to home ↗</a></main><footer>Cloud / HPC Engineering · CSCE 412</footer></div></body></html>'''

CSS = r''':root { color-scheme: dark; --bg:#09111e; --surface:#101e2d; --surface2:#15283a; --ink:#f1f6fb; --muted:#abc1d4; --border:#2a4153; --accent:#7adacb; --accent2:#8daaf6; }
:root[data-theme="light"] { color-scheme: light; --bg:#f5f8fb; --surface:#ffffff; --surface2:#eef4f8; --ink:#192c3b; --muted:#4c6275; --border:#d5e1ea; --accent:#007d75; --accent2:#315ab1; }
* {box-sizing:border-box} html {scroll-behavior:smooth} body {margin:0;background:var(--bg);color:var(--ink);font-family:'Segoe UI',Arial,sans-serif;line-height:1.65}
a {color:inherit;text-decoration:none} a:focus-visible,button:focus-visible {outline:3px solid var(--accent);outline-offset:4px}
.page-shell {max-width:1240px;margin:auto;padding:0 40px}.site-header {display:flex;gap:24px;align-items:center;justify-content:space-between;padding:24px 0;border-bottom:1px solid var(--border)}
.brand {font-family:'Segoe UI',Arial,sans-serif;font-weight:700;font-size:21px;letter-spacing:-.04em;white-space:nowrap}.brand-mark {color:var(--accent)}.brand-accent {color:var(--accent2)}
.nav {display:flex;align-items:center;gap:22px}.nav a {font-size:14px;color:var(--muted);transition:color .2s}.nav a:hover,.nav a[aria-current] {color:var(--accent)}
.theme-toggle,.menu-toggle {background:var(--surface);border:1px solid var(--border);border-radius:9px;color:var(--ink);cursor:pointer;padding:9px 13px;font:inherit;font-size:13px}.menu-toggle {display:none}
.skip-link {position:absolute;left:-999px;top:0;padding:10px;background:var(--accent);color:#071421}.skip-link:focus {left:12px;top:12px;z-index:5}
.hero {min-height:540px;display:grid;grid-template-columns:1.18fr .82fr;align-items:center;gap:34px;padding:66px 0 74px}.hero-copy {max-width:650px}.eyebrow {font-size:12px;color:var(--accent);font-weight:700;letter-spacing:.12em;text-transform:uppercase}.status-dot {display:inline-block;width:8px;height:8px;background:var(--accent);border-radius:50%;margin-right:8px}
h1,h2,h3 {font-family:'Segoe UI',Arial,sans-serif;line-height:1.15;letter-spacing:-.035em}h1 {font-size:clamp(42px,5.6vw,76px);margin:18px 0 24px}h2 {font-size:clamp(25px,3vw,36px)}h3 {font-size:20px;margin:14px 0 9px}.lead {color:var(--muted);font-size:clamp(17px,1.75vw,20px);max-width:600px}.hero-art {width:100%;height:auto;filter:drop-shadow(0 22px 50px #43b8b525)}
.hero-actions {display:flex;gap:12px;flex-wrap:wrap;margin-top:32px}.primary-btn,.secondary-btn {border-radius:10px;padding:13px 20px;font-weight:700;font-size:14px;display:inline-flex;align-items:center;gap:18px}.primary-btn {background:var(--accent);color:#081d24}.secondary-btn {border:1px solid var(--border);color:var(--ink)}.primary-btn:hover {filter:brightness(1.08)}.secondary-btn:hover {background:var(--surface2)}
.section-heading {display:flex;justify-content:space-between;align-items:baseline;gap:20px;padding:18px 0;border-bottom:1px solid var(--border);margin:18px 0}.section-heading span {font-size:12px;font-weight:700;letter-spacing:.15em;color:var(--accent)}.section-heading p {margin:0;color:var(--muted);font-size:13px}
.sections {display:grid;grid-template-columns:1fr 1fr;gap:34px;margin:34px 0 72px}.content-section {display:flex;align-items:flex-start;gap:18px}.section-number {font-size:13px;font-weight:700;color:var(--accent2);padding-top:9px}.content-section h2 {margin:0 0 15px}.content-section p,.feature-card p {color:var(--muted);margin:0}
.card-grid {display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:32px 0 90px}.feature-card {background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:27px;min-height:250px;transition:transform .2s,border-color .2s}.feature-card:hover {transform:translateY(-4px);border-color:var(--accent)}.card-icon {font-size:22px;color:var(--accent2)}
.page-cta {background:linear-gradient(125deg,var(--surface2),var(--surface));border:1px solid var(--border);border-radius:20px;padding:36px 42px;display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:75px}.page-cta h2 {margin:0 0 10px}.page-cta p {margin:0;color:var(--muted)}.page-cta .primary-btn {white-space:nowrap}
footer {border-top:1px solid var(--border);padding:24px 0 40px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;color:var(--muted);font-size:12px}.error-page {min-height:67vh;padding:130px 0;max-width:740px}.error-page h1 {font-size:clamp(42px,6vw,78px)}.error-page .primary-btn {margin-top:20px}
@media(max-width:900px) {.page-shell {padding:0 24px}.hero {grid-template-columns:1fr;padding:55px 0}.hero-art {max-width:520px;margin:auto}.card-grid {grid-template-columns:repeat(2,1fr)}.sections {grid-template-columns:1fr}.site-header {gap:13px}.nav {gap:12px}.nav a {font-size:12px}}
@media(max-width:650px) {.page-shell {padding:0 18px}.site-header {flex-wrap:wrap}.menu-toggle {display:block;margin-left:auto}.nav {display:none;order:4;flex-basis:100%;flex-direction:column;align-items:stretch;background:var(--surface);padding:16px;border:1px solid var(--border);border-radius:12px}.nav.is-open {display:flex}.nav a {font-size:15px;padding:5px}.theme-toggle {padding:9px}.hero {padding:44px 0}.card-grid {grid-template-columns:1fr;margin-bottom:46px}.page-cta {padding:25px;flex-direction:column;align-items:flex-start}.section-heading {flex-direction:column;gap:0}.sections {margin-bottom:46px}footer {flex-direction:column}h1 {font-size:44px}}
'''

JS = r'''(()=>{
  const root = document.documentElement;
  try { const saved=localStorage.getItem('csce412-theme'); if(saved==='light'||saved==='dark') root.dataset.theme=saved; } catch(e) {}
  const theme=document.getElementById('theme-toggle');
  if(theme) theme.addEventListener('click',()=>{
    root.dataset.theme=root.dataset.theme==='light'?'dark':'light';
    try {localStorage.setItem('csce412-theme',root.dataset.theme)} catch(e) {}
  });
  const menu=document.getElementById('menu-toggle'), nav=document.getElementById('main-nav');
  if(menu&&nav) menu.addEventListener('click',()=>{
    const open=nav.classList.toggle('is-open'); menu.setAttribute('aria-expanded',String(open));
  });
})();
'''

SVG_CLOUD = '''<svg xmlns="http://www.w3.org/2000/svg" width="460" height="360" viewBox="0 0 460 360" role="img" aria-label="Connected computing infrastructure illustration"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#70e0cc"/><stop offset="1" stop-color="#8ba8fb"/></linearGradient></defs><rect width="460" height="360" rx="28" fill="#0c2433"/><g fill="none" stroke="#4b8899" opacity=".35"><path d="M50 80 150 130 260 70 400 140 310 250 160 280 50 200Z"/><path d="m150 130 10 150m100-210 50 180M50 200l350-60"/></g><g fill="#102e3d" stroke="url(#g)" stroke-width="3"><rect x="130" y="100" width="200" height="135" rx="18"/><rect x="45" y="155" width="95" height="68" rx="12"/><rect x="323" y="170" width="95" height="68" rx="12"/></g><g fill="#7adacb"><circle cx="90" cy="188" r="11"/><circle cx="370" cy="203" r="11"/><circle cx="173" cy="145" r="7"/><circle cx="203" cy="145" r="7"/><circle cx="233" cy="145" r="7"/></g><path d="M168 181h125M168 200h88" stroke="#a2becd" stroke-width="8" stroke-linecap="round"/><text x="230" y="299" text-anchor="middle" fill="#c9e4f1" font-family="sans-serif" font-size="17">CLOUD · COMPUTE · NETWORK</text></svg>'''
SVG_COMPUTE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 360" width="460" height="360"><rect width="460" height="360" rx="28" fill="#112434"/><g stroke="#69a9c7" stroke-width="2" fill="#153448"><rect x="75" y="65" width="310" height="230" rx="18"/><rect x="100" y="97" width="260" height="52" rx="9"/><rect x="100" y="163" width="260" height="52" rx="9"/><rect x="100" y="229" width="260" height="40" rx="9"/></g><g fill="#72dac8"><circle cx="129" cy="124" r="10"/><circle cx="129" cy="190" r="10"/><circle cx="129" cy="249" r="10"/></g><g stroke="#8daaf6" stroke-width="7" stroke-linecap="round"><path d="M164 124h147M164 190h147M164 249h147"/></g></svg>'''
SVG_NETWORK = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 360" width="460" height="360"><rect width="460" height="360" rx="28" fill="#10283b"/><g fill="none" stroke="#659daf" stroke-width="4"><path d="M230 175 120 85M230 175 348 85M230 175 120 282M230 175 349 276M120 85 348 85M120 282 349 276"/></g><g fill="#1f4a5b" stroke="#7adacb" stroke-width="4"><circle cx="230" cy="175" r="45"/><circle cx="120" cy="85" r="27"/><circle cx="348" cy="85" r="27"/><circle cx="120" cy="282" r="27"/><circle cx="349" cy="276" r="27"/></g><g fill="#7adacb"><circle cx="230" cy="175" r="12"/><circle cx="120" cy="85" r="8"/><circle cx="348" cy="85" r="8"/><circle cx="120" cy="282" r="8"/><circle cx="349" cy="276" r="8"/></g></svg>'''
SVG_FAVICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0c2433"/><path d="m32 7 25 25-25 25L7 32Z" fill="#7adacb"/><path d="m32 18 14 14-14 14-14-14Z" fill="#8daaf6"/></svg>'''


def write_website(spec: dict) -> list[str]:
    """Safe local tool: only writes fixed filenames beneath website/."""
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)
    files: dict[Path, str] = {
        SITE / "assets" / "style.css": CSS,
        SITE / "assets" / "site.js": JS,
        SITE / "assets" / "cloud-illustration.svg": SVG_CLOUD,
        SITE / "assets" / "compute-illustration.svg": SVG_COMPUTE,
        SITE / "assets" / "network-illustration.svg": SVG_NETWORK,
        SITE / "assets" / "favicon.svg": SVG_FAVICON,
        SITE / "404.html": render_404(),
    }
    for slug, data in spec["pages"].items():
        files[SITE / f"{slug}.html"] = render_page(slug, data, spec["tagline"])
    for path, contents in files.items():
        path.write_text(contents, encoding="utf-8")
    return [str(path.relative_to(ROOT)) for path in files]


class ResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.resources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        properties = dict(attrs)
        if tag == "a" and properties.get("href"):
            self.resources.append(properties["href"])
        if tag in ("script", "img", "link"):
            ref = properties.get("src") or properties.get("href")
            if ref:
                self.resources.append(ref)


def verify_website() -> dict:
    """Independent local checks on required pages and all relative references."""
    problems = []
    page_files = [SITE / f"{slug}.html" for slug in PAGES] + [SITE / "404.html"]
    for page in page_files:
        if not page.is_file():
            problems.append(f"Missing page: {page.name}")
            continue
        content = page.read_text(encoding="utf-8")
        parser = ResourceParser()
        parser.feed(content)
        for ref in parser.resources:
            if ref.startswith(("#", "http://", "https://", "mailto:", "tel:")):
                continue
            target = ref.split("#", 1)[0].split("?", 1)[0]
            if target and not (SITE / target.lstrip("/")).is_file():
                problems.append(f"Broken local link in {page.name}: {ref}")
        for slug in PAGES:
            if f'href="{slug}.html"' not in content:
                problems.append(f"Missing navigation to {slug}.html in {page.name}")
    for asset in ("style.css", "site.js", "cloud-illustration.svg", "compute-illustration.svg", "network-illustration.svg", "favicon.svg"):
        if not (SITE / "assets" / asset).is_file():
            problems.append(f"Missing asset: {asset}")
    return {"passed": not problems, "html_pages": len([f for f in page_files if f.is_file()]), "problems": problems}


def main() -> None:
    parser = argparse.ArgumentParser(description="CSCE 412 Website Builder Agent")
    parser.add_argument("--check", action="store_true", help="Verify files locally without an API call")
    args = parser.parse_args()
    if args.check:
        result = verify_website()
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
        return
    requirements = read_requirements()
    print("Website Builder Agent: reading the Requirements Agent's output")
    print(f"Asking {MODEL} to create five pages of portfolio content...")
    spec = generate_site_spec(requirements)
    validate_spec(spec)
    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / "website_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    written = write_website(spec)
    result = verify_website()
    LOGS.mkdir(exist_ok=True)
    log = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "agent": "website_builder", "model": MODEL,
        "input": "outputs/requirements.json",
        "output": "outputs/website_spec.json",
        "tool": "write_website", "written_files": written,
        "verification": result,
    }
    (LOGS / "website_builder.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print("Generated:", ", ".join(f"{slug}.html" for slug in PAGES), "and 404.html")
    print("Local verification:", "PASS" if result["passed"] else "FAIL")
    print("Log saved to: logs/website_builder.json")
    if not result["passed"]:
        print("Problems:", result["problems"])
        raise SystemExit(1)
    print("Open website/index.html in your browser to preview the site.")


if __name__ == "__main__":
    main()
