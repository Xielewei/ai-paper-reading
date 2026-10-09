import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import fitz

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT
sys.path.insert(0, str(SKILL / "scripts"))
import fetch_paper as f

workspace = tempfile.TemporaryDirectory(prefix="paper-skill-check-")
base = Path(workspace.name).resolve()
print("Test workspace:", base)
source = base / "input.pdf"
doc = fitz.open()
p = doc.new_page()
p.insert_text((50, 50), "ToyNet: A Synthetic Reading Fixture", fontsize=19)
p.insert_text((50, 90), "1 Introduction", fontsize=13)
p.insert_text((50, 112), "This fixture tests material preparation, not a real paper.")
p.draw_rect(fitz.Rect(60, 160, 530, 310), color=(0, 0, 0), fill=(.9, .95, 1))
p.insert_text((100, 230), "Input -> Encoder -> Output", fontsize=17)
p.insert_text((60, 340), "Figure 1. Overview of the example architecture.", fontsize=10)
p.insert_text((60, 400), "Table 1. Synthetic accuracy results.", fontsize=10)
for y in (420, 447, 480, 513):
    p.draw_line((60, y), (510, y))
for x, label in ((70, "Method"), (270, "Accuracy")):
    p.insert_text((x, 439), label)
p.insert_text((70, 470), "Baseline")
p.insert_text((270, 470), "80.0")
p.insert_text((70, 502), "ToyNet")
p.insert_text((270, 502), "84.0")
doc.set_metadata({"title": "ToyNet: A Synthetic Reading Fixture"})
doc.save(source)
doc.close()

def run(*args, expected=0):
    r = subprocess.run([sys.executable, str(SKILL/"scripts/fetch_paper.py"), *map(str,args)],
                       capture_output=True, text=True)
    assert r.returncode == expected, r.stdout + r.stderr
    return r

dest = base / "library/医学影像/ToyNet_2025_MICCAI"
run(source, "--root", base/"library", "--field", "医学影像",
    "--name", "ToyNet", "--year", "2025", "--venue", "MICCAI", "--no-clone")
for path in ["paper.pdf", "paper.txt", "outline.md", "meta.json",
             "figures/index.md", "figures/index.json", "figures/_contact.png"]:
    assert (dest/path).exists(), path
items = json.loads((dest/"figures/index.json").read_text())
assert any(x["kind"] == "figure" and x.get("file") for x in items), items
assert any(x["kind"] == "table" and x.get("file") for x in items), items
assert not (dest/"精读笔记.md").exists()
print("PASS: local PDF, domain/name/year/venue, figure + table PNG, no automatic notes")

meta = json.loads((dest/"meta.json").read_text())
meta["verified_sources"] = {"venue": "fixture"}
(dest/"meta.json").write_text(json.dumps(meta))
(dest/"精读笔记.md").write_text("User-written notes must stay unchanged.")
(dest/"figures/custom.txt").write_text("user asset")
(dest/"source").mkdir(exist_ok=True)
(dest/"source/main.tex").write_text(
    r"\documentclass{article}"+"\n"+r"\begin{document}"+"\n"+
    r"\section{Method}"+"\n"+r"\input{method}"+"\n"+r"\end{document}")
(dest/"source/method.tex").write_text(
    r"\begin{equation}L = x^2\label{eq:loss}\end{equation}")
run(dest, "--no-clone")
assert "L = x^2" in (dest/"paper.tex").read_text()
assert "eq:loss" in (dest/"outline.md").read_text()
assert json.loads((dest/"meta.json").read_text())["verified_sources"]["venue"] == "fixture"
assert (dest/"精读笔记.md").read_text() == "User-written notes must stay unchanged."
assert (dest/"figures/custom.txt").read_text() == "user asset"
print("PASS: LaTeX expansion + equation outline; repeat preserves metadata and user files")

manual = base/"manual"
manual.mkdir(exist_ok=True)
(manual/"paper.pdf").write_bytes(source.read_bytes())
(manual/"figures").mkdir(exist_ok=True)
(manual/"figures/keep.png").write_bytes(b"user bytes")
run(manual, "--no-clone")
assert (manual/"figures-auto/index.json").exists()
assert (manual/"figures/keep.png").read_bytes() == b"user bytes"
print("PASS: user figures kept separate")

