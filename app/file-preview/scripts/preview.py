# -*- coding: utf-8 -*-
"""file-preview：让 AI 结构化预览各类文件（纯标准库，零第三方依赖）。

支持：
  - Excel（.xlsx/.xlsm）：解析每个 sheet 的行列数据（zip+XML，无需 openpyxl）
  - PowerPoint（.pptx）：按页提取标题/正文/备注（zip+XML，无需 python-pptx）
  - Word（.docx）：按段落/表格/标题层级提取（zip+XML）
  - CSV / TSV：表格化读取
  - 文本类（.txt/.md/.json/.py/.html/.log 等）：编码自动探测 + 行读取
  - PDF（.pdf）：优先用已安装的 PyPDF2 / pypdf / pdfplumber；没有则给出可执行建议
  - 图片（.png/.jpg/.jpeg/.gif/.bmp/.webp）：读取文件头，输出尺寸/格式/体积；画面内容交给 AI 的视觉能力

用法：
  python preview.py <文件路径> [--rows N] [--max-lines N]
  --rows       表格最多预览多少行（默认 15）
  --max-lines  文本文件最多输出多少行（默认 200）
  --full       关闭一切截断（尽量输出全部）

输出：JSON（UTF-8），字段统一为
  {"ok": true/false, "type": 文件类型, "path": 路径, "size": 字节数, "preview": {...}, "note": 提示}
"""
import argparse
import csv
import json
import os
import re
import struct
import sys
import zipfile
from xml.etree import ElementTree as ET

MAX_CELL_LEN = 300    # 单个单元格文本截断
MAX_TEXT_LEN = 1200   # 文本块截断
MAX_PDF_PAGES = 30


# ---------------------------------------------------------------- 工具
def clamp(text, n=MAX_TEXT_LEN):
    text = str(text)
    if len(text) > n:
        return text[:n] + "…（已截断）"
    return text


def read_text_auto(path, max_lines):
    """文本文件编码自动探测：UTF-8 优先，失败回退 GBK。"""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    total = len(lines)
    show = lines[:max_lines]
    return {"total_lines": total, "lines": show, "truncated": total > max_lines}


def ns(tag):
    return "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}" + tag


# ---------------------------------------------------------------- XLS (BIFF8, 纯标准库)
def _ole2_streams(path):
    """解析 OLE2 复合文档，返回 {流名: bytes}。支持普通流与 mini stream。"""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("不是有效的 xls (OLE2) 文件")
    sector_shift = struct.unpack("<H", data[30:32])[0]
    sector_size = 1 << sector_shift
    mini_shift = struct.unpack("<H", data[32:34])[0]
    mini_size = 1 << mini_shift
    first_dir = struct.unpack("<i", data[48:52])[0]
    first_mini_fat = struct.unpack("<i", data[60:64])[0]
    first_difat = struct.unpack("<i", data[68:72])[0]

    def read_sector(n):
        off = (n + 1) * sector_size
        return data[off:off + sector_size]

    # DIFAT → FAT 扇区列表
    fat_sectors = [x for x in struct.unpack("<109I", data[76:512]) if x != 0xFFFFFFFF]
    ds, seen = first_difat, set()
    while ds >= 0 and ds not in seen:
        seen.add(ds)
        sec = read_sector(ds)
        for i in range(0, sector_size - 4, 4):
            v = struct.unpack("<I", sec[i:i + 4])[0]
            if v == 0xFFFFFFFF:
                break
            fat_sectors.append(v)
        ds = struct.unpack("<I", sec[sector_size - 4:sector_size])[0]
    # FAT
    fat = []
    for fs in fat_sectors:
        sec = read_sector(fs)
        fat += [struct.unpack("<I", sec[i:i + 4])[0] for i in range(0, sector_size, 4)]

    def chain(start, fat_ref=fat):
        out, s, guard = b"", start, 0
        while 0 <= s < len(fat_ref) and s not in (0xFFFFFFFE, 0xFFFFFFFF) and guard < 1 << 20:
            out += read_sector(s)
            nxt = fat_ref[s]
            if nxt in (0xFFFFFFFE, 0xFFFFFFFF, s):
                break
            s = nxt
            guard += 1
        return out

    dir_bytes = chain(first_dir)
    entries = []
    root_mini = b""
    for i in range(0, len(dir_bytes), 128):
        e = dir_bytes[i:i + 128]
        if len(e) < 128:
            break
        name_len = struct.unpack("<H", e[64:66])[0]
        if name_len == 0:
            continue
        name = e[:name_len - 2].decode("utf-16-le", errors="replace")
        otype = e[66]
        start = struct.unpack("<I", e[116:120])[0]
        size = struct.unpack("<Q", e[120:128])[0]
        entries.append((name, otype, start, size))
        if name == "Root Entry":
            root_mini = chain(start)

    # mini FAT（小流分配表）
    mini_fat = []
    if first_mini_fat >= 0:
        mf_bytes = chain(first_mini_fat)
        mini_fat = [struct.unpack("<I", mf_bytes[i:i + 4])[0]
                    for i in range(0, len(mf_bytes), 4)]

    result = {}
    for name, otype, start, size in entries:
        if otype != 2 or name == "Root Entry":
            continue
        if size >= mini_size * 64:
            result[name] = chain(start)[:size]
        else:
            # mini stream：按 mini FAT 链拼
            out, s, guard = b"", start, 0
            while 0 <= s < len(mini_fat) and s not in (0xFFFFFFFE, 0xFFFFFFFF) and guard < 1 << 20:
                off = s * mini_size
                out += root_mini[off:off + mini_size]
                nxt = mini_fat[s]
                if nxt in (0xFFFFFFFE, 0xFFFFFFFF, s):
                    break
                s = nxt
                guard += 1
            result[name] = out[:size]
    return result


