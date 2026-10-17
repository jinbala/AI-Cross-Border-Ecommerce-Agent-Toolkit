# 裤装选品源码来源

来源：`https://github.com/jinbala/product-selection-specialist-skill.git`，本地目录 `D:\000code\product-selection-specialist-skill-1`。
引入时的版本与提交见 `VERSION` 和 `UPSTREAM_REVISION`。原项目版权与 MIT 许可完整保留在 `LICENSE`。

仅引入源码、规则、配置、说明和测试夹具。未复制原项目的 `results/`、`dist/`、真实榜单、登录配置或收藏。

整合修改：桌面导航增加产品、报价、工作流、试验、分析与设置入口；本地页面通过 `unified_desktop/BusinessBridge.cs` 调用 `desktop_app/service.py`。罗盘远程页面继续禁用本机消息与宿主对象，不接触经营后台。

整合桌面版另增账号可见男女装类目发现、自选类目、快速读榜和工厂初筛。默认 CLI 仍限定原先已核实的裤装路径；仅整合宿主在核对实际页面路径后启用 `allowApparel`，不会把其他账号未观察的类目标为已核实。原裤装类目目录与历史核实标记保持原意。

本目录保留原项目测试以核对筛选、来源和价格带语义。原 README / Skill 中有关独立客户端发布和已保存试采的描述属于上游历史，整合版不内置这些商家数据，以整合版说明为准。
