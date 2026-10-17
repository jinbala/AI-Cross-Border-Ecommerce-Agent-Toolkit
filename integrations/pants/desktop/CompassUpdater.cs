using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Web.WebView2.Core;

internal sealed class CompassUpdateOptions
{
    internal string Period;
    internal int Limit;
    internal string[][] Paths;
    internal string[] PriceQueries;
    internal bool CollectLinks = true;

    internal static CompassUpdateOptions Parse(Dictionary<string, object> input)
    {
        string preset = Convert.ToString(input["preset"]), period = Convert.ToString(input["period"]);
        int limit = Convert.ToInt32(input["limit"]);
        string[] priceQueries = input.ContainsKey("price_queries") ? DesktopJson.Items(input["price_queries"]).Select(Convert.ToString).Distinct().ToArray() : new[] { "all" };
        if (priceQueries.Length == 0 || priceQueries.Length > 5 || priceQueries.Any(q => !new[] { "all", "0-50", "50-70", "70-99", "99-150", "150+" }.Contains(q)) || (priceQueries.Contains("all") && priceQueries.Length != 1)) throw new InvalidOperationException("价位查询配置无效");
        if (!new[] { "common", "women", "men", "all", "custom" }.Contains(preset) || !new[] { "近1天", "近7天", "近30天" }.Contains(period) || !new[] { 10, 20, 50, 200 }.Contains(limit)) throw new InvalidOperationException("请选择有效的更新范围、周期和读取数量。");
        var catalog = DesktopJson.Object(File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "assets", "compass-categories.json")));
        var paths = DesktopJson.Items(catalog["anchors"]).Cast<Dictionary<string, object>>()
            .SelectMany(anchor => DesktopJson.Items(anchor["scan_nodes"]))
            .Select(path => DesktopJson.Items(path).Select(Convert.ToString).ToArray())
            .Where(path => preset == "all" || (preset == "women" && path[2] == "女装") || (preset == "men" && path[2] == "男装") || (preset == "common" && ((path[2] == "女装" && path[3] == "牛仔裤") || (path[2] == "男装" && path[3] == "休闲裤")))).ToArray();
        if (preset == "custom") paths = DesktopJson.Items(input["category_paths"]).Select(path => DesktopJson.Items(path).Select(Convert.ToString).ToArray()).GroupBy(path => DesktopJson.Write(path)).Select(group => group.First()).ToArray();
        if (paths.Length == 0 || paths.Length > 64 || paths.Any(path => path.Length != 4 || path.Contains("全部") || path.Any(part => String.IsNullOrWhiteSpace(part) || part.Length > 100) || path[0] != "服饰内衣" || path[1] != "服装" || !new[] {"男装", "女装"}.Contains(path[2]))) throw new InvalidDataException("请选择 1—64 个有效服装类目");
        if (input.ContainsKey("collect_links") && !(input["collect_links"] is bool)) throw new InvalidOperationException("商品链接采集选项无效");
        return new CompassUpdateOptions { Period = period, Limit = limit, Paths = paths, PriceQueries = priceQueries, CollectLinks = !input.ContainsKey("collect_links") || (bool)input["collect_links"] };
    }
}

internal sealed partial class CompassPanel
{
    internal async Task<string[][]> DiscoverApparelCategories()
    {
        if (collecting) throw new InvalidOperationException("请等待当前采集完成，再读取类目");
        collecting = true; cancelled = false; NeedsLogin = false; web.Enabled = false; save.Enabled = false; cancel.Enabled = true;
        try {
            await RefreshOnline();
            var paths = new List<string[]>();
            foreach (string gender in new[] {"女装", "男装"}) {
                await ClickCategory(new[] {"服饰内衣", "服装", gender});
                await Task.Delay(600);
                var result = await PageAction("category-children", null);
                var names = DesktopJson.Items(result["names"]).Select(Convert.ToString).ToArray();
                if (names.Length == 0 || names.Length > 100) throw new InvalidOperationException("未能读取服装子类目，请在罗盘确认账号权限和类目菜单");
                paths.AddRange(names.Select(name => new[] {"服饰内衣", "服装", gender, name}));
                await PageAction("category-item", names[0]);
                await Task.Delay(200);
            }
            if (cancelled) throw new OperationCanceledException("已停止读取类目");
            return paths.ToArray();
        } finally { collecting = false; navigationAllowed = false; web.Enabled = true; save.Enabled = true; cancel.Enabled = false; }
    }

