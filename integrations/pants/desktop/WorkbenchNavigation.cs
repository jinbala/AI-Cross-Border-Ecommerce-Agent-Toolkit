using System;
using System.Collections.Generic;
using System.Drawing;
using System.Threading.Tasks;
using System.Windows.Forms;

internal sealed partial class WorkbenchForm
{
    private readonly Dictionary<string, Button> navigationButtons = new Dictionary<string, Button>();
    private bool updating, startupUpdateDone;
    private string activeNativeSection = "workbench";
    private Dictionary<string, object> queuedUpdate, pendingLogin;
    private Dictionary<string, object> updateState = new Dictionary<string, object> { {"busy", false}, {"error", false}, {"message", "登录后自动更新；离线时可查看已保存的榜单。"} };

    private Control BuildSidebar()
    {
        var sidebar = new Panel { Dock = DockStyle.Left, Width = 200, BackColor = Color.FromArgb(21, 37, 59), Padding = new Padding(8) };
        var title = new Label { Text = "服装生意\n工作台 2.0", ForeColor = Color.White, Font = new Font("Microsoft YaHei", 15, FontStyle.Bold), Height = 88, Dock = DockStyle.Top, Padding = new Padding(12, 14, 0, 0) };
        var menu = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoScroll = true };
        foreach (var item in new[] { new[] {"workbench", "选品找款", ""}, new[] {"favorites", "我的收藏", ""}, new[] {"candidates", "我的候选", ""}, new[] {"products", "产品档案", ""}, new[] {"pricing", "报价与利润", ""}, new[] {"workflows", "AI 工作流", ""}, new[] {"experiments", "测款记录", ""}, new[] {"artifacts", "成果资料", ""}, new[] {"analytics", "数据分析", ""}, new[] {"checks", "视频与评论", ""}, new[] {"compass", "罗盘账号", ""}, new[] {"settings", "账号与设置", ""} }) {
            string section = item[0];
            string group = section == "workbench" ? "选款与筛选" : section == "products" ? "经营与测款" : section == "compass" ? "账户" : null;
            if (group != null) {
                var groupHeading = new Label {
                    Text = group, AccessibleName = group + "分组",
                    ForeColor = Color.White, BackColor = Color.FromArgb(49, 70, 95),
                    Font = new Font("Microsoft YaHei", 10.5f, FontStyle.Bold),
                    Width = 164, Height = 32, TextAlign = ContentAlignment.MiddleLeft,
                    Padding = new Padding(12, 0, 0, 0),
                    Margin = new Padding(0, section == "workbench" ? 0 : 12, 0, 6)
                };
                groupHeading.Paint += delegate(object sender, PaintEventArgs e) {
                    using (var pen = new Pen(Color.FromArgb(108, 133, 164)))
                        e.Graphics.DrawLine(pen, 0, groupHeading.Height - 1, groupHeading.Width, groupHeading.Height - 1);
                };
                menu.Controls.Add(groupHeading);
            }
            string caption = item[1], description = item[2];
            var button = new Button { Text = caption, AccessibleName = caption, AccessibleDescription = description, Width = 164, Height = 42, FlatStyle = FlatStyle.Flat, TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(0, 0, 0, 3), ForeColor = Color.FromArgb(214, 226, 242), Font = new Font("Microsoft YaHei", 10), BackColor = sidebar.BackColor, Cursor = Cursors.Hand };
            button.FlatAppearance.BorderSize = 0;
            button.Paint += delegate(object sender, PaintEventArgs e) {
                bool selected = activeNativeSection == section;
                using (var brush = new SolidBrush(button.BackColor)) e.Graphics.FillRectangle(brush, button.ClientRectangle);
                if (selected) using (var brush = new SolidBrush(Color.FromArgb(184, 210, 255))) e.Graphics.FillRectangle(brush, 0, 8, 3, button.Height - 16);
                TextRenderer.DrawText(e.Graphics, caption, button.Font, new Rectangle(16, 10, button.Width - 22, 24), selected ? Color.White : Color.FromArgb(214, 226, 242), TextFormatFlags.Left | TextFormatFlags.SingleLine);
                if (button.Focused) ControlPaint.DrawFocusRectangle(e.Graphics, new Rectangle(7, 4, button.Width - 11, button.Height - 8), Color.White, button.BackColor);
            };
            button.Click += async delegate { await NavigateSection(section); };
            navigationButtons.Add(section, button); menu.Controls.Add(button);
        }
        var help = new Button { Dock = DockStyle.Bottom, Height = 36, Text = "使用说明", FlatStyle = FlatStyle.Flat, ForeColor = Color.FromArgb(190, 208, 231) };
        help.FlatAppearance.BorderSize = 0;
        help.Click += delegate { MessageBox.Show(this, "首次在“罗盘账号”扫码登录。之后打开客户端会按更新设置自动取新数据，也可点“立即更新”。\n\n选品页可直接设置采集范围、周期和数量。勾选“快速读榜”跳过逐件补商品链接；需要链接时关闭该选项再更新。\n\n切换价位只筛选本地已保存数据，点“立即更新”再按当前条件取新榜单。更新完成保留筛选和收藏。\n\n更新中可停止。失败或未登录时保留旧数据。读取数量以每个类目、每个查询价位为单位，结果不代表完整市场。", "使用说明"); };
        sidebar.Controls.Add(menu); sidebar.Controls.Add(title); sidebar.Controls.Add(help); HighlightSection("workbench");
        return sidebar;
    }

    private void HighlightSection(string section)
    {
        activeNativeSection = section;
        foreach (var item in navigationButtons) item.Value.BackColor = item.Key == section ? Color.FromArgb(36, 91, 214) : Color.FromArgb(21, 37, 59);
    }

    private async Task NavigateSection(string section)
    {
        try {
            if (!ready) return;
            HighlightSection(section);
            if (section == "compass") { await ShowCompass(); return; }
            tabs.SelectedTab = listTab;
            if (section != "workbench" && section != "favorites" && section != "collection-settings") {
                await view.CoreWebView2.ExecuteScriptAsync("businessUI.navigate(" + DesktopJson.Write(section) + ")");
                return;
            }
            await view.CoreWebView2.ExecuteScriptAsync("businessUI.showPants()");
            if (section == "collection-settings") { HighlightSection("settings"); section = "settings"; }
            await LocalResult("pantsDesktop.navigate(" + DesktopJson.Write(section) + ")");
        } catch (Exception error) { status.Text = "页面尚未就绪：" + error.Message; }
    }

    private async void ReportUpdate(string message, bool busy, bool error)
    {
        updateState = new Dictionary<string, object> { {"busy", busy}, {"error", error}, {"message", message} };
        if (IsDisposed) return;
        status.Text = message;
        try { if (ready) await LocalResult("pantsDesktop.setUpdateState(" + DesktopJson.Write(updateState) + ")"); } catch (Exception) { }
    }

    private async Task<bool> StartUpdate(Dictionary<string, object> request)
    {
        if (updating) { queuedUpdate = request; if (compass != null) compass.RequestStop(); return false; }
        if (pendingLogin != null && compass != null && compass.AtLogin) {
            pendingLogin = request;
            ReportUpdate("请完成罗盘登录；登录后按最新选定的价位和范围继续更新。", false, false);
            return false;
        }
        updating = true; pendingLogin = null; queuedUpdate = null;
        try {
            var options = CompassUpdateOptions.Parse(request);
            ReportUpdate("正在连接罗盘并获取新数据…", true, false);
            await ShowCompass(false);
            bool result = await compass.UpdateRankings(options, async snapshots => {
                var prepared = await LocalResult("pantsDesktop.prepareUpdate(" + snapshots + ")");
                return await SavePrepared(prepared);
            }, ReportUpdate);
            if (compass.NeedsLogin) {
                pendingLogin = request;
                await ShowCompass();
                ReportUpdate("请在“罗盘账号”扫码登录，登录完成后会自动继续更新。已保存数据保留。", false, false);
            }
            return result;
        } catch (Exception error) { ReportUpdate("更新失败：" + error.Message + "。已保存数据保留。", false, true); return false; }
        finally {
            updating = false;
            if (queuedUpdate != null && !IsDisposed) BeginInvoke(new Action(async delegate {
                if (!updating && queuedUpdate != null) { var next = queuedUpdate; queuedUpdate = null; await StartUpdate(next); }
            }));
        }
    }

    private async Task UpdateSmokeTest()
    {
        try {
            await ShowCompass(); compass.EnableUpdateFixture();
            await NavigateSection("workbench");
            var discovered = await compass.DiscoverApparelCategories();
            await LocalResult("pantsDesktop.setCategories(" + DesktopJson.Write(discovered) + ")");
            if (discovered.Length != 15) throw new InvalidOperationException("模拟服装类目读取数量错误");
            var request = new Dictionary<string, object> { {"preset", "common"}, {"period", "近7天"}, {"limit", 10}, {"price_queries", new[] {"all"}} };
            request["preset"] = "custom"; request["category_paths"] = new[] {new[] {"服饰内衣", "服装", "女装", "测试上衣"}}; request["collect_links"] = false;
            bool apparelSaved = await StartUpdate(request);
            var apparelState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length,text:document.getElementById('cards').textContent})");
            if (!apparelSaved || Convert.ToInt32(apparelState["count"]) != 4 || !Convert.ToString(apparelState["text"]).Contains("测试上衣")) throw new InvalidOperationException("模拟上衣类目读取失败");
            request["preset"] = "common";
            request["collect_links"] = false;
            bool fast = await StartUpdate(request);
            var fastState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length,links:document.querySelectorAll('#cards .product-title').length,settingsVisible:!document.getElementById('desktop-update').hidden})");
            if (!fast || Convert.ToInt32(fastState["count"]) != 8 || Convert.ToInt32(fastState["links"]) != 0 || !(bool)fastState["settingsVisible"]) throw new InvalidOperationException("快速读榜验证失败：" + DesktopJson.Write(fastState));
            var factoryState = await LocalResult("(() => {document.getElementById('factory-starter').click(); const value={count:document.querySelectorAll('#cards .product-card').length,explained:document.getElementById('cards').textContent.includes('条件匹配')};document.getElementById('factory-clear').click();return value;})()");
            if (Convert.ToInt32(factoryState["count"]) != 8 || !(bool)factoryState["explained"]) throw new InvalidOperationException("工厂初筛卡片验证失败");
            request["collect_links"] = true;
            bool first = await StartUpdate(request);
            var firstState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length,links:document.querySelectorAll('#cards .product-title').length,progress:document.getElementById('update-progress').textContent})");
            request["price_queries"] = new[] {"0-50"};
            bool lowPriceSaved = await StartUpdate(request);
            var lowPriceCache = DesktopJson.Object(System.IO.File.ReadAllText(dataFile));
            var lowPriceSnapshots = new List<object>(DesktopJson.Items(lowPriceCache["snapshots"]));
            bool customPriceVerified = lowPriceSnapshots.Count == 2;
            foreach (Dictionary<string, object> snapshot in lowPriceSnapshots) {
                var category = new List<object>(DesktopJson.Items(snapshot["category_path"]));
                string expectedMode = Convert.ToString(category[2]) == "女装" ? "custom" : "preset";
                customPriceVerified = customPriceVerified && Convert.ToString(((Dictionary<string, object>)snapshot["source_filters"])["price_band_mode"]) == expectedMode;
            }
            var lowPriceState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length})");
            request["price_queries"] = new[] {"50-70"};
            bool emptySaved = await StartUpdate(request);
            var emptyState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length,emptyVisible:!document.getElementById('empty').hidden})");
            emptyState["updateResult"] = updateState;
            request["preset"] = "women";
            bool allWomen = await StartUpdate(request);
            var womenCache = DesktopJson.Object(System.IO.File.ReadAllText(dataFile));
            int womenCategories = new List<object>(DesktopJson.Items(womenCache["snapshots"])).Count;
            request["preset"] = "common";
            await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('custom-ranges').value='80-120；180-250'; document.getElementById('query').value='测试';");
            request["price_queries"] = new[] {"70-99", "99-150", "150+"};
            bool multiple = await StartUpdate(request);
            var multipleState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length,custom:document.getElementById('custom-ranges').value,query:document.getElementById('query').value})");
            string saved = System.IO.File.ReadAllText(dataFile);
            var stopTask = StartUpdate(request); await Task.Delay(300); compass.RequestStop();
            bool stopped = !await stopTask;
            bool preserved = saved == System.IO.File.ReadAllText(dataFile);
            await NavigateSection("collection-settings");
            var settings = await LocalResult("({visible:!document.getElementById('desktop-update').hidden,productsHidden:document.getElementById('product-board').hidden})");
            await NavigateSection("workbench");
            var result = new Dictionary<string, object> { {"firstSaved", first}, {"firstState", firstState}, {"lowPriceSaved", lowPriceSaved}, {"customPriceVerified", customPriceVerified}, {"lowPriceState", lowPriceState}, {"emptySaved",emptySaved}, {"emptyState",emptyState}, {"allWomenSaved",allWomen}, {"womenCategories",womenCategories}, {"multiPriceSaved", multiple}, {"multiPriceState", multipleState}, {"stopped", stopped}, {"oldDataPreserved", preserved}, {"settingsNavigation", settings}, {"isolatedFixture", true}, {"state", updateState} };
            if (!first || !lowPriceSaved || !customPriceVerified || Convert.ToInt32(lowPriceState["count"]) != 2 || !emptySaved || !allWomen || womenCategories != 6 || Convert.ToInt32(emptyState["count"]) != 0 || !(bool)emptyState["emptyVisible"] || !multiple || !stopped || !preserved || Convert.ToInt32(firstState["count"]) != 8 || Convert.ToInt32(firstState["links"]) != 8 || Convert.ToInt32(multipleState["count"]) != 6 || Convert.ToString(multipleState["custom"]) != "80-120；180-250" || !(bool)settings["visible"]) throw new InvalidOperationException("自动更新验证失败：" + DesktopJson.Write(result));
            result["fastRankingSaved"] = fast; result["fastRankingState"] = fastState;
            result["discoveredCategories"] = discovered.Length; result["apparelSaved"] = apparelSaved; result["factoryScreenState"] = factoryState;
            System.IO.File.WriteAllText(smokeOutput, DesktopJson.Write(result), new System.Text.UTF8Encoding(false));
            using (var stream = System.IO.File.Create(System.IO.Path.ChangeExtension(smokeOutput, ".png"))) await view.CoreWebView2.CapturePreviewAsync(Microsoft.Web.WebView2.Core.CoreWebView2CapturePreviewImageFormat.Png, stream);
            SaveWindowPreview();
            await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('collection-options').open=true;document.getElementById('update-scope').value='custom';renderCategoryChoices();updateCollectionSummary();window.scrollTo(0,0)");
            using (var stream = System.IO.File.Create(System.IO.Path.ChangeExtension(smokeOutput, ".categories.png"))) await view.CoreWebView2.CapturePreviewAsync(Microsoft.Web.WebView2.Core.CoreWebView2CapturePreviewImageFormat.Png, stream);
            await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('factory-starter').click();document.getElementById('list-heading').scrollIntoView({block:'start',behavior:'instant'})");
            await Task.Delay(200);
            using (var stream = System.IO.File.Create(System.IO.Path.ChangeExtension(smokeOutput, ".shortlist.png"))) await view.CoreWebView2.CapturePreviewAsync(Microsoft.Web.WebView2.Core.CoreWebView2CapturePreviewImageFormat.Png, stream);
        } catch (Exception error) { System.IO.File.WriteAllText(smokeOutput, "ERROR: " + error.ToString(), System.Text.Encoding.UTF8); Environment.ExitCode = 1; }
        Close();
    }

    private void SaveWindowPreview(string suffix = "")
    {
        using (var bitmap = new Bitmap(Width, Height)) {
            DrawToBitmap(bitmap, new Rectangle(Point.Empty, Size));
            using (var content = Image.FromFile(System.IO.Path.ChangeExtension(smokeOutput, suffix + ".png")))
            using (var graphics = Graphics.FromImage(bitmap)) {
                Point origin = view.PointToScreen(Point.Empty);
                graphics.DrawImage(content, origin.X - Left, origin.Y - Top, view.Width, view.Height);
            }
            bitmap.Save(System.IO.Path.ChangeExtension(smokeOutput, suffix + ".window.png"), System.Drawing.Imaging.ImageFormat.Png);
        }
    }
}