def _biff_records(stream):
    """BIFF8 记录流 → [(opcode, data)]。"""
    recs, i = [], 0
    while i + 4 <= len(stream):
        opcode, length = struct.unpack("<HH", stream[i:i + 4])
        recs.append((opcode, stream[i + 4:i + 4 + length]))
        i += 4 + length
    return recs


def _decode_biff8(raw, grbit):
    """BIFF8 字符串解码：grbit 位0(0x01)=UTF-16 双字节；否则=压缩单字节(代码页, 常见 cp936)。"""
    if grbit & 0x01:
        return raw.decode("utf-16-le", errors="replace")
    try:
        return raw.decode("cp936")
    except Exception:
        return raw.decode("latin-1")


def _parse_sst(recs):
    """共享字符串表（处理 CONTINUE 记录与跨块 grbit）。"""
    start = None
    for idx, (op, _) in enumerate(recs):
        if op == 0x00FC:
            start = idx
            break
    if start is None:
        return []
    blocks = []
    for op, d in recs[start:]:
        if op == 0x00FC:
            blocks.append(d[8:])
        elif op == 0x003C:
            blocks.append(d)
        else:
            break

    class MB:
        def __init__(self, blks):
            self.blocks = blks
            self.bi = 0
            self.pos = 0

        def read(self, n, skip_grbit=False):
            out = b""
            while n > 0:
                if self.bi >= len(self.blocks):
                    raise EOFError("SST 截断")
                avail = len(self.blocks[self.bi]) - self.pos
                if avail == 0:
                    self.bi += 1
                    self.pos = 0
                    if self.bi >= len(self.blocks):
                        raise EOFError("SST 截断")
                    if skip_grbit:
                        self.pos = 1  # 文本跨块：跳过新块首字节 grbit
                    continue
                take = min(avail, n)
                out += self.blocks[self.bi][self.pos:self.pos + take]
                self.pos += take
                n -= take
            return out

    mb = MB(blocks)
    strings = []
    try:
        total = struct.unpack("<I", recs[start][1][4:8])[0]
    except IndexError:
        return []
    for _ in range(total):
        cch = struct.unpack("<H", mb.read(2))[0]
        grbit = mb.read(1)[0]
        if grbit & 0x08:
            mb.read(4)
        if grbit & 0x04:
            mb.read(4)
        if grbit & 0x01:
            strings.append(_decode_biff8(mb.read(cch * 2, skip_grbit=True), grbit))
        else:
            strings.append(_decode_biff8(mb.read(cch, skip_grbit=True), grbit))
    return strings


