#!/bin/zsh
# Unattended Substack -> site sync. Run by launchd (com.drseantobin.site-sync).
# Pulls new Substack posts, rebuilds the static site, pushes to GitHub Pages.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO="/Users/Sean/Sites/drseantobin"
LOG="$REPO/ops-sync.log"

cd "$REPO" || exit 1
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') sync start ==="
  python3 scripts/sync_substack.py || { echo "sync failed"; exit 1; }
  python3 scripts/build.py || { echo "build failed"; exit 1; }
  git add content docs
  if git diff --cached --quiet; then
    echo "no changes"
  else
    git commit -m "Auto-sync Substack + rebuild"
    git pull --rebase origin main
    git push origin main && echo "pushed"
  fi
  echo "=== done ==="
} >> "$LOG" 2>&1
