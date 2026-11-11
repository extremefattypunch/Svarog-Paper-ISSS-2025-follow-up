"""
Build the Editorial Manager upload package in build/em_upload/:
  main_aa.tex   flattened LaTeX source (Sections inlined, bibliography inlined
                from main_aa.bbl, figure paths made bare) -- EM builds the PDF
                from files in a single directory
  *.png         every figure referenced by the manuscript (bare file names)
  main_aa_diff.pdf, response_to_reviewers.pdf, cover_letter.pdf, Highlights.docx
Run after scripts/build_revision.sh (which produces main_aa.bbl and the PDFs).
"""
import os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "em_upload")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))

src = open(os.path.join(ROOT, "main_aa.tex"), encoding="utf-8").read()

def inline_inputs(text):
    def repl(m):
        name = m.group(1)
        path = os.path.join(ROOT, name if name.endswith(".tex") else name + ".tex")
        body = open(path, encoding="utf-8").read()
        return "%% ---- begin " + name + " ----\n" + body + "\n%% ---- end " + name + " ----\n"
    return re.sub(r"\\input\{([^}]+)\}", repl, text)

flat = inline_inputs(src)
bbl = open(os.path.join(ROOT, "main_aa.bbl"), encoding="utf-8").read()
flat = re.sub(r"\\bibliographystyle\{[^}]*\}\s*", "", flat)
flat = re.sub(r"\\bibliography\{[^}]*\}", lambda m: bbl, flat)

figs = []
def fig_repl(m):
    opts, path = m.group(1) or "", m.group(2)
    base = os.path.basename(path)
    figs.append(path)
    return "\\includegraphics" + opts + "{" + base + "}"
flat = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}", fig_repl, flat)

open(os.path.join(OUT, "main_aa.tex"), "w", encoding="utf-8").write(flat)
missing = []
for p in sorted(set(figs)):
    cand = [os.path.join(ROOT, p)] + [os.path.join(ROOT, p + ext) for ext in (".png", ".pdf", ".jpg")]
    found = next((c for c in cand if os.path.isfile(c)), None)
    if found is None:
        missing.append(p); continue
    shutil.copy2(found, os.path.join(OUT, os.path.basename(found)))
for f in ("main_aa_diff.pdf", "response_to_reviewers.pdf", "cover_letter.pdf", "Highlights.docx", "main_aa.pdf"):
    shutil.copy2(os.path.join(ROOT, f), os.path.join(OUT, f))
print("package:", OUT)
for f in sorted(os.listdir(OUT)):
    print(f"  {os.path.getsize(os.path.join(OUT, f))/1e6:7.2f} MB  {f}")
print("figures referenced:", len(set(figs)), "missing:", missing)
if "\\input{" in flat or "\\bibliography{" in flat:
    print("WARNING: unresolved \\input or \\bibliography remains")
