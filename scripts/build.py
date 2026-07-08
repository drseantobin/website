#!/usr/bin/env python3
"""Build drseantobin.ca — static site generated from content/.

Zero dependencies. Reads content/site_data.json + content/posts_index.json +
content/posts/*.json (produced by sync_substack.py) and writes the whole site
into public/.
"""
import html
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
PUBLIC = ROOT / "docs"  # GitHub Pages serves from main:/docs
ASSETS = ROOT / "assets"

DATA = json.loads((CONTENT / "site_data.json").read_text())
SITE = DATA["site"]
INDEX = json.loads((CONTENT / "posts_index.json").read_text())

VOID = {"img", "br", "hr", "source", "meta", "link", "input", "wbr", "embed", "area", "col", "track"}

# Substack chrome that must not appear on the site
STRIP_CLASSES = (
    "subscription-widget", "subscribe-widget", "button-wrapper",
    "captioned-button-wrap", "install-substack-app", "digest-post-embed",
    "poll-embed", "community-chat", "subscribe-footer",
)
STRIP_TAGS = {"form", "script", "style", "iframe", "audio"}


class Sanitizer(HTMLParser):
    """Re-emit HTML, dropping blacklisted subtrees and Substack chrome."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.skip_depth = 0
        self.stack = []

    def _blacklisted(self, tag, attrs):
        if tag in STRIP_TAGS:
            return True
        cls = dict(attrs).get("class", "") or ""
        return any(t in cls for t in STRIP_CLASSES)

    def handle_starttag(self, tag, attrs):
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth += 1
            return
        if self._blacklisted(tag, attrs):
            if tag not in VOID:
                self.skip_depth = 1
            return
        attr_s = "".join(
            f' {k}="{html.escape(v, quote=True)}"' if v is not None else f" {k}"
            for k, v in attrs
        )
        self.out.append(f"<{tag}{attr_s}>")

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth -= 1
            return
        if tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if self.skip_depth or self._blacklisted(tag, attrs):
            return
        attr_s = "".join(
            f' {k}="{html.escape(v, quote=True)}"' if v is not None else f" {k}"
            for k, v in attrs
        )
        self.out.append(f"<{tag}{attr_s}/>")

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self.skip_depth:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip_depth:
            self.out.append(f"&#{name};")


def sanitize(body_html):
    s = Sanitizer()
    s.feed(body_html)
    return "".join(s.out)


def teaser(body_html, max_chars=700, max_blocks=5):
    """First few top-level blocks of a sanitized body, for paid previews."""
    blocks = re.findall(r"<(?:p|h[1-6]|blockquote|div class=\"captioned-image-container\").*?>.*?</(?:p|h[1-6]|blockquote|div)>", body_html, re.S)
    out, text_len = [], 0
    for b in blocks[:max_blocks * 2]:
        out.append(b)
        text_len += len(re.sub(r"<[^>]+>", "", b))
        if text_len >= max_chars or len(out) >= max_blocks:
            break
    return "".join(out) if out else body_html[:3000]


def esc(s):
    return html.escape(s or "", quote=True)


def fmt_date(iso):
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    months = ["", "January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    return f"{months[int(m)]} {int(d)}, {y}"


def page(title, body, *, active="", depth=0, description=""):
    r = "../" * depth
    nav_items = [("Writing", "writing/"), ("Books", "books/"), ("Podcast", "podcast/"),
                 ("Music", "music/"), ("About", "about/")]
    nav = "".join(
        f'<a href="{r}{href}" class="{"active" if active == label else ""}">{label}</a>'
        for label, href in nav_items
    )
    socials = "".join(
        f'<a href="{esc(url)}" target="_blank" rel="noopener">{name}</a>'
        for name, url in SITE["socials"].items() if url
    )
    desc = esc(description or SITE["intro"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="{r}assets/inner-exodus-logo.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500;1,600&family=Spectral:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{r}assets/style.css">
</head>
<body>
<header class="topbar">
  <a class="wordmark" href="{r if depth else './'}">Dr.&thinsp;Sean&thinsp;Tobin</a>
  <nav class="mainnav">{nav}</nav>
  <a class="btn btn-subscribe" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe</a>
</header>
{body}
<footer class="footer">
  <div class="footer-inner">
    <div>
      <p class="footer-name">Dr. Sean Tobin</p>
      <p class="footer-roles">{esc(SITE['roles'])}</p>
    </div>
    <div class="footer-links">{socials}</div>
    <p class="footer-note">Essays first appear on <a href="{esc(SITE['substack_url'])}" target="_blank" rel="noopener">The Inner Exodus</a>.</p>
  </div>
</footer>
</body>
</html>"""


