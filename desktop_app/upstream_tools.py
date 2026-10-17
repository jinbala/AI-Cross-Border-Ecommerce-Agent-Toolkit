"""Desktop adapters for upstream video timing and review statistics.

Only fixed bundled modules are loaded. Files are read after native selection;
input tables are normalized in a temporary directory, never rewritten in place.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import math
from pathlib import Path
import re
import tempfile

from desktop_app import core

LIMIT = 3_000_000
HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:['’\-][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*")
FIXABLE = "误解型,参数不符合预期,配件缺失,使用困难"
REVIEW_TEMPLATE = "评分,归因,带图,评论\n5,,是,版型合适\n2,误解型,否,尺码说明看错了\n1,产品质量问题,是,收到后发现开线\n"
POINTS_TEMPLATE = "卖点,频次,强度\n版型合适,5,强\n面料舒适,3,中\n"


def module(name):
    locations = {"video": ("05_Product_Video_Agent", "video_timing.py"),
                 "reviews": ("07_Review_Analysis_Agent", "review_stats.py")}
    folder, script = locations[name]
    path = core.ROOT / "Agents" / folder / "scripts" / script
    if not path.is_file():
        raise ValueError("上游计算组件缺失，请使用重新完整打包的桌面版。")
    spec = importlib.util.spec_from_file_location("desktop_upstream_" + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def string(value, label, limit=LIMIT):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(label + "格式不正确或资料过大，请分批处理。")
    return value.strip().lstrip("\ufeff")


def read_file(path, kind):
    path = Path(path)
    if path.suffix.lower() not in ((".txt",) if kind == "video" else (".csv", ".tsv")):
        raise ValueError("请选择 TXT 配音稿。" if kind == "video" else "请选择 CSV 或 TSV 表格。")
    if path.stat().st_size > LIMIT:
        raise ValueError("请使用 3 MB 以内的文件。")
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return dict(text=data.decode(encoding), name=path.name)
        except UnicodeDecodeError:
            pass
    raise ValueError("文件编码无法识别，请另存为 UTF-8 文本。")


def numeric(value, fallback, label, minimum, maximum, integer=False):
    if value in (None, ""):
        value = fallback
    result = core.number(value, label, integer=integer)
    if not minimum <= result <= maximum:
        raise ValueError(f"{label}需在 {minimum}—{maximum} 之间。")
    return float(result)


def video_report(args):
    script = string(args.get("script", ""), "配音稿", 200000)
    lines = [(i, line.strip()) for i, line in enumerate(script.splitlines(), 1) if line.strip() and not line.lstrip().startswith("#")]
    if not lines or len(lines) > 1000:
        raise ValueError("请粘贴有效配音稿，每行一句，最多 1000 句；空行和 # 注释不计。")
    language = args.get("language", "auto")
    if language == "auto":
        language = "zh" if any(HAN.search(line) for _, line in lines) else "words"
    if language not in ("zh", "words"):
        raise ValueError("请选择中文或葡语 / 英语计数方式。")
    rate = numeric(args.get("rate"), 4 if language == "zh" else 2.5, "语速", .1, 30)
    target = numeric(args.get("target"), 30, "目标秒数", 1, 600)
    maximum = int(numeric(args.get("subtitle_max"), 42, "单行字幕上限", 5, 200, integer=True))
    tool = module("video")
    prepared = [(i, " ".join(HAN.findall(line) + LATIN.findall(line))) for i, line in lines] if language == "zh" else lines
    result = tool.analyze(prepared, rate, maximum)
    issues = []
    for row, (_, original) in zip(result["rows"], lines):
        row["text"] = original
        row["subtitle_chars"] = len(original)
        row.pop("flag", None)
        warnings = []
        if len(original) > maximum:
            warnings.append(f"字幕 {len(original)} 字符，超过设定 {maximum} 字符")
        if tool._emoji_hit(original):
            warnings.append("含特殊符号，请检查字幕显示")
        if row["words"] == 0:
            warnings.append("没有可计数的朗读内容，请检查这一句")
        row["warnings"] = warnings
        issues.extend(f"第 {row['index']} 句：{warning}" for warning in warnings)
    if language == "zh":
        if result["rows"][0]["est_seconds"] > 3:
            issues.append("第一句预计超过 3 秒，可考虑精简开场。")
    elif result.get("hook_note"):
        issues.append(result["hook_note"])
    check = tool.target_check(result["total_seconds"], target)
    unit = "朗读单位 / 秒（汉字逐字计数，拉丁词与数字串各计一单位）" if language == "zh" else "词 / 秒（按空格分词）"
    demo = args.get("is_demo") is True
    report = ["# 配音稿时长与字幕校验" + ("（演示）" if demo else ""), "",
              f"预估时长：{result['total_seconds']:.2f} 秒；目标：{target:g} 秒；允许范围：{check['window']}。",
              f"语速：{rate:g} {unit}；字幕上限：{maximum} 字符 / 行。",
              "时长" + ("处于设定范围。" if check["pass"] else "不在设定范围，请调整台词后重新校验。"), "",
              "| 句 | 时间轴 | 计数 | 字幕字符 | 台词 |", "|---|---|---:|---:|---|"]
    for row in result["rows"]:
        report.append(f"| {row['index']} | {row['timeline']} | {row['words']} | {row['subtitle_chars']} | {row['text'].replace('|', '／')} |")
    report += ["", "## 待检查", *["- " + item for item in issues]] if issues else ["", "未发现超过所设字幕长度的行或开场提醒。"]
    report += ["", "这是按文字和语速假设估算的时长，不是实际音频测量；请按真实配音回听核对。中文混合外语、数字和停顿会影响实际时长。"]
    return dict(kind="video", is_demo=demo, language=language, rate=rate, unit=unit, target=target,
                total_seconds=result["total_seconds"], target_pass=check["pass"], window=check["window"],
                rows=result["rows"], issues=issues, report="\n".join(report))


def table(raw, label):
    raw = string(raw, label)
    if not raw:
        raise ValueError("请先粘贴或选择" + label + "。")
    first = raw.splitlines()[0]
    delimiter = "\t" if "\t" in first else ";" if ";" in first and "," not in first else ","
    try:
        reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
        if not reader.fieldnames or len(reader.fieldnames) > 100:
            raise ValueError(label + "表头缺失或列数过多。")
        fields = [name.strip() for name in reader.fieldnames]
        if len(set(fields)) != len(fields):
            raise ValueError(label + "有重复列名，请修改表头后重试。")
        reader.fieldnames = fields
        rows = []
        for row in reader:
            if len(rows) >= 50000:
                raise ValueError(label + "最多处理 50000 行，请分批处理。")
            if None in row:
                raise ValueError(label + "存在多余分隔符，请按 CSV 规范给含逗号的单元格加引号。")
            rows.append(row)
    except csv.Error as error:
        raise ValueError(label + "格式无法读取，请检查分隔符及单元格长度。") from error
    if not rows:
        raise ValueError(label + "没有数据行。")
    return fields, rows


def column(fields, aliases, label, required=False):
    found = next((key for key in aliases if key in fields), None)
    if required and not found:
        raise ValueError("缺少" + label + "列，可用列名：" + "、".join(aliases))
    return found


def write_table(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def review_report(args):
    tool = module("reviews")
    fields, rows = table(args.get("reviews_text", ""), "评论表")
    rating = column(fields, tool.RATING_COLS, "评分", True)
    category = column(fields, tool.CATEGORY_COLS, "归因")
    image = column(fields, tool.IMAGE_COLS, "带图")
    fixable_raw = string(args.get("fixable", FIXABLE), "可改进归因", 2000)
    fixable = set(filter(None, (part.strip() for part in re.split(r"[,，;；\n]", fixable_raw))))
    clean = []
    for row in rows:
        score = tool._num(row.get(rating), default=None)
        valid = score is not None and math.isfinite(score) and score.is_integer() and 1 <= score <= 5
        clean.append(dict(rating=str(int(score)) if valid else "", category=(row.get(category) or "").strip() if category else "", has_image=row.get(image, "") if image else ""))
    points_input = string(args.get("points_text", ""), "卖点表")
    point_rows = []
    if points_input:
        point_fields, points = table(points_input, "卖点表")
        name = column(point_fields, tool.POINT_COLS, "卖点", True)
        frequency = column(point_fields, tool.FREQ_COLS, "频次", True)
        strength = column(point_fields, tool.STRENGTH_COLS, "强度", True)
        for row in points:
            count = tool._num(row.get(frequency), default=None)
            if count is None or not math.isfinite(count) or count < 0 or not count.is_integer():
                raise ValueError("卖点频次需为非负整数，不能缺失或使用区间。")
            level = (row.get(strength) or "").strip()
            if level not in tool.WEIGHT or not (row.get(name) or "").strip():
                raise ValueError("卖点名称不能为空，强度请填写强、中或弱。")
            point_rows.append(dict(point=row[name].strip(), frequency=str(int(count)), strength=level))
    with tempfile.TemporaryDirectory(prefix="garment-review-") as folder:
        path = Path(folder) / "reviews.csv"
        write_table(path, clean, ["rating", "category", "has_image"])
        result = tool.analyze_reviews(str(path), fixable)
        points = None
        if point_rows:
            path = Path(folder) / "points.csv"
            write_table(path, point_rows, ["point", "frequency", "strength"])
            points = tool.analyze_points(str(path))
    valid_count = result["total"] - result["unrated"]
    warnings = []
    if result["unrated"]:
        warnings.append(f"{result['unrated']} 行评分缺失或不是 1—5 的整数，已剔出评分占比计算。")
    if result["unattributed"]:
        warnings.append(f"{len(result['unattributed'])} 条差评缺少归因，分类合计不完整，请补齐后再判断改进比例。")
    if not category:
        warnings.append("没有归因列；本工具只统计已有分类，不自动理解或分类评论。")
    if not valid_count:
        warnings.append("没有有效评分，无法计算好中差评占比。")
    demo = args.get("is_demo") is True
    report = ["# 评论统计与卖点排行" + ("（演示）" if demo else ""), "",
              f"原表 {result['total']} 行；有效评分 {valid_count} 行；无效 / 缺失评分 {result['unrated']} 行。",
              f"好评 {result['good']} 条，中评 {result['mid']} 条，差评 {result['bad']} 条。",
              "评分占比仅以有效评分为分母；不自动分类评论，也不将未知评分补为差评。", "",
              "## 差评归因", "| 归因 | 条数 | 占差评比 | 设为可通过说明改进 |", "|---|---:|---:|---|"]
    for key, count in result["attribution"].items():
        report.append(f"| {key.replace('|', '／')} | {count} | {count / result['bad']:.1%} | {'是' if key in fixable else '否'} |")
    if not result["bad"]:
        report.append("本次有效评分中没有差评。")
    elif not result["attribution"]:
        report.append("差评尚未归因。")
    report += ["", f"已标记可通过说明改进：{result['fixable_count']} 条；归因未覆盖：{len(result['unattributed'])} 条。",
               "“可改进”依据你填写的分类口径，不表示问题已经解决，也不替代质量和售后核实。"]
    if points:
        report += ["", "## 卖点排行", "| 排名 | 卖点 | 频次 | 强度 | 综合分 |", "|---|---|---:|---|---:|"]
        report += [f"| {row['rank']} | {row['point'].replace('|', '／')} | {row['freq']} | {row['strength']} | {row['score']} |" for row in points["rows"]]
        report += ["卖点频次由输入表提供；此处按频次 × 情感权重排序，不从评论自动提取频次。"]
    if warnings:
        report += ["", "## 资料待补", *["- " + item for item in warnings]]
    return dict(kind="reviews", is_demo=demo, reviews=result, valid_count=valid_count,
                points=points, warnings=warnings, report="\n".join(report))


def example(kind):
    if kind == "video":
        return dict(script="# 服装配音稿演示，内容虚构\n这是一条高腰直筒牛仔裤。\n裤腿宽松，搭配短款上衣展示日常穿搭。\n选购前请按实测尺码表核对腰围和裤长。", language="zh", rate="4", target="30", subtitle_max="42", is_demo=True)
    if kind == "reviews":
        return dict(reviews_text=REVIEW_TEMPLATE, points_text=POINTS_TEMPLATE, fixable=FIXABLE, is_demo=True)
    raise ValueError("请选择视频校验或评论统计。")
