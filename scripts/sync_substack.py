#!/usr/bin/env python3
"""Sync The Inner Exodus (drseantobin.substack.com) into content/posts/.

Free posts get their full body_html; paid posts get whatever preview the
public API returns (used on the site as a teaser above a subscribe wall).
Re-runnable: already-synced posts are skipped unless Substack shows a newer
post_date. Run with --force to refetch everything.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://drseantobin.substack.com"
ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
INDEX_FILE = ROOT / "content" / "posts_index.json"

HEADERS = {"User-Agent": "drseantobin.ca site sync (owner: seantobin.psyd@gmail.com)"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_archive():
    posts, offset = [], 0
    while True:
        batch = get_json(f"{BASE}/api/v1/archive?sort=new&offset={offset}&limit=25")
        if not batch:
            break
        # Substack may return fewer than `limit` mid-archive; only an empty
        # batch means the end.
        posts.extend(batch)
        offset += len(batch)
        time.sleep(0.5)
    # de-dup, keep newest-first order
    seen, out = set(), []
    for p in posts:
        if p["id"] not in seen:
            seen.add(p["id"])
            out.append(p)
    return out


def main():
    force = "--force" in sys.argv
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    archive = fetch_archive()
    print(f"archive: {len(archive)} posts")

    index = []
    fetched = skipped = 0
    for meta in archive:
        slug = meta["slug"]
        entry = {
            "slug": slug,
            "title": meta.get("title", ""),
            "subtitle": meta.get("subtitle") or "",
            "date": (meta.get("post_date") or "")[:10],
            "audience": meta.get("audience", "everyone"),
            "paid": meta.get("audience") == "only_paid",
            "url": meta.get("canonical_url", f"{BASE}/p/{slug}"),
            "cover_image": meta.get("cover_image") or "",
            "description": meta.get("description") or "",
            "type": meta.get("type", "newsletter"),
        }
        index.append(entry)

        out = POSTS_DIR / f"{slug}.json"
        if out.exists() and not force:
            existing = json.loads(out.read_text())
            if existing.get("post_date") == meta.get("post_date"):
                skipped += 1
                continue
        try:
            full = get_json(f"{BASE}/api/v1/posts/{slug}")
        except Exception as e:
            print(f"  ! {slug}: {e}")
            continue
        out.write_text(json.dumps({
            "slug": slug,
            "post_date": meta.get("post_date"),
            "audience": full.get("audience"),
            "title": full.get("title"),
            "subtitle": full.get("subtitle"),
            "cover_image": full.get("cover_image"),
            "description": full.get("description"),
            "body_html": full.get("body_html") or "",
        }, ensure_ascii=False))
        fetched += 1
        print(f"  + {entry['date']} [{'PAID' if entry['paid'] else 'free'}] {entry['title']}")
        time.sleep(0.4)

    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print(f"done: {fetched} fetched, {skipped} unchanged, index={len(index)}")


if __name__ == "__main__":
    main()
