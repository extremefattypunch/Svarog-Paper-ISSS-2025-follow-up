"""Extract the abstract of main_aa.tex as plain text (for the Editorial Manager form)."""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ROOT, "main_aa.tex"), encoding="utf-8").read()
a = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", s, re.S).group(1)
a = a.replace("\\(", "").replace("\\)", "")
a = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", a)
a = a.replace("\\,", " ").replace("---", "\u2014").replace("--", "\u2013").replace("~", " ")
a = re.sub(r"[{}]", "", a)
paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", a.strip()) if p.strip()]
txt = "\n\n".join(paras)
out = os.path.join(ROOT, "build", "em_upload", "abstract_plain.txt")
open(out, "w", encoding="utf-8").write(txt)
print(txt)
print("\nwords:", len(txt.split()), "->", out)
