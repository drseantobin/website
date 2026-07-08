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

_cat_file = CONTENT / "categories.json"
if _cat_file.exists():
    _cat_data = json.loads(_cat_file.read_text())
    CATS = _cat_data.get("assignments", {})
    CATEGORY_LIST = _cat_data.get("categories", [])
else:
    CATS, CATEGORY_LIST = {}, []

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


# Official brand marks (simple-icons / brand glyphs), single-path, 24x24 viewBox.
SOCIAL_ICONS = {
    "Instagram": '<path d="M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077"/>',
    "YouTube": '<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>',
    "Facebook": '<path d="M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z"/>',
    "LinkedIn": '<path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>',
    "Substack": '<path d="M22.539 8.242H1.46V5.406h21.08v2.836zM1.46 10.812V24L12 18.11 22.54 24V10.812H1.46zM22.54 0H1.46v2.836h21.08V0z"/>',
    "Spotify": '<path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>',
}
SOCIAL_COLORS = {
    "Instagram": "radial-gradient(circle at 30% 107%, #fdf497 0%, #fdf497 5%, #fd5949 45%, #d6249f 60%, #285AEB 90%)",
    "YouTube": "#FF0000", "Facebook": "#1877F2", "LinkedIn": "#0A66C2",
    "Substack": "#FF6719", "Spotify": "#1DB954",
}
SOCIAL_HANDLES = {
    "Instagram": "@drseantobin", "Facebook": "Dr. Sean Tobin", "YouTube": "@drseantobin",
    "LinkedIn": "Sean Tobin, PsyD", "Spotify": "Sean Tobin", "Substack": "The Inner Exodus",
}
SOCIAL_ORDER = ["Instagram", "YouTube", "Facebook", "LinkedIn", "Substack", "Spotify"]


def social_icon(name):
    paths = SOCIAL_ICONS.get(name, '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/>')
    return f'<svg class="soc-svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true">{paths}</svg>'


def social_tiles():
    tiles = []
    for name in SOCIAL_ORDER:
        url = SITE["socials"].get(name)
        if not url:
            continue
        handle = SOCIAL_HANDLES.get(name, "")
        color = SOCIAL_COLORS.get(name, "var(--night)")
        tiles.append(
            f'<a class="social-tile" href="{esc(url)}" target="_blank" rel="noopener" aria-label="{name}">'
            f'<span class="social-ico" style="background:{color};color:#fff">{social_icon(name)}</span>'
            f'<span class="social-tx"><b>{name}</b><em>{esc(handle)}</em></span></a>'
        )
    return '<div class="social-tiles">' + "".join(tiles) + "</div>"


