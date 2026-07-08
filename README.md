# drseantobin.ca

The personal site of Dr. Sean Tobin — psychologist, author, worship leader.
A dependency-free static site, managed from Claude Code.

## How it works
- `scripts/sync_substack.py` — pulls every post from The Inner Exodus (public Substack API)
  into `content/`. Free posts get full text; paid posts get a teaser only.
- `scripts/build.py` — regenerates the whole site from `content/` into `docs/`
  (GitHub Pages serves `main:/docs`).
- `content/site_data.json` — the hand-edited bits: about text, books, podcast list, music.
- `.github/workflows/deploy.yml` — re-syncs Substack + rebuilds daily and on every push.

## Update locally
    python3 scripts/sync_substack.py   # pull latest Substack posts
    python3 scripts/build.py           # rebuild docs/