def post_card(p, depth):
    r = "../" * depth
    badge = '<span class="badge badge-paid">Subscribers</span>' if p["paid"] else ""
    img = f'<div class="card-img" style="background-image:url(\'{esc(p["cover_image"])}\')"></div>' if p["cover_image"] else '<div class="card-img card-img-empty"></div>'
    sub = esc(p["subtitle"] or p["description"] or "")
    return f"""<a class="post-card" href="{r}writing/{esc(p['slug'])}/">
  {img}
  <div class="card-body">
    <p class="card-date">{fmt_date(p['date'])} {badge}</p>
    <h3>{esc(p['title'])}</h3>
    <p class="card-sub">{sub}</p>
  </div>
</a>"""


def build_home():
    latest = [p for p in INDEX if p.get("type", "newsletter") == "newsletter"][:3]
    cards = "".join(post_card(p, 0) for p in latest)
    books = "".join(book_card(b) for b in DATA["books"][:3])
    pillars = "".join(
        f'<div class="pillar"><h3>{esc(pl["name"])}</h3><p>{esc(pl["text"])}</p></div>'
        for pl in DATA["about"]["pillars"]
    )
    body = f"""
<section class="hero">
  <div class="hero-inner">
    <p class="eyebrow">{esc(SITE['roles'])}</p>
    <h1>{esc(SITE['tagline'])}</h1>
    <p class="hero-sub">{esc(SITE['intro'])}</p>
    <div class="hero-ctas">
      <a class="btn btn-gold" href="writing/">Read the essays</a>
      <a class="btn btn-ghost" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe on Substack</a>
    </div>
  </div>
  <div class="pillar-line" aria-hidden="true"></div>
</section>

<section class="section">
  <div class="section-head"><p class="eyebrow">The Inner Exodus</p><h2>Latest writing</h2>
  <a class="section-more" href="writing/">All {len(INDEX)} essays →</a></div>
  <div class="card-grid">{cards}</div>
</section>

<section class="section section-alt">
  <div class="section-head"><p class="eyebrow">Books</p><h2>The bookstore</h2>
  <a class="section-more" href="books/">Browse the books →</a></div>
  <div class="book-grid">{books}</div>
</section>

<section class="section">
  <div class="section-head"><p class="eyebrow">Listen</p><h2>Podcast &amp; music</h2></div>
  <div class="listen-grid">
    <a class="listen-card" href="podcast/">
      <h3>On other people's microphones</h3>
      <p>Conversations on psychology, deliverance, AI, and the interior life — every show Sean has been a guest on, in one place.</p>
      <span class="listen-more">Podcast appearances →</span>
    </a>
    <a class="listen-card" href="music/">
      <h3>Worship music</h3>
      <p>Sean leads worship — the posture the rest of the work flows from. Listen to the music.</p>
      <span class="listen-more">The music →</span>
    </a>
  </div>
</section>

<section class="quote-band">
  <blockquote>“{esc(SITE['irenaeus'])}”</blockquote>
  <p class="quote-attr">St. Irenaeus of Lyons</p>
</section>

<section class="section">
  <div class="section-head"><p class="eyebrow">About</p><h2>Healing. Worship. Teaching.</h2>
  <a class="section-more" href="about/">More about Sean →</a></div>
  <div class="pillars">{pillars}</div>
</section>

<section class="cta-band">
  <h2>Make the exodus with us.</h2>
  <p>One or two essays a week on faith, psychology, and staying human in the age of AI. Free to read — subscriber essays go deeper.</p>
  <a class="btn btn-gold" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe to The Inner Exodus</a>
</section>
"""
    write("index.html", page(f"Dr. Sean Tobin — {SITE['tagline']}", body, active="", depth=0))


