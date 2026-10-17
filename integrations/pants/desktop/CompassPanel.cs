using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

// The remote page never receives a host object or a file-system bridge.
// Collection reads rendered DOM and observes official title navigation only.
internal sealed partial class CompassPanel : UserControl
{
    internal const string CompassUrl = "https://compass.jinritemai.com/shop/chance/rank-product";
    private readonly WebView2 web = new WebView2 { Dock = DockStyle.Fill };
    private readonly ToolStripButton save = new ToolStripButton("保存当前页（可选）");
    private readonly ToolStripButton cancel = new ToolStripButton("停止") { Enabled = false };
    private readonly Label message = new Label { Dock = DockStyle.Top, Height = 50, Padding = new Padding(10, 6, 10, 2), Text = "请在下方罗盘官网自行登录。日常在“选品工作台”查看商品、调整价位；取新数据由后台更新完成。当前页手动保存仅作为可选入口。" };
    private readonly ToolStripLabel address = new ToolStripLabel();
    private readonly Func<string, Task> validate;
    private readonly Func<string, Task<string>> persist;
    private readonly Action<string> report;
    private readonly bool testMode;
    private readonly string testDirectory;
    private CoreWebView2Environment environment;
    private Task initialization;
    private bool collecting, cancelled;
    private string expectedProduct;
    private TaskCompletionSource<string> productNavigation;
    private string captureSource;

    internal CompassPanel(Func<string, Task> validate, Func<string, Task<string>> persist, Action<string> report, bool testMode, string testDirectory)
    {
        this.validate = validate; this.persist = persist; this.report = report; this.testMode = testMode;
        this.testDirectory = testDirectory;
        var toolbar = new ToolStrip { GripStyle = ToolStripGripStyle.Hidden };
        Button(toolbar, "商品榜", delegate { if (!collecting && web.CoreWebView2 != null) web.CoreWebView2.Navigate(HomeUrl); });
        Button(toolbar, "后退", delegate { if (!collecting && web.CanGoBack) web.GoBack(); });
        Button(toolbar, "刷新页面", delegate { if (!collecting && web.CoreWebView2 != null) web.Reload(); });
        save.Click += async delegate { await CaptureCurrentPage(); };
        cancel.Click += delegate { RequestStop(); };
        toolbar.Items.Add(save); toolbar.Items.Add(cancel); toolbar.Items.Add(address);
        Controls.Add(web); Controls.Add(message); Controls.Add(toolbar);
        Dock = DockStyle.Fill;
    }

    private bool updateFixtureMode;
    internal void EnableUpdateFixture() { if (!testMode) throw new InvalidOperationException(); updateFixtureMode = true; }
    private string HomeUrl { get { return testMode ? "https://compass-test.example/" + (updateFixtureMode ? "compass-update.html" : "compass-test.html") : CompassUrl; } }
    internal WebView2 Browser { get { return web; } }
    internal bool Collecting { get { return collecting; } }

    private static void Button(ToolStrip bar, string title, Action action)
    {
        var button = new ToolStripButton(title); button.Click += delegate { action(); }; bar.Items.Add(button);
    }

    internal Task Initialize(CoreWebView2Environment environment)
    {
        if (initialization == null) initialization = InitializeOnce(environment);
        return initialization;
    }