def preview_xls(path, rows_limit):
    """旧版 .xls：OLE2 + BIFF8 解析（文本/数字/公式缓存/RK/MULRK/多sheet）。"""
    streams = _ole2_streams(path)
    wb = streams.get("Workbook") or streams.get("Book")
    if not wb:
        return {"error": "找不到 Workbook 流，文件可能损坏或加密"}
    recs = _biff_records(wb)
    shared = _parse_sst(recs)

    # BOUNDSHEET
    sheets = []
    for op, d in recs:
        if op == 0x0085 and len(d) >= 8:
            pos = struct.unpack("<I", d[0:4])[0]
            cch = d[6]
            grbit = d[7]
            try:
                nbytes = cch * 2 if (grbit & 0x01) else cch
                name = _decode_biff8(d[8:8 + nbytes], grbit)
            except Exception:
                name = "Sheet%d" % (len(sheets) + 1)
            sheets.append((name, pos))

    # 按 sheet 分段读单元格（pos 到下一 sheet pos 或流尾）
    bounds = []
    for i, (name, pos) in enumerate(sheets):
        end = sheets[i + 1][1] if i + 1 < len(sheets) else len(wb)
        bounds.append((name, pos, end))

    result_sheets = []
    pending_formula = None  # (row, col)

    for name, start, end in bounds:
        grid = []
        max_row = 0
        row_count = 0
        in_sheet = False
        i = start
        while i + 4 <= end:
            opcode, length = struct.unpack("<HH", wb[i:i + 4])
            d = wb[i + 4:i + 4 + length]
            i += 4 + length
            if opcode == 0x0809 and d[2:4] == b"\x10\x00":  # BOF: worksheet (dt=0x0010)
                in_sheet = True
                continue
            if not in_sheet:
                continue
            row = col = None
            if len(d) >= 4:
                row, col = struct.unpack("<HH", d[0:4])
            if opcode in (0x0006, 0x00FD, 0x0203, 0x027E, 0x00BD, 0x0201, 0x00BE, 0x0205):
                max_row = max(max_row, row + 1)
                if row + 1 > row_count:
                    row_count = row + 1
            val = None
            if opcode == 0x0006:  # FORMULA
                cached = d[6:14]
                if cached == b"\xff" * 8:
                    pending_formula = (row, col)
                    continue
                val = struct.unpack("<d", cached)[0]
                if isinstance(val, float) and val != val:  # NaN → 无缓存结果
                    val = ""
            elif opcode == 0x00FD:  # LABELSST
                isst = struct.unpack("<I", d[6:10])[0]
                val = shared[isst] if isst < len(shared) else ""
            elif opcode == 0x0203:  # NUMBER
                val = struct.unpack("<d", d[6:14])[0]
            elif opcode == 0x027E:  # RK
                rk = struct.unpack("<i", d[6:10])[0]
                if rk & 0x02:
                    val = rk >> 2
                else:
                    val = rk / 65536.0
                if rk & 0x01:
                    val = val / 100.0
            elif opcode == 0x00BD:  # MULRK
                col_first = col
                j = 4
                while j + 6 <= len(d) - 2:
                    xf = struct.unpack("<H", d[j:j + 2])[0]
                    rk = struct.unpack("<i", d[j + 2:j + 6])[0]
                    c = col_first + (j - 4) // 6
                    if rk & 0x02:
                        v = rk >> 2
                    else:
                        v = rk / 65536.0
                    if rk & 0x01:
                        v = v / 100.0
                    grid.append((row, c, v))
                    j += 6
                continue
            elif opcode == 0x0205:  # BOOLERR
                val = d[6] if len(d) > 6 else ""
            elif opcode == 0x0207 and pending_formula is not None:  # STRING
                pr, pc = pending_formula
                cch = struct.unpack("<H", d[0:2])[0]
                grbit = d[2]
                if grbit & 0x01:
                    s = d[3:3 + cch * 2].decode("utf-16-le", errors="replace")
                else:
                    s = d[3:3 + cch].decode("cp936", errors="replace")
                grid.append((pr, pc, s))
                pending_formula = None
                continue
            elif opcode in (0x0201, 0x00BE):  # BLANK / MULBLANK
                continue
            else:
                continue
            grid.append((row, col, val))

        # 聚合网格，取前 rows_limit 行
        data = []
        seen_rows = set()
        for r, c, v in grid:
            if r < rows_limit:
                seen_rows.add(r)
        maxc = 0
        for _, c, _ in grid:
            maxc = max(maxc, c)
        for r in sorted(seen_rows):
            row_vals = [""] * (maxc + 1)
            for rr, c, v in grid:
                if rr == r:
                    row_vals[c] = "" if v is None else clamp(v, MAX_CELL_LEN)
            data.append(row_vals)
        result_sheets.append({
            "sheet": name,
            "rows": row_count,
            "preview_rows": len(data),
            "data": data,
        })
    return {"sheets": result_sheets}


