#!/bin/bash
# Copy code, small inputs, maps and results from the working folder into the git repository, then commit and push.
# Usage: code/sync.sh "commit message"   (run from the working folder that holds code/ and data/)
set -e
REPO=/home/user/gerrymandering-game
mkdir -p $REPO/code $REPO/data
rm -rf $REPO/code && mkdir -p $REPO/code && cp code/*.py code/*.sh $REPO/code/
find data -maxdepth 2 -type f \( -name '*.json' -o -name '*.csv' -o -name '*.log' -o -name 'wiki_house.txt' -o -name '2026_*.txt' -o -name 'vtd_files.txt' \) \
     -not -path 'data/vtd/*' -not -path 'data/vtd_repo/*' -exec cp --parents {} $REPO/ \;
cd $REPO
git add -A
if git diff --cached --quiet; then echo "nothing to commit"; exit 0; fi
git commit -q -m "$1

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_017NT9s9RaKxY4dw3sRKnyLG"
for d in 0 2 4 8 16; do sleep $d; git push -q -u origin main && { echo pushed; exit 0; }; done
echo "push failed"; exit 1
