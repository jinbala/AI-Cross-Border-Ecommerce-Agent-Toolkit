"""JSON-over-stdin service used by the unified WebView2 desktop host.

One request per process; no listening port, shell commands or browser sessions.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from desktop_app import core, selection

MAX_REQUEST = 12_000_000


def text(value, limit=4000):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("文字字段格式或长度不正确。")
    return value.strip()


def safe_url(value):
    raw = text(value)
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("商品链接格式需要核对。")
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query) if k in ("id", "item_id", "goods_id", "sku")])
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def object_value(value):
    if not isinstance(value, dict):
        raise ValueError("资料应为对象。")
    return value


def record(store, record_id, kind):
    item = store.get(text(record_id, 200))
    row = store.connection.execute("SELECT kind FROM records WHERE id=?", (record_id,)).fetchone()
    if not item or not row or row[0] != kind:
        raise ValueError("记录不存在或类型不匹配，请刷新列表。")
    return item


def source_note(item):
    evidence = item.get("evidence", {})
    lines = ["资料性质：演示（虚构，仅供试用）" if evidence.get("is_demo") else "资料性质：来源观察，实际经营需另行核实。",
             f"来源平台：{item.get('platform', '未注明')}", f"来源商品 ID：{item.get('source_id', '')}"]
    if evidence.get("source_url"):
        lines.append("商品链接：" + evidence["source_url"])
    observations = evidence.get("observations", [])
    for observation in observations[-10:]:
        lines += ["", f"来源账号：{observation.get('identity', '')}",
                  f"统计周期：{observation.get('period', '')}",
                  f"来源类目：{' / '.join(observation.get('category_path', []))}",
                  f"查询价位：{observation.get('price_query', '')}；榜内排名：{observation.get('rank', '')}",
                  f"页面价格带：{observation.get('price_band', '')}"]
        lines += [f"{key}：{value}" for key, value in observation.get("metrics", {}).items()]
    lines += ["", "以上为来源观察，不是本厂报价。价格带不代表实际 SKU 最低价，成交区间不能当作精确月销量。"]
    if len(observations) > 10:
        lines.append(f"共保留 {len(observations)} 条来源观察，这里显示最近 10 条；完整记录保存在候选资料与备份中。")
    return "\n".join(lines)[:24000]


def import_compass(store, args):
    group, meta = object_value(args.get("group")), object_value(args.get("meta"))
    product = object_value(group.get("product"))
    product_id = text(product.get("id"), 200)
    if not product_id or not text(product.get("name"), 500):
        raise ValueError("缺少原始文本商品 ID 或商品名称。")
    source_type = text(meta.get("source_type"), 100)
    if source_type != "product_ranking":
        raise ValueError("当前建档入口仅接受商品榜，图文资料可先保存任务包。")
    stamp = text(meta.get("ranking_date"), 10)
    date.fromisoformat(stamp)
    observations = group.get("observations", [])
    if not isinstance(observations, list) or not 1 <= len(observations) <= 500:
        raise ValueError("缺少可核对的商品榜观察记录。")
    identity = text(meta.get("observed_identity"), 300)
    period = text(meta.get("period"), 500)
    demo = meta.get("is_demo") is True
    if not demo and (not identity or not period):
        raise ValueError("真实榜单需要来源账号和实际统计周期。")
    incoming = []
    metric_labels = {"payment_amount": "用户支付金额（来源区间）", "transaction_amount": "成交金额（来源区间）",
                     "sales_count": "成交件数（来源区间）", "clicks": "点击次数（来源区间）", "click_conversion_rate": "点击成交转化率（来源区间）"}
    for observation in observations:
        object_value(observation)
        if observation.get("ranking_date") != stamp or str(object_value(observation.get("product")).get("id")) != product_id:
            raise ValueError("商品 ID 或统计日期不一致，未保存。")
        rank = observation.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 1_000_000:
            raise ValueError("榜内排名缺失或格式不正确。")
        path = observation.get("category_path")
        if not isinstance(path, list) or not path or len(path) > 12:
            raise ValueError("来源类目格式不正确。")
        metrics = object_value(observation.get("metrics", {}))
        source_filters = object_value(observation.get("source_filters", {}))
        observed_product = object_value(observation.get("product"))
        entry = dict(identity=identity, period=period, date=stamp, rank=rank,
                     category_path=[text(p, 200) for p in path],
                     price_query=text(source_filters.get("price_band_label") or source_filters.get("price_band") or "不限价格", 300),
                     price_band=text(observed_product.get("price_band_display") or observed_product.get("price_display"), 300),
                     metrics={label: text(str(metrics[key]), 300) for key, label in metric_labels.items() if metrics.get(key) is not None},
                     is_demo=demo)
        incoming.append(entry)
    record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"garment-compass:{'demo' if demo else 'real'}:{product_id}"))
    old = store.get(record_id)
    merged = {json.dumps(x, sort_keys=True, ensure_ascii=False): x for x in (old or {}).get("evidence", {}).get("observations", []) + incoming}
    if len(merged) > 1000:
        raise ValueError("该款的历史观察超过 1000 条，请先导出存档。")
    apparel = object_value(product.get("apparel", {}))
    item = dict(name=text(product["name"], 500), source_id=product_id, platform="抖音 / 罗盘", market="中国", currency="CNY",
                as_of=stamp, strategy="manual_lead", status="资料待补", review_status=(old or {}).get("review_status", "待复核"),
                source_file="罗盘商品榜" + ("（演示）" if demo else ""),
                source_digest=hashlib.sha256(json.dumps(incoming, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                source_columns={}, thresholds={},
                evidence=dict(source_url=safe_url(product.get("link")), source_platform="抖音 / 罗盘", shop=text(product.get("shop"), 500),
                              apparel={k: text(apparel.get(k), 500) for k in ("gender", "type", "fit", "fabric", "season", "sizes")},
                              is_demo=demo, observations=list(merged.values())),
                checks=["演示数据，仅用于试用。" if demo else "保留来源统计周期和实际采集范围。", "罗盘价格带不是本厂供货报价；补充生产成本和目标渠道费用后再核算。"])
    if old and old.get("product_id"):
        item["product_id"] = old["product_id"]
    store.save("candidate", item, record_id)
    return dict(candidate_id=record_id, candidate=store.get(record_id))


def public_settings(store):
    return dict(api_base=store.setting("api_base", ""), api_model=store.setting("api_model", ""),
                has_key=bool(store.setting("api_key", "")), monthly_budget=store.setting("monthly_budget", 3000))


def dispatch(store, command, args):
    object_value(args)
    if command == "state":
        return dict(version="2.0.0", products=store.list("product"), candidates=store.list("candidate"),
                    artifacts=store.list("artifact"), experiments=store.list("experiment"), settings=public_settings(store),
                    fields=core.PRODUCT_FIELDS + core.LONG_FIELDS, modules=[m[1] for m in core.MODULES], platforms=core.PLATFORMS,
                    strategies={key: selection.STRATEGIES[key] for key in selection.FILTER_KEYS})
    if command == "import_compass":
        return import_compass(store, args)
    if command == "create_product":
        source = record(store, args.get("candidate_id"), "candidate")
        product_id = source.get("product_id") or str(uuid.uuid5(uuid.NAMESPACE_URL, "garment-product:" + source["id"]))
        old = store.get(product_id)
        if old:
            return old
        apparel = source.get("evidence", {}).get("apparel", {})
        product = {key: "" for key, _ in core.PRODUCT_FIELDS + core.LONG_FIELDS}
        product.update(name=source["name"], category=apparel.get("type", ""), fabric=apparel.get("fabric", ""),
                       sizes=apparel.get("sizes", ""), notes=source_note(source), candidate_id=source["id"], is_demo=bool(source.get("evidence", {}).get("is_demo")))
        store.save("product", product, product_id)
        source["product_id"] = product_id
        store.save("candidate", source, source["id"])
        return store.get(product_id)
    if command == "save_product":
        value = object_value(args.get("product"))
        result = {key: text(value.get(key), 30000 if key in dict(core.LONG_FIELDS) else 2000) for key, _ in core.PRODUCT_FIELDS + core.LONG_FIELDS}
        if not result["name"]:
            raise ValueError("请填写款式名称。")
        for field in ("cost", "supply_price", "retail_price"):
            if result[field]:
                core.number(result[field], dict(core.PRODUCT_FIELDS)[field])
        record_id = value.get("id")
        if record_id:
            old = record(store, record_id, "product")
            if old.get("candidate_id"):
                result["candidate_id"] = old["candidate_id"]
            result["is_demo"] = bool(old.get("is_demo"))
        return store.get(store.save("product", result, record_id))
    if command == "intake" or command == "import_file":
        scope = {key: text(args.get(key), 100) for key in ("platform", "market", "currency", "as_of")}
        if command == "intake":
            screening = selection.prepare_text(text(args.get("text"), 3_000_000), **scope)
            dataset = dict(records=[x["record"] for x in screening["results"]], meta=screening["meta"])
        else:
            path = Path(text(args.get("path")))
            if path.suffix.lower() not in (".xlsx", ".csv", ".tsv"):
                raise ValueError("请选择 Excel、CSV 或 TSV 选品表。")
            dataset = selection.read_csv(path, partial=True, **scope)
            screening = selection.screen(dataset, selection.suggested_strategy(dataset))
        strategy = args.get("strategy")
        if strategy:
            screening = selection.screen(dataset, strategy, args.get("thresholds") or None)
        ids = selection.persist(store, screening)
        return dict(ids=ids, counts=screening["counts"], report=selection.report(screening))
    if command == "review_candidate":
        item = record(store, args.get("id"), "candidate")
        review = args.get("status")
        if review not in ("待复核", "已验证", "放弃"):
            raise ValueError("复核状态不正确。")
        item["review_status"] = review
        store.save("candidate", item, item["id"])
        return item
    if command == "candidate_brief":
        item = record(store, args.get("id"), "candidate")
        return dict(brief=selection.review_brief(item) + "\n\n" + source_note(item))
    if command == "pricing":
        values = object_value(args.get("values"))
        product = record(store, args["product_id"], "product") if args.get("product_id") else None
        result = core.calculate_pricing(values)
        report = core.pricing_report(values, result)
        if product:
            report = ("演示款测算（仅供试用）\n" if product.get("is_demo") else "") + f"产品：{product['name']} · 款号：{product.get('sku', '')}\n\n" + report
        if args.get("save"):
            if product and values.get("currency", "CNY") == "CNY":
                for key, source in (("cost", "production"), ("retail_price" if values.get("mode") == "自营零售" else "supply_price", "price")):
                    if str(values.get(source, "")).strip():
                        product[key] = str(values[source])
                store.save("product", product, product["id"])
            store.save("artifact", dict(name=("【演示】" if product and product.get("is_demo") else "") + (product['name'] + " · " if product else "") + "利润测算 · " + core.now()[:10], kind="利润报告", content=report))
        return dict(result=result, report=report)
    if command in ("compose", "generate_ai"):
        index = args.get("module", 0)
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(core.MODULES):
            raise ValueError("请选择有效工作流。")
        product = record(store, args["product_id"], "product") if args.get("product_id") else None
        brief = text(args.get("brief"), 500000)
        if product and product.get("is_demo"):
            brief = "演示任务：这是虚构试用资料，不代表真实商品或市场结果。\n" + brief
        prompt = core.workflow_prompt(index, product, text(args.get("platform"), 100), text(args.get("market"), 300), brief)
        if command == "generate_ai":
            result = core.call_ai(store.setting("api_base", ""), core.unprotect_key(store.setting("api_key", "")), store.setting("api_model", ""), prompt)
            store.save("artifact", dict(name=("【演示】" if product and product.get("is_demo") else "") + core.MODULES[index][1] + " · " + core.now()[:10], kind="AI文字成果", content=result))
            return dict(prompt=prompt, content=result)
        return dict(prompt=prompt)
    if command == "save_artifact":
        value = dict(name=text(args.get("name"), 500) or "未命名成果", kind=text(args.get("kind"), 100) or "文字成果", content=text(args.get("content"), 8_000_000))
        if not value["content"]:
            raise ValueError("没有可以保存的正文。")
        if args.get("product_id") and record(store, args["product_id"], "product").get("is_demo"):
            value["name"] = "【演示】" + value["name"]
        return dict(id=store.save("artifact", value))
    if command == "save_experiment":
        value = object_value(args.get("experiment"))
        result = {key: text(value.get(key), 10000) for key in ("name", "channel", "date", "status", "goal", "result", "next")}
        if not result["name"]:
            raise ValueError("请填写试验名称。")
        date.fromisoformat(result["date"])
        for key in ("budget", "spent", "revenue", "hours"):
            result[key] = float(core.number(value.get(key, 0), key))
        if value.get("product_id"):
            product = record(store, value["product_id"], "product")
            result.update(product_id=product["id"], is_demo=bool(product.get("is_demo")))
        else:
            result["is_demo"] = False
        if value.get("id"):
            record(store, value["id"], "experiment")
        return dict(id=store.save("experiment", result, value.get("id")))
    if command == "save_settings":
        base = text(args.get("api_base"), 2000)
        if base:
            core.api_url(base)
        model = text(args.get("api_model"), 300)
        budget = float(core.number(args.get("monthly_budget", 3000), "月度预算"))
        encrypted = core.protect_key(text(args["api_key"], 2000)) if args.get("api_key") and not args.get("clear_key") else None
        store.set_setting("api_base", base)
        store.set_setting("api_model", model)
        store.set_setting("monthly_budget", budget)
        if args.get("clear_key"):
            store.set_setting("api_key", "")
        elif encrypted is not None:
            store.set_setting("api_key", encrypted)
        return public_settings(store)
    if command in ("backup", "restore"):
        path = Path(text(args.get("path")))
        if command == "backup":
            store.backup(path)
            return dict(message="备份已保存，不包含模型密钥。")
        backup = store.folder / ("before-restore-" + uuid.uuid4().hex + ".json")
        store.backup(backup)
        count = store.restore(path)
        return dict(message=f"已合并恢复 {count} 条记录；恢复前的备份保留在经营数据目录。")
    if command == "market_report":
        path = Path(text(args.get("path")))
        if path.stat().st_size > 15_000_000:
            raise ValueError("市场分析请使用 15 MB 以内的表格。")
        return dict(report=core.market_report(path, text(args.get("currency"), 10) or "CNY"))
    if command == "ad_report":
        return dict(report=core.ad_report(object_value(args.get("values"))))
    raise ValueError("不支持的工作台操作。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    store = None
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise ValueError("本次资料过大，请分批处理。")
        payload = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("JSON 不能包含非有限数。")))
        object_value(payload)
        store = core.Store(args.data_dir)
        result = dispatch(store, text(payload.get("command"), 100), payload.get("args", {}))
        response = dict(ok=True, data=result)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        response = dict(ok=False, error=str(error) if isinstance(error, ValueError) else "资料无法处理，请检查文件格式、数据目录与输入字段。")
    except Exception:
        response = dict(ok=False, error="本次操作未完成，请缩小资料后重试。")
    finally:
        if store is not None:
            store.close()
    sys.stdout.buffer.write(json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8"))


if __name__ == "__main__":
    main()