def book_card(b):
    link_open = f'<a class="book-card" href="{esc(b["amazon_url"])}" target="_blank" rel="noopener">' if b["amazon_url"] else '<div class="book-card">'
    link_close = "</a>" if b["amazon_url"] else "</div>"
    badge = f'<span class="badge badge-gold">{esc(b["badge"])}</span>' if b.get("badge") else ""
    cover = b.get("cover", "")
    cover_el = (f'<div class="book-cover" style="background-image:url(\'{esc(cover)}\')"></div>'
                if cover else f'<div class="book-cover book-cover-type"><span>{esc(b["title"])}</span></div>')
    cta = '<span class="listen-more">Buy on Amazon →</span>' if b["amazon_url"] else '<span class="card-date">Details coming soon</span>'
    return f"""{link_open}
  {cover_el}
  <div class="card-body">
    <h3>{esc(b['title'])} {badge}</h3>
    <p class="card-date">{esc(b['formats'])}</p>
    <p class="card-sub">{esc(b['description'])}</p>
    {cta}
  </div>
{link_close}"""


def build_writing_index():
    by_year = {}
    for p in INDEX:
        by_year.setdefault(p["date"][:4], []).append(p)
    sections = ""
    for year in sorted(by_year, reverse=True):
        rows = "".join(post_card(p, 1) for p in by_year[year])
        sections += f'<h2 class="year-mark">{year}</h2><div class="card-grid card-grid-list">{rows}</div>'
    n_free = sum(1 for p in INDEX if not p["paid"])
    body = f"""
<section class="page-head">
  <p class="eyebrow">The Inner Exodus</p>
  <h1>Writing</h1>
  <p class="hero-sub">{len(INDEX)} essays on faith, psychology, and the age of AI. {n_free} are free to read here in full;
  essays marked <span class="badge badge-paid">Subscribers</span> are for subscribers of
  <a href="{esc(SITE['substack_url'])}" target="_blank" rel="noopener">The Inner Exodus</a>.</p>
</section>
<section class="section">{sections}</section>
"""
    write("writing/index.html", page("Writing — Dr. Sean Tobin", body, active="Writing", depth=1))


def build_posts():
    for meta in INDEX:
        slug = meta["slug"]
        f = CONTENT / "posts" / f"{slug}.json"
        if not f.exists():
            continue
        post = json.loads(f.read_text())
        clean = sanitize(post.get("body_html") or "")
        paid = meta["paid"]
        if paid:
            body_content = f"""
<div class="post-body post-body-teaser">{teaser(clean)}</div>
<div class="paywall">
  <p class="eyebrow">Subscriber essay</p>
  <h3>The rest of this essay is for subscribers of The Inner Exodus.</h3>
  <p>Subscriber essays go deeper — this one continues on Substack.</p>
  <div class="hero-ctas">
    <a class="btn btn-gold" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Become a subscriber</a>
    <a class="btn btn-ghost-dark" href="{esc(meta['url'])}" target="_blank" rel="noopener">Read on Substack</a>
  </div>
</div>"""
        else:
            body_content = f"""
<div class="post-body">{clean}</div>
<div class="post-footer-cta">
  <p>This essay first appeared on <a href="{esc(meta['url'])}" target="_blank" rel="noopener">The Inner Exodus</a>.
  Get the next one in your inbox:</p>
  <a class="btn btn-gold" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe free</a>
</div>"""
        cover = f'<div class="post-cover" style="background-image:url(\'{esc(meta["cover_image"])}\')"></div>' if meta["cover_image"] else ""
        badge = '<span class="badge badge-paid">Subscribers</span>' if paid else ""
        body = f"""
<article class="post">
  <header class="page-head">
    <p class="eyebrow">{fmt_date(meta['date'])} {badge}</p>
    <h1>{esc(meta['title'])}</h1>
    {f'<p class="hero-sub">{esc(meta["subtitle"])}</p>' if meta['subtitle'] else ''}
  </header>
  {cover}
  {body_content}
</article>
"""
        write(f"writing/{slug}/index.html",
              page(f"{meta['title']} — Dr. Sean Tobin", body, active="Writing", depth=2,
                   description=meta["description"] or meta["subtitle"]))


