"""Exercise the real Tk application without live network requests or real business data."""
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from desktop_app.app import Workbench, tk, ttk, content, put

BUILD = Path(__file__).resolve().parents[1] / ".build" / "tests"
BUILD.mkdir(parents=True, exist_ok=True)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def click(app, title):
    widgets = [w for w in descendants(app) if isinstance(w, tk.Button) and w.cget("text") == title]
    assert len(widgets) == 1, (title, len(widgets))
    widgets[0].invoke()
    app.update()


def assert_actions_fit(app):
    for control in descendants(app.page):
        if not isinstance(control, tk.Button):
            continue
        parent = control.master
        clipped = False
        while parent is not app:
            if isinstance(parent, tk.Canvas):
                clipped = True  # Long forms are intentionally scrollable.
            if isinstance(parent.master, ttk.Notebook) and str(parent.master.select()) != str(parent):
                clipped = True  # Inactive tabs are intentionally unmapped.
            parent = parent.master
        if clipped:
            continue
        context = (app.screen, control.cget("text"))
        assert control.winfo_ismapped(), context
        assert control.winfo_width() + 2 >= control.winfo_reqwidth(), context
        assert control.winfo_rootx() + control.winfo_width() <= app.winfo_rootx() + app.winfo_width(), context
        assert control.winfo_rooty() + control.winfo_height() <= app.winfo_rooty() + app.winfo_height(), context