    private bool navigationAllowed;
    private Action<string> batchProgress;
    private string navigationSource;
    internal bool NeedsLogin { get; private set; }
    internal bool AtLogin { get { return web.Source != null && web.Source.Host == "compass.jinritemai.com" && web.Source.AbsolutePath.Contains("login"); } }
    internal async Task<bool> IsSignedIn()
    {
        try {
            if (web.Source == null || web.CoreWebView2 == null || web.Source.Host != "compass.jinritemai.com" || web.Source.AbsolutePath.Contains("login")) return false;
            return await web.CoreWebView2.ExecuteScriptAsync("Array.from(document.querySelectorAll('[class^=\"userName-\"]')).some(el => el.getClientRects().length && el.innerText.trim())") == "true";
        } catch (Exception) { return false; }
    }

    internal void RequestStop()
    {
        cancelled = true;
        message.Text = "正在停止，本次更新不会覆盖已保存榜单。";
    }

    private async Task<Dictionary<string, object>> PageAction(string action, object value)
    {
        if (navigationSource == null) navigationSource = File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "assets", "compass-navigation.js"));
        var result = DesktopJson.Object(await web.CoreWebView2.ExecuteScriptAsync("(() => {try{return {ok:true,result:(" + navigationSource + ")(" + DesktopJson.Write(action) + "," + DesktopJson.Write(value) + ")};}catch(e){return {ok:false,error:e.message};}})()"));
        if (!(bool)result["ok"]) throw new InvalidOperationException(Convert.ToString(result["error"]));
        return (Dictionary<string, object>)result["result"];
    }

    private async Task RefreshOnline()
    {
        navigationAllowed = true;
        ulong navigationId = 0; bool navigationFinished = false;
        EventHandler<CoreWebView2NavigationStartingEventArgs> starting = delegate(object sender, CoreWebView2NavigationStartingEventArgs e) { navigationId = e.NavigationId; navigationFinished = false; };
        EventHandler<CoreWebView2NavigationCompletedEventArgs> completed = delegate(object sender, CoreWebView2NavigationCompletedEventArgs e) { if (e.NavigationId == navigationId && e.IsSuccess) navigationFinished = true; };
        web.CoreWebView2.NavigationStarting += starting;
        web.CoreWebView2.NavigationCompleted += completed;
        try {
            web.CoreWebView2.Navigate(HomeUrl);
            for (int i = 0; i < 80; i++) {
                if (cancelled) throw new OperationCanceledException();
                if (AtLogin) { NeedsLogin = true; throw new InvalidOperationException("请在“罗盘账号”完成登录，登录后会继续更新。原榜单已保留。"); }
                if (navigationFinished && AtRankingPage()) {
                    var state = await PageAction("ready", null);
                    if ((bool)state["ready"] && !(bool)state["loading"]) return;
                }
                await Task.Delay(250);
            }
            throw new TimeoutException("商品榜尚未就绪；请检查网络及账号权限，再重试。");
        } finally { navigationAllowed = false; web.CoreWebView2.NavigationStarting -= starting; web.CoreWebView2.NavigationCompleted -= completed; }
    }

    private async Task ClickCategory(string[] path)
    {
        await PageAction("category-open", null);
        foreach (string part in path) {
            bool clicked = false;
            for (int i = 0; i < 40; i++) {
                if (cancelled) throw new OperationCanceledException();
                if ((bool)(await PageAction("category-item", part))["clicked"]) { clicked = true; break; }
                await Task.Delay(200);
            }
            if (!clicked) throw new InvalidOperationException("找不到类目「" + part + "」，请检查账号可见类目或使用当前页保存。");
            await Task.Delay(150);
        }
    }

    private async Task<Dictionary<string, object>> WaitPriceAction(string action, object value)
    {
        for (int i = 0; i < 60; i++) {
            if (cancelled) throw new OperationCanceledException();
            var state = await PageAction(action, value);
            if (!state.ContainsKey("pending") || !(bool)state["pending"]) return state;
            await Task.Delay(200);
        }
        throw new TimeoutException("罗盘价位选项尚未加载或弹窗未就绪，请稍后重试。");
    }

    private async Task<bool> SelectPrice(string query)
    {
        var selection = await WaitPriceAction("price", query);
        bool custom = (bool)selection["custom"];
        if (custom) {
            await WaitPriceAction("price-custom-fill", query);
            await Task.Delay(250);
            await WaitPriceAction("price-custom-confirm", query);
            await WaitPriceAction("price-custom-reopen", query);
            await WaitPriceAction("price-custom-verify", query);
        }
        for (int i = 0; i < 60; i++) {
            if (cancelled) throw new OperationCanceledException();
            if ((bool)(await PageAction("price-state", new { query = query, custom = custom }))["applied"]) return custom;
            await Task.Delay(200);
        }
        throw new TimeoutException("罗盘没有确认所选价位，本次未覆盖旧榜单：" + query);
    }

    private async Task<Dictionary<string, object>> WaitForPage(string[] path, string period, int page, int afterRank)
    {
        string fingerprint = null; int stable = 0;
        await Task.Delay(600);
        for (int i = 0; i < 60; i++) {
            if (cancelled) throw new OperationCanceledException();
            if (!AtRankingPage()) throw new InvalidOperationException("登录或页面状态发生变化，本次更新未保存。");
            try {
                var state = await PageAction("ready", null);
                if ((bool)state["ready"] && !(bool)state["loading"]) {
                    var snapshot = await ReadSnapshot();
                    string[] tabs = DesktopJson.Items(snapshot["selected_tabs"]).Select(Convert.ToString).ToArray();
                    bool empty = snapshot.ContainsKey("empty_state_text") && !DesktopJson.Items(snapshot["rows"]).Any();
                    int minRank = empty ? 0 : DesktopJson.Items(snapshot["rows"]).Cast<Dictionary<string, object>>().Min(row => Int32.Parse(Convert.ToString(row["row_key"]).Split('_')[1]));
                    if (DesktopJson.Write(snapshot["category_path"]) == DesktopJson.Write(path) && tabs.SequenceEqual(new[] { "总榜", period }) && ((empty && page == 1) || (Convert.ToInt32(snapshot["page_number"]) == page && minRank > afterRank))) {
                        string current = Fingerprint(snapshot);
                        stable = current == fingerprint ? stable + 1 : 1; fingerprint = current;
                        if (stable >= 3) return snapshot;
                    } else { stable = 0; fingerprint = null; }
                } else { stable = 0; fingerprint = null; }
            } catch (OperationCanceledException) { throw; }
            catch (Exception) { stable = 0; fingerprint = null; }
            await Task.Delay(250);
        }
        throw new TimeoutException("「" + String.Join(" / ", path.Skip(2)) + "」第 " + page + " 页未稳定加载，本次未覆盖旧榜单。");
    }

    internal async Task<bool> UpdateRankings(CompassUpdateOptions options, Func<string, Task<string>> persistBatch, Action<string, bool, bool> progress)
    {
        if (collecting) return false;
        collecting = true; cancelled = false; NeedsLogin = false; save.Enabled = false; cancel.Enabled = true; web.Enabled = false;
        var snapshots = new List<object>();
        string context = null, stage = "正在联网刷新罗盘…";
        batchProgress = text => { message.Text = stage + " · " + text; progress(message.Text, true, false); };
        try {
            progress(stage, true, false);
            await RefreshOnline();
            await PageAction("tab", "总榜"); await PageAction("tab", options.Period);
            await PageAction("reset-filters", null);
            for (int categoryIndex = 0; categoryIndex < options.Paths.Length; categoryIndex++) {
                string[] path = options.Paths[categoryIndex];
                stage = "类目 " + (categoryIndex + 1) + "/" + options.Paths.Length + " · " + String.Join(" / ", path.Skip(2));
                progress(stage + " · 正在选择类目…", true, false);
                await ClickCategory(path);
                await WaitForPage(path, options.Period, 1, 0);
                foreach (string priceQuery in options.PriceQueries) {
                bool customPrice = await SelectPrice(priceQuery);
                await Task.Delay(400);
                if (!(bool)(await PageAction("first-page", null))["clicked"]) throw new InvalidOperationException("无法返回榜单第一页");
                int page = 1, lastRank = 0;
                while (page <= 200) {
                    var readyPage = await WaitForPage(path, options.Period, page, lastRank);
                    string actualContext = DesktopJson.Write(new object[] { readyPage["observed_identity"], readyPage["dates"], readyPage["selected_tabs"] });
                    if (context != null && context != actualContext) throw new InvalidOperationException("店铺或统计周期发生变化，本次更新未保存。");
                    context = actualContext;
                    stage = "类目 " + (categoryIndex + 1) + "/" + options.Paths.Length + " · " + String.Join(" / ", path.Skip(2)) + " · 价位 " + priceQuery + " · 第 " + page + " 页";
                    progress(stage + " · 已读 " + snapshots.Sum(s => DesktopJson.Items(((Dictionary<string, object>)s)["rows"]).Count()) + " 条 · " + (options.CollectLinks ? "读取榜单及链接…" : "快速读取榜单…"), true, false);
                    var captured = await ReadLinkedSnapshot(options.Limit, options.CollectLinks);
                    if (Fingerprint(captured) != Fingerprint(readyPage) && DesktopJson.Items(captured["rows"]).Count() == DesktopJson.Items(readyPage["rows"]).Count()) throw new InvalidOperationException("榜单在读取期间发生变化，本次未保存。");
                    captured["source_filters"] = new Dictionary<string, object> { {"price_band", priceQuery}, {"price_band_mode", customPrice ? "custom" : "preset"}, {"price_band_label", (customPrice ? "自定义 " : "") + (priceQuery == "all" ? "不限价格" : priceQuery == "150+" ? "150 元以上" : priceQuery + " 元") + (customPrice ? "（按罗盘口径）" : "")} };
                    snapshots.Add(captured);
                    if (!DesktopJson.Items(captured["rows"]).Any()) break;
                    lastRank = DesktopJson.Items(captured["rows"]).Cast<Dictionary<string, object>>().Max(row => Int32.Parse(Convert.ToString(row["row_key"]).Split('_')[1]));
                    int sourceTotal = Int32.Parse(System.Text.RegularExpressions.Regex.Match(Convert.ToString(captured["total_text"]), @"\d+").Value);
                    if (lastRank >= options.Limit || lastRank >= sourceTotal) break;
                    var next = await PageAction("next-page", null);
                    if ((bool)next["end"]) throw new InvalidOperationException("平台总条数与下一页状态不一致，本次未覆盖旧榜单。");
                    page++;
                }
                }
            }
            if (cancelled) throw new OperationCanceledException();
            string saved = await persistBatch(DesktopJson.Write(snapshots));
            int rows = snapshots.Cast<Dictionary<string, object>>().Sum(s => DesktopJson.Items(s["rows"]).Count());
            int links = snapshots.Cast<Dictionary<string, object>>().Sum(s => DesktopJson.Items(s["rows"]).Cast<Dictionary<string, object>>().Count(row => !String.IsNullOrEmpty(Convert.ToString(row["product_link"]))));
            string done = "更新完成：" + rows + " 条商品、" + options.Paths.Length + " 个类目、" + snapshots.Count + " 页；商品链接 " + links + " 条。" + (!options.CollectLinks ? "本次为快速读榜，未逐件补链接。" : links < rows ? "缺失链接已标注。" : "") + saved;
            message.Text = done; progress(done, false, false); return true;
        } catch (OperationCanceledException) { message.Text = "已停止更新，本次未覆盖之前保存的榜单。"; progress(message.Text, false, false); return false; }
        catch (Exception error) { message.Text = "更新未完成：" + error.Message + " 之前保存的榜单保留。"; progress(message.Text, false, true); return false; }
        finally { batchProgress = null; collecting = false; navigationAllowed = false; productNavigation = null; expectedProduct = null; web.Enabled = true; save.Enabled = true; cancel.Enabled = false; }
    }
}
