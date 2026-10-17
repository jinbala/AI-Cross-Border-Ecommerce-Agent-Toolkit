using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

// Local namespace scopes the lock to the Windows session; the SID isolates users.
internal sealed class SingleInstance : IDisposable
{
    private readonly System.Threading.Mutex mutex;
    private readonly System.Threading.EventWaitHandle activate, compass;
    private readonly List<System.Threading.RegisteredWaitHandle> waits = new List<System.Threading.RegisteredWaitHandle>();
    internal readonly bool IsPrimary;
    private const string WindowTitle = "服装生意工作台 2.0 · 选品与经营";
    [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
    private static extern IntPtr FindWindow(string className, string title);
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern bool AllowSetForegroundWindow(uint processId);
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr window);

    internal SingleInstance(string key)
    {
        string name = "Local\\" + key;
        activate = new System.Threading.EventWaitHandle(false, System.Threading.EventResetMode.AutoReset, name + ".activate");
        compass = new System.Threading.EventWaitHandle(false, System.Threading.EventResetMode.AutoReset, name + ".compass");
        mutex = new System.Threading.Mutex(false, name + ".lock");
        try { IsPrimary = mutex.WaitOne(0); }
        catch (System.Threading.AbandonedMutexException) { IsPrimary = true; }
    }

    internal void Notify(bool openCompass)
    {
        uint pid;
        IntPtr window = FindWindow(null, WindowTitle);
        if (window != IntPtr.Zero) { GetWindowThreadProcessId(window, out pid); AllowSetForegroundWindow(pid); }
        (openCompass ? compass : activate).Set();
    }

    internal void Attach(Form form, Action<bool> callback)
    {
        // Force handle creation before accepting notifications, including during startup.
        IntPtr handle = form.Handle;
        foreach (bool openCompass in new[] { false, true }) {
            bool requestCompass = openCompass;
            waits.Add(System.Threading.ThreadPool.RegisterWaitForSingleObject(openCompass ? compass : activate, delegate {
                try {
                    form.BeginInvoke(new Action(delegate {
                        if (form.IsDisposed) return;
                        if (!form.Visible) form.Show();
                        if (form.WindowState == FormWindowState.Minimized) form.WindowState = FormWindowState.Normal;
                        form.Activate(); SetForegroundWindow(form.Handle);
                        callback(requestCompass);
                    }));
                } catch (InvalidOperationException) { }
            }, null, System.Threading.Timeout.Infinite, false));
        }
    }

    public void Dispose()
    {
        foreach (var wait in waits) wait.Unregister(null);
        if (IsPrimary) mutex.ReleaseMutex();
        mutex.Dispose(); activate.Dispose(); compass.Dispose();
    }