def main():
    with tempfile.TemporaryDirectory(dir=BUILD) as directory:
        app = Workbench(Path(directory))
        app.withdraw()
        errors = []
        app.report_callback_exception = lambda typ, value, tb: errors.append(str(value))
        with patch("desktop_app.app.messagebox.showerror") as error, patch("desktop_app.app.messagebox.showinfo"), patch("desktop_app.app.messagebox.askyesnocancel", return_value=False):
            app.show("products")
            app.product_vars["name"].set("GUI 测试衬衫")
            app.product_vars["sku"].set("TEST-001")
            app.product_vars["cost"].set("20")
            app.product_vars["supply_price"].set("30")
            click(app, "保存档案")
            assert len(app.store.list("product")) == 1
            app.show("pricing")
            app.pricing_vars["price"].set("30")
            app.pricing_vars["production"].set("20")
            click(app, "计算利润与报价")
            assert "10.00" in app.last_pricing
            click(app, "保存报告")
            assert len(app.store.list("artifact")) == 1
            app.show("workflows")
            click(app, "生成任务包")
            assert "# 项目参考流程" in content(app.workflow_widgets["prompt"])
            click(app, "保存到成果库")
            assert len(app.store.list("artifact")) == 2
            app.store.set_setting("api_base", "https://example.test/v1")
            app.store.set_setting("api_model", "fake")
            with patch("desktop_app.app.core.call_ai", return_value="GUI 模拟生成成功"):
                click(app, "用已配置模型生成")
                # Navigate away while generation completes, then process its queue.
                app.show("dashboard")
                for _ in range(20):
                    time.sleep(.05)
                    app.update()
                    if not app.ai_running:
                        break
                assert not app.ai_running
                assert any(x["content"] == "GUI 模拟生成成功" for x in app.store.list("artifact"))
            app.show("workflows")
            assert content(app.workflow_widgets["result"]) == "GUI 模拟生成成功"
            app.show("selection_advanced")
            sample = Path(directory) / "selection.csv"
            sample.write_text("ASIN,标题,月销量,评分\nTEST-ASIN,测试候选,1200,3.2\n", encoding="utf-8-sig")
            app.selection_metadata["market"].set("US")
            with patch("desktop_app.app.filedialog.askopenfilename", return_value=str(sample)):
                click(app, "导入并筛选")
            assert app.selection_screening["counts"]["符合筛选"] == 1
            result_tree, pool_tree = app.selection_trees
            result_tree.selection_set("0")
            click(app, "加入候选池")
            saved = app.store.list("candidate")
            assert len(saved) == 1
            pool_tree.selection_set(saved[0]["id"])
            click(app, "生成 AI 复核任务")
            assert "市场分析" in app.workflow_widgets["module"].get()
            click(app, "生成任务包")
            assert "TEST-ASIN" in content(app.workflow_widgets["prompt"])
            assert "选品候选与工厂能力复核" in content(app.workflow_widgets["prompt"])
            app.show("selection_advanced")
            app.selection_trees[1].selection_set(saved[0]["id"])
            with patch.object(app, "experiment_dialog") as editor:
                click(app, "建立测款记录")
                assert editor.called
                assert app.store.list("experiment")[0]["budget"] == 0
            app.show("selection")
            with patch.object(app, "clipboard_get", return_value="亚麻宽松衬衫\n针织休闲裤"):
                click(app, "粘贴并整理")
            leads = app.store.list("candidate")
            assert len(leads) == 3
            assert sum(x["strategy"] == "manual_lead" for x in leads) == 2
            click(app, "+  添加选品")
            put(app.quick_selection_widgets["text"], "亚麻宽松衬衫\n针织休闲裤")
            click(app, "整理并保存")
            assert len(app.store.list("candidate")) == 3
            assert app.store.setting("quick_selection_draft") == ""
            with patch.object(app, "clipboard_get", return_value="ASIN\t标题\t月销量\t评分\nPASTED-1\t粘贴衬衫\t1200\t3.2"):
                click(app, "粘贴并整理")
            assert app.quick_selection_last["counts"]["符合筛选"] == 1
            assert len(app.store.list("candidate")) == 4
            widgets = app.quick_selection_widgets
            click(app, "待调研")
            assert len(widgets["tree"].get_children()) == 2
            click(app, "初筛匹配")
            assert len(widgets["tree"].get_children()) == 2
            widgets["search"].set("没有这个款式")
            app.update()
            assert not widgets["tree"].get_children()
            assert widgets["empty"].winfo_manager() == "place"
            assert str(widgets["review"].cget("state")) == "disabled"
            widgets["search"].set("")
            click(app, "全部")
            assert len(widgets["tree"].get_children()) == 4
            click(app, "+  添加选品")
            put(widgets["text"], "未提交的草稿")
            click(app, "取消")
            click(app, "+  添加选品")
            assert content(widgets["text"]) == "未提交的草稿"
            click(app, "取消")
            # Check visible controls at compact and normal window sizes. The
            # selection page has no scrolling container to hide clipped actions.
            app.deiconify()
            for size in ("1040x640", "1080x700", "1380x880"):
                app.geometry(size)
                app.update()
                for control in descendants(app.page):
                    if isinstance(control, (tk.Button, tk.Label)) and control.winfo_ismapped():
                        assert control.winfo_rootx() >= app.winfo_rootx(), (size, control.cget("text"))
                        assert control.winfo_rootx() + control.winfo_width() <= app.winfo_rootx() + app.winfo_width(), (size, control.cget("text"))
                        assert control.winfo_rooty() + control.winfo_height() <= app.winfo_rooty() + app.winfo_height(), (size, control.cget("text"))
                click(app, "+  添加选品")
                app.update()
                dialog = widgets["dialog"]
                for control in descendants(dialog):
                    if isinstance(control, tk.Button) and control.winfo_ismapped():
                        assert control.winfo_rooty() + control.winfo_height() <= dialog.winfo_rooty() + dialog.winfo_height()
                # Expanded optional metadata must also leave room for actions.
                for control in descendants(dialog):
                    if isinstance(control, tk.Checkbutton):
                        control.invoke()
                app.update()
                assert widgets["text"].winfo_height() >= 80
                click(app, "取消")
            for size in ("1040x640", "1380x880"):
                app.geometry(size)
                for page in ("products", "selection", "selection_advanced", "pricing", "workflows", "analytics", "experiments", "artifacts", "settings", "dashboard"):
                    app.show(page)
                    app.update()
                    assert_actions_fit(app)
            assert not errors, errors
            assert not error.called, error.call_args_list
        app.close_guard = None
        app.close()
    print("UI integration passed: quick clipboard intake, lead deduplication, table recognition, advanced screening, candidate/AI handoff, all pages.")


if __name__ == "__main__":
    main()
