# AI Paper Reading

**English** | [Chinese](README.zh-CN.md)

**Understand a paper's motivation, model architecture, and experimental evidence.**

Give your AI agent a PDF, an arXiv link, or a paper title. It prepares the paper, figures, tables, and code, then guides you through either a single-response **Overview** or a **Deep Read** with original visuals, equations, and worked examples.

[Quick start](#quick-start) · [Reading modes](#reading-modes) · [Materials and organization](#materials-and-organization) · [Acknowledgments and license](#acknowledgments-and-license)

## Reading modes

| Mode | Best for | Coverage | Pace |
|---|---|---|---|
| **Overview** | Building an initial understanding | Paper context, motivation, research story, and model architecture | One complete response |
| **Deep Read** | Understanding the method and its evidence in detail | Motivation → Method → Training → Experiments | Stage by stage by default; skip ahead or request everything at once |

Your specific instructions take priority. If you ask about a particular figure, equation, or piece of code, the agent addresses it directly. When you provide a paper without choosing a mode, it starts with an Overview.

### Overview: why the work matters and how it works

Start with the research problem, the limitations of prior approaches, and the authors' central idea. Then view the paper's original architecture diagram and follow the data through each component: why it exists, how it connects to the others, and how an input becomes an output.

The focus is the **research story and model architecture**. A full equation walkthrough is optional, and you do not need to keep saying “continue.”

### Deep Read: four stages through a paper

```text
① Motivation
   The problem, gaps in prior work, and the authors' key hypothesis
      ↓
② Method
   Original architecture figures, design rationale, every equation and symbol
      ↓
③ Training
   One sample → preprocessing → input/output flow → loss → parameter updates
   Worked examples, with inference and official code for comparison
      ↓
④ Experiments
   Main results, ablations, and other analyses and limitations in the paper
```

- **Explain design choices.** Connect each component to the problem it solves. Unpack symbols, tensor shapes, operations, and relationships between equations.
- **Trace an actual training example.** Follow the input, intermediate representations, predictions, supervision, and parameter updates.
- **Interpret the evidence.** Show original tables and figures, explain comparison conditions, and distinguish what the results support from what they leave unresolved.
- **Display the visuals.** Explain how to read each figure before discussing the details. Enlarge dense panels or crop a table for a closer look.
- **Make abstract ideas concrete.** Use small numerical examples, simple alternatives, and code walkthroughs when an explanation needs another angle.

## Quick start

Use an AI agent that can read files, access the web, run Python, and display images. The preparation scripts require **Python 3.9+** and **PyMuPDF**. The agent handles reading and explanation; the scripts do not call a model themselves.

### Install in Codex

```bash
git clone https://github.com/Xielewei/ai-paper-reading.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/ai-paper-reading"

cd "${CODEX_HOME:-$HOME/.codex}/skills/ai-paper-reading"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Have the agent run the preparation scripts with this directory's `.venv/bin/python`, or another Python environment with PyMuPDF installed.

### Install in Claude Code

```bash
git clone https://github.com/Xielewei/ai-paper-reading.git \
  ~/.claude/skills/ai-paper-reading

cd ~/.claude/skills/ai-paper-reading
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

For other agents, place the repository in your workspace and ask the agent to read [SKILL.md](SKILL.md). Image display depends on the interface you use.

### Example prompts

```text
Use $ai-paper-reading to give me an overview of this PDF.
Focus on the research story and model architecture.

Find and download this paper, save it under Medical Imaging,
and give me an overview.

Read this paper in depth: motivation, method, training, and experiments.

Explain every equation and symbol in the method section.
Use the original architecture figure to explain the design choices.

Walk through one training sample, including the inputs, outputs,
and loss computation.

Show Table 2 on its own and explain what the main results
and ablations establish.

Turn the three questions we just discussed into notes.
```

`$ai-paper-reading` is the explicit skill invocation syntax in Codex. Use the corresponding invocation mechanism in other agents. The skill instructions and reference examples are currently written in Chinese; you can specify your preferred explanation language in your prompt.

## Materials and organization

The default paper library is **`~/Desktop/paper/`**, organized by **field → paper**:

```text
~/Desktop/paper/
└── Medical Imaging/
    └── <short-name>_<year>_MICCAI/
        ├── paper.pdf
        ├── supplemental.pdf     # Separate appendix, when provided
        ├── supplemental/        # Appendix PDF, text, outline, and figures
        ├── versions/            # Secondary versions: main/appendix PDFs only
        ├── source/              # LaTeX sources matching the selected PDF, if available
        ├── paper.tex            # Flattened source for reading and navigation
        ├── paper.txt            # Text extracted page by page
        ├── outline.md           # Section and equation locations
        ├── meta.json            # Title, authors, dates, and relevant links
        ├── figures/
        │   ├── fig-*.png
        │   ├── tab-*.png
        │   ├── index.md
        │   ├── index.json
        │   └── _contact.png     # Contact sheet for checking crops
        └── code/                # Shallow clone of the identified official code
```

This directory tree uses placeholders rather than describing a real paper.

**Naming follows the verified publication.** Use the paper's stated acronym or short name first; otherwise use its subtitle, then its full title. For an officially accepted or published paper, always use the publication year and venue abbreviation, such as `VCD_2024_CVPR`, even when the selected PDF comes from arXiv. A submission alone does not establish acceptance. Only when no publication is confirmed should the directory use the selected preprint version's year and omit the venue.

### Which PDF version is selected?

Unless you explicitly request a particular version, the agent checks the official publication page, arXiv revision history, and author project page:

1. If any version provides an appendix, choose the **latest version with both the main paper and appendix available**. A single combined PDF and a matching main-paper/supplement pair both qualify.
2. If every version provides an appendix, choose the latest. If no version has an appendix, choose the latest main paper.
3. Compare actual release or revision dates, including arXiv version numbers and update dates. Download times and local file timestamps do not determine recency; a conference PDF is not automatically the newest.

An unavailable or unverified appendix is recorded as such, rather than treated as nonexistent. The agent follows up on missing attachments and reports unresolved gaps or ambiguous dates. Appendices from different versions are not combined to claim completeness. The publication identity used for naming and the PDF version used for reading are recorded separately in `meta.json`, along with candidate versions, source URLs, appendix status, and the selection reason. The agent performs this comparison; `fetch_paper.py` prepares the supplied material and does not discover or rank versions automatically.

### Final storage and verification

Supported inputs include local PDFs, direct PDF URLs, arXiv IDs or links, and existing paper directories. You can also ask the agent to locate a paper by title. Local PDFs are copied while preserving the original; revisiting a paper reuses its existing directory.

The final library is `~/Desktop/paper/` unless you specify another location. Temporary `work/` files and display copies in `outputs/` do not replace that archive. Before saying the paper is saved, the agent checks the selected reading version’s PDFs, version identity, page counts, appendix sections, extracted text, indexes, and final absolute paths. Copies made from a staging directory are checked against PDF checksums. Missing sources or code, and any access failure that prevents final storage, are reported explicitly.

Keep the selected reading version at the paper directory root, with its full extracted materials. Save its separate appendix as `supplemental.pdf` and process it under `supplemental/`. LaTeX sources must match this selected PDF; if only older sources are available, record the missing source and read the selected PDF without retaining those older sources.

**Secondary versions retain only the main-paper and appendix PDFs** under `versions/<source-version-date>/`. If the appendix is already included, keep the single combined `paper.pdf`; otherwise also keep `supplemental.pdf`. Download or copy these PDFs directly, without running `fetch_paper.py`, extracting text, outlines, or figures, downloading sources or code, or creating per-version metadata files. Record their provenance, dates, page counts, appendix status, and paths in the paper root's `meta.json`. Verify these PDFs without requiring extracted materials.

When a secondary version becomes the selected reading version, prepare its full materials then. When a version becomes secondary, remove its generated materials, downloaded sources, and duplicate code, retaining only its PDFs. Identify and preserve user notes, annotations, and manual edits separately at the paper root before cleanup.

### Notes only when you ask

**No reading-notes file is created by default. Conversations and stage-by-stage Q&A are not automatically saved.**

Ask explicitly to “turn this into notes” or “record these questions” to create or update notes within the requested scope. Material outlines and figure indexes are still generated automatically for navigation.

`profile.md` stores background and explanation preferences. Paper notes and Q&A follow the opt-in rule above. `profile.md` is excluded from Git tracking.

### Run the preparation scripts directly

Run these commands from the repository root. The user or agent should first verify the paper name, publication year, venue, and selected PDF version. Automatic naming with `--venue` requires an explicit `--year` to avoid silently using an arXiv date:

```bash
# Import a local PDF; omit --venue if there is no confirmed publication venue.
.venv/bin/python scripts/fetch_paper.py "/path/to/paper.pdf" \
  --field "Medical Imaging" --name "VerifiedShortName" --year 2025 --venue MICCAI

# Prepare an already selected arXiv version, using verified publication metadata.
# Replace the placeholders after checking appendix availability and version dates.
.venv/bin/python scripts/fetch_paper.py "<selected-arxiv-id-with-version>" \
  --field "<field>" --name "<short-name>" --year <publication-year> --venue <venue>

# Process a matching standalone appendix in its own directory.
# Also retain a copy named supplemental.pdf at the main paper directory root.
.venv/bin/python scripts/fetch_paper.py "/path/to/supplemental.pdf" \
  --dest "/path/to/paper-directory/supplemental" --no-clone

# Revisit a directory, optionally supplying a verified official repository.
.venv/bin/python scripts/fetch_paper.py "/path/to/paper-directory" \
  --code "<verified-official-repository-url>"

# Crop a region from PDF page 4; coordinates are normalized to 0–1.
.venv/bin/python scripts/crop.py "/path/to/paper.pdf" \
  --page 4 0.08 0.10 0.92 0.55 -o "/path/to/detail.png"
```

Use `--root` to change the library root, `--dest` to set the full paper directory, or `--no-clone` to discover code links without cloning. Run `--help` for the available metadata, figure, and download options.

If `figures/` already contains user-managed images, automatic crops go into `figures-auto/`. The original PDF, sources, and code are generally reused; extracted text and automatic indexes are rebuilt. Save separate copies of generated files you have edited manually.

## Repository guide

| File | Purpose |
|---|---|
| [SKILL.md](SKILL.md) | Complete reading workflow for the agent |
| [references/examples.md](references/examples.md) | Explanation examples for architectures, data, equations, and code |
| [references/notes-template.md](references/notes-template.md) | Notes template, used only when requested |
| [profile.example.md](profile.example.md) | Template for background, prior knowledge, and example preferences |
| [scripts/fetch_paper.py](scripts/fetch_paper.py) | PDF, sources, metadata, code, and material indexes |
| [scripts/extract_figures.py](scripts/extract_figures.py) | Figure and table extraction, plus a contact sheet |
| [scripts/crop.py](scripts/crop.py) | Detail crops of figures, tables, and equations |

## Limitations and validation

- Automatic cropping relies on captions and layout heuristics. Complex tables and multi-column figures may need manual recropping; the agent should inspect the original visuals before explaining them.
- `source/` and `paper.tex` are available only when the source can be retrieved. Papers outside arXiv or supplied only as PDFs may have no LaTeX source.
- Code discovery uses links in the paper and project pages. It can miss or misidentify a repository, so the correspondence between the paper and implementation should be checked.
- Paper code is read by default. Training scripts and their dependencies are not run or installed on your behalf unless requested.
- Preparing materials does not validate the paper's conclusions or guarantee reproducible training results.

Synthetic-PDF checks cover local import, directory naming (including publication-year and preprint-revision handling), LaTeX expansion, figure and table extraction, detail cropping, preservation of existing materials, and the absence of automatic notes. URL downloads and code cloning are tested with mocked responses; live network downloads have not yet been validated end to end.

Run the checks with:

```bash
.venv/bin/python tests/smoke_test.py
```

## Acknowledgments and license

Thanks to [skJack/kelip-paper-reading](https://github.com/skJack/kelip-paper-reading) for the reading workflow, material preparation scripts, and explanation examples that this skill builds on.

Released under the [MIT License](LICENSE), with the original copyright notice retained.
