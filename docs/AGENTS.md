# AGENTS.md

阴阳师自动化脚本（Windows，Python 3.10，视觉识别 + 图导航，不改内存不注入）。
业务逻辑在 `tasks/`，框架在 `module/`。**更详细的说明不要写在这里**，见文末文档指针。

## 运行

```powershell
cd D:\script-dev\yys\OnmyojiAutoScript-dev      # cwd 必须是仓库根
.\.venv\Scripts\python.exe gui.py               # 桌面 GUI
.\.venv\Scripts\python.exe server.py            # WebUI :22267
uv pip install <pkg> --python .\.venv\Scripts\python.exe
```

## 硬规则（违反必出问题）

1. **cwd = 仓库根**：`module/logger.py:59` 在 import 时 `os.chdir`，配置走 `Path.cwd()/"config"`。
2. **`assets.py` 是生成物**：改 `tasks/*/**.json` 后必须跑 `python dev_tools\assets_extract.py`（会重写**所有**任务的 assets.py），绝不手改 `assets.py`。
3. **任务 `run()` 必须以 `raise TaskEnd` 结束**，否则调度器认为没跑完。
4. **坐标基准 1280×720**，所有 ROI 都在这个坐标系；其他分辨率直接判失败。
5. **`config/deploy.yaml` 保持 `AutoUpdate: false` + `KeepLocalChanges: true`**，否则启动时 `git pull` 覆盖改动。
6. **不要升级 `setuptools`**（钉 `80.10.2`，84.x 移除 `pkg_resources` 会让 `adbutils`/`uiautomator2` 崩）。
7. 不要用 `deploy/` 下的安装器/启动器（不装 PySide6，期望不存在的 `./toolkit/python.exe`）。

## 加任务要登记三处

| 位置 | 作用 |
|---|---|
| `module/config/config_model.py` | 加 import + `Field(default_factory=...)`，否则配置读不到 |
| `module/config/config_menu.py:15-46` | 菜单分组列表，否则 GUI 里看不到 |
| `tasks/<Name>/page.py` | 放进去即被 `PageRegistry` 自动发现（无需中央登记） |

## 读什么 / 别读什么

读：`script.py`、`tasks/base_task.py`、`tasks/GameUi/USAGE.md`、`module/atom/image.py`、`module/config/scheduler.py`、`tasks/Orochi/{script_task,config}.py`。

别读（噪音，占 59% 行数）：`module/gui/res_rc.py`、`res_rcc.py`（各 42,912 行）、`qml_rc.py`、`qml_rcc.py`、`tasks/**/assets.py`、`fluentui/`、`module/config/argument/*.yaml|json`（除 `args.json` 外全是死代码）。

> 读中文注释用 `read` 工具；PowerShell `Get-Content` 会 mojibake。

## 验证

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -c "import script; print('ok')"
& $py -m pytest tests -q --ignore=tests/tasks/Component/GeneralBattle/test_battle_wait.py   # 期望 43 passed
```

## 行为准则

- 改动前先 grep 确认引用点（尤其三处登记）；报问题时给 `文件:行号`。
- 不重构 `module/` 存量风格，不"顺手"格式化大文件，不动 `requirements.txt`（pip-compile 产物）。
- 不把 `python.exe` 当万能写盘工具：受限环境下它对 `config/`、`tasks/` 可能无写权限，写文件用 `write`/`edit` 工具。

## 文档指针

| 需要什么 | 文件 |
|---|---|
| 二次开发详细指南（改规则、加任务、配置、导航、调试） | `开发指南.md` |
| 项目整体分析与技术债 | `OAS项目分析报告.md` |
| 图导航框架权威说明 | `tasks/GameUi/USAGE.md` |
