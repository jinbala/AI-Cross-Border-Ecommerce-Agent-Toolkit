using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

internal sealed partial class WorkbenchForm
{
    private readonly List<Process> businessProcesses = new List<Process>();
    private void TestTrace(string message)
    {
        if (smokeOutput == null) return;
        Directory.CreateDirectory(Path.GetDirectoryName(smokeOutput));
        File.AppendAllText(Path.ChangeExtension(smokeOutput, ".trace"), DateTime.Now.ToString("HH:mm:ss") + " " + message + Environment.NewLine);
    }
    private string BusinessFolder {
        get {
            if (smokeOutput != null) return Path.Combine(Path.GetDirectoryName(smokeOutput), "business-test-data");
            string explicitPath = Environment.GetEnvironmentVariable("GARMENT_WORKBENCH_DATA");
            return String.IsNullOrWhiteSpace(explicitPath) ? Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "data") : Path.GetFullPath(explicitPath);
        }
    }

    private async Task<Dictionary<string, object>> BusinessCall(string command, Dictionary<string, object> args)
    {
        TestTrace("backend request " + command);
        string helper = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "backend", "GarmentBackend.exe");
        if (!File.Exists(helper)) throw new FileNotFoundException("经营组件缺失，请完整解压软件目录。");
        var info = new ProcessStartInfo(helper, "--data-dir \"" + BusinessFolder + "\"") {
            UseShellExecute = false, CreateNoWindow = true, WindowStyle = ProcessWindowStyle.Hidden,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        using (var process = new Process { StartInfo = info }) {
            process.Start(); lock (businessProcesses) businessProcesses.Add(process);
            try {
                byte[] request = new UTF8Encoding(false).GetBytes(DesktopJson.Write(new Dictionary<string, object> { {"command", command}, {"args", args} }));
                await process.StandardInput.BaseStream.WriteAsync(request, 0, request.Length);
                process.StandardInput.Close();
                TestTrace("backend input sent " + command);
                var output = process.StandardOutput.ReadToEndAsync();
                var error = process.StandardError.ReadToEndAsync();
                var exit = Task.Run(() => process.WaitForExit());
                if (await Task.WhenAny(exit, Task.Delay(command == "generate_ai" ? 180000 : 45000)) != exit) {
                    try { process.Kill(); } catch (InvalidOperationException) { }
                    throw new TimeoutException("处理超时，请稍后重试；已保存资料保留。");
                }
                string response = await output; await error;
                TestTrace("backend completed " + command);
                if (process.ExitCode != 0 || String.IsNullOrWhiteSpace(response)) throw new InvalidOperationException("经营组件未返回结果，请检查软件目录是否可写。");
                return DesktopJson.Object(response);
            } finally { lock (businessProcesses) businessProcesses.Remove(process); }
        }
    }

    private void StopBusinessProcesses()
    {
        lock (businessProcesses) foreach (var process in businessProcesses) {
            try { if (!process.HasExited) process.Kill(); } catch (InvalidOperationException) { }
        }
    }

    private async Task HandleBusinessMessage(Dictionary<string, object> message)
    {
        string id = Convert.ToString(message["id"]), command = Convert.ToString(message["command"]);
        var response = new Dictionary<string, object>();
        try {
            var args = message.ContainsKey("args") ? (Dictionary<string, object>)message["args"] : new Dictionary<string, object>();
            // File paths are selected in native dialogs, never accepted from a web page.
            if (args.ContainsKey("path") || args.ContainsKey("points_path")) throw new InvalidOperationException("请通过软件中的文件选择按钮打开文件。");
            if (command == "backup" || command == "export_report") {
                bool csv = command == "export_report" && args.ContainsKey("format") && Convert.ToString(args["format"]) == "csv";
                string fileName = command == "backup" ? "服装生意备份-" + DateTime.Now.ToString("yyyyMMdd") + ".json" : csv ? "工作台模板.csv" : "工作台报告.md";
                if (command == "export_report" && args.ContainsKey("filename")) fileName = Path.GetFileName(Convert.ToString(args["filename"]));
                using (var dialog = new SaveFileDialog { Filter = command == "backup" ? "经营数据备份|*.json" : csv ? "CSV 表格|*.csv" : "Markdown 文档|*.md", FileName = fileName, AddExtension = true }) {
                    if (dialog.ShowDialog(this) != DialogResult.OK) { response["ok"] = true; response["data"] = new Dictionary<string, object> { {"cancelled", true} }; }
                    else if (command == "export_report") {
                        File.WriteAllText(dialog.FileName, Convert.ToString(args["content"]), new UTF8Encoding(csv));
                        response["ok"] = true; response["data"] = new Dictionary<string, object> { {"message", "文档已导出。"} };
                    } else { args["path"] = dialog.FileName; response = await BusinessCall(command, args); }
                }
            } else if (command == "restore" || command == "import_file" || command == "market_report" || command == "video_import" || command == "review_import" || command == "points_import") {
                string filter = command == "restore" ? "经营数据备份|*.json" : command == "market_report" || command == "review_import" || command == "points_import" ? "CSV / TSV 表格|*.csv;*.tsv" : command == "video_import" ? "TXT 配音稿|*.txt" : "选品表格|*.xlsx;*.csv;*.tsv";
                using (var dialog = new OpenFileDialog { Filter = filter }) {
                    if (dialog.ShowDialog(this) != DialogResult.OK) { response["ok"] = true; response["data"] = new Dictionary<string, object> { {"cancelled", true} }; }
                    else { args["path"] = dialog.FileName; response = await BusinessCall(command, args); }
                }
            } else {
                if (args.ContainsKey("path")) throw new InvalidOperationException("请通过软件中的文件选择按钮打开文件。");
                response = await BusinessCall(command, args);
            }
        } catch (Exception error) { response = new Dictionary<string, object> { {"ok", false}, {"error", error.Message} }; }
        response["id"] = id;
        if (!IsDisposed && view.Source != null && view.Source.AbsoluteUri == AppUrl)
            await view.CoreWebView2.ExecuteScriptAsync("window.businessUI && businessUI.receive(" + DesktopJson.Write(response) + ")");
    }

    private async Task UnifiedSmokeTest()
    {
        TestTrace("unified smoke entered");
        try {
            var baseline = await BusinessCall("state", new Dictionary<string, object>());
            if (!(bool)baseline["ok"]) throw new InvalidOperationException("后台启动检查失败");
            await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('demo').click()");
            string result = await view.CoreWebView2.ExecuteScriptAsync("businessUI.runSmoke()");
            for (int attempt = 0; attempt < 300; attempt++) {
                result = await view.CoreWebView2.ExecuteScriptAsync("window.unifiedSmokeResult || null");
                if (result != "null") break;
                await Task.Delay(100);
            }
            var output = DesktopJson.Object(result);
            if (!output.ContainsKey("passed") || !(bool)output["passed"]) throw new InvalidOperationException(DesktopJson.Write(output));
            Directory.CreateDirectory(Path.GetDirectoryName(smokeOutput));
            File.WriteAllText(smokeOutput, DesktopJson.Write(output), new UTF8Encoding(false));
            using (var stream = File.Create(Path.ChangeExtension(smokeOutput, ".png")))
                await view.CoreWebView2.CapturePreviewAsync(Microsoft.Web.WebView2.Core.CoreWebView2CapturePreviewImageFormat.Png, stream);
            SaveWindowPreview();
            foreach (string page in new[] { "pricing", "workbench", "checks-video", "checks-reviews" }) {
                if (page == "workbench") await NavigateSection(page);
                else {
                    string preview = page == "pricing" ? "businessUI.navigate('pricing')" : "businessUI.previewTool(" + DesktopJson.Write(page == "checks-video" ? "video" : "reviews") + ")";
                    await view.CoreWebView2.ExecuteScriptAsync("window.businessPreviewReady=false; " + preview + ".then(()=>window.businessPreviewReady=true)");
                    for (int attempt = 0; attempt < 100; attempt++) {
                        if (await view.CoreWebView2.ExecuteScriptAsync("window.businessPreviewReady===true") == "true") break;
                        await Task.Delay(100);
                    }
                }
                await Task.Delay(150);
                using (var stream = File.Create(Path.ChangeExtension(smokeOutput, "." + page + ".png")))
                    await view.CoreWebView2.CapturePreviewAsync(Microsoft.Web.WebView2.Core.CoreWebView2CapturePreviewImageFormat.Png, stream);
                if (page.StartsWith("checks-")) SaveWindowPreview("." + page);
                if (page == "workbench") {
                    await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('factory-sales').value='100';document.getElementById('factory-conversion').value='3';document.getElementById('factory-only').checked=false;applyView();document.getElementById('list-heading').scrollIntoView({block:'start',behavior:'instant'})");
                    await Task.Delay(150);
                    using (var stream = File.Create(Path.ChangeExtension(smokeOutput, ".states.png")))
                        await view.CoreWebView2.CapturePreviewAsync(Microsoft.Web.WebView2.Core.CoreWebView2CapturePreviewImageFormat.Png, stream);
                }
            }
        } catch (Exception error) {
            File.WriteAllText(smokeOutput, "ERROR: " + error.ToString(), Encoding.UTF8); Environment.ExitCode = 1;
        }
        Close();
    }
}
