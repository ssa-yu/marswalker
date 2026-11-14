# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Interface strings (web/i18n.js): every key the pages use exists, every entry has Chinese text, English is kept."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
SRC = (WEB / "i18n.js").read_text()
ENTRY = re.compile(r"^\s*'([^']+)':\s*\[`([^`]*)`,\s*(null|`[^`]*`)\]", re.M)
PREFIX = r"(?:nav|common|idx|rc|dt|sc|s2|r7|badge|cls|fmt|dir)"


def _entries():
    return {k: (zh, en) for k, zh, en in ENTRY.findall(SRC)}


def _page_files():
    return [p for p in list(WEB.glob("*.js")) + list(WEB.glob("*.html")) + list((WEB / "scratch").glob("*.js")) + list((WEB / "scratch").glob("*.html")) if p.name != "i18n.js"]


def test_default_language_is_switchable():
    assert re.search(r"const I18N_DEFAULT = '(zh|en)';", SRC)


def test_every_used_key_exists():
    E = _entries()
    used = set()
    for p in _page_files():
        used |= set(re.findall(r"""['"](%s\.[A-Za-z0-9_.]+[A-Za-z0-9_])['"]""" % PREFIX, p.read_text()))
    missing = sorted(k for k in used if k not in E)
    assert not missing, missing


def test_entries_have_zh_and_en():
    E = _entries()
    assert len(E) > 300
    for k, (zh, en) in E.items():
        assert zh.strip(), k
        if not k.startswith(("lyr.", "lyrd.", "grp.", "ck:", "unit.")):   # these fall back to the data's English
            assert en != "null" and en.strip("`").strip(), k


def test_pages_load_i18n_first():
    for page in ["jezero.html", "recon.html", "data.html", "scratch/index.html"]:
        s = (WEB / page).read_text()
        i = s.index("i18n.js")
        assert all(i < s.index(x) for x in re.findall(r'<script src="([^"]+)"', s) if "i18n" not in x), page