out = base/"crop.png"
r = subprocess.run([sys.executable, str(SKILL/"scripts/crop.py"), str(source),
                    "--page", "1", ".08", ".18", ".94", ".43", "-o", str(out)],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stderr
assert fitz.Pixmap(str(out)).width > 0
print("PASS: independent PDF crop")

args = SimpleNamespace(dest=None, root=None, field="医学影像", name="ToyNet", year=2025, venue="MICCAI")
assert f.pick_dest(args, f.paper_name(args, {})) == Path.home() / "Desktop/paper/医学影像/ToyNet_2025_MICCAI"
assert f.path_component("A/B: 中文") == "A-B- 中文"
original = (dest/"paper.pdf").read_bytes()
other = base/"different.pdf"
other.write_bytes(source.read_bytes() + b"\n%different")
run(other, "--dest", dest, "--no-clone", expected=2)
assert (dest/"paper.pdf").read_bytes() == original
print("PASS: default library path and collision protection")

# Publication naming remains stable even when the selected PDF is a preprint.
args = SimpleNamespace(name="VCD", year=2024, venue="CVPR")
assert f.paper_name(args, {"published": "2023-11-28", "updated": "2025-01-01"}) == "VCD_2024_CVPR"
args.year = None
try:
    f.paper_name(args, {"published": "2023-11-28"})
except ValueError as exc:
    assert "--year" in str(exc)
else:
    raise AssertionError("Venue naming must require an explicit publication year")
args.venue = None
assert f.paper_name(args, {"published": "2023-11-28", "updated": "2025-01-01"}) == "VCD_2025"
assert f.paper_name(args, {"published": "2023-11-28"}) == "VCD_2023"
print("PASS: publication year independent of PDF date; preprint revision-year fallback")

# A public-PDF download branch with deterministic network fixture.
download_dest = base/"download"
with patch.object(sys, "argv", ["fetch_paper.py", "https://example.org/fixture.pdf",
                              "--dest", str(download_dest), "--no-clone"]), \
     patch.object(f, "http_get", return_value=(source.read_bytes(), "https://example.org/fixture.pdf")), \
     contextlib.redirect_stdout(io.StringIO()):
    f.main()
assert (download_dest/"paper.pdf").read_bytes() == source.read_bytes()
assert not (download_dest/"精读笔记.md").exists()
print("PASS: PDF URL download branch (mock transport)")

candidate_dest = base/"candidate"
with patch.object(sys, "argv", ["fetch_paper.py", str(source), "--dest", str(candidate_dest)]), \
     patch.object(f, "collect_links", return_value={"code": [{"url": "https://github.com/example/model", "score": 10, "from": ["fixture"]}]}), \
     patch.object(f, "clone", return_value="ok") as mocked_clone, \
     contextlib.redirect_stdout(io.StringIO()):
    f.main()
candidate_meta = json.loads((candidate_dest/"meta.json").read_text())
assert candidate_meta["official_code"] == "https://github.com/example/model"
assert candidate_meta["links"]["code"]
mocked_clone.assert_called_once_with("https://github.com/example/model", candidate_dest/"code")
print("PASS: original automatic code discovery/clone workflow preserved (mock clone)")

# Existing arXiv materials must not silently refresh to the newest version.
saved_meta = json.loads((dest/"meta.json").read_text())
saved_meta.update(arxiv_id="2501.12345", version="v2")
(dest/"meta.json").write_text(json.dumps(saved_meta))
with patch.object(sys, "argv", ["fetch_paper.py", str(dest), "--no-clone"]), \
     patch.object(f, "arxiv_meta", return_value={}) as mocked_meta, \
     patch.object(f, "hf_paper", return_value={}), \
     contextlib.redirect_stdout(io.StringIO()):
    f.main()
mocked_meta.assert_called_once_with("2501.12345v2")
print("PASS: existing arXiv version pinned")

# Archive path protection and source references cannot escape source root.
archive = io.BytesIO()
with tarfile.open(fileobj=archive, mode="w") as tf:
    for name in ("main.tex", "../source-extra/escaped.tex"):
        b = b"test"
        info = tarfile.TarInfo(name)
        info.size = len(b)
        tf.addfile(info, io.BytesIO(b))
safe = base/"safe/source"
f.safe_extract(archive.getvalue(), safe)
assert (safe/"main.tex").exists()
assert not (base/"safe/source-extra/escaped.tex").exists()
print("PASS: source archive containment")

workspace.cleanup()
print("All material smoke checks passed.")