# ---------------------------------------------------------------- Excel
def preview_xlsx(path, rows_limit):
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return {"error": "不是有效的 xlsx 文件"}
    names = zf.namelist()
    try:
        root = ET.fromstring(zf.read("xl/workbook.xml"))
    except KeyError:
        return {"error": "缺少 xl/workbook.xml，文件可能损坏"}

    sheets = []
    ns_w = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ns_r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    for sh in root.iter(ns_w + "sheet"):
        name = sh.get("name")
        rid = sh.get(ns_r + "id")
        sheets.append((name, rid))

    # sheet 文件映射（workbook.xml.rels）
    rel_map = {}
    try:
        relroot = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in relroot:
            rel_map[rel.get("Id")] = rel.get("Target")
    except KeyError:
        pass

    # 共享字符串表
    shared = []
    try:
        sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in sst.iter(ns_w + "si"):
            txt = "".join(t.text or "" for t in si.iter(ns_w + "t"))
            shared.append(txt)
    except KeyError:
        pass

    result_sheets = []
    for name, rid in sheets:
        target = rel_map.get(rid, "")
        if not target:
            continue
        if target.startswith("/"):
            target = target.lstrip("/")
        else:
            target = "xl/" + target.lstrip("/")
        try:
            sheet_root = ET.fromstring(zf.read(target))
        except KeyError:
            continue
        data = sheet_root.find(ns_w + "sheetData")
        grid = []
        row_count = 0
        if data is not None:
            for row in data.findall(ns_w + "row"):
                row_count += 1
                if len(grid) >= rows_limit:
                    continue
                vals = []
                for c in row.findall(ns_w + "c"):
                    v = c.find(ns_w + "v")
                    t = c.get("t")
                    is_ = c.find(ns_w + "is")
                    if is_ is not None:
                        txt = "".join(x.text or "" for x in is_.iter(ns_w + "t"))
                        vals.append((c.get("r"), txt))
                    elif v is not None and v.text is not None:
                        txt = v.text
                        if t == "s" and txt.isdigit():
                            idx = int(txt)
                            txt = shared[idx] if idx < len(shared) else ""
                        elif t == "inlineStr":
                            pass
                        vals.append((c.get("r"), txt))
                    elif t == "inlineStr" and c.find(ns_w + "is") is not None:
                        txt = "".join(x.text or "" for x in c.find(ns_w + "is").iter(ns_w + "t"))
                        vals.append((c.get("r"), txt))
                grid.append(vals)
        result_sheets.append({
            "sheet": name,
            "rows": row_count,
            "preview_rows": len(grid),
            "data": [[clamp(v, MAX_CELL_LEN) for _, v in row] for row in grid],
        })
    return {"sheets": result_sheets}


