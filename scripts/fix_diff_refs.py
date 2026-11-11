"""Resolve references and citations that latexdiff cannot resolve in the marked-up source.

latexdiff removes deleted float environments (PICTUREENV) together with their
\\label commands, so a \\ref{...} inside deleted text prints as "??"; likewise a
\\citep{...} of a bibliography entry that was deleted from the .bib prints as
"[?]" (with --flatten the new .bbl is inlined, so the key is simply absent from
the inlined thebibliography).  This script replaces such references with the
number the label or entry had in the as-submitted build, so the struck-through
text reads as it did in the original manuscript.  Label numbers come from the
as-submitted .aux; citation numbers from explicit key=N arguments (checked
against the submitted PDF).

Usage: python scripts/fix_diff_refs.py main_aa_diff.tex build/submitted/main_aa.aux [key=N ...]
"""
import io
import os
import re
import sys

diff_tex, old_aux = sys.argv[1], sys.argv[2]
oldcite = dict(a.split("=", 1) for a in sys.argv[3:] if "=" in a)
src = io.open(diff_tex, encoding="utf-8").read()

# Strip comments (an unescaped % to end of line) to see what LaTeX will see.
code = re.sub(r"(?<!\\)%.*", "", src)
defined = set(re.findall(r"\\label\{([^}]*)\}", code))

old = {}
for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}\{[^}]*\}", io.open(old_aux, encoding="utf-8", errors="replace").read()):
    old[m.group(1)] = m.group(2)

out = src
missing = sorted({k for k in re.findall(r"\\(?:eq)?ref\{([^}]*)\}", code) if k not in defined})
for key in missing:
    if key not in old:
        print("UNRESOLVED (no old number):", key)
        continue
    num = old[key]
    out = re.sub(r"\\ref\{" + re.escape(key) + r"\}", num, out)
    out = re.sub(r"\\eqref\{" + re.escape(key) + r"\}", "(" + num + ")", out)
    print("%s -> %s" % (key, num))

# Citation keys the diff can resolve: \bibitem entries of an inlined
# thebibliography, plus the entries of any .bib named by \bibliography{...}.
bibkeys = set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}", code))
m = re.search(r"\\bibliography\{([^}]*)\}", code)
if m:
    for b in m.group(1).split(","):
        b = b.strip()
        for cand in (b, b + ".bib"):
            if os.path.exists(cand):
                bibkeys |= set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", io.open(cand, encoding="utf-8", errors="replace").read()))
                break
if bibkeys:
    for cmd, key in sorted(set(re.findall(r"\\(cite[a-z]*)\{([^}]*)\}", code))):
        if "," in key or key in bibkeys:
            continue
        if key not in oldcite:
            print("UNRESOLVED citation (pass %s=N on the command line):" % key, key)
            continue
        rep = "[" + oldcite[key] + "]"
        out = re.sub(r"\\" + cmd + r"\{" + re.escape(key) + r"\}", rep, out)
        print("%s{%s} -> %s" % (cmd, key, rep))
else:
    print("no bibliography found in", diff_tex)

if out != src:
    io.open(diff_tex, "w", encoding="utf-8", newline="\n").write(out)
    print("rewrote", diff_tex)
else:
    print("nothing to fix")