    internal static void RunTestHost(string folder, bool openCompass)
    {
        Directory.CreateDirectory(folder);
        string key;
        using (var hash = System.Security.Cryptography.SHA256.Create())
            key = "GarmentWorkbench.Test." + BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(folder))).Replace("-", "");
        using (var instance = new SingleInstance(key)) {
            if (!instance.IsPrimary) { instance.Notify(openCompass); return; }
            using (var form = new Form { Text = WindowTitle, Width = 480, Height = 220 }) {
                instance.Attach(form, delegate(bool requested) {
                    File.AppendAllText(Path.Combine(folder, "activation.log"), (requested ? "compass" : "activate") + ":" + form.WindowState + "\n");
                });
                form.Shown += delegate { File.WriteAllText(Path.Combine(folder, "ready"), Process.GetCurrentProcess().Id + ":" + form.Handle.ToInt64()); };
                DateTime deadline = DateTime.UtcNow.AddMinutes(2);
                using (var timer = new Timer { Interval = 250 }) {
                    timer.Tick += delegate { if (DateTime.UtcNow > deadline || File.Exists(Path.Combine(folder, "close"))) form.Close(); };
                    timer.Start(); Application.Run(form);
                }
            }
        }
    }
}

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        bool unifiedSmoke = args.Length == 2 && args[0] == "--unified-smoke-test";
        bool updateSmoke = args.Length == 2 && args[0] == "--update-smoke-test";
        bool collectorSmoke = args.Length == 2 && (args[0] == "--collector-smoke-test" || updateSmoke);
        bool loginSmoke = args.Length == 2 && args[0] == "--login-smoke-test";
        bool openCompass = args.Length == 1 && args[0] == "--open-compass";
        string smokeOutput = args.Length == 2 && (args[0] == "--smoke-test" || collectorSmoke || loginSmoke || unifiedSmoke) ? Path.GetFullPath(args[1]) : null;
        if (args.Length >= 2 && args[0] == "--instance-test-host") {
            SingleInstance.RunTestHost(Path.GetFullPath(args[1]), args.Length == 3 && args[2] == "--open-compass");
            return;
        }
        if (smokeOutput != null) {
            Application.Run(new WorkbenchForm(smokeOutput, collectorSmoke, loginSmoke, openCompass, updateSmoke, unifiedSmoke));
            return;
        }
        string identity = System.Security.Principal.WindowsIdentity.GetCurrent().User.Value;
        using (var instance = new SingleInstance("GarmentWorkbench.2." + identity)) {
            if (!instance.IsPrimary) { instance.Notify(openCompass); return; }
            var form = new WorkbenchForm(null, false, false, openCompass, false, false);
            instance.Attach(form, form.ActivateExisting);
            Application.Run(form);
        }
    }
}

