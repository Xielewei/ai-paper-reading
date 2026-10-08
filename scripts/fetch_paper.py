#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
准备 AI 论文材料；保留已有 PDF/源码/代码，重新生成文本、索引和自动图表。不生成阅读笔记。
改编自 skJack/kelip-paper-reading（MIT，见 ../LICENSE）。

  python3 fetch_paper.py 2410.24164 --field 机器人 --name pi0 --year 2024
  python3 fetch_paper.py /path/to/paper.pdf --field 医学影像 --name NAME --year 2025 --venue MICCAI
  python3 fetch_paper.py /path/to/existing/paper-directory

放哪：已有论文目录就地补全；--dest 指定完整目录；
否则 [--root ~/Desktop/paper]/<--field>/<--name 或标题>_<--year>[_<--venue>]。
--year 未提供时尝试 arXiv published 年份；会议版本请明确传入已核实的发表年。
沿用原版自动发现并浅克隆官方代码的流程，--code 可手动补充仓库。
代码保存在 <论文目录>/code，--code-dir 可覆盖，--no-clone 不克隆。

产出：
  paper.pdf     原文
  source/       arXiv 的 LaTeX 源码（有的话）
  paper.tex     源码拍平成一个文件：\\input 展开、注释和参考文献去掉，开头附正文用到的自定义宏
  paper.txt     PDF 逐页文本（带页码）
  outline.md    章节、公式在 paper.tex 里的行号（没有源码就用 PDF 书签 + 页码）
  meta.json     标题、作者、日期、摘要、版本、代码 / 项目页链接
  figures/      每张图（和表）一个 PNG + index.md + _contact.png（见 extract_figures.py）
  code/         官方代码浅克隆（找得到官方仓库时）