# ---------------------------------------------------------------- PPTX
def preview_pptx(path):
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return {"error": "不是有效的 pptx 文件"}
    names = zf.namelist()
    if "ppt/presentation.xml" not in names:
        return {"error": "缺少 ppt/presentation.xml，文件可能损坏"}

    # 幻灯片顺序
    ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    ns_r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    pres = ET.fromstring(zf.read("ppt/presentation.xml"))
    sld_ids = []
    for sld in pres.iter(ns_p + "sldId"):
        sld_ids.append(sld.get(ns_r + "id"))

    rel_map = {}
    try:
        relroot = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
        for rel in relroot:
            rel_map[rel.get("Id")] = rel.get("Target")
    except KeyError:
        pass

    def slide_text(xml_bytes):
        root = ET.fromstring(xml_bytes)
        paras = []
        for p in root.iter(ns_a + "p"):
            texts = [t.text or "" for t in p.iter(ns_a + "t")]
            line = "".join(texts).strip()
            if line:
                paras.append(line)
        return paras

    slides = []
    for i, rid in enumerate(sld_ids, 1):
        target = rel_map.get(rid, "")
        if not target:
            continue
        if target.startswith("/"):
            target = target.lstrip("/")
        else:
            target = "ppt/" + target.lstrip("/")
        try:
            paras = slide_text(zf.read(target))
        except KeyError:
            continue
        slide_info = {"page": i, "text": [clamp(p) for p in paras]}
        # 备注
        notes_target = target.replace("slides/slide", "notesSlides/notesSlide").replace(
            "slides\\slide", "notesSlides\\notesSlide")
        try:
            notes_paras = slide_text(zf.read(notes_target))
            if notes_paras:
                slide_info["notes"] = [clamp(p) for p in notes_paras]
        except (KeyError, ET.ParseError):
            pass
        slides.append(slide_info)
    return {"pages": len(slides), "slides": slides}


# ---------------------------------------------------------------- DOCX
def preview_docx(path):
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return {"error": "不是有效的 docx 文件"}
    try:
        doc = ET.fromstring(zf.read("word/document.xml"))
    except KeyError:
        return {"error": "缺少 word/document.xml，文件可能损坏"}

    ns_w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    body = doc.find(ns_w + "body")
    blocks = []
    para_count = 0
    table_count = 0

    def walk(node):
        nonlocal para_count, table_count
        for child in node:
            tag = child.tag
            if tag == ns_w + "p":
                para_count += 1
                style = ""
                pstyle = child.find(ns_w + "pPr/" + ns_w + "pStyle")
                if pstyle is not None:
                    style = pstyle.get(ns_w + "val") or ""
                texts = "".join(t.text or "" for t in child.iter(ns_w + "t")).strip()
                if texts:
                    level = ""
                    m = re.match(r"(Heading|标题|Title|TitleText|Subtitle)?", style)
                    if style.lower().startswith(("heading", "title", "subtitle")):
                        m2 = re.search(r"(\d+)$", style)
                        level = "H" + (m2.group(1) if m2 else "1")
                    blocks.append({"type": "p", "level": level, "text": clamp(texts)})
            elif tag == ns_w + "tbl":
                table_count += 1
                rows_out = []
                for tr in child.findall(ns_w + "tr")[:15]:
                    cells = []
                    for tc in tr.findall(ns_w + "tc"):
                        cell_text = "".join(t.text or "" for t in tc.iter(ns_w + "t")).strip()
                        cells.append(clamp(cell_text, 120))
                    rows_out.append(cells)
                blocks.append({"type": "table", "rows": rows_out})

    walk(body)
    return {"paragraphs": para_count, "tables": table_count, "blocks": blocks}


# ---------------------------------------------------------------- PDF
def preview_pdf(path):
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
        except ImportError:
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    pages = []
                    for i, page in enumerate(pdf.pages[:MAX_PDF_PAGES]):
                        txt = (page.extract_text() or "").strip()
                        pages.append({"page": i + 1, "text": clamp(txt)})
                return {"pages": len(pdf.pages), "total_pages": len(pdf.pages), "extractor": "pdfplumber", "pages": pages}
            except ImportError:
                return {"error": "PDF 文本提取需要 pypdf / PyPDF2 / pdfplumber 之一。"
                                 "可执行：pip install pypdf 后重试；或让 AI 用系统的 PDF 工具处理"}
    n = len(reader.pages)
    pages = []
    for i in range(min(n, MAX_PDF_PAGES)):
        try:
            txt = (reader.pages[i].extract_text() or "").strip()
        except Exception:
            txt = ""
        pages.append({"page": i + 1, "text": clamp(txt)})
    return {"pages": n, "total_pages": n, "extractor": "pypdf", "pages": pages}