def page(title, body, *, active="", depth=0, description=""):
    r = "../" * depth
    nav_items = [("Writing", "writing/"), ("Books", "books/"), ("Podcast", "podcast/"),
                 ("Music", "music/"), ("About", "about/"), ("Contact", "contact/")]
    nav = "".join(
        f'<a href="{r}{href}" class="{"active" if active == label else ""}">{label}</a>'
        for label, href in nav_items
    )
    _ordered = [n for n in SOCIAL_ORDER if SITE["socials"].get(n)]
    _ordered += [n for n in SITE["socials"] if n not in SOCIAL_ORDER and SITE["socials"].get(n)]
    socials = "".join(
        f'<a href="{esc(SITE["socials"][name])}" target="_blank" rel="noopener" aria-label="{name}" title="{name}">{social_icon(name)}</a>'
        for name in _ordered
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
    badge = '<span class="badge badge-paid">Paid subscribers</span>' if p["paid"] else ""
    img = f'<div class="card-img" style="background-image:url(\'{esc(p["cover_image"])}\')"></div>' if p["cover_image"] else '<div class="card-img card-img-empty"></div>'
    sub = esc(p["subtitle"] or p["description"] or "")
    cat = CATS.get(p["slug"], "")
    blob = esc((p["title"] + " " + (p.get("subtitle") or "") + " " + (p.get("description") or "")).lower())
    chip = f'<span class="cat-chip">{esc(cat)}</span>' if cat else ""
    return f"""<a class="post-card" data-cat="{esc(cat)}" data-search="{blob}" href="{r}writing/{esc(p['slug'])}/">
  {img}
  <div class="card-body">
    <p class="card-date">{fmt_date(p['date'])} {badge}</p>
    <h3>{esc(p['title'])}</h3>
    <p class="card-sub">{sub}</p>
    {chip}
  </div>
</a>"""


def build_home():
    latest = [p for p in INDEX if p.get("type", "newsletter") == "newsletter"][:3]
    cards = "".join(post_card(p, 0) for p in latest)
    books = "".join(book_card(b, 0) for b in DATA["books"][:3])
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
      <p>Conversations on psychology, deliverance, AI, and the interior life. Every show Sean has been a guest on, in one place.</p>
      <span class="listen-more">Podcast appearances →</span>
    </a>
    <a class="listen-card" href="music/">
      <h3>Worship music</h3>
      <p>Sean leads worship, the posture the rest of the work flows from. Listen to the music.</p>
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
  <p>One or two essays a week on faith, psychology, and staying human in the age of AI. Free to read, with paid subscribers going deeper.</p>
  <a class="btn btn-gold" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe to The Inner Exodus</a>
</section>
"""
    write("index.html", page(f"Dr. Sean Tobin · {SITE['tagline']}", body, active="", depth=0))


def book_card(b, depth=0):
    r = "../" * depth
    link_open = f'<a class="book-card" href="{esc(b["amazon_url"])}" target="_blank" rel="noopener">' if b["amazon_url"] else '<div class="book-card">'
    link_close = "</a>" if b["amazon_url"] else "</div>"
    badge = f'<span class="badge badge-gold">{esc(b["badge"])}</span>' if b.get("badge") else ""
    cover = b.get("cover", "")
    if cover:
        cover3d = cover.replace("covers/", "covers/3d/").rsplit(".", 1)[0] + ".png"
        cover_inner = f'<img class="book-3d" src="{r}{esc(cover3d)}" alt="{esc(b["title"])} cover" loading="lazy">'
    else:
        cover_inner = f'<div class="book-cover-type"><span>{esc(b["title"])}</span></div>'
    cover_el = f'<div class="book-stage">{cover_inner}</div>'
    cta = '<span class="listen-more">Buy on Amazon →</span>' if b["amazon_url"] else '<span class="card-date">Coming soon</span>'
    return f"""{link_open}
  {cover_el}
  <div class="card-body">
    <h3>{esc(b['title'])} {badge}</h3>
    <p class="card-date">{esc(b['formats'])}</p>
    <p class="card-sub">{esc(b['description'])}</p>
    {cta}
  </div>
{link_close}"""


WRITING_JS = r"""
(function(){
  var grid=document.getElementById('essay-grid');
  var cards=Array.prototype.slice.call(grid.querySelectorAll('.post-card'));
  var search=document.getElementById('essay-search');
  var pills=document.getElementById('cat-pills');
  var noResults=document.getElementById('no-results');
  var activeCat='all';
  function apply(){
    var q=search.value.trim().toLowerCase();
    var shown=0;
    cards.forEach(function(c){
      var okCat=activeCat==='all'||c.getAttribute('data-cat')===activeCat;
      var hay=c.getAttribute('data-search')+' '+c.getAttribute('data-cat').toLowerCase();
      var okQ=!q||hay.indexOf(q)>-1;
      var show=okCat&&okQ;
      c.style.display=show?'':'none';
      if(show)shown++;
    });
    noResults.hidden=shown>0;
  }
  search.addEventListener('input',apply);
  pills.addEventListener('click',function(e){
    var b=e.target.closest('.cat-pill'); if(!b)return;
    activeCat=b.getAttribute('data-cat');
    pills.querySelectorAll('.cat-pill').forEach(function(p){p.classList.toggle('active',p===b);});
    apply();
  });
  function setView(v){
    grid.classList.toggle('view-grid',v==='grid');
    grid.classList.toggle('view-list',v==='list');
    document.querySelectorAll('.view-toggle button').forEach(function(x){
      x.classList.toggle('active',x.getAttribute('data-view')===v);
    });
    try{localStorage.setItem('essayView',v);}catch(e){}
  }
  document.querySelectorAll('.view-toggle button').forEach(function(btn){
    btn.addEventListener('click',function(){setView(btn.getAttribute('data-view'));});
  });
  try{var v=localStorage.getItem('essayView'); if(v)setView(v);}catch(e){}
})();
"""


def build_writing_index():
    posts = sorted(INDEX, key=lambda p: p["date"], reverse=True)
    cards = "".join(post_card(p, 1) for p in posts)
    n_free = sum(1 for p in INDEX if not p["paid"])
    counts = {}
    for p in INDEX:
        c = CATS.get(p["slug"], "")
        if c:
            counts[c] = counts.get(c, 0) + 1
    pills = f'<button class="cat-pill active" data-cat="all">All <span>{len(posts)}</span></button>'
    for c in CATEGORY_LIST:
        if counts.get(c):
            pills += f'<button class="cat-pill" data-cat="{esc(c)}">{esc(c)} <span>{counts[c]}</span></button>'
    body = f"""
<section class="page-head">
  <p class="eyebrow">The Inner Exodus</p>
  <h1>Writing</h1>
  <p class="hero-sub">{len(INDEX)} essays on faith, psychology, and the age of AI. {n_free} are free to read here in full;
  essays marked <span class="badge badge-paid">Paid subscribers</span> continue on
  <a href="{esc(SITE['substack_url'])}" target="_blank" rel="noopener">The Inner Exodus</a>.</p>
</section>
<section class="section writing-section">
  <div class="writing-controls">
    <div class="search-wrap">
      <input type="search" id="essay-search" placeholder="Search essays…" autocomplete="off" aria-label="Search essays">
    </div>
    <div class="view-toggle" role="group" aria-label="Choose a view">
      <button type="button" data-view="list" class="active" aria-label="List view" title="List view">&#9776;</button>
      <button type="button" data-view="grid" aria-label="Grid view" title="Grid view">&#9638;</button>
    </div>
  </div>
  <div class="cat-pills" id="cat-pills">{pills}</div>
  <div id="essay-grid" class="card-grid view-list">{cards}</div>
  <p id="no-results" class="empty-note" hidden>No essays match your search.</p>
</section>
<script>{WRITING_JS}</script>
"""
    write("writing/index.html", page("Writing · Dr. Sean Tobin", body, active="Writing", depth=1))


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
  <p class="eyebrow">Paid subscriber essay</p>
  <h3>The rest of this piece is for paid subscribers of The Inner Exodus.</h3>
  <p>Unlock this essay and the full archive with a paid subscription on Substack. It is what keeps the writing going.</p>
  <div class="hero-ctas">
    <a class="btn btn-gold" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Unlock with a paid subscription</a>
    <a class="btn btn-ghost-dark" href="{esc(meta['url'])}" target="_blank" rel="noopener">Open on Substack</a>
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
        badge = (f'<a class="badge badge-paid badge-link" href="{esc(SITE["subscribe_url"])}" '
                 f'target="_blank" rel="noopener" title="For paid subscribers of The Inner Exodus. Click to unlock.">Paid subscribers</a>') if paid else ""
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
              page(f"{meta['title']} · Dr. Sean Tobin", body, active="Writing", depth=2,
                   description=meta["description"] or meta["subtitle"]))


def build_books():
    cards = "".join(book_card(b, 1) for b in DATA["books"])
    body = f"""
<section class="page-head">
  <p class="eyebrow">Books</p>
  <h1>The bookstore</h1>
  <p class="hero-sub">Books for the exodus: on fear and deliverance, and on staying human in the age of AI.</p>
</section>
<section class="section"><div class="book-grid">{cards}</div></section>
"""
    write("books/index.html", page("Books · Dr. Sean Tobin", body, active="Books", depth=1))


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
  <p class="hero-sub">Conversations Sean has joined as a guest: psychology, deliverance, worship, and the age of AI.</p>
</section>
<section class="section">{listing}</section>
"""
    write("podcast/index.html", page("Podcast · Dr. Sean Tobin", body, active="Podcast", depth=1))


def build_music():
    tracks = DATA["music"]
    links = SITE.get("music_links", {})
    btns = "".join(
        f'<a class="btn btn-ghost-dark" href="{esc(u)}" target="_blank" rel="noopener">{esc(n)} →</a>'
        for n, u in links.items() if u
    )
    linkbar = f'<div class="music-links">{btns}</div>' if btns else ""
    if tracks:
        def meta_line(t):
            return " · ".join(x for x in (t.get('type', ''), t.get('year', '')) if x)
        items = "".join(f"""<a class="ep-row" href="{esc(t['url'])}" target="_blank" rel="noopener">
  <div><p class="card-date">{esc(meta_line(t))}</p>
  <h3>{esc(t['title'])}</h3><p class="card-sub">{esc(t.get('blurb',''))}</p></div>
  <span class="listen-more">Listen →</span></a>""" for t in tracks)
        listing = f'<div class="ep-list">{items}</div>'
    else:
        listing = '<p class="empty-note">Discography being assembled — check back shortly.</p>'
    body = f"""
<section class="page-head">
  <p class="eyebrow">Music</p>
  <h1>Worship</h1>
  <p class="hero-sub">Sean leads worship, the posture the rest of the work flows from. Hear the full catalogue on Spotify and Apple Music.</p>
  {linkbar}
</section>
<section class="section">{listing}</section>
"""
    write("music/index.html", page("Music · Dr. Sean Tobin", body, active="Music", depth=1))


def build_contact():
    email = SITE.get("contact_email", "")
    js = (
        "(function(){var f=document.getElementById('contact-form');if(!f)return;"
        "var g=function(n){return f.querySelector('[name=\"'+n+'\"]');};"
        "f.addEventListener('submit',function(e){e.preventDefault();"
        "var name=g('name').value.trim(),email=g('email').value.trim(),"
        "msg=g('message').value.trim(),updates=g('updates').checked?'Yes':'No';"
        "var subject='Website message from '+name;"
        "var body='Name: '+name+'\\nEmail: '+email+'\\nKeep in the loop: '+updates+'\\n\\n'+msg;"
        "window.location.href='mailto:" + email + "?subject='+encodeURIComponent(subject)+'&body='+encodeURIComponent(body);"
        "document.getElementById('contact-status').textContent="
        "'Opening your email app to send. If nothing happens, write to " + email + " directly.';});})();"
    )
    body = f"""
<section class="page-head">
  <p class="eyebrow">Contact</p>
  <h1>Say hello.</h1>
  <p class="hero-sub">This one is just me. If something here landed, or you'd like to work together, write to me directly. I read these.</p>
</section>
<section class="section contact-section">
  <div class="contact-grid">
    <form class="contact-box" id="contact-form">
      <label>Your name
        <input type="text" name="name" autocomplete="name" required>
      </label>
      <label>Your email
        <input type="email" name="email" autocomplete="email" required>
      </label>
      <label>Message
        <textarea name="message" rows="5" required></textarea>
      </label>
      <label class="checkbox">
        <input type="checkbox" name="updates" checked>
        <span>Keep me in the loop with new essays and updates from The Inner Exodus.</span>
      </label>
      <button type="submit" class="btn btn-gold">Send message</button>
      <p class="contact-note" id="contact-status">Your message opens in your own email app, addressed to me. Nothing is stored on this site.</p>
    </form>
    <aside class="contact-aside">
      <div class="contact-card">
        <h3>Rather just subscribe?</h3>
        <p>The simplest way to keep in touch is The Inner Exodus. One or two essays a week, free.</p>
        <a class="btn btn-ghost-dark" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe on Substack</a>
      </div>
      <div class="contact-card">
        <h3>Work with me</h3>
        <p>For clinical work, speaking, and booking, my main site has the details.</p>
        <a class="btn btn-ghost-dark" href="{esc(SITE.get('main_site_url',''))}" target="_blank" rel="noopener">Visit my main site</a>
      </div>
      <div class="contact-card contact-card-bonus">
        <h3>A bonus: my dissertation</h3>
        <p>Exorcism, Deliverance, and Psychotherapy, from a Catholic-Christian perspective. Free to read.</p>
        <a class="btn btn-ghost-dark" href="{esc(SITE.get('dissertation_url',''))}" target="_blank" rel="noopener">Read the PDF</a>
      </div>
    </aside>
  </div>
</section>
<section class="section connect-section">
  <div class="connect-head">
    <p class="eyebrow">Elsewhere</p>
    <h2>Find me on your feed.</h2>
    <p class="hero-sub">I'm most active on Instagram and YouTube. Follow wherever you already spend your time.</p>
  </div>
  {social_tiles()}
</section>
<script>{js}</script>
"""
    write("contact/index.html", page("Contact · Dr. Sean Tobin", body, active="Contact", depth=1))


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
  <h2>Get in touch.</h2>
  <p>Write to Sean directly, subscribe to the essays, or find him on Instagram.</p>
  <div class="hero-ctas" style="justify-content:center">
    <a class="btn btn-gold" href="../contact/">Contact me</a>
    <a class="btn btn-ghost-dark" href="{esc(SITE['subscribe_url'])}" target="_blank" rel="noopener">Subscribe on Substack</a>
  </div>
</section>
"""
    write("about/index.html", page("About · Dr. Sean Tobin", body, active="About", depth=1))


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
    build_contact()
    (PUBLIC / ".nojekyll").write_text("")
    cname = ROOT / "CNAME"
    if cname.exists():
        (PUBLIC / "CNAME").write_text(cname.read_text().strip() + "\n")
    n = sum(1 for _ in PUBLIC.rglob("*.html"))
    print(f"built {n} pages → {PUBLIC}")


if __name__ == "__main__":
    main()