"""
import argparse
import datetime
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True  # import extract_figures 时别在 skill 目录里留 __pycache__

UA = "ai-paper-reading/1.0 (academic paper reader; based on kelip-paper-reading)"
NEW_ID = r'\d{4}\.\d{4,5}(?:v\d+)?'
OLD_ID = r'[a-z][a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?'
ARXIV_RE = re.compile(rf'(?<![\d.])({NEW_ID}|{OLD_ID})(?!\d)')
GREEK = {"π": "pi", "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "λ": "lambda",
         "μ": "mu", "σ": "sigma", "τ": "tau", "φ": "phi", "ω": "omega", "θ": "theta", "ρ": "rho"}
STOP = {"a", "an", "the", "of", "for", "and", "to", "in", "on", "with", "via", "from", "by", "is", "are", "towards",
        "toward", "at", "as", "its", "using", "we", "our"}


def log(msg):
    print(msg, flush=True)


# ---------------- 网络 ----------------

def http_get(urls, timeout=120, tries=2):
    """依次试这几个地址，返回 (内容, 最终地址)。全失败就抛最后一个错。"""
    if isinstance(urls, str):
        urls = [urls]
    last = None
    for url in urls:
        for i in range(tries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read(), r.geturl()
            except Exception as e:  # noqa: BLE001 —— 网络错误五花八门，统一重试
                last = e
                time.sleep(1.5 * (i + 1))
    raise last


# ---------------- 输入解析 ----------------

def parse_target(target):
    p = Path(os.path.expanduser(target))
    if p.is_dir():
        return {"kind": "dir", "path": p.resolve()}
    if p.is_file() and p.suffix.lower() == ".pdf":
        m = ARXIV_RE.search(p.name)
        return {"kind": "local-pdf", "path": p.resolve(), "arxiv": m.group(1) if m else None}
    m = ARXIV_RE.search(target)
    if m and ("arxiv" in target.lower() or "huggingface.co/papers" in target or "alphaxiv" in target
              or "papers.cool" in target or re.fullmatch(r'\s*(arXiv:)?' + m.group(1) + r'\s*', target, re.I)):
        return {"kind": "arxiv", "arxiv": m.group(1)}
    if target.startswith(("http://", "https://")):
        return {"kind": "url-pdf", "url": target}
    sys.exit(f"认不出这个输入：{target}（要 arXiv ID / 链接 / PDF 路径 / 已有目录）")


def tidy_title(t):
    """arXiv 标题里会带 LaTeX：'$π_0$: A Vision-...' → 'π0: A Vision-...'"""
    def inline(m):
        x = m.group(1)
        for k, v in {"\\pi": "π", "\\alpha": "α", "\\beta": "β", "\\lambda": "λ", "\\mu": "μ", "\\tau": "τ"}.items():
            x = x.replace(k, v)
        return re.sub(r'[_^{}\\]', '', x)
    return " ".join(re.sub(r'\$([^$]*)\$', inline, t).split())


def slugify(title, fallback):
    if not title:
        return fallback.replace("/", "-")
    t = "".join(GREEK.get(c, c) for c in title)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    head, _, rest = t.partition(":")
    words = lambda s: [w for w in re.split(r'[^A-Za-z0-9]+', s.lower()) if w and w not in STOP]
    if rest and len(head.split()) <= 3:  # "π0: A Vision-Language-Action ..." → 方法名在冒号前
        name = []
        for w in words(head):
            if w.isdigit() and name:
                name[-1] += w
            else:
                name.append(w)
        parts = ["-".join(name)] + words(rest)[:3]
    else:
        parts = words(t)[:5]
    slug = "-".join(p for p in parts if p)[:60].strip("-")
    return slug or fallback.replace("/", "-")


def path_component(value):
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", value)
    value = re.sub(r'\s+', " ", value).strip(" .")
    if not value or value in (".", ".."):
        raise ValueError("领域或论文名称不能为空")
    # Leave room for year/venue on filesystems with a 255-byte component limit.
    while len(value.encode("utf-8")) > 180:
        value = value[:-1]
    return value.rstrip(" .")


def paper_name(args, meta):
    title = args.name or meta.get("title")
    if not title:
        raise ValueError("无法确定标题，请先查看 PDF 并用 --name 指定论文名")
    year = str(args.year or meta.get("published", "")[:4])
    if not re.fullmatch(r"(19|20)\d{2}", year):
        raise ValueError("无法确定年份，请用 --year 指定已核实的发表年份")
    parts = [path_component(title), year]
    if args.venue:
        parts.append(path_component(args.venue))
    return "_".join(parts)


def pick_dest(args, name):
    if args.dest:
        return Path(os.path.expanduser(args.dest)).resolve()
    if not args.field:
        raise ValueError("请用 --field 指定已选定的领域，或用 --dest 指定完整论文目录")
    root = Path(os.path.expanduser(args.root or "~/Desktop/paper"))
    return (root / path_component(args.field) / name).resolve()


# ---------------- arXiv：元数据、PDF、源码 ----------------

def arxiv_meta(aid):
    try:
        xml, _ = http_get([f"https://export.arxiv.org/api/query?id_list={aid}",
                           f"http://export.arxiv.org/api/query?id_list={aid}"], timeout=40)
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠ arXiv API 没连上（{e}），元数据从 PDF 里凑")
        return {}
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    try:
        e = ET.fromstring(xml).find("a:entry", ns)
    except ET.ParseError:
        return {}
    if e is None:
        return {}
    txt = lambda tag: " ".join((e.findtext(tag, default="", namespaces=ns) or "").split())
    idurl = txt("a:id")
    if "arxiv.org/abs/" not in idurl:
        return {}
    ver = re.search(r'v(\d+)$', idurl)
    return {
        "arxiv_id": aid.split("v")[0] if re.match(NEW_ID, aid) else re.sub(r'v\d+$', '', aid),
        "version": f"v{ver.group(1)}" if ver else "",
        "title": tidy_title(txt("a:title")),
        "authors": [" ".join(a.findtext("a:name", default="", namespaces=ns).split()) for a in e.findall("a:author", ns)],
        "published": txt("a:published")[:10],
        "updated": txt("a:updated")[:10],
        "abstract": txt("a:summary"),
        "comment": txt("x:comment"),
        "journal_ref": txt("x:journal_ref"),
        "categories": [c.get("term") for c in e.findall("a:category", ns)],
        "abs_url": f"https://arxiv.org/abs/{aid}",
    }


def hf_paper(aid):
    """Hugging Face Papers 收录了作者认领的代码仓库和项目页；连不上就算了。"""
    try:
        raw, _ = http_get(f"https://huggingface.co/api/papers/{aid.split('v')[0]}", timeout=12, tries=1)
        d = json.loads(raw)
        return {"github": d.get("githubRepo") or "", "project": d.get("projectPage") or ""}
    except Exception:  # noqa: BLE001
        return {}


def safe_extract(raw, dest):
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
        for m in tf.getmembers():
            target = (dest / m.name).resolve()
            if m.issym() or m.islnk() or m.isdev() or not target.is_relative_to(root):
                continue  # 符号链接、设备文件、../ 越界：一律不解
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif m.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(m) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)


def fetch_source(aid, src_dir):
    """返回 'tar' / 'single-tex' / 'pdf-only' / 'failed'。"""
    try:
        data, _ = http_get([f"https://arxiv.org/e-print/{aid}", f"https://export.arxiv.org/e-print/{aid}"], timeout=240)
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠ 源码没下下来（{e}）")
        return "failed"
    if data[:4] == b"%PDF":
        return "pdf-only"
    raw = data
    if data[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(data)
        except OSError:
            pass
    try:
        safe_extract(raw, src_dir)
        if any(src_dir.rglob("*.tex")):
            return "tar"
    except tarfile.TarError:
        pass
    if raw[:4] == b"%PDF":
        return "pdf-only"
    text = raw.decode("utf-8", errors="replace")
    if "\\documentclass" in text or "\\begin{document}" in text:
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "main.tex").write_text(text, encoding="utf-8")
        return "single-tex"
    return "failed"


def arxiv_id_from_pdf(pdf):
    """arXiv 生成的 PDF 第一页左边有竖排的 'arXiv:2410.24164v4 [cs.LG] ...' 水印。"""
    try:
        import fitz
        with fitz.open(str(pdf)) as d:
            m = re.search(r'arXiv:\s*(' + NEW_ID + ')', d[0].get_text())
            return m.group(1) if m else None
    except Exception:  # noqa: BLE001
        return None


def title_from_pdf(pdf):
    """非 arXiv 的 PDF：先看文档属性里的标题，不像标题就取第一页上半部分字号最大的那几行。"""
    try:
        import fitz
        with fitz.open(str(pdf)) as d:
            t = (d.metadata or {}).get("title") or ""
            if len(t) > 12 and not re.search(r'untitled|microsoft word|\.pdf$|\.dvi$|^p\d+$', t, re.I):
                return " ".join(t.split())
            page = d[0]
            spans = []
            for b in page.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for sp in l["spans"]:
                        if sp["text"].strip() and sp["bbox"][1] < 0.45 * page.rect.height:
                            spans.append((round(sp["size"], 1), sp["bbox"][1], sp["text"].strip()))
            if not spans:
                return ""
            big = max(x[0] for x in spans)
            words = [x[2] for x in sorted(spans, key=lambda x: x[1]) if x[0] >= big - 0.5]
            return " ".join(" ".join(words).split())[:200]
    except Exception:  # noqa: BLE001
        return ""


# ---------------- LaTeX：拍平、宏、大纲 ----------------

VERB_ENVS = r'verbatim|Verbatim|lstlisting|minted|alltt'


def strip_comments(text):
    text = re.sub(r'\\begin\{comment\}.*?\\end\{comment\}', '', text, flags=re.S)
    out, verb = [], False
    for line in text.split("\n"):
        if re.search(r'\\begin\{(' + VERB_ENVS + r')\}', line):
            verb = True
        if verb:
            out.append(line)
            if re.search(r'\\end\{(' + VERB_ENVS + r')\}', line):
                verb = False
            continue
        if re.match(r'\s*%', line):  # 整行注释直接丢，不留空行
            continue
        out.append(re.sub(r'(?<!\\)%.*$', '', line))
    return "\n".join(out)


def drop_iffalse(text):
    """去掉 \\iffalse ... \\fi 包起来的废稿（会数嵌套的 \\ifxxx）。"""
    out, i = [], 0
    for m in re.finditer(r'\\iffalse\b', text):
        if m.start() < i:
            continue
        depth, j = 1, m.end()
        for t in re.finditer(r'\\(if(?!thenelse)[a-zA-Z@]*|fi)\b', text[m.end():]):
            depth += 1 if t.group(1) != "fi" else -1
            if depth == 0:
                j = m.end() + t.end()
                break
        else:
            continue
        out.append(text[i:m.start()])
        i = j
    out.append(text[i:])
    return "".join(out)


INPUT_RE = re.compile(r'\\(?:input|include|subfile)\s*\{([^}]+)\}|\\(?:sub)?import\s*\{([^}]*)\}\s*\{([^}]+)\}'
                      r'|\\input\s+([^\s{}\\]+)')


def flatten(path, root, seen=None, depth=0):
    seen = seen or set()
    if depth > 12 or path in seen:
        return ""
    seen.add(path)
    text = drop_iffalse(strip_comments(path.read_text(encoding="utf-8", errors="ignore")))

    def repl(m):
        if m.group(1):
            name, base = m.group(1).strip(), path.parent
        elif m.group(3):
            name, base = m.group(3).strip(), (path.parent / m.group(2).strip())
        else:
            name, base = m.group(4).strip(), path.parent
        for cand in (base / name, root / name, base / (name + ".tex"), root / (name + ".tex")):
            if cand.resolve().is_relative_to(root.resolve()) and cand.is_file() and cand.suffix in (".tex", ".bbl", ".tikz", ".pgf", ""):
                if cand.suffix in (".tikz", ".pgf"):
                    return f"% [图：{cand.relative_to(root)}]"
                return flatten(cand.resolve(), root, seen, depth + 1)
        return m.group(0)

    return INPUT_RE.sub(repl, text)


def find_main_tex(src):
    readme = src / "00README.json"
    if readme.exists():
        try:
            for s in json.loads(readme.read_text()).get("sources", []):
                if s.get("usage") == "toplevel" and (src / s["filename"]).exists():
                    return src / s["filename"]
        except (ValueError, KeyError):
            pass
    cands = []
    for p in src.rglob("*.tex"):
        if ".stale" in p.parts:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'^\s*\\documentclass', txt, re.M):
            score = (10 if "\\begin{document}" in txt else 0) \
                + (3 if p.stem.lower() in ("main", "paper", "ms", "arxiv", "manuscript", "root") else 0) \
                + (2 if p.parent == src else 0) + min(len(txt) / 20000, 3)
            cands.append((score, str(p)))
    return Path(max(cands)[1]) if cands else None


DEF_RE = re.compile(r'\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand|DeclareMathOperator)\*?|\\def\s*(?=\\)')


def macro_defs(text):
    """正文前面定义的宏：返回 [(名字, 完整定义)]。"""
    from extract_figures import read_group
    out = []
    for m in DEF_RE.finditer(text):
        i = m.end()
        while i < len(text) and text[i] in " \t\n":
            i += 1
        if i >= len(text):
            break
        if text[i] == "{":
            j, name = read_group(text, i)
            name = name.strip()
        elif text[i] == "\\":
            nm = re.match(r'\\[A-Za-z@]+|\\.', text[i:])
            name, j = nm.group(0), i + nm.end()
        else:
            continue
        if not name.startswith("\\"):
            continue
        k = j
        if m.group(0).startswith("\\def"):
            pm = re.match(r'[^{]*', text[k:])
            k += pm.end()
        else:
            for _ in range(2):  # [参数个数][默认值]
                ws = re.match(r'\s*\[[^\]]*\]', text[k:])
                if ws:
                    k += ws.end()
        ws = re.match(r'\s*', text[k:])
        k += ws.end()
        if k < len(text) and text[k] == "{":
            end, _ = read_group(text, k)
            out.append((name, " ".join(text[m.start():end].split())))
    return out


def strip_bib(body):
    body = re.sub(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}', '', body, flags=re.S)
    body = re.sub(r'\\(?:bibliography|bibliographystyle|addbibresource)\s*\{[^}]*\}', '', body)
    return re.sub(r'\\printbibliography(\[[^\]]*\])?', '', body)


def build_tex(dest):
    src = dest / "source"
    main = find_main_tex(src) if src.is_dir() else None
    if not main:
        return None
    full = flatten(main.resolve(), src.resolve())
    b = full.find("\\begin{document}")
    e = full.rfind("\\end{document}")
    pre, body = (full[:b], full[b + len("\\begin{document}"):e if e > b else None]) if b >= 0 else ("", full)
    body = strip_bib(body)
    body = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', body).strip("\n")
    used = []
    seen = set()
    for name, d in macro_defs(pre):
        if name in seen:
            continue
        if re.search(re.escape(name) + r'(?![A-Za-z@])', body):
            seen.add(name)
            used.append(d)
    head = [f"% paper.tex —— 由 source/{main.relative_to(src)} 拍平：\\input 已展开，注释、废稿（\\iffalse）、参考文献已去掉。",
            "% 读正文就读这个文件；行号和 outline.md 对得上。",
            f"% ==== 正文用到的自定义宏（{len(used)} 个；看不懂的记号先查这里）===="]
    head += used
    head += ["% ==== 正文 ===="]
    (dest / "paper.tex").write_text("\n".join(head) + "\n" + body + "\n", encoding="utf-8")
    return {"main": str(main.relative_to(dest)), "macros": len(used),
            "lines": len(head) + body.count("\n") + 1}


EQ_ENVS = r'equation|align|gather|multline|eqnarray|flalign'


def build_outline(dest, meta):
    import extract_figures as ef  # noqa: F811
    L = [f"# 大纲 · {meta.get('title', '')}", ""]
    tex = dest / "paper.tex"
    if tex.exists():
        lines = tex.read_text(encoding="utf-8").split("\n")
        secs = ef.latex_sections(lines)
        levels = {}
        for i, line in enumerate(lines, 1):
            mm = re.search(r'\\(section|subsection|subsubsection)\*?\s*[\[{]', line)
            if mm:
                levels[i] = ["section", "subsection", "subsubsection"].index(mm.group(1))
        n = len(lines)
        L.append("行号指 `paper.tex`。读某一节：`sed -n '起,止p' paper.tex`（或用 Read 的 offset/limit）。")
        L.append("")
        abs_line = next((i for i, l in enumerate(lines, 1) if "\\begin{abstract}" in l), None)
        if abs_line:
            L.append(f"- L{abs_line} 摘要")
        app_line = next((i for i, l in enumerate(lines, 1) if re.match(r'\s*\\appendix\b', l)), None)
        for k, (i, num, title) in enumerate(secs):
            lvl = levels.get(i, 0)
            end = n
            for j, _, _ in secs[k + 1:]:
                if levels.get(j, 0) <= lvl:
                    end = j - 1
                    break
            if app_line and i > app_line and (k == 0 or secs[k - 1][0] < app_line):
                L.append(f"- L{app_line} —— 附录 ——")
            shown = title or ("（无标题，多半是附录开头）" if app_line and i > app_line else "（无标题）")
            L.append(f"{'  ' * lvl}- L{i}–{end} {(num + ' ') if num else ''}{shown}")
        # 公式：训练那一站找 loss 用
        eqs = []
        for m in re.finditer(r'\\begin\{(' + EQ_ENVS + r')(\*?)\}(.*?)\\end\{\1\2\}', "\n".join(lines), re.S):
            ln = "\n".join(lines).count("\n", 0, m.start()) + 1
            content = m.group(3)
            labels = re.findall(r'\\label\{([^}]+)\}', content)
            content = " ".join(re.sub(r'\\label\{[^}]+\}', '', content).split())
            eqs.append((ln, labels, content))
        for m in re.finditer(r'(?m)^\s*\\\[(.*?)\\\]', "\n".join(lines), re.S):
            ln = "\n".join(lines).count("\n", 0, m.start()) + 1
            eqs.append((ln, [], " ".join(m.group(1).split())))
        eqs.sort()
        if eqs:
            L += ["", f"## 公式（{len(eqs)} 个，按出现顺序；L 后面是所在小节）", ""]
            for ln, labels, content in eqs:
                lab = f" `{', '.join(labels)}`" if labels else ""
                prev = content[:110] + ("…" if len(content) > 110 else "")
                L.append(f"- L{ln} {ef.section_of(secs, ln)}{lab}：{prev}")
        L += ["", f"图表的页码、caption、在哪节被引用：见 `{ef.figures_dir(dest).name}/index.md`。"]
    else:
        L.append("没有 LaTeX 源码：正文读 `paper.txt`（按页分好了），公式只能看 PDF 渲染（`crop.py paper.pdf --page N`）。")
        L.append("")
        try:
            import fitz
            with fitz.open(str(dest / "paper.pdf")) as d:
                toc = d.get_toc()
            for lvl, title, page in toc:
                L.append(f"{'  ' * (lvl - 1)}- 第 {page} 页 · {title}")
            if not toc:
                L.append("（PDF 没有书签。用 `grep -n` 在 paper.txt 里找 Introduction / Method / Experiments 这类标题。）")
        except Exception:  # noqa: BLE001
            pass
        L += ["", f"图表的页码和 caption：见 `{ef.figures_dir(dest).name}/index.md`。"]
    (dest / "outline.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def build_txt(dest):
    try:
        import fitz
    except ImportError:
        if shutil.which("pdftotext"):
            subprocess.run(["pdftotext", "-layout", str(dest / "paper.pdf"), str(dest / "paper.txt")], check=False)
        return None
    from extract_figures import clean
    parts = []
    with fitz.open(str(dest / "paper.pdf")) as d:
        n = len(d)
        for i, page in enumerate(d, 1):
            text = "\n".join(l for l in clean(page.get_text()).split("\n")
                             if not l.strip() or l.count("\ufffd") < 0.3 * len(l.strip()))  # 图里字体抽出来的乱码行
            parts.append(f"\n===== 第 {i} 页 =====\n" + text)
    (dest / "paper.txt").write_text("".join(parts), encoding="utf-8")
    return n


# ---------------- 代码 / 项目页链接 ----------------

URL_RE = re.compile(r'https?://[^\s<>"\'{}|\\^`\[\]]+')
SKIP_OWNERS = {"sponsors", "features", "orgs", "topics", "settings", "marketplace", "about", "login"}


def norm_url(u):
    u = u.rstrip(".,;:)]}>'\"")
    u = re.sub(r'#.*$', '', u)
    return u.rstrip("/")


def classify(u):
    m = re.search(r'github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)', u)
    if m:
        owner, repo = m.group(1), re.sub(r'\.git$', '', m.group(2))
        if owner.lower() in SKIP_OWNERS or repo.lower().endswith(".github.io"):
            return None, None  # 项目页模板（nerfies.github.io 之类）的致谢链接
        return "code", f"https://github.com/{owner}/{repo}"
    if re.search(r'huggingface\.co/(?!papers)', u):
        return "hf", u
    if ".github.io" in u or "sites.google.com" in u or re.search(r'project|page|website', u, re.I):
        return "project", u
    return "other", u


def collect_links(dest, meta, hf):
    score = defaultdict(lambda: {"score": 0, "from": []})

    def add(u, w, src, hint=""):
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        kind, url = classify(norm_url(u))
        if kind == "other" and re.search(r'project|website|videos|homepage', hint, re.I):
            kind = "project"
        if not kind or re.search(r'arxiv\.org|doi\.org|creativecommons', url or ""):
            return
        if kind == "other" and src in ("arXiv 备注", "摘要", "HF Papers"):
            kind = "project"
        s = score[(kind, url)]
        s["score"] += w
        if src not in s["from"]:
            s["from"].append(src)

    for u in URL_RE.findall(meta.get("comment", "")):
        add(u, 5, "arXiv 备注")
    for u in URL_RE.findall(meta.get("abstract", "")):
        add(u, 5, "摘要")
    if hf.get("github"):
        add(hf["github"], 6, "HF Papers")
    if hf.get("project"):
        add(hf["project"], 4, "HF Papers")
    try:
        import fitz
        with fitz.open(str(dest / "paper.pdf")) as d:
            for pno, page in enumerate(d):
                first = pno < 2
                for ln in page.get_links():
                    if ln.get("uri"):
                        add(ln["uri"], 4 if first else 0.5, "首页链接" if first else "正文链接")
                if first:
                    for u in URL_RE.findall(page.get_text()):
                        add(u, 3, "首页文字")
    except Exception:  # noqa: BLE001
        pass
    tex = dest / "paper.tex"
    if tex.exists():
        for line in tex.read_text(encoding="utf-8", errors="ignore").split("\n"):
            if re.search(r'code|github|release|available|project|website|open[- ]?source', line, re.I):
                for u in set(re.findall(r'\\(?:url|href)\{([^}]+)\}', line) + URL_RE.findall(line)):
                    add(u, 2, "正文提到", hint=line)
    out = defaultdict(list)
    merged = {}
    for (kind, url), s in score.items():  # 同一个地址先后被归成 other / project 时合并到 project
        key = url
        if key in merged and merged[key][0] == "project":
            merged[key][1]["score"] += s["score"]
            continue
        if key in merged and kind == "project":
            s["score"] += merged[key][1]["score"]
        merged[key] = (kind, s)
    for url, (kind, s) in sorted(merged.items(), key=lambda kv: -kv[1][1]["score"]):
        if kind == "other" and s["score"] < 2:  # 正文里顺手提到的商品 / 数据集网页，不是这篇的东西
            continue
        out[kind].append({"url": url, "score": round(s["score"], 1), "from": s["from"]})
    return dict(out)


def code_from_project_page(url):
    try:
        raw, _ = http_get(url, timeout=15, tries=1)
    except Exception:  # noqa: BLE001
        return None
    cnt = defaultdict(int)
    for u in URL_RE.findall(raw.decode("utf-8", errors="ignore")):
        kind, norm = classify(norm_url(u))
        if kind == "code":
            cnt[norm] += 1
    return max(cnt, key=cnt.get) if cnt else None


def clone(url, code_dir):
    if code_dir.exists() and any(code_dir.iterdir()):
        return "exists"
    if not shutil.which("git"):
        return "no-git"
    code_dir.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
    try:
        r = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", url, str(code_dir)],
                           env=env, capture_output=True, text=True, timeout=300)
        return "ok" if r.returncode == 0 else "failed: " + r.stderr.strip().split("\n")[-1][:160]
    except subprocess.TimeoutExpired:
        shutil.rmtree(code_dir, ignore_errors=True)
        return "timeout"


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser(description="把一篇论文拉到本地，备好精读材料")
    ap.add_argument("target", help="arXiv ID / 链接 / PDF 路径 / 已有的论文目录")
    ap.add_argument("--dest", help="论文目录（完整路径）")
    ap.add_argument("--root", help="论文库根目录，默认 ~/Desktop/paper")
    ap.add_argument("--field", help="领域目录名")
    ap.add_argument("--name", help="经核实的论文简称、小标题或完整标题")
    ap.add_argument("--year", type=int, help="经核实的发表年份")
    ap.add_argument("--venue", help="已正式发表的会议/期刊简称，没有则省略")
    ap.add_argument("--code-dir", help="代码克隆到哪")
    ap.add_argument("--no-clone", action="store_true", help="只找代码链接，不克隆")
    ap.add_argument("--code", help="官方代码仓库地址（论文里没写、自己搜到的时候用；会克隆并记进 meta.json）")
    ap.add_argument("--dpi", type=int, default=220, help="裁图分辨率")
    args = ap.parse_args()

    t = parse_target(args.target)
    aid = t.get("arxiv")
    dest = t["path"] if t["kind"] == "dir" else None
    if dest and not aid:
        mj = dest / "meta.json"
        if mj.exists():
            aid = json.loads(mj.read_text(encoding="utf-8")).get("arxiv_id")
        if not aid and (dest / "paper.pdf").exists():
            aid = arxiv_id_from_pdf(dest / "paper.pdf")

    tmp_pdf = None
    if t["kind"] in ("url-pdf", "local-pdf"):
        if t["kind"] == "url-pdf":
            data, _ = http_get(t["url"], timeout=180)
            if data[:4] != b"%PDF":
                sys.exit("  ✗ 这个链接下下来不是 PDF（可能是网页）。给 PDF 直链，或者先手动下载再传本地路径。")
            import tempfile
            tmp_pdf = Path(tempfile.mkstemp(suffix=".pdf")[1])
            tmp_pdf.write_bytes(data)
        else:
            tmp_pdf = t["path"]
        aid = aid or arxiv_id_from_pdf(tmp_pdf)  # 改过名的 arXiv PDF 第一页上有水印，照样能拉源码

    previous = {}
    if dest and (dest / "meta.json").exists():
        previous = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        if aid and previous.get("version") and not re.search(r'v\d+$', aid):
            aid += previous["version"]
    meta = dict(previous)
    if aid:
        meta.update(arxiv_meta(aid))
    if not meta.get("title"):
        pdf_for_title = tmp_pdf or (dest / "paper.pdf" if dest else None)
        if pdf_for_title and Path(pdf_for_title).exists():
            meta["title"] = title_from_pdf(pdf_for_title)
    if dest is None:
        try:
            dest = pick_dest(args, "" if args.dest else paper_name(args, meta))
        except ValueError as exc:
            ap.error(str(exc))
    if (dest / "paper.pdf").exists() and t["kind"] != "dir":
        if t["kind"] != "local-pdf" or not __import__("filecmp").cmp(tmp_pdf, dest / "paper.pdf", shallow=False):
            ap.error("目标已有 PDF；请核对论文和版本，使用已有目录作为输入，或指定另一个目录。不会覆盖。")
    if not previous and (dest / "meta.json").exists():
        previous = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        meta = {**previous, **meta}
    meta.update({k: v for k, v in {
        "field": args.field, "short_name": args.name, "year": args.year, "venue": args.venue
    }.items() if v is not None})
    meta.setdefault("input_source", str(t.get("path") or t.get("url") or args.target))
    dest.mkdir(parents=True, exist_ok=True)
    shown = (re.sub(r'v\d+$', '', aid) + meta.get("version", "")) if aid and meta.get("version") else aid
    head = f"▸ {shown + ' · ' if aid else ''}{meta.get('title', '')}"
    log(head.rstrip(" ·"))
    if meta.get("authors"):
        au = meta["authors"]
        log(f"  {', '.join(au[:4])}{' 等 %d 人' % len(au) if len(au) > 4 else ''} · {meta.get('published', '')}"
            + (f" · {meta['journal_ref']}" if meta.get("journal_ref") else "")
            + (f" · {meta['comment'][:80]}" if meta.get("comment") else ""))
    log(f"  → {dest}")

    # PDF
    pdf = dest / "paper.pdf"
    if not pdf.exists():
        if tmp_pdf:
            shutil.copy(tmp_pdf, pdf)
            if t["kind"] == "url-pdf":
                Path(tmp_pdf).unlink(missing_ok=True)
        elif aid:
            data, _ = http_get([f"https://arxiv.org/pdf/{aid}", f"https://export.arxiv.org/pdf/{aid}"], timeout=240)
            if data[:4] != b"%PDF":
                sys.exit("  ✗ arXiv 返回的不是 PDF，稍后再试")
            pdf.write_bytes(data)
        else:
            sys.exit(f"  ✗ {dest} 里没有 paper.pdf")
    try:
        import fitz  # noqa: F401
    except ImportError:
        sys.exit("  ✗ 需要 PyMuPDF：pip install pymupdf（裁图、抽文本都靠它）")
    npages = build_txt(dest)
    log(f"  ✓ paper.pdf（{npages} 页）+ paper.txt")

    # LaTeX
    src = dest / "source"
    tex_info = None
    if aid and not (src.is_dir() and any(src.rglob("*.tex"))):
        kind = fetch_source(aid, src)
        if kind == "pdf-only":
            log("  · arXiv 上没有 LaTeX 源码（作者只传了 PDF）：公式和表格只能看 PDF")
    if src.is_dir() and any(src.rglob("*.tex")):
        tex_info = build_tex(dest)
        if tex_info:
            log(f"  ✓ LaTeX 源码 → source/，拍平成 paper.tex（{tex_info['lines']} 行，主文件 {tex_info['main']}，"
                f"正文用到的自定义宏 {tex_info['macros']} 个）")
    if not meta.get("title"):
        meta.setdefault("title", "")
    build_outline(dest, meta)

    # 链接 + 代码
    hf = hf_paper(aid) if aid else {}
    links = collect_links(dest, meta, hf)
    code = [c for c in links.get("code", []) if c["score"] >= 3]
    official, official_from = (code[0]["url"], "、".join(code[0]["from"])) if code else (None, None)
    if args.code:
        official, official_from = args.code.rstrip("/").removesuffix(".git"), " --code 手动指定"
    old_meta = dest / "meta.json"
    if not official and old_meta.exists():  # 上一轮手动指定过 / 克隆过，重跑别丢
        prev = json.loads(old_meta.read_text(encoding="utf-8"))
        official, official_from = prev.get("official_code"), prev.get("official_code_from")
    if not official:
        for p in links.get("project", [])[:2]:
            found = code_from_project_page(p["url"])
            if found:
                official, official_from = found, f"项目页 {p['url']}"
                links.setdefault("code", []).insert(0, {"url": found, "score": 3, "from": ["项目页"]})
                break
    code_dir, clone_state = None, None
    if official:
        repo = official.rstrip("/").split("/")[-1]
        if args.code_dir:
            code_dir = Path(os.path.expanduser(args.code_dir)).resolve()
        else:
            code_dir = dest / "code"
        if not args.no_clone:
            clone_state = clone(official, code_dir)
        elif code_dir.exists() and any(code_dir.iterdir()):
            clone_state = "exists"

    meta.update({
        "pdf_pages": npages, "has_latex": bool(tex_info), "main_tex": tex_info["main"] if tex_info else None,
        "links": links, "official_code": official, "official_code_from": official_from,
        "code_dir": str(code_dir) if code_dir and clone_state in ("ok", "exists") else None,
        "fetched": datetime.date.today().isoformat(),
    })
    if aid and not meta.get("arxiv_id"):
        meta["arxiv_id"] = aid
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # 图
    import extract_figures
    items = extract_figures.extract(dest, dpi=args.dpi, quiet=True)
    nfig = sum(1 for it in items if it["kind"] == "figure")
    ntab = sum(1 for it in items if it["kind"] == "table" and it.get("file"))
    nfull = sum(1 for it in items if it.get("mode") == "整页")
    fd = extract_figures.figures_dir(dest).name
    log(f"  ✓ 图 {nfig} 张、表 {ntab} 张 → {fd}/（整页兜底 {nfull} 张）· 全部裁剪拼在 {fd}/_contact.png")
    if fd != "figures":
        log("    （figures/ 里已经有你自己整理的图，自动裁的放进了 figures-auto/，原来的没动）")
    log(f"  ✓ outline.md · meta.json · {fd}/index.md")

    if official:
        state = {"ok": f"已浅克隆到 {code_dir}", "exists": f"已在 {code_dir}", None: "没克隆（--no-clone）"}.get(
            clone_state, f"克隆没成功（{clone_state}），可以手动 git clone --depth 1")
        log(f"  代码：{official}（来自{official_from}）→ {state}")
    else:
        log("  代码：未找到官方仓库，可以搜索后用 --code 补充；没有就正常阅读。")
    for p in links.get("project", [])[:2]:
        log(f"  项目页：{p['url']}")
    log(f"下一步：读 outline.md、{fd}/index.md，看一眼 {fd}/_contact.png，然后按 SKILL.md 开讲。")


if __name__ == "__main__":
    main()