internal sealed partial class WorkbenchForm : Form
{
    private const string AppUrl = "https://pants-workbench.example/pants-tool.html";
    private readonly WebView2 view = new WebView2();
    private readonly ToolStripStatusLabel status = new ToolStripStatusLabel("正在打开已保存榜单…");
    private readonly Timer updateTimer = new Timer();
    private readonly string assets = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "assets");
    private readonly string smokeOutput;
    private readonly bool collectorSmoke;
    private readonly bool loginSmoke;
    private readonly bool updateSmoke;
    private readonly bool unifiedSmoke;
    private bool openCompassAtStart;
    private readonly TabControl tabs = new TabControl { Dock = DockStyle.Fill };
    private readonly TabPage listTab = new TabPage("选品清单");
    private readonly TabPage compassTab = new TabPage("罗盘登录 / 更新");
    private CoreWebView2Environment environment;
    private CompassPanel compass;
    private object[] savedSnapshots = new object[0];
    private string dataFile;
    private bool smokeStarted;
    private DateTime sourceTime;
    private bool ready;
    private bool timerBusy;
    private bool watchSource;
    private CoreWebView2DownloadOperation testDownload;

    public WorkbenchForm(string smokeOutput, bool collectorSmoke, bool loginSmoke, bool openCompass, bool updateSmoke, bool unifiedSmoke)
    {
        this.smokeOutput = smokeOutput;
        this.collectorSmoke = collectorSmoke;
        this.loginSmoke = loginSmoke; this.openCompassAtStart = openCompass;
        this.updateSmoke = updateSmoke;
        this.unifiedSmoke = unifiedSmoke;
        Text = "服装生意工作台 2.0 · 选品与经营";
        Width = 1280; Height = 900; MinimumSize = new Size(760, 620);
        StartPosition = FormStartPosition.CenterScreen;
        AutoScaleMode = AutoScaleMode.Dpi;
        string iconPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "pants.ico");
        if (File.Exists(iconPath)) Icon = new Icon(iconPath);

        var statusBar = new StatusStrip(); statusBar.Items.Add(status);
        view.Dock = DockStyle.Fill;
        listTab.Controls.Add(view); tabs.TabPages.Add(listTab); tabs.TabPages.Add(compassTab);
        tabs.Appearance = TabAppearance.FlatButtons; tabs.ItemSize = new Size(0, 1); tabs.SizeMode = TabSizeMode.Fixed;
        Controls.Add(tabs); Controls.Add(BuildSidebar()); Controls.Add(statusBar);
        Shown += async delegate { await Initialize(); };
        updateTimer.Interval = 2500;
        updateTimer.Tick += async delegate {
            if (timerBusy) return;
            timerBusy = true;
            try {
            if (watchSource && ready && !updating && (compass == null || !compass.Collecting) && SyncSource()) view.Reload();
            if (pendingLogin != null && !updating && compass != null && await compass.IsSignedIn()) {
                if (pendingLogin == null || updating) return;
                var request = pendingLogin; pendingLogin = null; await StartUpdate(request);
            }
            } finally { timerBusy = false; }
        };
        FormClosed += delegate { StopBusinessProcesses(); updateTimer.Stop(); updateTimer.Dispose(); view.Dispose(); };
    }

    internal void ActivateExisting(bool openCompass)
    {
        if (!openCompass) return;
        if (ready) OpenCompass(); else openCompassAtStart = true;
    }

    private static void AddButton(ToolStrip toolbar, string label, Action action)
    {
        var button = new ToolStripButton(label); button.Click += delegate { action(); }; toolbar.Items.Add(button);
    }

    private bool SyncSource()
    {
        try {
            string linkFile = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "source-path.txt");
            if (!File.Exists(linkFile)) return false;
            string source = File.ReadAllText(linkFile, Encoding.UTF8).Trim();
            if (!File.Exists(source)) return false;
            DateTime modified = File.GetLastWriteTimeUtc(source);
            if (modified == sourceTime) return false;
            string html = File.ReadAllText(source, Encoding.UTF8);
            if (!html.TrimEnd().EndsWith("</html>", StringComparison.OrdinalIgnoreCase)) return false;
            Directory.CreateDirectory(assets);
            string target = Path.Combine(assets, "pants-tool.html"), pending = target + ".tmp";
            File.WriteAllText(pending, html, new UTF8Encoding(false));
            if (File.Exists(target)) File.Replace(pending, target, null); else File.Move(pending, target);
            sourceTime = modified;
            return true;
        } catch (IOException) { return false; }
        catch (UnauthorizedAccessException) { return false; }
    }

    private async Task Initialize()
    {
        TestTrace("initialize entered");
        try {
            watchSource = File.Exists(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "source-path.txt"));
            if (watchSource) SyncSource();
            if (!File.Exists(Path.Combine(assets, "pants-tool.html"))) throw new FileNotFoundException("未找到选品页面，请重新运行桌面版安装脚本。");
            string profile = smokeOutput == null
                ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PantsSelectionWorkbench", "UserData")
                : Path.Combine(Path.GetDirectoryName(smokeOutput), "desktop-smoke-profile");
            dataFile = Path.Combine(smokeOutput == null ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PantsSelectionWorkbench", "Data") : Path.Combine(Path.GetDirectoryName(smokeOutput), "desktop-collector-smoke-data"), "compass-data.json");
            if (collectorSmoke && File.Exists(dataFile)) File.Delete(dataFile);
            environment = await CoreWebView2Environment.CreateAsync(null, profile);
            TestTrace("environment created");
            await view.EnsureCoreWebView2Async(environment);
            TestTrace("webview ready");
            await view.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync("if(location.origin === 'https://pants-workbench.example') window.PANTS_DESKTOP = true;");
            view.CoreWebView2.SetVirtualHostNameToFolderMapping("pants-workbench.example", assets, CoreWebView2HostResourceAccessKind.DenyCors);
            view.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
            view.CoreWebView2.Settings.IsStatusBarEnabled = false;
            view.CoreWebView2.WebMessageReceived += async delegate(object sender, CoreWebView2WebMessageReceivedEventArgs e) {
                if (e.Source != AppUrl) return;
                try {
                    var command = DesktopJson.Object(e.WebMessageAsJson); string action = Convert.ToString(command["action"]);
                    if (action == "open-compass") OpenCompass();
                    else if (action == "business") await HandleBusinessMessage(command);
                    else if (action == "collection-settings") await NavigateSection("collection-settings");
                    else if (action == "business-navigation") { tabs.SelectedTab = listTab; HighlightSection(Convert.ToString(command["section"])); }
                    else if (action == "update-rankings" && smokeOutput == null) await StartUpdate(command);
                    else if (action == "discover-categories" && smokeOutput == null) {
                        if (updating) return;
                        updating = true;
                        try {
                            ReportUpdate("正在读取账号可见服装类目…", true, false);
                            await ShowCompass(false);
                            var paths = await compass.DiscoverApparelCategories();
                            await LocalResult("pantsDesktop.setCategories(" + DesktopJson.Write(paths) + ")");
                            ReportUpdate("已读取 " + paths.Length + " 个服装类目，请勾选要采集的类目后更新。", false, false);
                        } catch (Exception error) {
                            if (compass != null && compass.NeedsLogin) OpenCompass();
                            ReportUpdate("类目未更新：" + error.Message, false, true);
                        } finally { updating = false; }
                    }
                    else if (action == "stop-update") { queuedUpdate = null; pendingLogin = null; if (compass != null) compass.RequestStop(); }
                } catch (Exception error) { ReportUpdate("操作失败：" + error.Message, false, true); }
            };
            view.CoreWebView2.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e) { e.Handled = true; OpenExternal(e.Uri); };
            view.CoreWebView2.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e) {
                if (e.Uri == AppUrl || e.Uri.StartsWith("blob:https://pants-workbench.example/", StringComparison.OrdinalIgnoreCase)) return;
                e.Cancel = true; OpenExternal(e.Uri);
            };
            view.CoreWebView2.DownloadStarting += OnDownload;
            view.CoreWebView2.NavigationCompleted += async delegate(object sender, CoreWebView2NavigationCompletedEventArgs e) {
                TestTrace("navigation completed: " + e.IsSuccess + " " + e.WebErrorStatus);
                if (!e.IsSuccess) { status.Text = "页面打开失败，可点击刷新重试。"; return; }
                status.Text = "桌面版 · 收藏保存在本机 · 当前展示已保存榜单";
                try {
                    if (File.Exists(dataFile)) {
                        var cache = DesktopJson.Object(File.ReadAllText(dataFile, Encoding.UTF8));
                        if (Convert.ToString(cache["schema"]) != "pants-desktop-collection-v1") throw new InvalidDataException("采集缓存格式不支持");
                        var snapshots = new List<object>(DesktopJson.Items(cache["snapshots"])).ToArray();
                        var cacheData = (Dictionary<string, object>)cache["data"];
                        var cacheMeta = (Dictionary<string, object>)cacheData["meta"];
                        await LocalResult("pantsDesktop.loadSnapshots(" + DesktopJson.Write(snapshots) + "," + DesktopJson.Write(cacheMeta["generated_at"]) + ")");
                        savedSnapshots = snapshots;
                        status.Text = "已加载你在客户端保存的榜单；登录状态和收藏保留在本机。";
                    }
                } catch (Exception error) { status.Text = "本机采集榜单读取失败，文件已保留：" + error.Message; }
                await LocalResult("pantsDesktop.setUpdateState(" + DesktopJson.Write(updateState) + ")");
                if (smokeOutput != null && !smokeStarted) {
                    smokeStarted = true;
                    if (unifiedSmoke) await UnifiedSmokeTest(); else if (updateSmoke) await UpdateSmokeTest(); else if (collectorSmoke) await CollectorSmokeTest(); else if (loginSmoke) await LoginSmokeTest(); else await SmokeTest();
                }
                if (openCompassAtStart) { openCompassAtStart = false; OpenCompass(); }
                if (smokeOutput == null && !startupUpdateDone) {
                    startupUpdateDone = true;
                    try {
                        var options = await LocalResult("pantsDesktop.getUpdateOptions()");
                        if (options.ContainsKey("auto_update") && (bool)options["auto_update"]) await StartUpdate(options);
                    } catch (Exception error) { ReportUpdate("未自动更新：" + error.Message + "。请调整采集设置后点击立即更新，已保存榜单保留。", false, true); }
                }
            };
            ready = true; view.CoreWebView2.Navigate(AppUrl);
            if (smokeOutput == null) updateTimer.Start();
        } catch (Exception error) {
            if (smokeOutput != null) {
                Directory.CreateDirectory(Path.GetDirectoryName(smokeOutput));
                File.WriteAllText(smokeOutput, "ERROR: " + error.ToString(), Encoding.UTF8); Environment.ExitCode = 1; Close();
            } else {
                status.Text = "未能打开桌面版";
                MessageBox.Show(this, "桌面版启动失败：\n" + error.Message + "\n\n请检查 Microsoft Edge WebView2 Runtime 是否已安装，或重新运行安装脚本。", "裤装选品工作台", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    private void OnDownload(object sender, CoreWebView2DownloadStartingEventArgs e)
    {
        if (smokeOutput != null) {
            e.ResultFilePath = Path.Combine(Path.GetDirectoryName(smokeOutput), "desktop-smoke-export.csv");
            e.Handled = true; testDownload = e.DownloadOperation; return;
        }
        var deferral = e.GetDeferral();
        BeginInvoke(new Action(delegate {
            try {
                using (var dialog = new SaveFileDialog()) {
                    dialog.FileName = Path.GetFileName(e.ResultFilePath);
                    dialog.InitialDirectory = DownloadsFolder();
                    dialog.Filter = "所有文件 (*.*)|*.*";
                    if (dialog.ShowDialog(this) == DialogResult.OK) { e.ResultFilePath = dialog.FileName; e.Handled = true; status.Text = "正在保存清单到所选位置。"; }
                    else { e.Cancel = true; e.Handled = true; }
                }
            } finally { deferral.Complete(); }
        }));
    }

    private static string DownloadsFolder()
    {
        string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads");
        return Directory.Exists(folder) ? folder : Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
    }
    private static void OpenDownloads() { Process.Start(new ProcessStartInfo(DownloadsFolder()) { UseShellExecute = true }); }
    private async void OpenCompass()
    {
        try { await ShowCompass(); }
        catch (Exception error) { status.Text = "罗盘页面未能打开：" + error.Message; }
    }

    private async Task ShowCompass(bool foreground = true)
    {
        if (!ready) return;
        if (foreground && tabs.SelectedTab != compassTab) { tabs.SelectedTab = compassTab; HighlightSection("compass"); }
        if (compass == null) {
            compass = new CompassPanel(async snapshot => { await LocalResult("pantsDesktop.prepareSnapshot(" + DesktopJson.Write(savedSnapshots) + "," + snapshot + ")"); }, SaveSnapshot, text => status.Text = text, collectorSmoke, Path.Combine(Path.GetDirectoryName(dataFile), "fixture"));
            compassTab.Controls.Add(compass);
        }
        await compass.Initialize(environment);
    }

    private async Task<Dictionary<string, object>> LocalResult(string expression)
    {
        if (view.Source == null || view.Source.AbsoluteUri != AppUrl) throw new InvalidOperationException("选品页面尚未就绪，请稍后重试。");
        var result = DesktopJson.Object(await view.CoreWebView2.ExecuteScriptAsync("(() => { try { return {ok:true,result:" + expression + "}; } catch(e) { return {ok:false,error:e.message}; } })()"));
        if (!(bool)result["ok"]) throw new InvalidOperationException(Convert.ToString(result["error"]));
        return (Dictionary<string, object>)result["result"];
    }

    private async Task<string> SaveSnapshot(string snapshot)
    {
        var prepared = await LocalResult("pantsDesktop.prepareSnapshot(" + DesktopJson.Write(savedSnapshots) + "," + snapshot + ")");
        return await SavePrepared(prepared);
    }

    private async Task<string> SavePrepared(Dictionary<string, object> prepared)
    {
        var next = new List<object>(DesktopJson.Items(prepared["snapshots"])).ToArray();
        var cache = new Dictionary<string, object> { {"schema", "pants-desktop-collection-v1"}, {"snapshots", next}, {"data", prepared["data"]} };
        Directory.CreateDirectory(Path.GetDirectoryName(dataFile));
        string pending = dataFile + ".tmp";
        File.WriteAllText(pending, DesktopJson.Write(cache), new UTF8Encoding(false));
        if (File.Exists(dataFile)) File.Replace(pending, dataFile, null); else File.Move(pending, dataFile);
        savedSnapshots = next;
        var data = (Dictionary<string, object>)prepared["data"];
        var meta = (Dictionary<string, object>)data["meta"];
        try { await LocalResult("pantsDesktop.loadSnapshots(" + DesktopJson.Write(next) + "," + DesktopJson.Write(meta["generated_at"]) + ")"); }
        catch (Exception) { view.Reload(); }
        tabs.SelectedTab = listTab;
        if (activeNativeSection == "compass") await NavigateSection("workbench");
        return ((bool)prepared["replaced_context"] ? "账号或周期已变化，已建立新榜单；" : "") + "已保存「" + Convert.ToString(meta["observed_identity"]) + "」" + new List<object>(DesktopJson.Items(data["products"])).Count + " 条商品";
    }

    private async Task LoginSmokeTest()
    {
        try {
            await StartUpdate(await LocalResult("pantsDesktop.getUpdateOptions()"));
            string page = "{}";
            for (int attempt = 0; attempt < 120; attempt++) {
                page = await compass.Browser.CoreWebView2.ExecuteScriptAsync("({url:location.origin+location.pathname,title:document.title,ready:document.readyState,text:document.body?.innerText.slice(0,800) || ''})");
                var state = DesktopJson.Object(page);
                if (Convert.ToString(state["text"]).Contains("登录") || Convert.ToString(state["text"]).Contains("扫码")) break;
                await Task.Delay(200);
            }
            // The sign-in shell appears before its QR image finishes loading.
            await Task.Delay(5000);
            var loginState = DesktopJson.Object(await compass.Browser.CoreWebView2.ExecuteScriptAsync("({url:location.origin+location.pathname,title:document.title,ready:document.readyState,text:document.body?.innerText.slice(0,800) || '',visibleImages:Array.from(document.images).filter(el => el.getClientRects().length).map(el => ({loaded:el.complete,width:el.naturalWidth,height:el.naturalHeight})),visibleFrames:document.querySelectorAll('iframe').length})"));
            loginState["pendingUpdate"] = pendingLogin != null; loginState["updateState"] = updateState;
            page = DesktopJson.Write(loginState);
            Directory.CreateDirectory(Path.GetDirectoryName(smokeOutput));
            File.WriteAllText(smokeOutput, page, new UTF8Encoding(false));
            using (var stream = File.Create(Path.ChangeExtension(smokeOutput, ".png"))) await compass.Browser.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream);
        } catch (Exception error) { File.WriteAllText(smokeOutput, "ERROR: " + error.ToString(), Encoding.UTF8); Environment.ExitCode = 1; }
        Close();
    }

    private async Task CollectorSmokeTest()
    {
        try {
            await ShowCompass();
            for (int attempt = 0; attempt < 100; attempt++) {
                if (await compass.Browser.CoreWebView2.ExecuteScriptAsync("document.querySelectorAll('tbody tr[data-row-key]').length") == "2") break;
                await Task.Delay(100);
            }
            bool first = await compass.CaptureCurrentPage();
            var firstState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length, links:document.querySelectorAll('#cards .product-title').length})");
            bool repeated = await compass.CaptureCurrentPage();
            var repeatedState = await LocalResult("({count:document.querySelectorAll('#cards .product-card').length})");
            string saved = File.ReadAllText(dataFile, Encoding.UTF8);
            await compass.Browser.CoreWebView2.ExecuteScriptAsync("document.querySelector('table').remove()");
            bool rejected = !await compass.CaptureCurrentPage();
            bool preserved = saved == File.ReadAllText(dataFile, Encoding.UTF8);
            var disk = DesktopJson.Object(saved);
            var restored = await LocalResult("pantsDesktop.loadSnapshots(" + DesktopJson.Write(disk["snapshots"]) + ")");
            var result = new Dictionary<string, object> { {"firstSaved", first}, {"firstState", firstState}, {"rereadSaved", repeated}, {"rereadState", repeatedState}, {"invalidPageRejected", rejected}, {"previousDataPreserved", preserved}, {"restoredFromDisk", restored}, {"testUsesIsolatedProfileAndFixture", true} };
            if (!first || !repeated || !rejected || !preserved || Convert.ToInt32(firstState["count"]) != 2 || Convert.ToInt32(firstState["links"]) != 2 || Convert.ToInt32(repeatedState["count"]) != 2) throw new InvalidOperationException("客户端采集验证失败：" + DesktopJson.Write(result));
            Directory.CreateDirectory(Path.GetDirectoryName(smokeOutput));
            File.WriteAllText(smokeOutput, DesktopJson.Write(result), new UTF8Encoding(false));
            tabs.SelectedTab = listTab;
            using (var stream = File.Create(Path.ChangeExtension(smokeOutput, ".png"))) await view.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream);
        } catch (Exception error) { File.WriteAllText(smokeOutput, "ERROR: " + error.ToString(), Encoding.UTF8); Environment.ExitCode = 1; }
        Close();
    }
    private static void OpenExternal(string value)
    {
        Uri uri;
        if (!Uri.TryCreate(value, UriKind.Absolute, out uri) || (uri.Scheme != "https" && uri.Scheme != "http")) return;
        try { Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true }); } catch (System.ComponentModel.Win32Exception) { }
    }

    private async Task SmokeTest()
    {
        try {
            string result = await view.CoreWebView2.ExecuteScriptAsync(@"(() => {
                const count = () => document.querySelectorAll('#cards .product-card').length;
                const total = count();
                document.getElementById('women').click(); const women = count();
                document.getElementById('men').click(); const men = count();
                document.getElementById('all').click();
                document.getElementById('floor').value = '100';
                document.getElementById('ceiling').value = '200';
                document.getElementById('price-basis').value = 'price_band';
                document.getElementById('generate').click(); const band100to200 = count();
                document.getElementById('women').click(); const women100to200 = count();
                document.getElementById('men').click(); const men100to200 = count();
                document.getElementById('reset').click();
                document.getElementById('ceiling').value = '100';
                document.getElementById('ceiling').dispatchEvent(new Event('change', { bubbles: true }));
                const changeMax100 = count();
                document.getElementById('query').value = '__no_match_in_filter_smoke__';
                document.getElementById('query').dispatchEvent(new Event('input', { bubbles: true })); const emptyCount = count();
                document.getElementById('reset').click(); const resetCount = count();
                return { title: document.title, total, women, men, band100to200, women100to200, men100to200, changeMax100, emptyCount, resetCount,
                  source: document.getElementById('source').textContent,
                  downloadEnabled: !document.getElementById('download').disabled,
                  storage: (() => { localStorage.setItem('desktop-smoke', 'ok'); const ok = localStorage.getItem('desktop-smoke') === 'ok'; localStorage.removeItem('desktop-smoke'); return ok; })() };
            })()");
            Directory.CreateDirectory(Path.GetDirectoryName(smokeOutput));
            await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('csv-download').click()");
            for (int attempt = 0; attempt < 100 && (testDownload == null || testDownload.State == CoreWebView2DownloadState.InProgress); attempt++) await Task.Delay(50);
            bool downloaded = testDownload != null && testDownload.State == CoreWebView2DownloadState.Completed && File.Exists(Path.Combine(Path.GetDirectoryName(smokeOutput), "desktop-smoke-export.csv"));
            result = result.TrimEnd('}') + ",\"downloadSaved\":" + (downloaded ? "true" : "false") + "}";
            File.WriteAllText(smokeOutput, result, new UTF8Encoding(false));
            using (var stream = File.Create(Path.ChangeExtension(smokeOutput, ".png"))) await view.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream);
            SaveWindowPreview();
        } catch (Exception error) { File.WriteAllText(smokeOutput, "ERROR: " + error.ToString(), Encoding.UTF8); Environment.ExitCode = 1; }
        Close();
    }
}
