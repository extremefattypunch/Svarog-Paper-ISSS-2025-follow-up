#!/usr/bin/env bash
# Build the revised submission package:
#   main_aa.pdf            clean manuscript
#   main_aa_diff.pdf       latexdiff against the as-submitted tag (submitted-AA-D-26-02719)
#   response_to_reviewers.pdf, cover_letter.pdf
# and run the text checks (forbidden words, undefined references, placeholders).
# Usage: bash scripts/build_revision.sh [path-to-as-submitted-tree]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OLD="${1:-}"
if [ -z "$OLD" ]; then
  OLD="$ROOT/build/submitted"
  if [ ! -f "$OLD/main_aa.tex" ]; then
    mkdir -p "$OLD"
    git archive submitted-AA-D-26-02719 main_aa.tex Sections D.bib cas-refs.bib Figures | tar -x -C "$OLD"
    (cd "$OLD" && pdflatex -interaction=nonstopmode main_aa.tex >/dev/null 2>&1; bibtex main_aa >/dev/null 2>&1)
  fi
fi

build() {  # build <jobname.tex> [bibtex]
  local tex="$1"; local job="${tex%.tex}"
  pdflatex -interaction=nonstopmode "$tex" >/dev/null 2>&1
  if [ "${2:-}" = "bib" ]; then bibtex "$job" >/dev/null 2>&1; pdflatex -interaction=nonstopmode "$tex" >/dev/null 2>&1; fi
  pdflatex -interaction=nonstopmode "$tex" >/dev/null 2>&1
  local err; err=$(grep -c '^!' "$job.log" || true)
  local undef; undef=$(grep -c 'undefined' "$job.log" || true)
  local over; over=$(grep -c 'Overfull' "$job.log" || true)
  printf '%-28s errors=%s undefined=%s overfull=%s pages=%s\n' "$job.pdf" "$err" "$undef" "$over" "$(grep -o 'Output written on .* ([0-9]* pages' "$job.log" | grep -o '[0-9]* pages')"
  grep '^!' "$job.log" | head -5
  grep -i 'undefined' "$job.log" | head -5
}

echo "== clean manuscript"
build main_aa.tex bib

echo "== marked-up manuscript (latexdiff --flatten vs $OLD)"
# Tables are marked as replaced wholesale (PICTUREENV) because latexdiff cannot
# mark up booktabs rows cell by cell without producing \noalign errors. The
# bibliography is NOT flattened: both .bbl files are kept out of latexdiff's way so
# the diff keeps \bibliography and is run through bibtex itself (an inlined new .bbl
# is marked up as one wholesale insertion whose underlined lines cannot break and
# run off the page edge).
rm -f "$OLD/main_aa.bbl" main_aa_diff.bbl main_aa_diff.aux
mv -f main_aa.bbl build/main_aa.bbl.keep
latexdiff --flatten --math-markup=0 --graphics-markup=0 \
  --exclude-textcmd="section,subsection,subsubsection" \
  --config="PICTUREENV=(?:picture|DIFnomarkup|table|table\\*|tabular|figure|figure\\*)[\\w\\d*@]*" \
  "$OLD/main_aa.tex" main_aa.tex > main_aa_diff.tex 2> build/latexdiff.err || true
mv -f build/main_aa.bbl.keep main_aa.bbl
# underlined/struck words cannot hyphenate; let paragraphs stretch instead of overrunning the margin
sed -i 's/^\\begin{document}/\\setlength{\\emergencystretch}{3em}\\begin{document}/' main_aa_diff.tex
# deleted floats lose their labels in latexdiff; print the old numbers instead of "??"
# (usStandardAtmosphere1976 was entry [40] of the submitted PDF; the entry was
#  removed from D.bib for R2-m5, so its deleted citation needs the old number)
python scripts/fix_diff_refs.py main_aa_diff.tex "$OLD/main_aa.aux" usStandardAtmosphere1976=40
build main_aa_diff.tex bib

echo "== response and cover letter"
build response_to_reviewers.tex
build cover_letter.tex

echo "== text checks (sources)"
grep -n "LTDN\|offline\|Chapter~\|PLACEHOLDER\|Julia\|TODO\|\[\[" main_aa.tex Sections/*.tex && echo "  ^^ forbidden tokens found" || echo "  no forbidden tokens in manuscript sources"
grep -n "TODO\|\[\[" response_to_reviewers.tex cover_letter.tex && echo "  ^^ placeholders in letters" || echo "  no placeholders in letters"
echo "== highlights"
python - <<'PY'
for l in open("Highlights.md", encoding="utf-8"):
    if l.startswith("- "):
        t = l[2:].strip(); print(f"  {len(t):3d}  {'OK ' if len(t) <= 85 else 'LONG'} {t}")
PY
echo "== abstract word count"
python - <<'PY'
import re
s = open("main_aa.tex", encoding="utf-8").read()
a = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", s, re.S).group(1)
a = re.sub(r"\\\(|\\\)|\\,|\\mathrm\{[^}]*\}|[{}]", " ", a)
print("  words:", len(a.split()))
PY
