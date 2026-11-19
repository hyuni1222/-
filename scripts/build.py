"""Build only public files; secrets, scripts, and workflow files never enter dist."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "web", DIST)
    shutil.copytree(ROOT / "data", DIST / "data")
    shutil.copyfile(ROOT / "config.json", DIST / "config.json")
    (DIST / ".nojekyll").touch()
    # Embed data for an instant first render and a working downloaded HTML preview.
    bootstrap = {"config": json.loads((ROOT / "config.json").read_text()),
                 "latest": json.loads((ROOT / "data/latest.json").read_text()),
                 "archive": json.loads((ROOT / "data/archive.json").read_text())}
    status = ROOT / "data/status.json"
    bootstrap["status"] = json.loads(status.read_text()) if status.exists() else {}
    for key, filename in (("weather", "weather.json"), ("backfill", "backfill-report.json")):
        path = ROOT / "data" / filename
        bootstrap[key] = json.loads(path.read_text()) if path.exists() else {}
    encoded = json.dumps(bootstrap, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    page = (DIST / "index.html").read_text()
    (DIST / "index.html").write_text(page.replace("/*__BOOTSTRAP__*/", "window.BRIEFING_BOOTSTRAP=" + encoded + ";"))
    print("Built dist/ (public files only)")

if __name__ == "__main__":
    main()