def build_books():
    cards = "".join(book_card(b) for b in DATA["books"])
    body = f"""
<section class="page-head">
  <p class="eyebrow">Books</p>
  <h1>The bookstore</h1>
  <p class="hero-sub">Books for the exodus: on fear and deliverance, and on staying human in the age of AI.</p>
</section>
<section class="section"><div class="book-grid">{cards}</div></section>
"""
    write("books/index.html", page("Books — Dr. Sean Tobin", body, active="Books", depth=1))


def build_podcast():
    eps = DATA["podcast"]
    if eps:
        items = "".join(f"""<a class="ep-row" href="{esc(e['url'])}" target="_blank" rel="noopener">
  <div><p class="card-date">{esc(e.get('show',''))} · {esc(e.get('date',''))}</p>
  <h3>{esc(e['episode'])}</h3><p class="card-sub">{esc(e.get('blurb',''))}</p></div>
  <span class="listen-more">Listen →</span></a>""" for e in eps)
        listing = f'<div class="ep-list">{items}</div>'
    else:
        listing = '<p class="empty-note">Episode list being assembled — check back shortly.</p>'
    body = f"""
<section class="page-head">
  <p class="eyebrow">Podcast</p>
  <h1>On other people's microphones</h1>
  <p class="hero-sub">Conversations Sean has joined as a guest — psychology, deliverance, worship, and the age of AI.</p>
</section>
<section class="section">{listing}</section>
"""
    write("podcast/index.html", page("Podcast — Dr. Sean Tobin", body, active="Podcast", depth=1))


def build_music():
    tracks = DATA["music"]
    if tracks:
        items = "".join(f"""<a class="ep-row" href="{esc(t['url'])}" target="_blank" rel="noopener">
  <div><p class="card-date">{esc(t.get('type',''))} · {esc(t.get('year',''))}</p>
  <h3>{esc(t['title'])}</h3><p class="card-sub">{esc(t.get('blurb',''))}</p></div>
  <span class="listen-more">Listen →</span></a>""" for t in tracks)
        listing = f'<div class="ep-list">{items}</div>'
    else:
        listing = '<p class="empty-note">Discography being assembled — check back shortly.</p>'
    body = f"""
<section class="page-head">
  <p class="eyebrow">Music</p>
  <h1>Worship</h1>
  <p class="hero-sub">Sean leads worship — the posture the rest of the work flows from.</p>
</section>
<section class="section">{listing}</section>
"""
    write("music/index.html", page("Music — Dr. Sean Tobin", body, active="Music", depth=1))


def build_about():
    bio = "".join(f"<p>{esc(b)}</p>" for b in DATA["about"]["bio"])
    pillars = "".join(
        f'<div class="pillar"><h3>{esc(pl["name"])}</h3><p>{esc(pl["text"])}</p></div>'
        for pl in DATA["about"]["pillars"]
    )
    body = f"""
<section class="page-head">
  <p class="eyebrow">About</p>
  <h1>Man fully alive.</h1>
</section>
<section class="section"><div class="post-body about-bio">{bio}</div>
<div class="pillars">{pillars}</div></section>
<section class="quote-band">
  <blockquote>“{esc(SITE['irenaeus'])}”</blockquote>
  <p class="quote-attr">St. Irenaeus of Lyons</p>
</section>
<section class="cta-band">
  <h2>Say hello.</h2>
  <p>The best ways to reach Sean: subscribe and reply to any essay, or find him on Instagram.</p>
  <div class="hero-ctas" style="justify-content:center">
    <a class="btn btn-gold" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe on Substack</a>
    <a class="btn btn-ghost" href="{esc(SITE['socials']['Instagram'])}" target="_blank" rel="noopener">@drseantobin</a>
  </div>
</section>
"""
    write("about/index.html", page("About — Dr. Sean Tobin", body, active="About", depth=1))


def write(rel, content):
    out = PUBLIC / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)


def main():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    shutil.copytree(ASSETS, PUBLIC / "assets")
    build_home()
    build_writing_index()
    build_posts()
    build_books()
    build_podcast()
    build_music()
    build_about()
    (PUBLIC / ".nojekyll").write_text("")
    cname = ROOT / "CNAME"
    if cname.exists():
        (PUBLIC / "CNAME").write_text(cname.read_text().strip() + "\n")
    n = sum(1 for _ in PUBLIC.rglob("*.html"))
    print(f"built {n} pages → {PUBLIC}")


if __name__ == "__main__":
    main()
