# 服装生意工作台 2.0 · 整合桌面版

将裤装项目的罗盘找款、收藏与榜单更新，和跨境工具箱的档案、报价、AI 工作流及测款记录接进同一个主窗口。

## 使用

双击根目录 `启动服装生意工作台.cmd`，或 `桌面版/服装生意工作台-2.0/服装生意工作台.exe`。分发包为根目录的 `服装生意工作台-整合版-2.0.zip`，解压整个目录即可使用。需要 Windows 10/11 x64、.NET Framework 4.8 和 Microsoft Edge WebView2 Runtime，不需要用户安装 Python 或 Node.js。

1. 首次到“罗盘账号”自行扫码登录，在“选品找款”更新并筛选商品。
   选品页可直接展开采集设置，查看范围与最多读取条数；勾选“快速读榜”跳过逐件补链接。切换价位只筛选本地数据，点击“立即更新”再取新榜单，避免反复重启采集。
   更新范围选择“自选类目”，可以勾选需要的类目；点击“从已登录罗盘读取更多服装类目”读取账号菜单实际可见的男装 / 女装子类目，不预先宣称所有账号都具备这些权限。原来的 14 个裤装类目仍可直接使用。
   “初筛：成交≥100 件、转化≥3%”为可调整的参考条件。支持本厂擅长款关键词，卡片解释匹配、未匹配及资料不足；以原统计周期的区间下限比较，不折算月销量，不推断利润。
2. 收藏会加入原裤装收藏，同时同步当前商品到“我的候选”。也可手动同步当前榜单范围内的收藏。
3. 点击商品卡片或候选的“建档算利润”，原始名称、链接和来源带入档案；工厂成本与报价留给经营者填写。
4. 人民币测算点击“计算并保存报告”时，将成本与相应供货 / 零售价同步到档案，供后续工作流复用。其他币种不会覆盖人民币档案字段。
5. 产品档案、七类 AI 工作流、测款记录、成果资料、市场 / 广告分析和备份可在同一主窗口使用。
6. 新增侧栏“视频与评论”：配音稿可粘贴或导入 TXT，设置目标时长并检查字幕；评论评分表可粘贴或导入 CSV / TSV，统计好中差评、已有归因和卖点排行。提供明确标记的服装示例与表格模板，报告可保存到成果资料或导出。这两项离线计算，不需模型密钥。

视频自动识别有效台词中的中文 / 葡英，中文参考语速为每秒 4 个朗读单位，葡英每秒 2.5 词，可按实际配音调整。结果是文字估算，不能替代真实音频时长。评论按有效的 1—5 整数评分统计；未知评分与缺失归因单独披露，不自动给评论分类。演示资料的报告保留标记，使用“清空，填自己的资料”后可录入真实数据。

原作者同步的模块 Skill 入口也会进入相应 AI 任务包作为参考；根级 Skill 是外部 AI 工具的安装入口。接入情况与验证见 [桌面接入说明](../docs/12_Upstream_Desktop_Tools.md)。

来源观察与经营数据分别保存。罗盘价格带不会变成工厂收入，成交区间不会转换成精确月销量。历史统计周期和不同查询价位的排名保留为各自的观察。

“我的候选”支持手工款名 / 链接 / 表格线索及 8 类可调参考条件；Excel `.xlsx` 可直接选择。手工链接本身不会抓取实时销量。

## 旧资料

罗盘的登录、收藏和采集缓存沿用当前 Windows 用户的 `PantsSelectionWorkbench/UserData`、`Data`；程序包不包含这些目录。请避免同时用两个客户端操作同一账号的榜单。

经营数据库位于整合版程序目录的 `data/workbench.db`，可用 `GARMENT_WORKBENCH_DATA` 指定其他目录。旧 1.3 的资料先导出 JSON 备份，再在整合版“账号与设置”合并恢复。恢复前自动备份当前资料；经营备份不包含模型密钥或浏览器登录信息。

## 架构

- `integrations/pants/`：引入的裤装源码与规则，出处、上游提交和许可见该目录的 `INTEGRATION.md`、`UPSTREAM_REVISION`、`LICENSE`。
- C# / WebView2 为统一桌面外壳，罗盘页面与本地经营页面分开；远程罗盘页面不开放本机消息或宿主对象。
- `BusinessBridge.cs`：仅处理本地工作台页面消息，通过标准输入 / 输出调用固定后台程序；本地文件通过原生选择框打开或保存。
- `business.html`、`business.js`：经营页面与选品卡片交接，使用现有 `desktop_app/core.py` 的计算和工作流。
- `desktop_app/service.py`：JSON 命令接口、来源转换、幂等建档、财务和业务资料存储。没有本地监听端口。

## 构建

Windows 构建环境需要 Python、Node.js 22+、.NET Framework C# 编译器与 Microsoft.Web.WebView2 1.0.2903.40 SDK。

```powershell
python -m pip install --target desktop_app/.build/deps -r desktop_app/requirements-build.txt
python unified_desktop/build.py --webview-sdk C:/path/to/Microsoft.Web.WebView2/1.0.2903.40
```

SDK 可从微软 NuGet 的固定版本包取得：`https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.2903.40/microsoft.web.webview2.1.0.2903.40.nupkg`，解压后将包含 `lib`、`runtimes` 的目录传给构建脚本。当前开发电脑有旧裤装项目的 SDK 缓存时，脚本也可复用它；分发产物不依赖旧项目目录。

`--skip-backend` 仅在后台源码与资源没有变化、已经构建过后台时使用，用于快速重建桌面外壳。整合版统一使用本目录构建入口；`desktop_app/build.py` 是经典 Tk 版构建入口，裤装目录的原构建脚本不作为整合版发布入口。

构建只打包明确的程序文件、运行组件和说明，不读取开发电脑的真实榜单，不打包经营数据库、用户备份、密钥、收藏或登录状态。保留两个项目的许可及依赖许可。

## 验证

```powershell
python -m unittest discover -s desktop_app/tests -q
python integrations/pants/scripts/validate_skill.py
python -m unittest discover -s integrations/pants/tests -p test_skill_contract.py -q
node --test integrations/pants/tests/render_selection_html.test.mjs integrations/pants/tests/compass_snapshot.test.mjs integrations/pants/tests/price_band_filter.test.mjs integrations/pants/tests/compass_navigation.test.mjs
node --test integrations/pants/tests/factory_screen.test.mjs integrations/pants/tests/local_tool_saved_data.test.mjs
python unified_desktop/check_release.py
python unified_desktop/check_release.py --mode collector
python unified_desktop/check_release.py --mode update
```

成品检查使用独立资料目录和模拟罗盘页面，不登录真实商家账号。生成 JSON 结果、页面截图及部分完整窗口截图到 `desktop_app/.build/unified/tests/`，不写正式经营资料。WebView2 在受限沙箱内可能无法完成初始化；成品界面检查需要正常 Windows 桌面环境。

程序运行时可用 `build.py --output-dir <临时目录> --archive <临时zip>` 构建待验收程序，再用 `check_release.py --app-dir <临时目录> --archive <临时zip>` 检查。正式替换前保存资料并关闭软件，避免 Windows 文件占用；构建不会复制或覆盖 `data`。
