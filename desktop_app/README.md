# 服装生意工作台 · Windows 桌面版

将仓库的七类 Agent 工作流封装成原生桌面软件，补充服装工厂的产品档案、供货与零售利润测算、业务试验台账。1.3 统一浅色界面、紧凑中文标题和按钮层级；选品以完整清单为主，添加时才打开输入窗口，支持搜索和进度切换。保留粘贴即整理、直接选择 Excel，以及款式 / 链接线索收集。Windows 发布版自带 Python 和 Excel 读取组件。

## 直接使用

双击仓库根目录的 `启动服装生意工作台.cmd`，或 `桌面版/服装生意工作台-1.3.exe`。保持 `runtime-1.3`、`data` 文件夹与程序在一起。新版同目录启动可继续使用已有数据。完整操作说明见 [使用说明.txt](./使用说明.txt)。

打开“选品实操”：从 Excel / 网页复制含列名的表格后点击“粘贴并整理”，或直接选择 `.xlsx` / CSV / TSV 文件；也可以只输入商品链接、ASIN 或款式名称，点击整理后自动保存为待调研线索。来源资料可后补，数据齐全后再进入“更多条件筛选”。方法来源及输入口径见 [选品实操说明](../docs/06_Selection_Practice.md)。

## 本地开发

```powershell
python -m pip install --target desktop_app/.build/deps -r desktop_app/requirements-runtime.txt
python -m desktop_app.app
```

数据默认位于 `desktop_app/data/`，可通过 `--data-dir` 或环境变量 `GARMENT_WORKBENCH_DATA` 指定。首次打开为空白业务数据，不会自动塞入案例。AI 请求在后台线程执行，成功结果写入本地 SQLite；不配置接口也可复制完整任务包使用。

## 验证

```powershell
python -m unittest discover -s desktop_app/tests -v
python -m desktop_app.app --smoke-test --data-dir desktop_app/.build/smoke
python -m desktop_app.tests.check_ui
python -m desktop_app.tests.check_release
```

受限环境若无法读取全局 Tcl 资源，可将 Python 安装目录下 `tcl/tcl8.6`、`tcl/tk8.6` 复制到项目内，分别设置 `TCL_LIBRARY` 与 `TK_LIBRARY` 后执行 GUI 测试。构建脚本自动处理。

## 打包

```powershell
python -m pip install --target desktop_app/.build/deps -r desktop_app/requirements-build.txt
python desktop_app/build.py
```

产出 `桌面版/服装生意工作台-1.3.exe` 与 `runtime-1.3/`。仅在 Windows 上打包，使用 PyInstaller 目录式免安装模式，整体复制即可使用；资源选择性打包 Markdown、模板和脚本，不包含原始未删改 SOP PDF 或用户 Word 文件的个人元数据。源码、构建缓存、业务数据库和可执行文件分开保存，构建不会覆盖用户数据。

同时生成根目录的 `服装生意工作台-Windows.zip`，便于移动到其他电脑。压缩包只含程序与运行组件，不包含用户的 `data/`、备份和 API 密钥。

## 架构与口径

- `core.py`：Decimal 金额计算、原脚本适配、工作流组装、SQLite 事务、备份校验、Windows DPAPI、可选 HTTP 文字模型适配器。
- `app.py`：Tk 原生界面，模型后台任务通过队列回到主线程写入数据库。
- `selection.py`：选品 CSV 字段映射、参考条件、缺项与逐项判定、筛选报告及候选交接。
- `tabular.py`：复制表格、CSV / TSV 和 Excel 读取，自动寻找前 20 行中的表头，处理日期和百分比格式；仅读取缓存结果，不执行或计算公式。
- `build.py`：收集原仓库资源并生成免安装程序。
- `tests/`：财务边界、数据恢复、七个工作流、原市场脚本、模型协议及桌面交互检查。

供货利润 = 商家供货收入 − 单件固定成本 − 按供货收入计的真实费用。零售同理，输入消费者销售收入。预留是单件绝对金额，比例费用是收入百分比；不预设平台费率。市场报告描述导入样本；广告指标不作因果归因或自动投放。API 密钥使用 DPAPI 保存，不包含在 JSON 备份或导出成果中，非本机 HTTP 服务拒绝明文传输，不跟随重定向发送密钥。

备份格式升级为 2，新增 `candidate` 记录；恢复兼容格式 1。候选通过筛选或被人工标记已验证，都不会自动设置产品策略的 `decision_approved`。

手工线索和不完整表格允许来源、币种或日期为空；此时结果保持“资料待补”，不伪造销量、价格或市场结论。链接只在本机识别地址和可验证的 ASIN 结构，没有抓取实时商品数据。相同手工线索重复保存会更新原条目，批量保存使用单次事务。
