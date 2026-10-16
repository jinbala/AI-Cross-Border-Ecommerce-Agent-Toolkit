"""Evidence-based candidate screening from manually exported data.

SellerSprite's public selection methods are adapted as editable filters, not as
profit predictions. Missing values remain unknown and never become zero.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import hashlib
from pathlib import Path
import re
import urllib.parse
import uuid

from . import core, tabular

SOURCE_URL = "https://www.sellersprite.com/v3/knowledge/article/26-method-of-select-product"
GUIDE = "docs/06_Selection_Practice.md"

# (field, operator, user-facing label, editable initial threshold)
STRATEGIES = {
    "factory_upgrade": dict(name="工厂改进机会", kind="产品", purpose="从有需求、评价偏低的产品里寻找面料、版型、尺码或做工改进点。",
        rules=[("monthly_sales", ">=", "月销量至少", 1000), ("rating", "<=", "评分至多（5 分制）", 3.7)],
        next="读取低星评论原文，区分产品缺陷、尺码误解与履约问题；打样验证工厂确实能解决哪些问题。"),
    "new_product": dict(name="增长中的新品", kind="产品", purpose="观察近期上架且销量在增长的产品，继续核查增长持续性。",
        rules=[("monthly_sales", "<=", "月销量至多", 600), ("sales_growth", ">=", "月销量增长率至少 %", 10), ("age_days", "<=", "上架天数至多", 180)],
        next="核对至少两期销量与库存记录，排除短期活动、断货恢复及季节影响。"),
    "low_reviews": dict(name="新品与评价门槛", kind="产品", purpose="从近期上架、评价积累较少的产品里寻找进一步研究的参照。",
        rules=[("age_days", "<=", "上架天数至多", 90), ("review_count", "<=", "评价数量至多", 50)],
        next="评价少可能也代表没有需求；补充销量、流量、投放成本和真实售价。此筛选不判断是否进入榜单。"),
    "content_gap": dict(name="商品页面改进空间", kind="产品", purpose="观察有销量但页面质量分偏低的产品，复核信息表达是否存在缺口。",
        rules=[("monthly_sales", ">=", "月销量至少", 1000), ("lqs", "<=", "LQS 至多（10 分制）", 5)],
        next="人工检查尺寸图、实拍细节、面料说明与洗护信息；LQS 低不代表市场竞争低。"),
    "long_tail": dict(name="长尾需求线索", kind="关键词", purpose="用较具体的词组寻找细分人群、服装场景或版型需求。",
        rules=[("word_count", ">=", "词组单词数至少", 3), ("search_volume", ">=", "月搜索量至少", 1)],
        next="核对搜索结果是否匹配你的服装品类和工艺；单词数仅是分词线索，不保证精准转化。"),
    "low_click_share": dict(name="点击分布较分散", kind="关键词", purpose="观察头部点击占比较低的关键词市场，继续核查品牌和卖家壁垒。",
        rules=[("click_share", "<=", "前三商品点击集中度至多 %", 50), ("search_volume", ">=", "月搜索量至少", 1)],
        next="点击集中度、销售额集中度和卖家集中度是不同口径；继续核对实际销售与竞争结构。"),
    "rising_search": dict(name="搜索排名增长线索", kind="关键词", purpose="从指定搜索排名区间及近一周排名增长数据中寻找需求线索。",
        rules=[("search_rank", ">=", "搜索排名下限", 10000), ("search_rank", "<=", "搜索排名上限", 100000), ("rank_growth_week", ">=", "近一周排名增长率至少 %", 10)],
        next="排名数值越小通常越靠前；这里直接使用数据源提供的排名增长率，不把排名变化当搜索量增长。"),
    "traffic_cost": dict(name="点击成本与货值", kind="关键词", purpose="比较单次点击价格占商品均价的比例，作为引流成本的初筛线索。",
        rules=[("traffic_ratio", "<=", "PPC / 商品均价至多 %", 5)],
        next="该比例不是 ACoS。需要实际转化率和广告前贡献才能核算可承受 CPC，且 PPC 与均价必须同币种。"),
    "manual_lead": dict(name="先收集，待调研", kind="线索", purpose="先记下想研究的款式或商品链接，有资料后再验证。", rules=[],
        next="核实商品实际信息、数据来源与市场，再补充销量、评价、工厂成本及小批量验证计划。"),
}
FILTER_KEYS = tuple(key for key in STRATEGIES if key != "manual_lead")

FIELD_ALIASES = {
    "source_id": ["ASIN", "商品ID", "产品ID", "商品编号", "product id", "SKU", "款号"],
    "parent_id": ["父ASIN", "parent asin"],
    "title": ["标题", "商品标题", "产品标题", "商品名称", "产品名称", "title", "product name", "款式名称", "款名", "名称"],
    "monthly_sales": ["月销量", "月销量(父)", "月销量（父）", "父体月销量", "monthly sales", "sales"],
    "price": ["价格", "售价", "price"],
    "sales_growth": ["月销量增长率", "销量增长率", "monthly sales growth", "sales growth"],
    "rating": ["评分", "评分值", "rating"],
    "review_count": ["评分数", "评价数", "评论数", "ratings", "review count", "reviews"],
    "age_days": ["上架天数", "上架时长(天)", "listing age days", "age days"],
    "listing_date": ["上架日期", "上架时间", "date first available", "listing date"],
    "lqs": ["LQS", "Listing质量得分", "listing quality score"],
    "keyword": ["关键词", "搜索词", "keyword", "search term"],
    "search_volume": ["月搜索量", "monthly searches", "search volume"],
    "word_count": ["单词数", "单词个数", "word count"],
    "click_share": ["点击集中度", "前三商品点击集中度", "top 3 click share", "click concentration"],
    "search_rank": ["搜索排名", "搜索频率排名", "search rank", "search frequency rank"],
    "rank_growth_week": ["近1周排名增长率", "近一周排名增长率", "搜索排名增长率(近1周)", "weekly rank growth"],
    "ppc": ["PPC", "PPC竞价", "建议竞价", "CPC", "bid"],
    "average_price": ["商品均价", "平均价格", "average price"],
}
NUMERIC = set(FIELD_ALIASES) - {"source_id", "parent_id", "title", "keyword", "listing_date"}
LABELS = {k: values[0] for k, values in FIELD_ALIASES.items()}
LABELS["traffic_ratio"] = "PPC / 商品均价 %"


def norm(value):
    return re.sub(r"[\s_（）()\[\]%％:：\-]", "", str(value)).lower()


def metric(value, label="数据", allow_negative=False, integer=False):
    if value is None or str(value).strip().lower() in ("", "-", "--", "n/a", "na", "null", "none", "暂无", "无"):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label}不应是布尔值。")
    had_percent = "%" in str(value) or "％" in str(value)
    s = str(value).strip().replace("%", "").replace("％", "")
    s = re.sub(r"(?i)(R\$|BRL|USD|CNY|RMB|EUR|MXN|\$|¥|￥|€|元)", "", s).replace(" ", "")
    multiplier = Decimal(1)
    for suffix, scale in [("万", 10000), ("亿", 100000000), ("k", 1000), ("K", 1000)]:
        if s.endswith(suffix):
            multiplier = Decimal(scale)
            s = s[:-len(suffix)]
            break
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + "." + tail if len(tail) in (1, 2) or had_percent else s.replace(",", "")
    elif multiplier == 1 and (integer or s.count(".") > 1) and re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        result = Decimal(s) * multiplier
    except InvalidOperation:
        raise ValueError(f"{label}无法识别为数字：{str(value)[:40]}") from None
    if not result.is_finite() or abs(result) > Decimal("1000000000000") or (result < 0 and not allow_negative):
        raise ValueError(f"{label}含有负数、非有限数或超大数值。")
    return float(result)


def read_csv(path, *, as_of, platform, market, currency, partial=False):
    path = Path(path)
    rows, sheet = tabular.read_file(path, FIELD_ALIASES)
    data = from_rows(rows, as_of=as_of, platform=platform, market=market, currency=currency,
                     source_name=path.name, digest=hashlib.sha256(path.read_bytes()).hexdigest(), partial=partial)
    data["meta"]["sheet"] = sheet
    return data


def from_rows(rows, *, as_of, platform, market, currency, source_name, digest, partial=False):
    try:
        stamp = date.fromisoformat(as_of) if as_of else None
    except (ValueError, TypeError):
        raise ValueError("数据日期请使用 YYYY-MM-DD 格式。") from None
    if not partial and (stamp is None or not all(str(v).strip() for v in (platform, market, currency))):
        raise ValueError("请填写数据所属平台、市场与币种。")
    if not rows:
        raise ValueError("导入表没有数据行。")
    if len(rows) > 10000:
        raise ValueError("单次最多导入 10000 行，请先按类目拆分。")
    headers = {norm(h): h for h in rows[0] if h is not None}
    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if norm(alias) in headers:
                mapping[field] = headers[norm(alias)]
                break
    if not any(k in mapping for k in ("source_id", "title", "keyword")):
        raise ValueError("未识别 ASIN、标题或关键词。请先导出软件中的空白模板并对照表头。")
    records, seen, duplicates = [], set(), 0
    integer_fields = {"monthly_sales", "review_count", "age_days", "search_volume", "word_count", "search_rank"}
    for i, row in enumerate(rows, 2):
        record = {field: (row.get(header) or "").strip() for field, header in mapping.items() if field not in NUMERIC}
        for field in NUMERIC:
            try:
                value = metric(row.get(mapping[field]), LABELS[field], allow_negative=field in ("sales_growth", "rank_growth_week"), integer=field in integer_fields) if field in mapping else None
                if value is not None and field in integer_fields and value != int(value):
                    raise ValueError(f"{LABELS[field]}应为整数。")
                if value is not None and field in {"rating", "lqs", "click_share"}:
                    cap = {"rating": 5, "lqs": 10, "click_share": 100}[field]
                    if value > cap:
                        raise ValueError(f"{LABELS[field]}不能超过 {cap}。")
                record[field] = value
            except ValueError as error:
                raise ValueError(f"第 {i} 行：{error}") from None
        if record.get("listing_date"):
            try:
                listed = date.fromisoformat(record["listing_date"].replace("/", "-")[:10])
                age = (stamp - listed).days if stamp else None
            except ValueError:
                raise ValueError(f"第 {i} 行上架日期无效，请使用 YYYY-MM-DD。") from None
            if age is not None and age < 0:
                raise ValueError(f"第 {i} 行上架日期晚于数据日期。")
            if record.get("age_days") is None and age is not None:
                record["age_days"] = age
            elif age is not None and abs(record["age_days"] - age) > 1:
                raise ValueError(f"第 {i} 行上架天数与日期不一致，请核对。")
        keyword = record.get("keyword", "")
        if record.get("word_count") is None and keyword and re.fullmatch(r"[A-Za-zÀ-ÿ0-9\s'’\-]+", keyword):
            record["word_count"] = len(keyword.split())
        average = record.get("average_price")
        record["traffic_ratio"] = record["ppc"] / average * 100 if average and record.get("ppc") is not None else None
        identity = record.get("source_id") or keyword.casefold()
        if identity and identity in seen:
            duplicates += 1
            continue
        if identity:
            seen.add(identity)
        record["source_row"] = i
        records.append(record)
    if not records:
        raise ValueError("没有可筛选的候选行。")
    return dict(records=records, meta=dict(file=source_name, digest=digest, date=as_of, platform=platform.strip(), market=market.strip(),
                currency=currency.strip(), row_count=len(rows), kept=len(records), duplicates=duplicates, columns=mapping))


def suggested_strategy(dataset):
    fields = set(dataset["meta"]["columns"])
    for strategy, needed in [("factory_upgrade", {"monthly_sales", "rating"}),
                             ("new_product", {"monthly_sales", "sales_growth"}),
                             ("low_click_share", {"keyword", "click_share"}),
                             ("traffic_cost", {"ppc", "average_price"}),
                             ("long_tail", {"keyword", "search_volume"}),
                             ("low_reviews", {"review_count", "age_days"}),
                             ("content_gap", {"monthly_sales", "lqs"})]:
        if needed <= fields:
            return strategy
    return "manual_lead"


def prepare_text(text, *, as_of="", platform="", market="", currency=""):
    text = text.strip()
    if not text:
        raise ValueError("先粘贴一段表格、商品链接，或输入想研究的款式名称。")
    if len(text.encode("utf-8")) > 3_000_000:
        raise ValueError("内容较大，请分批整理。")
    try:
        rows = tabular.pasted_rows(text, FIELD_ALIASES)
    except ValueError:
        if "\t" in text:
            raise ValueError("复制表格时请带上列名，例如 ASIN、标题、月销量或评分；不必改成软件模板。") from None
        rows = None
    if rows is not None:
        dataset = from_rows(rows, as_of=as_of, platform=platform, market=market, currency=currency,
                            source_name="粘贴表格", digest=hashlib.sha256(text.encode()).hexdigest(), partial=True)
        return screen(dataset, suggested_strategy(dataset))
    records, seen = [], set()
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]+|\d+[、.)])\s*", "", line).strip()
        if not line:
            continue
        urls = re.findall(r"https?://[^\s<>\"，。]+", line)
        entries = urls or [line]
        for value in entries:
            url, asin, inferred = "", "", ""
            name = value
            if urls:
                try:
                    parsed = urllib.parse.urlsplit(value.rstrip(".,;；)）"))
                    host = (parsed.hostname or "").lower()
                    if not host or parsed.username or parsed.password:
                        raise ValueError("商品链接不应包含账号或密码。")
                    query = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if k in ("goods_id", "item_id", "id", "sku")])
                    url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
                    amazon = any(host == "amazon." + suffix or host.endswith(".amazon." + suffix) for suffix in ("com", "co.uk", "de", "fr", "it", "es", "co.jp", "ca", "com.au", "com.br", "com.mx", "in"))
                    match = re.search(r"/(?:dp|gp/product)/([A-Za-z0-9]{10})(?:[/ ?]|$)", parsed.path) if amazon else None
                    asin = match.group(1).upper() if match else ""
                    inferred = "Amazon" if amazon else "Temu 全托管" if host in ("temu.com", "www.temu.com") else ""
                    if inferred == "Temu 全托管":
                        inferred = "Temu（模式待确认）"
                    note = re.sub(r"https?://[^\s<>\"，。]+", "", line[:line.find(value)]).strip(" ：:-/")
                    name = note or f"链接线索 · {asin or host}"
                except ValueError as error:
                    raise ValueError(f"链接格式需要核对：{error}") from None
            elif re.fullmatch(r"B0[A-Za-z0-9]{8}", value, re.IGNORECASE):
                asin, inferred = value.upper(), "Amazon"
                name = f"ASIN 线索 · {asin}"
            identity = "Amazon:" + asin if asin else url or " ".join(name.casefold().split())
            if identity in seen:
                continue
            seen.add(identity)
            record = {k: None for k in NUMERIC}
            record.update(title=name[:500], source_id=asin, source_url=url, source_platform=inferred,
                          source_row=len(records) + 1, user_note=(note if urls else line)[:2000], traffic_ratio=None)
            records.append(record)
            if len(records) > 1000:
                raise ValueError("一次最多收集 1000 条线索，请分批整理。")
    if not records:
        raise ValueError("没有识别到可保存的内容。")
    dataset = dict(records=records, meta=dict(file="手工收集", digest=hashlib.sha256(text.encode()).hexdigest(), date=as_of,
        platform=platform, market=market, currency=currency, row_count=len(records), kept=len(records), duplicates=0, columns={}))
    return screen(dataset, "manual_lead")


def candidate_id(item):
    if item["strategy"] == "manual_lead":
        is_asin = item["source_id"] and (item["evidence"].get("source_platform") == "Amazon" or item.get("source_columns", {}).get("source_id", "").upper() == "ASIN")
        identity = "Amazon:" + item["source_id"] if is_asin else item["evidence"].get("source_url") or item["source_id"] or " ".join(item["name"].casefold().split())
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "garment-lead:" + identity))
    identity = item["source_id"] or item["evidence"].get("keyword") or item["source_file"] + str(item["evidence"]["source_row"])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps([item[k] for k in ("platform", "market", "currency", "as_of", "strategy", "source_digest")] + [identity, item["thresholds"]], ensure_ascii=False, sort_keys=True)))


def persist(store, screening):
    prepared = []
    for result in screening["results"]:
        item = candidate(screening, result)
        record_id = candidate_id(item)
        old = store.get(record_id)
        if old:
            item["review_status"] = old.get("review_status", "待复核")
        prepared.append((record_id, item))
    store.save_batch("candidate", prepared)
    return [record_id for record_id, _ in prepared]


def thresholds(strategy, values=None):
    if strategy not in STRATEGIES:
        raise ValueError("未知选品策略。")
    parsed = {}
    bounds = {}
    for field, op, label, default in STRATEGIES[strategy]["rules"]:
        key = field + op
        value = metric((values or {}).get(key, default), label, allow_negative="growth" in field)
        if value is None:
            raise ValueError(f"请填写「{label}」。")
        if field in ("rating", "lqs", "click_share", "traffic_ratio") and value > {"rating": 5, "lqs": 10, "click_share": 100, "traffic_ratio": 100}[field]:
            raise ValueError(f"「{label}」超过有效范围。")
        parsed[key] = value
        bounds.setdefault(field, {})[op] = value
    for field, limits in bounds.items():
        if limits.get(">=", 0) > limits.get("<=", float("inf")):
            raise ValueError(f"{LABELS[field]}下限不能高于上限。")
    return parsed


def screen(dataset, strategy, values=None):
    limits = thresholds(strategy, values)
    results = []
    for record in dataset["records"]:
        checks, missing, failed = [], [], []
        if strategy == "manual_lead":
            checks.append("已收集研究线索，尚未完成市场和利润验证。")
            missing.append("市场与产品证据")
        for key, name in [("platform", "数据平台"), ("market", "数据市场"), ("currency", "币种"), ("date", "数据日期")]:
            if not dataset["meta"].get(key) or dataset["meta"].get(key) in ("未注明", "待确认"):
                missing.append(name)
                checks.append(f"{name}：待确认")
        for field, op, _, _ in STRATEGIES[strategy]["rules"]:
            expected = limits[field + op]
            actual = record.get(field)
            name = LABELS[field]
            if actual is None:
                checks.append(f"{name}：缺失；需要 {op} {expected:g}")
                missing.append(name)
            else:
                ok = actual >= expected if op == ">=" else actual <= expected
                checks.append(f"{name} {actual:g} {op} {expected:g}：{'符合' if ok else '不符'}")
                if not ok:
                    failed.append(name)
        status = "不符合" if failed else "资料待补" if missing else "符合筛选"
        results.append(dict(record=record, status=status, checks=checks, missing=missing, failed=failed))
    return dict(strategy=strategy, thresholds=limits, meta=dataset["meta"], results=results,
                counts={status: sum(r["status"] == status for r in results) for status in ("符合筛选", "资料待补", "不符合")})


def report(screening):
    strategy = STRATEGIES[screening["strategy"]]
    meta = screening["meta"]
    safe = lambda v: str(v).replace("|", " / ").replace("\n", " ").replace("\r", " ")
    lines = [f"# 选品初筛 · {strategy['name']}", "", f"数据：{meta['platform']} / {meta['market']} / {meta['currency']} / {meta['date']}",
             f"文件：{meta['file']}；原始 {meta['row_count']} 行，保留 {meta['kept']} 行，重复 ID / 关键词 {meta['duplicates']} 行。", "",
             "这是人工导出数据的条件匹配结果，不是选品批准、全市场容量或收益预测。", "",
             "同一 ASIN / 关键词仅保留首行；未自动合并父子变体，不能把父体销量逐行相加当市场总量。", "",
             "导入字段映射：" + "；".join(f"{LABELS.get(k, k)} ← {v}" for k, v in meta["columns"].items()), "",
             "## 本次条件"]
    for field, op, _, _ in strategy["rules"]:
        lines.append(f"- {LABELS[field]} {op} {screening['thresholds'][field + op]:g}")
    lines += ["", "## 匹配结果", "| 候选 | 标识 | 结论 | 依据 |", "|---|---|---|---|"]
    for result in screening["results"]:
        r = result["record"]
        title = r.get("title") or r.get("keyword") or "未命名候选"
        lines.append(f"| {safe(title)} | {safe(r.get('source_id', ''))} | {result['status']} | {safe('；'.join(result['checks']))} |")
    lines += ["", "## 复核动作", strategy["next"], "",
              "服装工厂复核：面料、版型、尺码、工艺、起订量与交期能否满足；实测样衣是否改善问题；供货或零售实际费用是否完整；首批资金是否在预算内。",
              "\n跨平台提示：需要在目标平台重新验证需求。Amazon 导出数据只代表该数据源，不能直接当作 Temu、Shopee 等平台的需求或价格证据。",
              "\n百分比字段无 % 时仍按百分点读取：10 表示 10%，0.1 表示 0.1%；不根据数值大小猜测比例单位。",
              f"\n方法参考：{SOURCE_URL}。软件增加了资料完整性、服装复核和预算检查；参考阈值可修改，边界使用 ≥ / ≤。"]
    return "\n".join(lines)


def candidate(screening, result):
    record = result["record"]
    return dict(name=record.get("title") or record.get("keyword") or "未命名候选", source_id=record.get("source_id", ""),
                strategy=screening["strategy"], status=result["status"], review_status="待复核",
                platform=screening["meta"]["platform"] or record.get("source_platform", "") or "未注明", market=screening["meta"]["market"] or "未注明", currency=screening["meta"]["currency"] or "未注明",
                as_of=screening["meta"]["date"], evidence=record, checks=result["checks"], thresholds=screening["thresholds"],
                source_file=screening["meta"]["file"], source_digest=screening["meta"].get("digest", ""), source_columns=screening["meta"]["columns"])


def review_brief(item):
    strategy = STRATEGIES.get(item["strategy"], STRATEGIES["factory_upgrade"])
    return "\n".join(["# 选品候选人工复核", f"候选：{item['name']}", f"策略：{strategy['name']}",
        f"来源：{item['platform']} / {item['market']} / {item['currency']} / {item['as_of'] or '数据日期待确认'}",
        "导入字段映射：" + "；".join(f"{LABELS.get(k, k)} ← {v}" for k, v in item.get("source_columns", {}).items()),
        f"筛选结论：{item['status']}；复核状态：{item['review_status']}", "\n## 筛选依据", *item["checks"],
        "\n## 原始候选数据", "```json", json.dumps(item["evidence"], ensure_ascii=False, indent=2), "```",
        "\n## 请执行", strategy["next"],
        "1. 将已有证据、缺失证据、假设分开列出；不把条件匹配当作可盈利或已获选品批准。",
        "2. 对照本厂面料、尺码、工艺、交期和起订量；工厂资料未提供时先列缺项。",
        "3. 请求真实成本、目标平台费用和首批数量，再核算利润与试错预算，不把竞品售价当我方收入。",
        "4. Amazon 与目标销售平台不同，必须补充目标平台证据。",
        "5. 输出需要人验证的样衣检查、市场检查和小批量试验清单，不替人批准采购或生产。"])
