# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""W0: every page shares the same top bar (brand + nav#pages in the same order); only the current page is marked active."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
PAGES = ["jezero.html", "recon.html", "data.html"]
ORDER = ["jezero.html", "recon.html", "data.html", "scratch/"]


def _header(page):
    s = (WEB / page).read_text()
    m = re.search(r'<header id="top">(.*?)</header>', s, re.S)
    assert m, page
    return m.group(1)


def _nav(page):
    h = _header(page)
    return re.search(r'<a class="brand".*?</nav>', h, re.S).group(0)


def test_same_nav_markup_on_every_page():
    norm = {p: _nav(p).replace(' active', '').replace(' aria-current="page"', '') for p in PAGES}
    assert len(set(norm.values())) == 1, norm


def test_order_and_current_page():
    for p in PAGES:
        nav = _nav(p)
        hrefs = re.findall(r'<a class="btn[^"]*" href="([^"]+)"', nav)
        assert hrefs == ORDER, (p, hrefs)
        active = re.findall(r'<a class="btn active" href="([^"]+)" aria-current="page"', nav)
        assert active == [p], (p, active)
        assert 'Interactive demo' in nav


def test_shared_css_only():
    for css in ("recon.css", "astronaut.css"):
        t = (WEB / css).read_text()
        assert "nav#pages" not in t and "header#top" not in t, css
