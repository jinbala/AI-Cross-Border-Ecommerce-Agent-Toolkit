# 男女裤装选品工具

> 本目录是整合版引入的源码。整合应用请从 [2.0 构建与使用说明](../../unified_desktop/README.md)启动和构建；下文保留上游独立客户端的历史说明，不代表整合包内置了真实试采或支持原独立版安装脚本。

面向男裤、女裤业务的本地选款工具与 AI Skill。打开即加载已保存的罗盘真实榜单，按价格和款别筛选，生成可搜索和分享的 HTML。图文榜另支持发布时间、新上榜和作品账号汇总。

**桌面版可自行登录罗盘、保存商品榜当前页，无需浏览器插件或 Codex 连接授权。** 2026-10-13 的内置榜单为女装牛仔裤、男装休闲裤各 10 条真实首页试采，不代表全量 TOP200。演示数据均为虚构；不自动判断同厂同货、利润或销售趋势。

你提供的四个罗盘入口已保存到 `config/data-sources.json`，也显示在工具顶部。选款主入口为 [商品榜单](https://compass.jinritemai.com/shop/chance/rank-product)；[类目挖掘](https://compass.jinritemai.com/shop/chance/category-mining)、[类目概况](https://compass.jinritemai.com/shop/chance/category-overview)、[店铺榜单](https://compass.jinritemai.com/shop/chance/rank-shop) 作为分析入口。已核实商品榜表头、统计周期及男女裤菜单；其他三个入口未实现数据映射。

**工具默认“商品榜”模式**：商品数据无需作品 ID、发布时间或新上榜标记，只应用价格和款别条件，不计算内容重复度。另一种“图文榜”模式继续使用作品证据。切换模式后下载对应模板：`裤装商品榜模板.csv` 或 `裤装图文榜模板.csv`。原 `裤装数据模板.csv` 是旧图文模板，保留且不会被覆盖。

## 直接使用（Windows）

**桌面版已可用：双击桌面的“裤装选品工作台”图标。** 独立窗口可查看、筛选、收藏、下载，不用打开 VS Code 或启动服务器。安装脚本为根目录 `安装桌面版.cmd`；安装到当前用户目录并创建桌面和开始菜单入口，无需管理员权限。构建包在 `dist/desktop`，可分发压缩包为 `dist/裤装选品桌面版.zip`。详见 [桌面版说明](desktop/README.md)。

桌面版左侧为“选品工作台”“我的收藏”“罗盘账号”“更新设置”。首次在“罗盘账号”扫码登录；之后启动默认后台更新，也可点“立即更新”。自动切类目、价位和周期、翻页并保存，新结果直接显示，保留筛选条件和收藏。登录状态、收藏和采集结果保留在本机，重新安装不会清空。日常使用无需 Node.js、Codex 或浏览器插件。

主界面支持多选价位，以及 `80-120；180-250` 等多段自定义区间。勾选或修改后立即筛选，随后后台按相应价位补取并合并去重。罗盘各类目的推荐价位不同：没有匹配项时，客户端通过官网“自定义”填写并核对上下限，按罗盘口径查询并保留标注。多段自定义区间按覆盖它的客户端价位分段取榜再精确筛选，读取数量针对每个类目、每个查询价位，不代表所有商品。可保存常用价位组合。更新失败或停止时保留旧榜单。

以下独立 HTML 方式仍可使用：

1. 双击根目录 **`打开裤装选品.cmd`**，自动构建并打开工具。需 Node.js 22+，无需安装 npm 依赖或启动服务器。也可直接打开已生成的 `results/裤装选品工具.html`。
2. 工具自动显示上次采集的真实榜单及结果，无需下载模板或导入文件。页面显示店铺、实际统计周期、保存时间和采集范围；没有缓存时提示先采集，不自动用演示冒充真实数据。
3. 点击“女裤／男裤／全部裤装”，搜索商品或店铺、选择裤型，结果立即更新。主界面可直接填价格上下限并点“应用筛选”；商品榜默认按页面价格带与输入区间有交集筛选（含边界）。价格带不足时使用已知最低价，无法判定的价格保留并提示。图文设置收在“更多设置”。
4. 喜欢的商品点“收藏”，再勾选“只看收藏”集中看；也可选择“收藏优先”。收藏按店铺分开，保存在当前浏览器；存储不可用会提示临时保存，关闭前可下载清单。
5. “下载当前表格”导出 CSV，“下载当前清单”导出 HTML，均只包含当前显示的商品；清空筛选可恢复全部。导出的 CSV 用于查看和对比，不是重新导入的原始模板；用表格软件导入时仍需把长商品 ID 列设为文本。
6. 更新数据：保持已登录的 Edge 罗盘打开，点击“复制更新指令”，粘贴到 VS Code 的 Codex 中发送。采集转换成功后自动更新缓存并重建工具；重新打开或刷新页面即可。按钮只复制指令，打开页面不会自动联网更新。
7. 报告 JSON 保存结果与待核记录，不是原始输入，不能直接重复导入。外部 CSV/JSON、模板和演示收在“其他数据来源与手工导入（可选）”，日常罗盘取数无需使用。

商品卡片和导出 HTML 都明确显示网页原始价格带；点击商品标题或“打开商品”均打开同一地址。当前 20 条已逐个点击罗盘官方商品名称，补齐实际弹出的商品地址。点击记录保存在 `results/compass-title-click-links-2026-10-13.json`，与原始快照的商品 ID、类目和周期逐项核对。不能因为“查看详情”按钮不可用就判断标题也不可点击；新采数据仍应保存实际打开地址，不自动拼接未经核实的详情地址。

款别填写“男款／女款／中性款”，未知留空。版型、面料、季节、尺码填有来源依据的数据。类目路径用 `>` 分隔。长商品 ID 和作品 ID 按文本保存，避免 Excel 科学计数法或精度截断。

数据在本地处理；点击真实商品/作品链接会访问外部网站。工具不验证链接是否可访问。

## 配置与命令行

修改 `config/selection.json` 调整单段筛选默认值，再重新双击启动器。单段区间初始为 0–1000 元；桌面主界面的多价位筛选默认不限价格，并可记住你的选择。

```powershell
node scripts/build_local_tool.mjs
node scripts/render_selection_html.mjs tests/fixtures/pants-demo.json --config config/selection.json --output results/裤装演示结果.html
node scripts/render_selection_html.mjs input.json --config config/selection.json --output-dir results
```

参数：`publication_days`（1–90）、`price_floor`、`price_ceiling`、`price_basis`（`sku_min` 或 `price_band`）、`require_new_entry`（布尔值）、`gender`、`timezone`（Asia/Shanghai）。CLI 为兼容原规则默认按最低价；商品榜界面显式选择价格带。价格含边界，价格未知保留，不把价格带写成已核实 SKU 最低价。指定款别时，未知款别进入待核。

图文榜的默认三天指**同一期榜单中作品发布时间的三日窗口**。关闭“只看新上榜”只放宽本期作品条件，不查询过去多期榜单。商品榜禁用这两个条件，统计周期以实际源页面为准；未知周期标为待核实。多个榜单日期不能直接混在同次任务中。

## 从已登录的罗盘取数

桌面版优先使用内置“罗盘账号”和“立即更新”，详见 [桌面版说明](desktop/README.md)。采集结果保存在本机 `PantsSelectionWorkbench/Data/compass-data.json`，再次启动会优先加载；按所选类目、价位和数量自动读取，不把局部结果标成完整 TOP200。登录、验证码和店铺选择由用户在官网完成。

以下是可选的开发者连接方式，桌面端日常取数不需要它：

如果使用 **VS Code Codex + 已登录的 Edge**，项目提供 Playwright MCP 的扩展模式配置示例，连接方法见 [Edge 连接说明](references/edge-connection.md)。本机 `.codex/` 配置不提交到 Git。你需要在 Edge 安装 Playwright Extension 并重载 VS Code，首次连接时选择罗盘标签页；配置文件本身不代表页面已连接或采集成功。

连接后可直接告诉 Codex：“读取罗盘商品榜的女装牛仔裤和男装休闲裤首页，保存原始数据并更新选品工具。”每次先核实店铺身份、类目与实际周期，再在页面上选择目标类目。当前页读取函数为 `scripts/capture_compass_product.mjs`，由已连接的 Playwright MCP 在页面中执行并保存快照；它本身不是浏览器启动器或自动翻页程序。

快照转换并生成报告：

```powershell
node scripts/normalize_compass_snapshot.mjs results/compass-women-jeans-page1.json results/compass-men-casual-page1.json --output results/罗盘裤装试采-2026-10-12.json --identity "你的店铺名称"
node scripts/render_selection_html.mjs results/罗盘裤装试采-2026-10-12.json --config config/selection.json --output results/罗盘裤装真实试采-2026-10-12.html
```

转换命令自动更新 `results/latest-compass-products.json` 并重建工具，打开页面即可筛选；无需再手工导入。构建脚本也可用 `--data 原始数据.json --output-dir 输出目录` 指定已保存数据。页面显示的是价格带，最低可购买 SKU 价仍待验证。已有 20 条试采的标题链接已补齐；新采数据仍需记录实际标题跳转地址。开发者采集的源数据与报告保存在本机 `results`，不会提交到 Git。客户端中自行采集的榜单优先于这些内置数据，不会因页面更新被覆盖。

[category-catalog.yaml](references/category-catalog.yaml) 已记录男裤 8 个、女裤 6 个实际叶子路径；按 `scan_nodes` 选择，不采全服装汇总、不追加“全部”。菜单路径核实不等于各类目完成采集。原五类保留在 `references/category-catalog.legacy.yaml`。

AI 规范见 [SKILL.md](SKILL.md)。`evals/evals.json` 是行为验收题库，不是商品数据，没有自动对话评测运行器。无人值守全类目翻页、飞书写入、断点续采和多日趋势仍需后续实现。离线 HTML 自身不能调用 VS Code 的 MCP。

## 验证

```powershell
python scripts/validate_skill.py
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/render_selection_html.test.mjs tests/pants_selection.test.mjs tests/compass_snapshot.test.mjs tests/local_tool_saved_data.test.mjs tests/price_band_filter.test.mjs tests/compass_navigation.test.mjs
```

MIT License，见 [LICENSE](LICENSE)。