    private async Task InitializeOnce(CoreWebView2Environment environment)
    {
        this.environment = environment;
        captureSource = File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "assets", "compass-capture.js"));
        await web.EnsureCoreWebView2Async(environment);
        web.CoreWebView2.Settings.IsWebMessageEnabled = false;
        web.CoreWebView2.Settings.AreHostObjectsAllowed = false;
        web.CoreWebView2.NewWindowRequested += OnNewWindow;
        web.CoreWebView2.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e) {
            if (collecting && !navigationAllowed) {
                e.Cancel = true;
                ObserveProduct(e.Uri);
                return;
            }
            Uri uri;
            if (!Uri.TryCreate(e.Uri, UriKind.Absolute, out uri) || uri.Scheme != "https") e.Cancel = true;
        };
        web.CoreWebView2.SourceChanged += delegate { address.Text = web.Source == null ? "" : web.Source.GetLeftPart(UriPartial.Authority); };
        web.CoreWebView2.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e) {
            if (!e.IsSuccess) message.Text = "页面未能加载，请检查网络后刷新。登录、验证码和店铺选择均在罗盘官网完成。";
        };
        if (testMode) {
            Directory.CreateDirectory(testDirectory);
            using (var fixture = System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream("CompassFixture"))
            using (var reader = new StreamReader(fixture)) File.WriteAllText(Path.Combine(testDirectory, "compass-test.html"), reader.ReadToEnd());
            using (var fixture = System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream("CompassUpdateFixture"))
            using (var reader = new StreamReader(fixture)) File.WriteAllText(Path.Combine(testDirectory, "compass-update.html"), reader.ReadToEnd());
            web.CoreWebView2.SetVirtualHostNameToFolderMapping("compass-test.example", testDirectory, CoreWebView2HostResourceAccessKind.DenyCors);
        }
        web.CoreWebView2.Navigate(HomeUrl);
    }

    private bool AtRankingPage()
    {
        var uri = web.Source;
        return uri != null && uri.Scheme == "https" && ((uri.Host == "compass.jinritemai.com" && uri.AbsolutePath == "/shop/chance/rank-product") || (testMode && uri.Host == "compass-test.example"));
    }

    private void ObserveProduct(string address)
    {
        Uri uri;
        if (productNavigation == null || !AtRankingPage() || !Uri.TryCreate(address, UriKind.Absolute, out uri) || uri.Scheme != "https" || uri.Host != "haohuo.jinritemai.com" || uri.AbsolutePath != "/ecommerce/trade/detail/index.html") return;
        var query = System.Web.HttpUtility.ParseQueryString(uri.Query);
        if (query["id"] == expectedProduct) productNavigation.TrySetResult(uri.AbsoluteUri);
    }

    private async void OnNewWindow(object sender, CoreWebView2NewWindowRequestedEventArgs e)
    {
        if (collecting) { e.Handled = true; ObserveProduct(e.Uri); return; }
        // Keep official login popups in the app and in the same app-owned profile.
        // Product detail links can open in the user's normal browser.
        Uri uri;
        if (!Uri.TryCreate(e.Uri, UriKind.Absolute, out uri) || uri.Scheme != "https") { e.Handled = true; return; }
        if (uri.Host == "haohuo.jinritemai.com") {
            e.Handled = true;
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
            return;
        }
        var deferral = e.GetDeferral();
        Form popup = null;
        try {
            popup = new Form { Text = "罗盘登录页面", Width = 1000, Height = 760, StartPosition = FormStartPosition.CenterParent };
            var child = new WebView2 { Dock = DockStyle.Fill };
            popup.Controls.Add(child); popup.Show(FindForm());
            await child.EnsureCoreWebView2Async(environment);
            child.CoreWebView2.Settings.IsWebMessageEnabled = false;
            child.CoreWebView2.Settings.AreHostObjectsAllowed = false;
            child.CoreWebView2.WindowCloseRequested += delegate { popup.Close(); };
            popup.FormClosed += delegate { child.Dispose(); };
            e.NewWindow = child.CoreWebView2; e.Handled = true;
        } catch (Exception error) {
            e.Handled = true; if (popup != null) popup.Close();
            message.Text = "登录窗口打开失败：" + error.Message;
        } finally { deferral.Complete(); }
    }

    private async Task<Dictionary<string, object>> ReadSnapshot()
    {
        if (!AtRankingPage()) throw new InvalidOperationException("请先在客户端登录，并打开罗盘商品榜，选择一个男女裤的具体类目。");
        string source = captureSource;
        if (testMode) source = source.Replace("location.hostname !== 'compass.jinritemai.com'", "location.hostname !== 'compass-test.example'").Replace("location.pathname !== '/shop/chance/rank-product'", "false");
        var result = DesktopJson.Object(await web.CoreWebView2.ExecuteScriptAsync("(() => { try { return {ok:true,snapshot:(" + source + ")()}; } catch(e) { return {ok:false,error:e.message}; } })()"));
        if (!(bool)result["ok"]) throw new InvalidOperationException(Convert.ToString(result["error"]));
        if (!AtRankingPage()) throw new InvalidOperationException("页面已切换，请重新保存当前页。");
        var snapshot = (Dictionary<string, object>)result["snapshot"];
        if (testMode) snapshot["source_url"] = CompassUrl;
        return snapshot;
    }

    private static string Fingerprint(Dictionary<string, object> snapshot)
    {
        return DesktopJson.Write(new object[] { snapshot["observed_identity"], snapshot["category_path"], snapshot["selected_tabs"], snapshot["dates"], snapshot["page_number"],
            DesktopJson.Items(snapshot["rows"]).Select(item => { var row = (Dictionary<string, object>)item; return new object[] { row["row_key"], row["product_name"], row["price_band"], row["shop_name"], row["cells"] }; }).ToArray() });
    }

    private async Task<Dictionary<string, object>> ReadLinkedSnapshot(int maxRank, bool collectLinks = true)
    {
        var snapshot = await ReadSnapshot();
        await validate(DesktopJson.Write(snapshot));
        string before = Fingerprint(snapshot);
        var rows = DesktopJson.Items(snapshot["rows"]).Cast<Dictionary<string, object>>()
            .Where(row => Int32.Parse(Convert.ToString(row["row_key"]).Split('_')[1]) <= maxRank).ToArray();
        if (rows.Length == 0) {
            if (snapshot.ContainsKey("empty_state_text")) return snapshot;
            throw new InvalidOperationException("当前页没有目标排名内的商品。");
        }
        foreach (var row in rows) {
            if (cancelled) throw new OperationCanceledException();
            if (!collectLinks) continue;
            if (!String.IsNullOrEmpty(Convert.ToString(row["product_link"]))) continue;
            expectedProduct = Convert.ToString(row["row_key"]).Split('_')[0];
            productNavigation = new TaskCompletionSource<string>();
            message.Text = "正在读取商品链接 " + (Array.IndexOf(rows, row) + 1) + "/" + rows.Length + "，请稍候…";
            if (batchProgress != null) batchProgress(message.Text);
            string key = DesktopJson.Write(row["row_key"]), title = DesktopJson.Write(row["product_name"]);
            string click = await web.CoreWebView2.ExecuteScriptAsync("(() => { const row = Array.from(document.querySelectorAll('tbody tr[data-row-key]')).find(el => el.getAttribute('data-row-key') === " + key + "); const name = row?.querySelector('td:nth-child(2) [class^=\"name-\"]'); if(!name || name.innerText.trim() !== " + title + ") return false; name.click(); return true; })()");
            if (click != "true") throw new InvalidOperationException("商品行发生变化，请等页面稳定后重试。");
            if (await Task.WhenAny(productNavigation.Task, Task.Delay(2000)) == productNavigation.Task) {
                string link = await productNavigation.Task;
                row["product_link"] = link;
                row["product_link_evidence"] = new Dictionary<string, object> { {"method", "desktop_visible_title_click"}, {"captured_at", DateTime.UtcNow.ToString("o")}, {"url", link} };
            }
            productNavigation = null; expectedProduct = null;
        }
        if (cancelled) throw new OperationCanceledException();
        if (Fingerprint(await ReadSnapshot()) != before) throw new InvalidOperationException("账号、类目、周期或榜单内容已变化，本次未保存。请重新读取。");
        snapshot["rows"] = rows;
        return snapshot;
    }

    internal async Task<bool> CaptureCurrentPage()
    {
        if (collecting) return false;
        collecting = true; cancelled = false; save.Enabled = false; cancel.Enabled = true;
        try {
            var snapshot = await ReadLinkedSnapshot(Int32.MaxValue);
            string saved = await persist(DesktopJson.Write(snapshot));
            int links = DesktopJson.Items(snapshot["rows"]).Cast<Dictionary<string, object>>().Count(row => !String.IsNullOrEmpty(Convert.ToString(row["product_link"])));
            message.Text = saved + "；本页商品链接 " + links + " 条。获取更多新数据可使用选品清单中的“立即更新”。";
            report(message.Text); return true;
        } catch (OperationCanceledException) { message.Text = "已停止，本次采集未覆盖已保存榜单。"; report(message.Text); return false; }
        catch (Exception error) { message.Text = "未保存：" + error.Message; report(message.Text); return false; }
        finally { collecting = false; productNavigation = null; expectedProduct = null; save.Enabled = true; cancel.Enabled = false; }
    }

}

internal static class DesktopJson
{
    private static System.Web.Script.Serialization.JavaScriptSerializer Serializer()
    {
        return new System.Web.Script.Serialization.JavaScriptSerializer { MaxJsonLength = 32 * 1024 * 1024, RecursionLimit = 100 };
    }
    internal static string Write(object value) { return Serializer().Serialize(value); }
    internal static Dictionary<string, object> Object(string value) { return (Dictionary<string, object>)Serializer().DeserializeObject(value); }
    internal static IEnumerable<object> Items(object value) { return ((IEnumerable)value).Cast<object>(); }
}
