# OnmyojiAutoScript（dev 分支）项目分析报告

> 分析对象：`D:\script-dev\yys\OnmyojiAutoScript-dev`，分支 `dev`，HEAD `65311c50 Merge pull request #1977 from leovefy/dev`（2026-10-29）
> 分析方式：静态阅读源码 + git 统计（未实际启动游戏/模拟器运行）

---

## 0. 一句话结论

OAS 是一个**"图色识别 + 模拟点击"型手游托管框架**，脱胎于碧蓝航线脚本 Alas，但已经通过"前后端拆离 + pydantic 配置 + 独立 OCR 进程 + 页面图导航"改造成了**一套可多实例、可分任务编排的阴阳师自动化平台**。工程量真实（真实代码约 6.3 万行、59 个任务包、1920 条图像规则），长期活跃（2855 commits / 110 位贡献者 / 近 90 天仍有 305 次提交）；代价是**重度依赖运行时环境与"睡一会儿再看看"的同步风格**，自动化测试与错误恢复是明显的短板。

---

## 1. 项目定位与生态

| 维度 | 内容 |
|---|---|
| 游戏 | 网易《阴阳师》手游（含 PC 桌面客户端） |
| 形态 | Windows 桌面 GUI（PySide6 + QML）驱动多个后台实例；另有 FastAPI Web 服务对外提供工具/标注页面 |
| 原理 | 截屏 → OpenCV 模板匹配 / PaddleOCR(onnx) 文字识别 → 有限状态机 + 页面图寻路 → ADB / Win32 消息模拟点击 |
| 许可 | GPLv3 |
| 前身 | [AzurLaneAutoScript](https://github.com/LmeSzinc/AzurLaneAutoScript)（代码中仍大量保留 Alas 痕迹） |
| 文档 | <https://runhey.github.io/OnmyojiAutoScript-website/> |
| 关联 | OASX（全平台 GUI）、OAS-website（Docusaurus 文档站）、ppocr-onnx、gurs（贝塞尔滑动轨迹） |

README 自述的四大改造：前后端拆离、新 GUI（README 写的是 Flutter，**实际实现是 PySide6/QML**）、ppocr-onnx OCR、Assets 管理系统、pydantic 配置化。前四条在代码里都能对上，只有第 2 条与现状不符——README 那段文字是从早期规划继承下来的。

---

## 2. 技术栈与运行约束

- **Python 3.10**（`requirements.txt` 由 pip-compile 生成，`requirements-in.txt` 是唯一手写源）
- **仅 Windows**：`module/device/method/desktop_impl.py` 无条件 `import win32api/win32gui`；`server.py` 用 `ctypes._tzset()` 打 `CST-8` 时区补丁；`deploy/launcher/oas-gui.bat` 用 UAC + batch-to-exe 混淆启动
- 核心依赖：`pydantic 2.10`、`fastapi 0.104` + `uvicorn`、`zerorpc 0.6.3` + `pyzmq`（跨进程 RPC）、`opencv-python 4.7` + `numpy 1.24`、`ppocr-onnx 0.0.3.9` + `onnxruntime 1.16`、`uiautomator2 2.16` + `adbutils 0.11`、`pywin32 306`、`frida 17.6`（签到类任务的 App 内部调用）、`paho-mqtt`（多账号协同）、`onepush`（推送）
- **未声明但必需的依赖**：`PySide6` 不在 `requirements-in.txt` / `requirements.txt` 里，`deploy/pip.py:54` 只装 requirements.txt，`deploy/fluentui.py` 的 `FluentuiManager` 是空实现（`pass`），FluentUI 插件 dll 直接提交在 `module/gui/FluentUI/fluentuiplugin.dll`。→ 用 `pip install -r requirements.txt` 之后 `python gui.py` 会直接 `ImportError`

---

## 3. 代码规模（剔除生成物后的真实数字）

仓库里 461 个 `.py`、154,028 行，但其中 **90,915 行（59%）是 4 个 Qt 资源生成文件**：

| 文件 | 行数 | 说明 |
|---|---|---|
| `module/gui/res_rc.py` | 42,912 | 资源二进制转 Python 字面量 |
| `module/gui/res_rcc.py` | 42,912 | 与上者内容重复提交的同一份资源 |
| `module/gui/qml_rc.py` | 3,627 | |
| `module/gui/qml_rcc.py` | 1,464 | |

**真实手写代码 ≈ 63,113 行 / 457 文件。**

按层分布：

| 模块 | 文件 | 行数 | 职责 |
|---|---:|---:|---|
| `tasks/` | 314 | 39,677 | 业务：任务、页面定义、资源规则、配置模型 |
| `module/device/` | 32 | 8,812 | 设备连接（模拟器/桌面客户端）、截图、点击 |
| `module/server/` | 16 | 3,017 | FastAPI Web 服务、实例进程管理、标注工具 |
| `module/base/` | 12 | 2,078 | 工具函数、计时器、装饰器、日志高亮 |
| `module/config/` | 15 | 1,911 | 配置模型、调度、监视、实例排队 |
| `module/atom/` | 13 | 1,575 | 识别/点击元对象（RuleImage 等） |
| `module/gui/` | 10 | 899 | PySide6/QML 前端上下文与类型注册（不含生成资源） |
| `module/ocr/` | 6 | 759 | OCR 引擎与独立 RPC 服务 |
| `module/team_flow/` | 5 | 464 | MQTT 多账号协同 |
| 其它（logger/map/daemon/notify/handler/exception） | 8 | 991 | |

资源：`tasks/**` 下 **1,905 张**模板图；`assets/i18n/zh-CN.json`（11 KB，任务名/日志翻译），`en-US.json` 只有 4 字节（占位）。

规则元对象总量（`tasks/**/assets.py`，共 79 个文件）：`RuleImage` 1,920 条、`RuleClick` 303 条、`RuleOcr` 259 条、`RuleSwipe` 46 条、`RuleList`/`RuleLongClick` 各 10 条。这是项目最重的"资产"——**游戏 UI 一改版，主要工作量就是改这些坐标和模板图**。

---

## 4. 目录地图

```
.
├── gui.py                    # 桌面 GUI 入口（PySide6）
├── server.py                 # Web 服务入口（uvicorn，默认 :22270）
├── script.py                 # 单个实例的"调度器 + RPC 服务"（755 行，核心）
├── docker-compose.yaml       # WSL/容器内跑 Web 端（network_mode: host）
├── requirements-in.txt       # 手写依赖源
├── assets/i18n/              # 任务名与文案翻译
├── bin/                      # droidcast / hermit / minitouch 等设备端二进制
├── deploy/                   # 安装与升级：git/pip/adb/进程/FluentUI 管理器、docker、launcher
├── dev_tools/                # 开发期工具：assets_extract.py（生成 assets.py）、get_images.py、bind_desktop_window.py
├── tests/                    # 7 个测试文件（unittest + pytest 混用，未接入 CI）
├── module/                   # 通用框架层（不含业务）
│   ├── atom/                 #   RuleImage / RuleClick / RuleOcr / RuleList / RuleSwipe / RuleGif ...
│   ├── base/                 #   工具、Timer、装饰器（cached_property / run_once）
│   ├── config/               #   Config / ConfigModel / TaskScheduler / InstanceGuard / AntiBanGuard
│   ├── device/               #   Device 多继承：DesktopDevice + Platform + Screenshot + Control + AppControl
│   │   └── method/           #     adb / uiautomator2 / droidcast / scrcpy / nemu_ipc / windows / desktop_impl
│   ├── gui/                  #   PySide6 + QML（qml/ 37 个文件、FluentUI 插件、context 桥接）
│   ├── ocr/                  #   ppocr 封装 + zerorpc OCR 服务（:22268）
│   ├── server/               #   FastAPI（home/script/tool 三个 router）+ 多实例进程管理
│   ├── team_flow/            #   MQTT 主从协同（Host/Player + Task 策略）
│   └── notify/ handler/ map/ daemon/ logger.py
└── tasks/                    # 业务层
    ├── base_task.py          # BaseTask = 识别/点击/等待/结算 等原语集合（857 行）
    ├── GameUi/               # 页面图导航引擎（Page/Transition/Registry/Session/Navigator）
    ├── Component/            # 19 个可复用组件（通用战斗、邀请、组队、换御魂、换皮肤、切换账号…）
    └── <59 个任务包>/         # assets.py / config.py / page.py / script_task.py / o/ / res/
```

**任务包的"四件套"结构**（以 `tasks/Orochi/` 为例，这是新增任务的模板）：

| 文件 | 作用 | 是否手写 |
|---|---|---|
| `assets.py` | 声明本任务的 `RuleImage/RuleClick/RuleOcr`，`file="./tasks/Orochi/o/xxx.png"` | 否，由 `dev_tools/assets_extract.py` 生成（文件头有注释） |
| `config.py` | pydantic `ConfigBase` 子类，字段 `Field(default=..., description='xxx_help')` | 是 |
| `page.py` | 本任务的 `Page(...)` 页面节点与跳转边 | 是 |
| `script_task.py` | `class ScriptTask(GeneralBattle, GameUi, ...)` + `run()`，结尾 `raise TaskEnd` | 是 |
| `o/`、`res/` | 模板图 / 其它资源 | 二进制 |

---

## 5. 分层架构

```
┌───────────────────────────────────────────────────────────────┐
│ 表现层   PySide6 GUI (gui.py)  │  FastAPI Web (server.py)      │
│          QML + FluentUI 插件   │  /home /script /tool(标注器)   │
└──────────────┬──────────────────────────┬─────────────────────┘
               │ zerorpc (每实例一个端口)   │ HTTP
┌──────────────▼──────────────────────────▼─────────────────────┐
│ 实例层  ScriptProcess(multiprocessing.Process, daemon)         │
│         └─ Script：config / device / scheduler loop / RPC 服务 │
└──────────────┬───────────────────────────────────────────────┘
               │ 动态加载 tasks/<Command>/script_task.py
┌──────────────▼───────────────────────────────────────────────┐
│ 业务层  ScriptTask(BaseTask + GameUi + Component mixin)        │
│         59 个任务包 × 19 个 Component 组件                     │
└──────────────┬───────────────────────────────────────────────┘
               │ appear/click/ocr/swipe（BaseTask 原语）
┌──────────────▼───────────────────────────────────────────────┐
│ 感知执行层  module/atom (RuleImage/RuleOcr/...)                │
│             module/device (Screenshot + Control + AppControl)  │
│             module/ocr (ppocr + zerorpc 服务)                  │
└──────────────┬───────────────────────────────────────────────┘
               │ ADB / uiautomator2 / scrcpy / DroidCast / Win32
┌──────────────▼───────────────────────────────────────────────┐
│ 目标  安卓模拟器（MuMu/雷电/夜神…） │ 阴阳师 PC 桌面客户端      │
└───────────────────────────────────────────────────────────────┘
```

横向支撑：`module/config`（配置+调度）、`module/logger`（rich 彩色日志 + 分实例文件日志）、`module/notify`（onepush 推送）、`module/team_flow`（MQTT）。

---

## 6. 运行时全链路

### 6.1 启动

1. `deploy/launcher/oas-gui.bat`：提权 → 设置 `toolkit` 内的 Python/Git/adb 到 PATH → `python -m deploy.installer`（git 更新、pip 安装、adb 准备）→ `start /B pythonw gui.py`
2. `gui.py:16` 先 `ensure_ocr_server_started()`（`module/ocr/rpc.py`，独立 `multiprocessing.Process` + zerorpc，默认 `:22268`，端口被占用则直接复用）
3. `FluentApp()` 创建 `QGuiApplication` + `QQmlApplicationEngine`，`addImportPath(module/gui)` 加载 `module/gui/qml/app.qml`；注入 `setting / add_config / process_manager / utils` 四个上下文对象，注册 `PaintImage`、`RuleFile` 两个 QML 类型

### 6.2 多实例进程模型

- `ProcessManager`（QObject，`module/gui/context/process_manager.py:52`）持有 `processes / configs / ports / clients` 四张表，是 GUI 的总控
- 每个 `config/<name>.json` 对应一个 `ScriptProcess(Process, daemon=True)`，`run()` 里 `Script(config_name)` → `init_server(port)`（`zerorpc.Server` 绑定 `tcp://127.0.0.1:<port>`）→ `run_server()`
- 跨进程回传只有两条队列：`log_queue`（日志字符串）与 `update_queue`（任务状态 dict）；GUI 用 `Signal` 转到 QML。截图镜像走 `gui_mirror_image` 这个 `@zerorpc.stream` 方法（JPEG 字节流）
- `server.py` 那条 Web 路径则是另一套：`MainManager`（单例 `mm`）为每个配置维护 `ScriptProcess`，`push_data_thread` 每 3 秒为活跃进程补建 `coroutine_broadcast_state` / `coroutine_broadcast_log` 协程。**GUI 与 Web 服务是两条并列的宿主，共用同一批 `ScriptProcess` 类**

### 6.3 单实例调度循环（`script.py`）

```
loop()
 ├─ 每天 0 点切分日志文件；首次运行按配置把模拟器窗口显示/最小化
 └─ while 1:
      get_next_task()                     # 核心：决定下一个跑谁 / 要不要等
        ├─ config.get_next()              #  TaskScheduler 按 rule 排序，取 pending 首个
        ├─ anti_ban_guard.wake_time()     #  防封禁时段时间顺延
        ├─ _try_acquire_queue_token()     #  queue_mode 下的跨进程互斥（InstanceGuard）
        └─ _handle_wait_during_idle()     #  空闲策略 close_game / goto_main / stay_there
      run(command)                        # 动态 import tasks/<Command>/script_task.py 执行
      _gui_update_tasks()                 # 推送 task/pending/waiting 给 GUI
```

`run()`（`script.py:540`）的异常映射是理解整个"容错哲学"的关键：

| 异常 | 处理 | 后果 |
|---|---|---|
| `TaskEnd` | 正常结束 | 返回 True，继续调度 |
| `GameNotRunningError` | 记日志 + `task_call('Restart')` | 拉起重启任务 |
| `GameStuckError` / `GameTooManyClickError` | `save_error_log()`（最近 60 张截图 + 日志切片 + 敏感信息打码）+ 推送 + `Restart` | 继续 |
| `GameBugError` / `GamePageUnknownError` | 同上 + `device.sleep(10)` | 继续 |
| `ScriptError` / `RequestHumanTakeover` / 其它 `Exception` | `logger.critical` + 推送 | **`exit(1)`**（整实例进程死亡） |

同一任务连续失败 3 次会 `logger.critical` + 推送 + `exit(1)`。`save_error_log()`（`script.py:101`）会把 `screenshot_deque` 里最近 60 帧落盘，并用 `module/handler/sensitive_info.py` 把昵称/ID 等打码——这块做得比很多同类脚本认真。

### 6.4 感知-识别-执行闭环

`tasks/base_task.py`（857 行）是业务层唯一的"原语库"：

- 识别：`appear(rule)` / `appear_multi_scale` / `appear_then_click` / `ocr_appear` / `ocr_appear_click` / `list_find` / `wait_until_appear` / `wait_until_stable`
- 动作：`click` / `swipe`（贝塞尔轨迹）/ `ui_click` / `ui_get_reward` / `ui_back`
- 节流：`@interval_timer` + `Timer(limit)` 缓存，避免同一帧内重复识别

识别对象在 `module/atom/`：`RuleImage(roi_front, roi_back, method, threshold, file)`，构造时 `name = Path(file).stem.upper()`，`load_image()` 用 `cv2.imdecode(np.fromfile(...))` 读图（规避 Windows 中文路径问题），BGR→RGB 后在 ROI 内做 `cv2.matchTemplate`。

一个很能说明"工程细节"的设计在 `module/atom/image.py`：

```python
ROI_MATCH_PAD = 0
DESKTOP_ROI_MATCH_PAD = 2
def set_roi_match_padding(pad): ...
```

注释解释了原因：桌面客户端经过 DPI 重采样，模板与截图存在约 1px 相位差，而仓库里约 1/3 的模板 `roi_back` 与模板等宽，因此**桌面模式扩 2px、模拟器保持 0**，避免为了桌面端把模拟器基线改坏。

### 6.5 设备层

`class Device(DesktopDevice, Platform, Screenshot, Control, AppControl)`（`module/device/device.py`），`__init__` 对 `EmulatorNotRunningError` 重试 4 次，桌面模式走 `_init_desktop()`。

- 截图后端（`module/device/screenshot.py:37`）：`ADB` / `ADB_nc` / `uiautomator2` / `DroidCast` / `DroidCast_raw` / `scrcpy` / `window_background` / `nemu_ipc`；配置为 `auto` 时跑 `run_simple_screenshot_benchmark()` 选最快的一种——这是把"不同模拟器性能差异"交给运行时自适应，实用主义做法
- 桌面客户端：`module/device/method/desktop_impl.py`（1,501 行）是纯 mixin `DesktopWindow`，模块 docstring 明确写了边界约定（不定义 `__init__`、不反向依赖 `handle.py`、常量与 helper 不外转），`DESKTOP_WINDOW_TITLES = ('阴阳师-网易游戏', '阴阳师-MuMu模拟器专版')`；因为多开时窗口标题相同，靠档案目录里的 `oas_instance.json` 认领归属；PID 每次重启都变，所以**只活在运行时、不写配置**
- 点击：ADB input / minitouch / uiautomator2 / Win32 `SendMessage`（后台窗口）

---

## 7. 六个核心机制

### 7.1 配置系统（pydantic 化，有代价）

- `module/config/config.py`：`class Config(ConfigState, ConfigManual, ConfigWatcher, ConfigMenu)`，`__getattr__` 委托给 `self.model`
- `module/config/config_model.py`：显式 `from tasks.X.config import X` 共 56 个 `Field(default_factory=...)` 字段，组装成 `ConfigModel`。**新增任务必须在这里登记一行**
- 每个任务用 `ConfigBase` + `Field(default=..., description='xxx_help')` 描述，`description` 同时是 i18n key
- 生命周期：`Config` 读 `config/<name>.json` → `ConfigModel(**data)` 校验 → 任何属性赋值触发 `__setattr__`（`config_model.py:170`）→ **自动 `self.save()` 写回整个 JSON**
- **副作用**：一次 GUI 保存一个参数会全量重写 JSON；`script.py:175` 的 `gui_set_task` 里又手动 `self.config.save()` 并留下注释"我是没有想到什么方法可以使得属性改变自动保存的"（`script.py:206`），说明自动保存是后来加的、旧调用点没清理 → 双写
- `module/config/argument/` 下 8 个文件里，**只有 `args.json` 还被引用**（`module/config/config_updater.py:22`）；`menu.json` / `task.yaml` / `gui.yaml` / `override.yaml` / `default.yaml` 全仓库 0 引用，且内容仍是 Alas 的（`Main/Main2/Main3/GemsFarming/Sos`、`Alas:/General:`）→ 已死的中间产物

### 7.2 调度系统

- `module/config/scheduler.py`：`TaskScheduler.schedule(rule, pending)`，三种规则
  - `FILTER`：按 `ConfigManual.SCHEDULER_PRIORITY` 的字符串做正则过滤排序
  - `FIFO`：按 `next_run` 升序，**强制把 `Restart` 插到队首**（`scheduler.py:59-65`）
  - `PRIORITY`：先按 `priority` 分组，组内 FIFO，再按优先级合并
- 优先级字符串手写在 `module/config/config_manual.py:10`，把"御魂整理/结界"排最前、"活动类"排最后
- 每个任务结束调 `set_next_run(task, finish, success, server, target)` → `config.task_delay()` 算出下次时间；`Config.Function` 包装 `enable/command/next_run/priority`
- `pending_task` / `waiting_task` 两个列表分别表示"待执行"和"等待条件满足"（如等队友、等冷却）
- **已知小 bug**：`priority()` 里 `sorted(pending, ...)` 的返回值被丢弃（`scheduler.py:75`），分组仍按原顺序插入，只靠第 3 步 `sorted(groups.keys())` 兜底——对"同优先级内部顺序"无影响，但这一行是无效代码

### 7.3 视觉识别与 OCR

- `module/ocr/ppocr.py`：包装 `ppocronnx.predict_system.TextSystem`，并把 `sorted_boxes` 替换成 PaddleOCR 2.6 的实现（注释：比 ppocr-onnx 自带的更好，按 y 阈值 10 做行内 x 排序）
- `module/ocr/rpc.py`：OCR 跑在**独立进程**里（模型加载慢 + onnxruntime 吃内存），通过 zerorpc 暴露，`ensure_ocr_server_started()` 先探端口再起进程，支持 `OcrClientAddress` 远程模式（`StartOcrServer=False` 时作为纯客户端）
- 这是整个项目最合理的一处架构决策：多实例共享一个 OCR 服务，避免每个实例加载一份 PP-OCR 模型
- 文本过滤在 `module/ocr/base_ocr.py`（`tests/test_ocr_filter.py` 专门覆盖"精确匹配不能命中昵称子串"）

### 7.4 设备抽象

见 6.5。补充：`module/device/platform2/` 处理模拟器窗口管理（列出已装模拟器、启动、最小化、`emulator_base.py` 甚至读 `argument.yaml` 里的模拟器路径表），`module/device/method/windows.py` 做后台窗口截图/发送消息，`nemu_ipc.py` 走 MuMu 的共享内存通道（最快路径）。

### 7.5 GameUi 页面图导航（dev 分支最重要的演进）

`tasks/GameUi/` 已从"一堆 `while` + `if appear`"重构成**加权有向图 + Dijkstra 寻路**：

- `page_definition.py:75` `class Page`：`recognizer`（可组合 matcher）、`category`（按文件路径自动推断）、`priority`（1-100，多页面同帧命中时的复验顺序）、`cost`（寻路代价）、`transitions`、四阶段 hook（`on_enter_success/failure`、`on_leave_success/failure`）
- `registry.py:13` `PageRegistry`：进程级静态注册表，`load_all_pages()` 扫描并 `import` 所有 `tasks/*/page.py`，只加载一次
- `session.py` `NavigatorSession`：**任务级**运行态（页面快照、边惩罚、局部未知页关闭规则），与静态定义分离
- `navigator.py`：`_build_path(current, destination)` 用 `heapq` 做 Dijkstra（`navigator.py:428`），边权 = `next_page.cost + transition.cost + penalty`；`_execute_transition()` 失败时 `add_penalty(transition)` 并记 warning，连续失败 `REPEATED_TRANSITION_FAILURE_THRESHOLD = 3` 次后报 `Repeated transition failure`
- `DEFAULT_UNKNOWN_CLOSERS`（`navigator.py:42`）：11 个全局"关弹窗"规则，遇到未知页逐个尝试
- `tasks/GameUi/USAGE.md`（347 行）是模块自带的开发手册，规定了 Page 定义、组合器 `any_of/all_of/not_`、hook 写法、优先级语义
- 现状：110 处 `Page(`，但只在 8 个文件里（`default_pages.py`、`ActivityShikigami/page.py`、`Exploration/page.py`、`Orochi/page.py`、`DailyTrifles/page.py`、`OtherWorldTwilight/page.py` 等）→ **迁移进行中**，老任务仍是过程式写法，`page_act_list.link(...)` 之类旧 API 在部分 `page.py` 里被整段注释掉

### 7.6 多实例协同与风控

- `module/config/instance_guard.py`（310 行）：**跨进程实例看守器**。共享 `log/.queue_state.json`（`filelock.FileLock` 保护），结构 `{current, timestamp, queue}`，心跳 `STALE_TIMEOUT=300s` 判定持有者崩溃；`queue_mode=True` 时同一时刻只有一个实例操作模拟器，其余排队
- 配套 `AntiBanGuard`（`module/config/anti_ban.py`）：在配置的时间段内不执行任务，`get_next_task()` 里把 `next_run` 顺延
- `module/team_flow/`：MQTT（`paho-mqtt`）实现多账号主从协同，topic 为 `FirstNotice`（上线广播）、`LastWill`（掉线）、`TaskStart`（任务开始）、`Strategy`（策略下发）；`Host(Mqtt, Player)` 按 `config.global_game.team_flow.username` 区分身份——用于"司机带乘客"刷本场景
- 空闲策略（`script.py:400-500`）：`close_game`（关模拟器省内存，下个任务前按 `emulator_startup_lead_time` 提前预热）/ `goto_main`（回主界面）/ `stay_there`（原地不动），配合 `queue_idle_threshold` 在长时间等待时释放执行权

---

## 8. 工程化与协作

- **提交规模**：2,855 commits / 110 位作者 / 2023-05-05 起 / 近 90 天 305 次提交（约每周 25 次），仍在高频维护
- **贡献模式**：PR 为主，`Merge pull request #1977` 说明已处理近 2000 个 PR；近期提交以 `fix(<任务名>):` 为主（UI 改版适配、阈值调整、ROI 修正）
- **近 90 天改动热点**：`tasks/Component/GeneralBattle/battle_wait.py`（25 次）、`assets/i18n/zh-CN.json`（17）、`general_battle.py`（16）、`ActivityShikigami/script_task.py`（11）、`Exploration/base.py`（10）、`costume_base.py`（10）→ **战斗等待策略是最不稳定的部分**
- **`.github/` 很"AI 时代"**：不只是 ISSUE 模板，还有一整套 agentic workflow（`issue-handle-bug/enhancement/other/question`、`issue-triage`、`pr-review-intent`、`pr-review-checklist`、`auto-merge-pr`、`auto-create-pr`、`weekly-report`、`github-mirror`、`copilot-setup-steps`），带 `.lock.yml`（编译产物）+ `.md`（源定义）+ `shared/engine.md`、`shared/review-checklist.md`、`workflows/tools/extract_tasks_i18n.py`。**用 AI agent 做 issue 分类、PR 审查、自动合并**，这在国内游戏脚本项目里比较少见
- **CI 缺失**：`.github/workflows/` 里没有任何 `pytest` / `python -m` 步骤。测试全靠本地手动跑

---

## 9. 质量评估

### 做得好的地方

1. **架构分层清晰**：`module`（框架）与 `tasks`（业务）分离彻底，任务包四件套约定明确，新增一个任务只需 4 个文件 + 1 行 `config_model.py` 登记
2. **组件复用到位**：19 个 `Component`（通用战斗/邀请/组队/换御魂/换皮肤/切换账号/掉落统计）被几十个任务 mixin 复用，避免了 Alas 时代的大量复制粘贴
3. **OCR 独立进程**：多实例共享一份模型，是对"资源密集 + 多实例"的正确解法
4. **GameUi 图导航**：页面即节点、动作即边、Dijkstra + 失败惩罚，这是从"脚本"走向"框架"的关键一步，且带 347 行开发手册
5. **可观测性**：rich 彩色日志 + 分实例文件日志（14 天清理）+ 错误时自动保存最近 60 帧截图 + 敏感信息打码 + onepush 推送（支持多种渠道）
6. **多开与风控**：`InstanceGuard` 文件锁排队、`AntiBanGuard` 时段规避、桌面客户端多开认领机制，都考虑到了真实使用场景
7. **自适应**：截图后端自动测速选优、桌面/模拟器两套 ROI padding、`appear_multi_scale` 多尺度匹配——承认"环境差异"并用运行时探测解决

### 风险与坏味道（按严重度）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| 1 | **`exit(1)` 当错误处理** | `script.py:609/613/621`；`config`/`device` 的 `cached_property` 也在 `script.py:75/78/88/91` 直接退出 | 一次 `ScriptError` 就让整个实例进程死掉，GUI 只能看到"掉线"，`loop` 的 `continue` 语义形同虚设；多开时其它实例不受影响但本实例无法自愈 |
| 2 | **配置双写 + 全量 JSON 重写** | `config_model.py:170-179`（每次赋值 save）+ `script.py:206` 再手动 save | 配置变更放大 I/O；多进程同时写 `config/*.json` 有覆盖风险（无文件锁） |
| 3 | **import 即改工作目录** | `module/logger.py:59` `os.chdir(os.path.join(os.path.dirname(__file__), '../'))` | 全局副作用，任何 `import module.logger` 都会改 cwd，测试与嵌入式调用都会被影响 |
| 4 | **睡眠式同步遍地** | 165 处 `time.sleep(`；`wait_until` 5s 轮询（`script.py:318`）、队列等待 30s 轮询（`script.py:391`） | 配置变更/停止响应慢；无法用假时钟测试 |
| 5 | **裸 `except:`** | 17 处，如 `module/gui/context/process_manager.py:45` | 吞掉 `KeyboardInterrupt`/`SystemExit`，异常定位困难 |
| 6 | **测试形同虚设** | `tests/` 仅 7 个文件，unittest 与 pytest 混用，无 `conftest.py`、无 pytest 配置、CI 无测试 | 6.3 万行真实代码几乎无回归保护；改动 `battle_wait.py`（90 天 25 次）全靠人肉验证 |
| 7 | **Alas 遗留死代码/死文案** | `module/config/argument/` 5 个文件 0 引用；`config_updater.py:20-35` 两个方法体是 `pass`；`script.py:580` "please stop Alas"、`:589` "Azur Lane game client"；`deploy/fluentui.py` 空实现 | 认知负担 + 误导新贡献者；`config_updater` 空壳说明配置迁移没做完 |
| 8 | **生成物重复提交** | `res_rc.py` 与 `res_rcc.py` 各 42,912 行、同尺寸 | 仓库无谓膨胀，diff/搜索噪音大 |
| 9 | **Web/工具端攻击面** | `module/server/app.py:36-42` CORS `*` + `allow_credentials=True`；`zerorpc` 本地端口无鉴权（`script.py:139`）；`tool_router` 有 `rules/source/create`、`rules/source/delete` 可写源码 | 本机任意网页可跨域调用（配合管理员权限运行 = 高风险）；标注工具的写文件接口没有路径校验就无法防目录穿越 |
| 10 | **依赖不可复现** | `PySide6` 未进 requirements；`fluentuiplugin.dll` 以二进制提交；`ppocr-onnx/onnxruntime/numpy` 版本互锁 | 新机器按 README 装完跑不起 GUI；升级 numpy 会踩 onnxruntime 1.16 的 ABI |
| 11 | **Windows 强绑定 + Python 3.10 强绑定** | `desktop_impl.py` 顶层 `import win32api`；`server.py` 用 `_tzset` 打 `CST-8` | 无法在 Linux/macOS 跑；Python 3.11+ 的 `zerorpc`/`frida` 兼容性未验证 |
| 12 | **魔法数字与硬编码** | 端口 `22268`/`22270`、`STALE_TIMEOUT=300`、`REPEATED_TRANSITION_FAILURE_THRESHOLD=3`、`ROI_MATCH_PAD=2`、`sorted_boxes` 里 `abs(...) < 10` | 大多数有注释，但仍散落各处，缺少集中配置 |

### 一个具体的"维护性"观察

近 90 天 305 次提交里，改动的绝大多数是**任务实现（tasks/）与模板资源**，而不是框架层（module/）。这说明：
- 框架层已相对稳定，收益递减；
- **真正的维护成本在"游戏 UI 变化 → 改 ROI/模板图/等待策略"**，这类改动无法用单元测试覆盖，只能靠实机跑；
- `battle_wait.py` 被改 25 次是典型信号：战斗等待是最难抽象、最容易 regression 的地方，也是 `tests/tasks/Component/GeneralBattle/` 下唯一有测试的模块（说明维护者已经意识到这点）。

---

## 10. 上手与二次开发建议

### 想跑起来

1. Python 3.10，`pip install -r requirements.txt`，**再手动 `pip install PySide6`**（requirements 漏了）
2. 从 release 或 `toolkit/` 拿到 `fluentuiplugin.dll`（本仓库已带）、`bin/droidcast`、`bin/hermit`
3. `python server.py` 起 Web（`:22270`）或 `python gui.py` 起桌面端；OCR 服务会自动起在 `:22268`
4. 配置写在 `config/<name>.json`，日志在 `log/`（错误截图在 `log/error/<ts>/`）

### 想改/加任务

1. 复制 `tasks/Orochi/` 四件套 → 改 `config.py`（pydantic 字段）→ 在 `module/config/config_model.py` 加 import + `Field(default_factory=...)`
2. 用 `dev_tools/assets_extract.py` 从截图裁模板并生成 `assets.py`
3. 在 `script_task.py` 里写 `run()`，尽量复用 `Component/*`；**导航优先用 `goto_page(page_xxx)`**，别回到手写 `while` + `appear`
4. 给新页面写 `page.py`：`Page(RuleImage, priority=..)` + 建立边；参考 `tasks/GameUi/USAGE.md`
5. 新任务务必用 `set_next_run(..., finish, success)` 收尾并 `raise TaskEnd`，否则调度器无法推进

### 如果要"重构优先级"排序（我的建议）

1. **先补测试骨架**：给 `BaseTask` 的 `appear/click` 做可注入的 fake device，给 `battle_wait`/`navigator` 加纯逻辑单测，接入 CI（目前 0 测试门禁是最大风险）
2. **把 `exit(1)` 换成"抛出 → 实例重启任务"**：`RequestHumanTakeover` 已经是一种语义化异常，但当前被当作进程终止；至少让 `loop` 捕获后 `task_call('Restart')` 而不是杀进程
3. **加配置写锁**：`config/*.json` 的写入放到 `FileLock` 下（`InstanceGuard` 已有现成依赖 `filelock`）
4. **清死代码**：删 `module/config/argument/` 下 5 个 0 引用文件、修 `config_updater.py` 的两个 `pass`、把 `logger.py:59` 的 `chdir` 移到入口函数
5. **补 `PySide6` 到 requirements**，并把 `res_rc.py`/`res_rcc.py` 二选一（或改为构建期生成、不入库）
6. **收敛 CORS 与本地 RPC**：`allow_origins` 收窄到 `127.0.0.1`，zerorpc 加 token（`script.py:139` 那条 `bind` 只绑本地，但同机任意进程可连）
7. **继续推进 GameUi 图化**：老任务里成片的 `while True: if appear(...)` 是最大的技术债，也是 `GameStuckError` 的主要来源

---

## 11. 总评

| 维度 | 评价 |
|---|---|
| 功能完整度 | ★★★★★ 59 个任务覆盖日常/周常/寮/御魂/活动/爬塔，接近"全托管" |
| 架构设计 | ★★★★☆ 分层清晰、组件复用、图导航；扣分在 `exit(1)`、全局 cwd、配置双写 |
| 代码质量 | ★★★☆☆ 命名与注释质量不错（中文注释 + docstring 边界说明），但同步阻塞、裸 except、死代码、生成物重复 |
| 可测试性 | ★☆☆☆☆ 几乎为零，且无 CI |
| 可维护性 | ★★★☆☆ 框架稳定、任务层高频改动；游戏 UI 适配是长期成本 |
| 文档/社区 | ★★★★☆ 独立文档站 + 模块内 USAGE.md + 110 位贡献者 + AI workflow 自动化；但 README 有过期内容 |
| 上手难度 | 中偏高：需理解"配置模型 → 调度 → 任务 → 识别原语 → 设备"五层，且必须实机调试 |

**适用判断**：这是一个"产品成熟度高于工程成熟度"的项目——能真实跑、能覆盖绝大多数玩法、社区活跃，但把它当作**框架**去二次开发或长期维护时，测试缺失与错误处理方式会持续放血。若目标是"用"，直接按 release 用；若目标是"改/学架构"，`tasks/GameUi/`（图导航）与 `module/ocr/rpc.py`（进程拆分）是最值得读的两处，`script.py` 与 `module/config/` 是最值得重构的两处。
