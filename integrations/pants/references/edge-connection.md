# VS Code Codex 连接现有 Edge 页面

本项目提供 [playwright-edge.example.toml](playwright-edge.example.toml) 配置示例，可复制到本机 `.codex/config.toml`，注册 `playwright_edge`，使用微软 Playwright MCP 的扩展连接模式。本机 `.codex/` 配置不提交到 Git。示例固定核实过的 npm 版本 0.0.83，指定 `--extension --browser msedge`。这是客户端配置，不代表已连接或成功采集。

本机排障已根据用户提供的版本页显式指定 Edge 程序：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`。首次成功采集时工具等待为 120 秒；当前延长为 300 秒，给用户在 Edge 内确认授权和选择标签页留出时间。2026-10-13 重载后曾成功连接，并读取商品榜两类裤装首页共 20 条；这证明当时配置可用，未单独确认后续断开与超时的全部根因。其他电脑应按实际 Edge 安装位置调整。配置变更后需要重载 Codex/VS Code，当前已运行的 MCP 服务不会自动替换参数。

## 你需要完成的操作

1. 在**已经登录罗盘的那个 Edge 配置**中，打开微软文档链接的 [Playwright Extension 安装页](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)，添加扩展。如 Edge 提示允许其他商店的扩展，按页面提示完成。
2. 保持商品榜单标签页打开。在 VS Code 命令面板运行 `Developer: Reload Window`（重新加载窗口），然后重新打开 Codex 会话，使新 MCP 配置生效。
3. 在 Codex 的 MCP 服务器列表中检查 `playwright_edge`。首次连接时，Edge 会显示连接/标签页选择界面，选择罗盘商品榜单标签页。
4. 发给 Codex：

   > 使用 playwright_edge 连接我已登录的 Edge 罗盘商品榜单，先只读核实账号身份、类目、统计周期、表头和第一页数据。核实成功后，再接入本项目的商品榜数据格式。不要读写 Cookie 或导出登录凭据。

浏览器扩展需要在 Edge 内点击安装；本会话不能代替这一步。完成连接前无法保证能读取具体罗盘页面、翻页或采集全量。

## 连接超时且没有出现选择界面

先在**打开罗盘的同一个 Edge 窗口**输入 `edge://extensions`，检查 Playwright Extension 是否存在、是否启用。VS Code 中的 Playwright 测试扩展不能替代 Edge 的 Playwright Extension。

- 没有：在这个 Edge 配置中安装上方链接的浏览器扩展。
- 有但关闭：打开扩展开关。
- 已启用：点击扩展图标查看状态；若仍无连接界面，再核实浏览器配置是否一致。微软提供 `--profile-dir-name` 用于指定连接的配置，但需要先确认实际配置名称，不能盲填 Default。

确认后重新加载 VS Code，再发起一次连接。MCP 工具列出成功和本地服务运行都不等于 Edge 已连接；仍未连接时不得声称采集到数据。不要通过修改登录数据、导出 Cookie 或跳过连接确认来解决。

若反复显示 No clients 且不出现授权页，停止反复调用。2026-10-13 排障曾确认：MCP 进程仍在运行并带有 `--extension`，但 Edge 启动时那张连接页的本机端口已不再监听；这只证明旧启动请求已经失效，不能证明当前所有标签页或配置的状态。保留已登录的 Edge，执行 VS Code 的 `Developer: Reload Window`，重新打开 Codex 后发起新请求；出现有效授权页时直接在 Edge 点击允许并选择罗盘标签。不要在对话中复制连接令牌。

本次重载后，用户允许连接并选择罗盘商品榜，工具成功列出该标签页。随后在相同店铺、类目和周期下逐个点击两类首页共 20 个商品名称，记录实际弹出的商品地址并立即关闭临时详情页；链接已写入保存榜单和桌面工具。

## 如果列表没有服务器

项目级配置只在 Codex 信任的项目中加载。如果重载后看不到服务器，可在 Codex 侧栏齿轮 → MCP servers → Add server 手动添加：

- 名称：`playwright_edge`
- 传输：STDIO
- 命令：`cmd.exe`
- 参数依次为：`/d`、`/c`、`npx.cmd`、`-y`、`@playwright/mcp@0.0.83`、`--extension`、`--browser`、`msedge`、`--executable-path`、`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`（最后一项作为一个完整参数）

保存后重启扩展。避免重复添加同名服务器。配置中没有保存浏览器令牌或登录凭据。Node.js 22+ 已满足本项目要求。

## 官方资料

- [OpenAI：MCP 的 IDE 与项目级配置](https://learn.chatgpt.com/docs/extend/mcp)
- [微软：Playwright 浏览器扩展](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md)
- [微软：Playwright MCP](https://github.com/microsoft/playwright-mcp)
