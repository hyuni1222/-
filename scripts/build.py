"""Build only public files; secrets, scripts, and workflow files never enter dist."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    # The user-selected newsletter replaces the former public product catalog.
    shutil.copytree(ROOT / "web", DIST, ignore=shutil.ignore_patterns("products.js", "products-model.js"))
    shutil.copytree(ROOT / "data", DIST / "data", ignore=shutil.ignore_patterns("products.json"))
    shutil.copyfile(ROOT / "config.json", DIST / "config.json")
    (DIST / ".nojekyll").touch()
    # Embed data for an instant first render and a working downloaded HTML preview.
    bootstrap = {"config": json.loads((ROOT / "config.json").read_text()),
                 "latest": json.loads((ROOT / "data/latest.json").read_text()),
                 "archive": json.loads((ROOT / "data/archive.json").read_text())}
    status = ROOT / "data/status.json"
    bootstrap["status"] = json.loads(status.read_text()) if status.exists() else {}
    daily = ROOT / 'data/daily-analysis.json'
    bootstrap['daily_analysis'] = json.loads(daily.read_text()).get('editions',{}).get(bootstrap['latest']['date'],{}) if daily.exists() else {}
    for key, filename in (("weather", "weather.json"), ("trends", "trends.json")):
        path = ROOT / "data" / filename
        bootstrap[key] = json.loads(path.read_text()) if path.exists() else {}
    encoded = json.dumps(bootstrap, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    page = (DIST / "index.html").read_text()
    page=page.replace("/*__BOOTSTRAP__*/", "window.BRIEFING_BOOTSTRAP=" + encoded + ";")
    (DIST / "index.html").write_text(page)
    # A fresh public URL avoids reusing an older social-preview cache entry.
    # It serves the full app without a redirect and keeps query-selected views.
    share_page=page.replace(
        '<link rel="canonical" href="https://hyuni1222.github.io/-/">',
        '<link rel="canonical" href="https://hyuni1222.github.io/-/brief.html">'
    ).replace(
        '<meta property="og:url" content="https://hyuni1222.github.io/-/">',
        '<meta property="og:url" content="https://hyuni1222.github.io/-/brief.html">'
    )
    (DIST / "brief.html").write_text(share_page)
    print("Built dist/ (public files only)")

if __name__ == "__main__":
    main()