# ---------------------------------------------------------------- 图片
def preview_image(path):
    with open(path, "rb") as f:
        head = f.read(64)
    info = {"format": os.path.splitext(path)[1].lower().lstrip(".").upper()}
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        info.update(format="PNG", width=w, height=h)
    elif head[:2] == b"\xff\xd8":
        # JPEG：扫 SOF 段
        i = 2
        w = h = None
        while i < len(head) - 8:
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                break
            i += 2 + struct.unpack(">H", head[i + 2:i + 4])[0]
        info.update(format="JPEG", width=w, height=h)
    elif head[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", head[6:10])
        info.update(format="GIF", width=w, height=h)
    elif head[:2] == b"BM":
        w, h = struct.unpack("<ii", head[18:26])
        info.update(format="BMP", width=w, height=h)
    elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        info.update(format="WEBP")
    return info


# ---------------------------------------------------------------- 主入口
def detect_type(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        return "excel"
    if ext == ".xls":
        return "excel-old"
    if ext in (".pptx", ".pptm"):
        return "powerpoint"
    if ext == ".docx":
        return "word"
    if ext == ".doc":
        return "word-old"
    if ext == ".pdf":
        return "pdf"
    if ext in (".csv", ".tsv"):
        return "csv"
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
        return "image"
    if ext in (".ppt",):
        return "old-office"
    return "text"


def main():
    ap = argparse.ArgumentParser(description="file-preview：结构化预览文件")
    ap.add_argument("path")
    ap.add_argument("--rows", type=int, default=15)
    ap.add_argument("--max-lines", type=int, default=200)
    args = ap.parse_args()

    path = args.path
    if not os.path.exists(path):
        print(json.dumps({"ok": False, "error": "文件不存在: %s" % path}, ensure_ascii=False))
        return
    size = os.path.getsize(path)
    ftype = detect_type(path)
    base = {"ok": True, "type": ftype, "path": os.path.abspath(path), "size": size}
    note = []

    try:
        if ftype == "excel":
            r = preview_xlsx(path, args.rows)
            base["preview"] = r
        elif ftype == "excel-old":
            r = preview_xls(path, args.rows)
            base["preview"] = r
        elif ftype == "powerpoint":
            r = preview_pptx(path)
            base["preview"] = r
        elif ftype == "word":
            r = preview_docx(path)
            base["preview"] = r
        elif ftype == "pdf":
            r = preview_pdf(path)
            base["preview"] = r
        elif ftype == "csv":
            with open(path, "r", encoding="utf-8-sig", newline="", errors="replace") as f:
                reader = csv.reader(f)
                rows = []
                total = 0
                for row in reader:
                    total += 1
                    if len(rows) < args.rows:
                        rows.append([clamp(c, MAX_CELL_LEN) for c in row])
            base["preview"] = {"total_rows": total, "preview_rows": len(rows), "data": rows}
        elif ftype == "image":
            base["preview"] = preview_image(path)
            note.append("图片内容需要 AI 的视觉能力查看；此处为文件元信息")
        elif ftype == "old-office":
            base["preview"] = {"error": ".xls/.ppt 是旧版 Office 二进制格式，需先转成 .xlsx/.pptx 或让 AI 用系统的 Office 工具转换后再预览"}
        else:
            r = read_text_auto(path, args.max_lines)
            base["preview"] = {"text": [clamp(x) for x in r["lines"]],
                               "total_lines": r["total_lines"],
                               "truncated": r["truncated"]}
    except Exception as e:
        base["ok"] = False
        base["error"] = "%s: %s" % (type(e).__name__, e)

    if note:
        base["note"] = note
    print(json.dumps(base, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
