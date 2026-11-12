# OAS 独立技术分析报告 — Codex

分析日期：2026-11-02。对象：`D:\script-dev\yys\OnmyojiAutoScript-dev`。
基线实测：`dev`，`65311c50338c4ec20e71809705626a7e9c462db2`。
本次仅新增本报告；未修改源码、配置、生成物或数据库，未启动 GUI、服务、OCR、模拟器或真实任务。

## 1. 一页纸摘要

**我的判断：值得用于“在现有阴阳师流程上增补功能”的二次开发，但不宜直接当作行为统一、配置契约稳定的通用自动化框架。** 代码有实际的任务复用、设备抽象和图导航；薄弱点在接口之间的契约、宿主生命周期和回归验证。这里评价的是可核实的结构与维护成本，**游戏成功率、产品稳定性、平台兼容性未验证**。依据：`tasks/Orochi/script_task.py:23` 的组件组合，`module/device/device.py:30` 的设备组合，`tasks/GameUi/navigator.py:404` 的寻路，以及下文的配置/退出缺陷。

**最大的三个坑：**

1. **配置“模型能定义”不等于“两端都能显示、修改、保存”。** 桌面 QML 读取 `definitions/allOf`，本仓安装的 Pydantic 2.10 产生 `$defs/$ref`；HTTP 又要求任务→组→叶字段，并直接读取 `default`。指南里的顶层标量字段示例会踩这个契约。嵌套字段赋值也不会触发根模型的自动保存。证据：`module/gui/qml/Component/Args.qml:561`、`ModelParse.js:79`、`module/config/config_model.py:307`、`:335`、`:170`；本地依赖 `.venv/Lib/site-packages/pydantic/main.py:1421`、`json_schema.py:113`。
2. **任务异常后的状态与宿主有关，GUI 可能是“实例还活着、调度线程已经死了”。** GUI 调用 `start_loop()` 建线程，且只检查线程对象是不是 `None`，不检查线程是否存活；Web 则在实例子进程主线程执行 `loop()`。所以“exit(1) 总会杀死整个实例”的文档结论不成立。证据：`script.py:742`、`module/gui/process/script_process.py:43`、`module/server/script_process.py:149`。隔离验证输出：`HOST_ALIVE=True LOOP_ALIVE=False LOOP_START_COUNT=1`。
3. **资源修改与流程维护仍需要开发者自己守住约束，CI 没有提供仓库测试兜底。** 生成器按第一条记录的字段数和键名分型，不校验全文件一致性；当前 JSON 已有一个重复资产名；缺少自动测试执行步骤。证据：`dev_tools/assets_extract.py:299`、`:312`、`:375`，`tasks/GlobalGame/ui/image.json:66`、`:138`，`.github/workflows/auto-merge-pr.yaml:38`。

**独立统计：** 剔除 4 个 Qt 资源 Python 文件、79 个任务 `assets.py` 和 `fluentui/` 后，Git 跟踪的 Python 为 **378 文件、68,719 物理行、59,139 非空行**，不是已验证的“6.3 万手写行”。54 个任务入口中 48 个直接调用图导航，另 4 个已核实间接使用；同时 47 个入口类仍有手写识别/点击循环。这是“导航广泛接入、任务内部过程式逻辑保留”，不能用只有 6 个 `page.py` 推断绝大多数任务未迁移。统计方法与证据见 §3、§6。

**条件性高风险：** 当前部署配置的 HTTP 监听为 `0.0.0.0:22267`，API 能修改规则并生成 Python，不能视作“默认仅本机”。若网络可达，安全问题应排到修复第一位；防火墙和真实网络可达性未验证。证据：`config/deploy.yaml:124`、`:128`，`module/server/app.py:36`，`module/server/tool.py:1339`。OCR 还存在独立的全接口监听与反序列化风险，见 §7。

## 2. 方法、证据等级与未验证范围

本报告按用户指定顺序读了 `AGENTS.md` → `开发指南.md` → `OAS项目分析报告.md`，之后才读代码。三份文件仅作为待核实的假说。

- **【文档声称】**：上一轮文档或 README 的说法，不代表已成立。
- **【代码核实】**：本次亲自检查的源码、引用链或只读统计；其中“隔离验证”不是完整系统测试。
- **【推断】**：从已核实控制流推导的维护影响，明确给出条件。
- **【未验证】**：游戏运行效果、完整 GUI 渲染、远端仓库设置、历史活跃度，以及没有本次实测支持的环境结论。

证据行号对应当前工作区。开始与结束检查均未发现已跟踪文件改动；开始时两份旧分析文档已是未跟踪文件。没有查询 GitHub，故原报告“2855 commits / 110 作者 / 近90天305提交”和上游当前状态均**未验证**，也没有用这些数字支撑评级。

### 验证执行记录

| 操作 | 关键输出/结果 | 能证明什么 |
|---|---|---|
| `git branch --show-current`；`git rev-parse HEAD` | `dev`；`65311c50338c4ec20e71809705626a7e9c462db2` | 基线正确 |
| `git status --short` | 两份既有文档未跟踪；两个旧 pytest 缓存目录 Permission denied | 不把这些目录混入统计 |
| `.\.venv\Scripts\python.exe -B -c "print('audit-runtime-ok')"` | exit code 1，stdout/stderr 均为空 | 当前执行环境下仓库解释器探针失败；**不能据此断言 venv 已损坏** |
| Codex 自带 Python `-B -c` 的只读 AST/计数程序 | 378 个允许读取的 Python 文件全部成功 AST 解析 | 语法解析成功，不代表依赖导入或测试成功 |
| 读取本地 Pydantic 源文件 | `version.py:7` 为 `2.10.0`；`schema()` 转交 `model_json_schema()` | 桌面端 schema 契约不匹配有本地版本证据 |
| AST 抽取生成器分类方法，对现有 JSON 和合成输入做纯内存检查 | 335 个 JSON，无解析/分类异常；1 组重复名 | 不写 assets、不导入游戏 |
| 抽取 ConfigModel 方法、执行 ConfigBase 的隔离检查 | 嵌套保存0次、顶层替换1次；直接标量/无默认字段触发 KeyError | 辅助验证配置代码行为，见 §4 |
| 抽取 `Script.start_loop`，用只抛 SystemExit 的替身 loop 验证 | 宿主存活，线程死亡，再调用未重启 | GUI 线程对象生命周期缺口 |
| `pytest tests`、`import script` | **未执行** | 不能声称“43 passed”或导入成功 |

隔离检查使用已有的 Codex Python **3.12.14 / Pydantic 2.14.1**，与仓库目标 **3.10 / 2.10.0** 不同；结果作为辅助证据，不冒充目标环境测试。所有探针使用 `-B`；未安装依赖。配置探针用内存 logger 替身，替换保存为内存计数。

未继续直接导入项目的另一个原因是**导入并非只读**：`module/logger.py:59` 改 cwd，`:369` 在模块末尾调用文件日志初始化，`:139` 可能创建 log 目录。配置读取也可能创建锁文件：`module/config/utils.py:52`。本次严格维持“唯一新增报告”的边界。

## 3. 真实代码量与生成边界

### 3.1 统计口径

【代码核实】文件集合来自 `git -c core.quotepath=false ls-files`，统计当前工作区中相应文件的 `read_text(encoding='utf-8-sig').splitlines()`。物理行包含空白、注释和 docstring；非空行仍包含注释，不称为可执行 SLOC。

排除规则在打开文件之前执行：

1. `fluentui/` 全目录：vendored 代码，不读取。
2. 文件名 `res_rc.py/res_rcc.py/qml_rc.py/qml_rcc.py`：4 个 Qt 编译资源，不读取、不数其内部行。
3. `tasks/**/assets.py`：79 文件，不读取、不数其内部行。
4. 未跟踪文件、venv、缓存、运行日志、数据、图片、模型、二进制均不进入 Python 源统计。

生成边界的独立证据：`dev_tools/assets_extract.py:13` 指定输出名，`:23` 写生成提示，`:366` 直接覆盖写；Qt 的 `module/gui/README.md:8`、`:9` 给出 rcc 命令，`res.qrc:3`、`qml.qrc:3` 声明输入，`fluent_app.py:17` 只实际导入 res_rcc。其余允许读取的 Python 搜索生成标记，命中的是生成器自己的模板。**这能建立可复现的排除边界，不能证明剩余代码全部原创手写**；其中也有 Alas 衍生代码和库兼容实现。

旧文档的“四个 Qt 文件共90,915行、两个 res 内容相同、占全仓59%”，遵守阅读边界后本次**未验证**。本次不拿这些旧数字做总量减法。

### 3.2 Python 分层统计

| 层 | 文件 | 物理行 | 占全部 Python |
|---|---:|---:|---:|
| tasks（业务、Component、GameUi、配置，不含 assets.py） | 233 | 39,815 | 57.94% |
| module/device | 32 | 10,475 | 15.24% |
| module/server | 16 | 3,555 | 5.17% |
| module/base | 12 | 2,588 | 3.77% |
| module/config | 15 | 2,345 | 3.41% |
| module/atom | 12 | 1,838 | 2.67% |
| module/gui Python | 10 | 1,100 | 1.60% |
| module/ocr | 6 | 916 | 1.33% |
| module/team_flow | 5 | 551 | 0.80% |
| module 其余（daemon、exception、handler、logger、map、notify） | 7 | 1,212 | 1.76% |
| deploy | 12 | 1,278 | 1.86% |
| dev_tools | 7 | 825 | 1.20% |
| tests | 7 | 1,167 | 1.70% |
| 根入口 gui/server/script | 3 | 885 | 1.29% |
| .github 中的 Python 工具 | 1 | 169 | 0.25% |
| **合计** | **378** | **68,719** | **100%（四舍五入）** |

【代码核实】补充统计：不含 fluentui 的 QML **35 文件/5,906行**、JS **8/3,687**、HTML **5/198**、CSS **5/1,907**、BAT **1/74**。Python + 前述四类界面源码共 **80,417物理行**；加 BAT 为80,491。不要把 Python 的规模叫作“整个产品的代码量”。

任务口径也应拆开：Git 跟踪文件归属的 tasks 一级目录61个，排除 Component、GameUi 后为59个目录；但其中包含 GlobalGame、Script、Utils、General 等，**不等于59个可运行游戏任务**。顶层 `tasks/*/script_task.py` 有54个；`ConfigModel` 的 `Field(default_factory=...)` 登记56个，也包含非调度配置；Component 子目录19个。证据：文件清单与 AST 统计，以及 `module/config/config_model.py:89`、`:91`。

### 3.3 复现计数的最小程序

以下是本次统计方法的缩减版，不会读取被禁止的生成物：

```powershell
$auditCode = @'
import sys, pathlib, collections
layers = collections.defaultdict(lambda: [0, 0])
for name in sys.stdin.read().splitlines():
    p = pathlib.Path(name)
    if p.suffix != ".py" or name.startswith("fluentui/"):
        continue
    if p.name in {"res_rc.py", "res_rcc.py", "qml_rc.py", "qml_rcc.py"}:
        continue
    if name.startswith("tasks/") and p.name == "assets.py":
        continue
    group = "/".join(name.split("/")[:2]) if name.startswith("module/") else name.split("/")[0] if "/" in name else "[root]"
    lines = p.read_text(encoding="utf-8-sig").splitlines()
    layers[group][0] += 1
    layers[group][1] += len(lines)
print(dict(sorted(layers.items())))
print(sum(x[0] for x in layers.values()), sum(x[1] for x in layers.values()))
'@
git -c core.quotepath=false ls-files |
  & 'C:/Users/szh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -c $auditCode
```

关键输出：`378 68719`。初次尝试从 Python 内启动 git 遇到 `WinError 5`；最终采用上面同一权限下的 PowerShell git 管道，没有提升权限。

## 4. 配置系统：能自动生成，但契约远窄于文档

### 4.1 实际有两条配置展示链

【文档声称】指南 `:443-453` 把 HTTP 的 `script_task` 和桌面的 `gui_args` 连成一条，断言新增字段就自动出控件。

【代码核实】两条独立链路如下：

- 桌面：`ScriptView.qml:89` → `ProcessManager.gui_args`（`module/gui/context/process_manager.py:231`）→ 实例 zerorpc `Script.gui_args`（`script.py:154`）→ `ConfigModel.gui_args`（`config_model.py:202`）→ schema JSON → `Args.qml:555`、`ModelParse.js:13`。
- HTTP：`script_router.py:120` → `mm.config_cache(...).model.script_task(task)` → `config_model.py:295` 内部将 schema 与当前值拼成分组参数列表。**没有调用 gui_args**。
- 桌面保存走 `script.py:175` 的 RPC；HTTP 保存走 `script_router.py:124` → `config_model.py:361`。它们的字符串转换并不一致。

【代码核实】合理的现有模板是 Orochi：任务模型的顶层字段都是配置组，叶字段放在 `OrochiConfig`。见 `tasks/Orochi/config.py:37`、`:68`。指南 `:306-310` 的示例把 `limit_count/limit_time/enable_buff` 直接放在任务顶层，与现有 GUI/API 契约不符。

### 4.2 会失败的边界

| 边界 | 代码核实 | 实际影响 / 推断 |
|---|---|---|
| Pydantic v2 schema | `gui_args` 原样输出 schema；QML `Args.qml:561` 取 `args.definitions`。安装版本 `pydantic/version.py:7` 是2.10.0；`main.py:1421` 转交 v2 schema，`json_schema.py:113` 是 `#/$defs/{model}` | 桌面普通参数页存在系统性协议不匹配；未启动GUI验证具体画面，不能说已修复或可用 |
| 顶层 int/bool/str | 桌面 `ModelParse.js:16` 忽略无 `$ref` 的字段；HTTP `config_model.py:316` 强取 `$ref` | 桌面漏字段；HTTP KeyError。隔离样例输出 `direct_scalar KeyError '$ref'` |
| Enum | 桌面 `ModelParse.js:79` 只认 `allOf[0].$ref`；HTTP `config_model.py:338` 认直接 `$ref` 并读取定义的 enum | HTTP 常规 Enum 路径存在；桌面不是文档保证的通用下拉框 |
| Time/DateTime/TimeDelta | `config_base.py:56`、`:61`、`:66` 自定义 type；`Args.qml:74-115` 只分派 string/integer/number/boolean/enum/multi_line | QML 未实现对应自定义类型分支；“时间选择器自动出现”不成立 |
| Scheduler 特例 | `config_model.py:216` 只在旧式 `definitions` 中改间隔 type | 在本仓 v2 schema 结构中该特例不会生效 |
| 必填叶字段，没有 default | HTTP `config_model.py:335` 无条件读 `value["default"]` | 即使实例已有合法值，展示也会 KeyError |
| 叶字段使用 default_factory | 同上 | schema 不一定包含 default，隔离样例 `factory_leaf KeyError 'default'` |
| 嵌套第三层模型 | HTTP `config_model.py:338-340` 把叶 `$ref` 当 Enum；桌面没有递归分组解析 | 可能先缺 default，或取不到 enum；不是任意深度模型编辑器 |
| Optional/Union | 两端没有通用 `anyOf` 分支；`script.py:198`、`config_model.py:401` 把当前值 None 判为参数不存在 | 可空字段不仅展示受限，从 None 改成有效值也可能失败 |
| list/dict | QML 无 array/object 分支；HTTP 顶层数组专门读取 `items.$ref`（`:313`） | 仅有特定模型列表路径，不能推广成任意列表/字典支持 |
| 同一个组类用于多个顶层字段 | `ModelParse.js:39` 用类型名作 key | 组实例映射相互覆盖，存在显示/写回错组风险 |
| 类型正确但超出约束 / Enum 非成员赋值 | `ConfigBase` 未启用 validate_assignment；两个 setter 都直接 setattr 后保存（`script.py:203`、`config_model.py:421`） | 声明约束不保证编辑时校验；非法值可能写入，重载时再暴露 |
| 默认值修复 | `config_base.py:94-110` 只修复首个范围错误并重建一次 | 不是“所有错误均回退”；两个越界字段的隔离样例仍抛 ValidationError |

【代码核实】HTTP 时间转换有独立 bug：`script_router.py:146` 使用 `int(value[1])` 取“天”。`12 03:04:05` 会变成2天，`10 ...` 变0天。另有 `config_base.py:34` 将不匹配格式的字符串默认为1天。字符串长度猜测类型还可能误把普通字符串当时间：`script.py:185`、`config_model.py:368`。这些都是二开新增字段时能直接遇到的问题。

### 4.3 保存：有锁，普通嵌套赋值不自动保存

【文档声称】指南 `:457-463` 与旧报告 `:229-230` 认为任何字段赋值都保存，GUI 通常双写；旧报告 `:303` 认为没有锁。

【代码核实】自动保存只覆盖 **ConfigModel 自身的 `__setattr__`**（`config_model.py:170`）。`config.orochi.orochi_config.limit_count = n` 修改的是 ConfigBase 子对象，不会调用根模型方法。`script.py:206` 和 `config_model.py:423` 的显式 save 对这条路径是必要的。隔离检查：`NESTED_SAVES 0`、`TOP_SAVES 1`。

真正存在的双写例子是整任务复制：`config_model.py:432` 对根模型 setattr 后，`:433` 又 save。调度器对根级 `running_task` 赋值也会触发写入（`script.py:700`、`:703`）。不能据此说所有 GUI 叶字段都会双写。

保存是**全模型序列化 + FileLock + atomic_write**：`config_model.py:244`、`module/config/utils.py:85`、`:97`。【推断】单次写入不会因为完全没锁而随意交错，但不同进程读到各自快照、随后全量覆盖仍可能丢失对方更新；当前锁不包住“读—修改—写”的完整事务。该并发丢更新未做运行复现。

## 5. 资源系统：生成规则与实际异常面

### 5.1 已核实的算法

【代码核实】命令行入口 `assets_extract.py:429` 构造 AllAssetsExtractor；它遍历 tasks 一级目录，剔除路径含 Component 的项，再加入 Component 子目录（`:410-415`）；每个目录递归查找 JSON，路径含小写 `temp` 的跳过（`:276`）。各任务以目录名生成 `<Task>Assets`（`:264`），随后 `open(...,"w")`（`:366`）。

实际分型**有优先级**，不是无序的字段规则表：

| 优先级 | 判定 | 输出前缀 |
|---:|---|---|
| 1 | dict 且含 name | L_ / RuleList |
| 2 | 第一项含 imageName | I_ / RuleImage |
| 3 | 第一项长度恰为4 | C_ / RuleClick |
| 4 | 第一项含 duration | L_ / RuleLongClick |
| 5 | 第一项含 mode 且长度恰为5 | S_ / RuleSwipe |
| 6 | 第一项含 keyword | O_ / RuleOcr |

依据：`assets_extract.py:293-359`、`:380-392`。空数据由 `:377` 跳过；有内容但不匹配任何类型的列表没有报错分支，可能静默漏生成。非空 dict 没 name 会进入列表检测的 `data[0]`，可 KeyError。

路径与名称：变量名是前缀 + itemName.upper（`:29`、`:69`）；image 路径取 JSON 目录 + imageName（`:51`、`:74`）；OCR 将 roiFront/roiBack 分别映射到 roi/area（`:189`）；list 尺寸是项目 roiFront 宽高的均值取整数（`:233-238`）。这些部分与指南基本一致。

### 5.2 哪些组合会分错类

【代码核实 + 隔离验证】调用原生成器分类方法，得到：

| 输入变化 | 结果 | 后果 |
|---|---|---|
| click 四键增加一个无关 metadata | unknown | 静默漏生成 |
| long_click 丢 description，剩四键并保留 duration | click | 随后的 ClickExtractor 可能因缺字段报错；不会进入长按分支 |
| 包含 mode、keyword 的五键简化 OCR | swipe | OCR 被抢先当滑动；本例后续还因缺 description 失败 |
| 同一列表首条 click、后条 image | 全列表 click | 后条的 imageName 等字段被忽略，产生错误类型 |
| 非空 dict，没有 name | KeyError 0 | 整个任务生成中断 |
| 同时有 imageName 与其他类型特征 | image | image 分支优先，额外特征不能改变类型 |

第一项正常不代表全文件正常，生成器会把所有条目交给首条决定的 Extractor（`:55`、`:86`）。没有 schema 级一致性验证，也没有任务级事务回滚；全量生成半途失败时，之前任务可能已经被覆盖（`:418-420`）。

### 5.3 当前资源的实际扫描

只读扫描 **335 个 JSON、69 个有规则的目录**，按相同优先级统计：

| 类型 | JSON 文件 | 规则条目 |
|---|---:|---:|
| image | 186 | 1,920 |
| click | 50 | 302 |
| ocr | 63 | 259 |
| swipe | 22 | 46 |
| long_click | 4 | 10 |
| list | 10 | 10 |

未发现当前 JSON 的解析或分型异常。任务 PNG 文件1905个。旧报告的 click 303 来自其声称的生成物计数；本次 JSON 为302，**未读取生成物，不能确认是否存在生成物漂移**。

发现 **1组重复生成变量名**：`tasks/GlobalGame/ui/image.json:66` 与 `:138` 都是 `ui_back_circle`。两条会落成同一个 `I_UI_BACK_CIRCLE`，后定义覆盖前定义；规则 ROI 不同，不能只当无害重复。本次未发现跨 long_click/list 的 L_ 同名，但共享前缀的结构性冲突成立（`assets_extract.py:129`、`:242`）。不应靠“看右侧类名”解决，需保证同一目标资产类中的最终变量名唯一。

### 5.4 指南中可以直接误导操作的地方

- **ROI 格式**：现有2537个普通规则的 roiFront 全是字符串 `"x,y,w,h"`，不是指南示例的数组。普通 Extractor 的字符串插值对数组可能生成 list 参数，而 list 规则明确调用 `.split(",")`，照抄指南数组示例会失败（`assets_extract.py:233`）。标注器也要求字符串（`tool.py:664`）。
- **长按单位**：指南 `:180` 写“秒”，实际规则默认1000、执行时除1000，单位是**毫秒**（`module/atom/long_click.py:13`、`tasks/base_task.py:531`）。0.5不是半秒。
- **生成范围**：命令行确实全量；标注器保存只对目标任务/组件调用 AssetsExtractor（`tool.py:871`、`:1354`），不是任何修改都必须重写全部任务。
- **裁图职责**：生成器只生成 Python；图片裁剪在 `tool.py:1423`、`:1426`。旧报告 `:336` 把“裁模板”和“生成”混在一起。
- **不安全的文本拼接**：名称仅 upper、不验证 Python 标识符；字符串直接写进 Python 字面量，description 直接拼注释（`assets_extract.py:68-74`、`:188-195`）。引号、换行等可导致语法破坏；若规则来自不可信请求，可能形成代码注入条件。**未执行攻击载荷、未验证远程利用**。
- 标注器的类型检测优先 keyword 再 duration/mode（`tool.py:967-981`），与生成器不同；手写非标准 JSON 可能出现“标注器认得，生成器分类不同”。

## 6. GameUi：迁移程度与新增任务的真实成本

### 6.1 不用 page.py 文件数冒充迁移率

【文档声称】6个 page.py、110处 Page(，因此迁移尚浅。

【代码核实】AST 排除注释/docstring 后，`Page(...)` 调用点为52：

- `default_pages.py` 45处；
- ActivityShikigami 1、DailyTrifles 1、Exploration 2、Orochi 1、OtherWorldTwilight 1；
- `page_definition.py:266` 的 clone 内部调用1处。

因此是**51个静态页面构造调用点 + 1个克隆实现调用点**，不能称52个唯一运行时页面；运行时唯一键和注册覆盖数量未导入验证。`tasks/GameUi/page.py` 是兼容导出层，6个 page.py 只有5个是业务页面文件。证据：AST统计、`GameUi/USAGE.md:7`、`page_definition.py:266`。

54个任务入口中，48个直接调用 goto_page。其余6个经核对：

| 入口没有直接 goto_page | 实际链路 |
|---|---|
| Exploration | 继承 SoloScriptTask（`script_task.py:14`、`:21`），经 BaseExploration 使用导航（`base.py:118`） |
| RichMan | 组合 Mall/Guild/ThousandThings/Shrine（`script_task.py:19`），例如 `guild.py:28`、`shrine.py:22` |
| FindJade | `script_task.py:29`、`:33` 动态调用 WantedQuests，后者 `script_task.py:40` 等使用导航 |
| FrogBoss | `script_task.py:74` 调 RightActivity.enter，`RightActivity/right_activity.py:15` 使用导航 |
| Restart | 继承专门登录处理器（`Restart/script_task.py:24`），`Restart/login.py:18` 是 BaseTask 路线 |
| AutoCheckinBigGod | 大神 App 的签到/Frida/HTTP 路线；不是普通游戏页面导航任务（`script_task.py:36`、`:75`、`:458`） |

这意味着至少52个入口在直接或间接路径上**存在**图导航使用，**不意味着每个分支都导航成功，或整个任务均已图化**。旧式 `ui_goto/ui_goto_page/ui_get_current_page/try_close_unknown_page/run_additional` 在54个入口中 AST 调用计数均为0。

### 6.2 “还在硬编码”的可复现口径

【代码核实】按“ScriptTask 类内存在 while，循环子树内调用 appear/appear_then_click/ocr_appear/ocr_appear_click/ui_click/click”扫描，**47/54个入口类**命中。这是保守的语法指标，不包含继承实现，也不能区分“必须保留的战斗循环”与“应该图化的跨页导航”。

已核实的并存实例：

- Orochi 先 goto_page，再手写选层、组队与战斗循环：`script_task.py:127`、`:135`、`:150`、`:276`。
- FrogBoss 通过组件回主界面，但活动入口切换仍由 ui_click 完成：`RightActivity/right_activity.py:15-18`；活动内部 `FrogBoss/script_task.py:93` 继续循环。
- Exploration 的真正实现移到 base/solo，入口本身极短；仅搜入口会漏掉其 `base.py:118` 导航和 `solo.py:123` 状态循环。

【推断】准确描述是**公共移动已广泛图化，玩法内部大量过程式控制**。把所有 while 都迁移成图不是合理的完成标准；新增任务的成本仍是页面识别、进出边、局部状态循环和失败恢复。

### 6.3 框架能力与边界

【代码核实】任务级 NavigatorSession 在 `navigator.py:64-68` 创建，克隆 Page 和 transitions（`session.py:52-68`）；Dijkstra 边权为目标页 cost + transition.cost + penalty（`navigator.py:439`）；两帧确认见 `:159-174`；同边失败计数逢3次尝试关未知页（`:872`），超时抛 GamePageUnknownError（`:896`）。

实际构图集合为**global + 目标分类 + 当前页分类（若有）+ 本任务分类**。`_navigation_graph_categories` 返回前三者（`:122`），调用方还补本任务（`:397`）。指南 `:533` 漏了最后一个。

新增任务至少要：

1. 在 ConfigModel 和菜单登记，按任务→组→字段建模；依据 `config_model.py:89`、`config_menu.py:24`。
2. 如果加入独立页面，写 `tasks/<Task>/page.py`，声明识别规则及可达的双向/单向边；参考 `Orochi/page.py:8-16`。
3. page.py 能自动发现，但**不是隔离加载**：`registry.py:78-90` 对所有一级任务 page.py 逐个 import，没有局部异常保护。新 page.py 的导入错误可能影响其他 GameUi 任务初始化。
4. 注册只扫一次（`registry.py:76`），并且 `register` 直接覆盖同键（`:37`）。【推断】修改页面定义后应重建实例验证，不能假定热刷新；键冲突可能影响全局图。
5. 新任务构造时走 `super().__init__`，让 BaseTask 和 GameUi 完成初始化；任务级 session 不会自动继承上一任务的惩罚和当前页状态（`script.py:567`、`navigator.py:67`）。

## 7. 主控制流及质量风险

### 7.1 主链路的准确版本

| 阶段 | 代码核实 | 与旧文档的关系 |
|---|---|---|
| GUI 启动 | `gui.py:16` 起OCR；`:22-35` 创建QML宿主 | 基本一致，但并非启动GUI就立即调 loop |
| GUI 实例 | `process_manager.py:111` 创建 GUI 专用 ScriptProcess；其 `run:43-48` 创建 Script 并运行zerorpc服务 | 需要另一次 start_script RPC |
| GUI 开始调度 | `process_manager.py:465` → `script.py:747-749` 创建线程 | loop 是子线程 |
| Web 启动 | `server.py:75-89` 选择host/port、OCR、uvicorn factory；`app.py:75` 可自动启动配置 | 是独立宿主 |
| Web 实例 | `main_manager.py:14` 导入的是 server.script_process；`script_process.py:43` 创建子进程，`:152` 直接调用loop | **与GUI不是同一个ScriptProcess类，也不走同一套RPC控制** |
| 选任务 | `script.py:329` 调 Config.get_next；`config.py:186-211` 分pending/waiting并排序；`script.py:334` 风控、`:337` 排队 | 基本一致，忽略了首次Restart跳过与桌面登录补跑 |
| 实际执行 | `script.py:671` 跳过首次Restart；`:689` 未登录桌面先改为Restart；`:702` 调run | 不是单纯“选到哪个就直接跑哪个” |
| 动态加载 | `script.py:562-567` 先截图，再动态加载并实例化；`module/base/utils/utils.py:898-901` 执行模块、写固定模块名 | 每次调用创建任务实例，非长期共享一个ScriptTask |
| 感知/执行 | `BaseTask.__init__:52` 保存config/device；`:204` 用现有image匹配，`:149` 显式截图，`:531-533` 委派点击 | appear 本身不保证刷新截图；Device也并非由BaseTask创建 |
| 结束 | `BaseTask.set_next_run:689` 写调度；`Script.run:568` 捕获TaskEnd返回True | 两个动作职责不同，不能互相替代 |

【代码核实】普通 Python return 不会被当作成功：`Script.run` 未在 `ScriptTask.run()` 返回后 return True，函数落到末尾返回 None；随后 `script.py:711` 作为失败计数。故“必须 TaskEnd”的操作建议成立，但“否则调度器认为永远没跑完”不准确。反过来，抛 TaskEnd 也**不会自动设置下次时间**，任务可能再次到期被选中。

GameNotRunningError 返回 True 并调度 Restart（`:570-574`）；Stuck/TooManyClick、Bug、UnknownPage 返回False并调度Restart，其中均有10秒等待（`:575-603`）。连续失败是按任务名累积到下次该任务成功清零，不要求整个调度序列中三个任务紧挨着（`:710-714`）。这是比指南“记一次失败”更完整的恢复语义。

### 7.2 按“会不会咬到二开者”排序

以下按本地增加任务/配置的遇到概率和修复成本排序；**一旦对不可信网络开放，安全项应升到第一位**。

| 顺位 | 风险 | 实际影响范围与证据 |
|---:|---|---|
| 1 | 配置两端协议、类型与保存语义不统一 | 新字段最容易立刻踩到；见 §4。比“配置有双写”更关键 |
| 2 | 资源契约脆弱、已有重名、错误流程缺回归保护 | 修改JSON、加模板和改公共战斗组件均直接受影响；见 §5 与下文CI证据 |
| 3 | exit(1) 的宿主差异与调度线程无法重建 | Web实例退出；GUI可能保留RPC但失去任务线程；`script.py:609/615/621/729/747` |
| 4 | 同步等待与async接口中直接执行重工作 | 任务内主要影响当前实例；HTTP同步生成/OCR工作会影响服务事件循环；`tool_router.py:319/336` |
| 5 | API修改能力与监听边界 | 服务开启且可达时，影响规则、配置和进程操作；不是单纯“CORS是否美观” |
| 6 | 裸except掩盖特定错误 | 大部分是局部回退/日志，不是每处都会静默吞掉；见下文 |
| 7 | 导入副作用、依赖清单与环境约束 | 离线测试、嵌入复用、新机安装都受影响；`logger.py:59/369`、`generate_requirements.py:14` |

#### exit(1)：8处在 Script，不能等同杀掉整套应用

【代码核实】AST找到20个 exit/sys.exit/os._exit 调用点（包含安装器、正常GUI退出和信号处理）；`script.py` 的8处均是失败退出：75、78、88、91、609、615、621、729。数目本身不代表20个同级缺陷。

- Web：实例子进程主线程跑loop，`server/script_process.py:153-158` 捕获SystemExit、上报WARNING后退出。Web宿主及其他实例不因这段退出而直接死亡。
- GUI：主线程跑zerorpc，loop在Thread中。SystemExit结束调用线程，`start_loop` 不清理旧线程引用。隔离验证再次调用start_loop仍只有一次启动。**推断**：用户可能看到实例进程存活，却无法仅靠“开始任务”恢复，需重建实例。
- GUI实例 `run` 的裸except（`gui/process/script_process.py:49`）是外层主线程的捕获，不能捕获另一个线程的异常。
- config/device 的cached_property也有exit；它们可能从调度或RPC触发，影响要按具体上下文判断。没有做RPC框架内部调度行为实测，不统一断言退出进程。

#### 同步阻塞：155处有效 time.sleep，不是165个活跃调用

【代码核实】对允许读取Python做AST扫描，得到155个 `time.sleep(...)`：tasks113、module39、根script3。它不包含 `from time import sleep`、`Device.sleep`、`Timer.wait`，也不包含注释中的“sleep”；因此也不能当成全部阻塞点总数。

调度空闲每5秒检查配置（`script.py:318`），队列等待30秒（`:391`）。战斗等待有0.6/0.5/0.3秒轮询（`battle_wait.py:1101/1350/1476`）。【推断】当前实例响应条件变化的延迟受轮询粒度影响，但不是每个sleep都阻塞整个GUI或所有实例。

GUI停止使用进程terminate（`gui/process/script_process.py:59`），并不必须等sleep醒来。Web还有一个**更直接的停止缺陷**：`script_router.py:117` 不await `ScriptProcess.stop()`，而后者是async（`server/script_process.py:50`）；`start:42` 同样漏await。**推断**：HTTP stop可能只创建协程而不执行停止，重启路径也可能遗留旧实例。此项是静态核实的调用缺口，未启动服务复现。

“需要长任务就写async def”是错误建议：标注器测试/保存路由在async函数中直接调用同步方法（`tool_router.py:321`、`:338`），生成器有同步文件遍历写入（`tool.py:1354`）。应把真正耗时操作移出事件循环；本次不修改实现。

#### CORS与写接口：确实有风险，但“无路径校验”是错的

【代码核实】

- CORS允许任意origin/method/header，并启用credentials：`app.py:36-42`。
- 被检查的app/路由链没有有效身份验证依赖；`app.py:100` 虽解析key参数，后续factory只设置启动实例并返回app（`:113-126`），没有用它保护接口。
- `source/create/delete` 只创建/删除tasks内的JSON，不是任意路径写.py接口（`tool.py:931-963`）。
- 路径先resolve，再relative_to校验；JSON和图片分别有限制后缀（`tool.py:833-867`、`:1097-1099`）。
- 规则保存会写JSON，并生成目标assets.py（`:1341-1354`）；生成器文本转代码的信任问题见 §5。
- 默认/本机配置都为0.0.0.0、22267（`deploy/config.py:57-58`、`config/deploy.yaml:124/128`），22270只是 `server.py:76` 的末级fallback。

【推断】网络可达且无外层鉴权时，调用者可损坏合法任务规则、触发生成、控制脚本。CORS放大浏览器来源访问面，但**不能仅凭这几行证明任意浏览器/任意网站必定成功跨域**；浏览器本地网络策略、凭证模式、防火墙均未验证。服务端鉴权问题也不依赖浏览器CORS才成立。

额外核实：OCR默认绑定0.0.0.0（`module/ocr/rpc.py:59`、`:116`），RPC方法对收到的bytes直接 `pickle.loads`（`:135`、`:147`）。【推断】若该RPC暴露给不可信调用者，危险程度超过普通规则误改，应作为独立安全边界处理。**未发送任何测试载荷，未核实端口实际开放或可利用性。**

#### 裸except：17处属实，但传播面不同

【代码核实】AST计数17处：deploy2、module10、tasks5。

- 端口探测：`process_manager.py:45` 将异常当端口未占用，可能误判。
- 实例运行/日志初始化：`gui/process/script_process.py:49/80` 记录后重新抛出，**没有静默吞掉**。
- 窗口树兼容：`device/handle.py:389`、`windows_impl.py:153` 尝试另一个分支，可能掩盖结构变化原因。
- 业务回退：`Dokan/script_task.py:439` 选择默认攻击优先级；错误配置可能被静默降级。
- `config_menu.py:67` 位于main测试段，不是正常菜单路径的运行风险。

所以处理顺序应按活跃调用链和恢复语义定，不能“17处都一样严重”。

#### CI与测试：测试少不等于零，但没有核实到仓库测试门禁

【代码核实】7个跟踪测试文件，共1167物理行；已知坏文件 `tests/tasks/Component/GeneralBattle/test_battle_wait.py:10` 导入 `_DEFAULT_PER_BATTLE`，对应实现中搜索不到该定义。未跑收集，不冒称本次实际ImportError。

命令 `rg -n 'pytest|unittest|python -m pytest' .github/workflows -g '*.yml' -g '*.yaml' -g '*.md'` 无匹配；核对自动合并流程 `auto-merge-pr.yaml:16-43` 为查PR再gh merge，Copilot setup `copilot-setup-steps.yml:20-26` 只checkout和装gh-aw。**本地workflow未发现执行仓库测试的步骤。**

远端branch protection、外部check、组织级required workflow **未验证**，所以只能说“仓库内缺少可见测试门禁”，不能断言GitHub绝对没有任何外部保护。旧“43 passed + 16 subtests”亦未验证。

## 8. README与背景边界

1. **GUI技术栈**：【文档声称】README `:62` 使用Flutter搭建全平台界面。【代码核实】本仓入口导入PySide6，建立QGuiApplication、QQmlApplicationEngine并加载本地QML（`module/gui/fluent_app.py:7-8/35/40/50`）。另一个外部客户端是否Flutter，不在本次验证范围。
2. **与游戏解耦**：【文档声称】README `:61` 强调更通用。【代码核实】module/atom也存在游戏专用规则：`module/atom/ocr.py:80`；设备层包含阴阳师桌面窗口实现。因此是有分层的游戏框架，不是完全无业务依赖的底座。
3. **“全仓不注入”不能直接接受**：【代码核实】主游戏路径确实是截图、模板/OCR、设备输入，但 AutoCheckinBigGod 对 `com.netease.gl`（大神App）使用Frida附加与Java调用：`script_task.py:36/458/658/722`，依赖声明 `requirements-in.txt:34-36`。没有证据把这等同于注入阴阳师游戏进程，但“仓库所有任务都不注入”不成立。
4. **Windows边界**：README `:11` 标Windows；桌面后端确为Win32，但 `device.py:15-19`、`platform2/__init__.py:3-6` 有平台分支，`server.py:12-25` 也分平台设时区。旧报告用“desktop_impl顶层Win32 import、_tzset”直接证明整个仓库不可能跑Linux，论证不足；Linux/macOS运行能力**未验证**。
5. **安装契约**：requirements未声明PySide6，`generate_requirements.py:14` 还会剔除小写pyside6；`:21-22` 的qml分支在找不到时调用index而非添加。【推断】新机依赖安装与桌面入口存在缺口，但本次没有清洁环境安装实验。不要引用旧文档认定“环境已全配好”。

许可/上游历史沿用用户提供的项目背景，不在本次法律或远端核验范围；未据此给出许可合规判断。

## 9. 对既有文档的更正

以下是明确发现的不一致，不是为了凑数推翻正确结论。

| 文档说X（定位） | 实际Y | 证据 |
|---|---|---|
| 旧报告 `:50`：剔除生成物后63,113行/457文件 | 其边界漏掉79个assets；本次口径378文件/68,719物理行、59,139非空行。旧计数口径不明，不能直接比较增长率 | §3只读命令；`assets_extract.py:366` |
| 旧报告 `:102/357`：59个游戏任务 | 59是排除Component/GameUi后的目录数；实际54个顶层入口，56个模型登记，三者不等价 | 文件清单、AST统计；`config_model.py:89-91` |
| 指南 `:452`：加字段自动出GUI；`:306` 的顶层字段模板 | 只有受支持的分组/schema布局才有机会；桌面端还存在v1/v2协议不匹配 | `ModelParse.js:16/79`、`Args.qml:561`、`config_model.py:316/335` |
| 指南 `:443-450`：HTTP→gui_args一条链 | HTTP用script_task；桌面用RPC/gui_args；两套解析与setter | `script_router.py:122`、`process_manager.py:240` |
| 指南 `:433-435`：Time等自动是时间控件 | QML只有六种分派，没有time/date_time/time_delta分支 | `Args.qml:74-115`、`config_base.py:56-69` |
| 指南 `:457-463` / 旧报告 `:230`：嵌套字段每次赋值自动保存，普通GUI双写 | 根模型赋值才自动保存；叶字段显式save必要；整任务copy另有双写 | `config_model.py:170/421/432`、`script.py:203` |
| 旧报告 `:303/345`：配置没锁，应加FileLock | 已有FileLock+原子写；需要考虑的是跨快照读改写一致性 | `config/utils.py:85-99` |
| 指南 `:180`：long_click duration单位秒 | 毫秒，执行时除1000 | `long_click.py:13`、`base_task.py:531` |
| 指南 `:203-212`：list规则roiFront用数组 | ListExtractor要求逗号字符串并split | `assets_extract.py:233` |
| 旧报告 `:336`：assets_extract裁模板并生成 | 生成器只产Python；裁图在标注器 | `assets_extract.py:68`、`tool.py:1423` |
| 指南 `:401`：不抛TaskEnd就被认为没跑完 | 普通return使Script.run返回None，进入失败逻辑；设置next_run是另一职责 | `script.py:567-569/711`、`base_task.py:689` |
| 旧报告 `:163`：GUI/Web共用同一ScriptProcess类 | GUI持有Process子类跑RPC+loop线程；Web是包装器创建子进程直接跑loop | `gui/process/script_process.py:10/48`、`server/script_process.py:23/43/152` |
| 指南 `:112` / 旧报告 `:188/302`：exit总是杀整实例 | Web主线程退出实例；GUI调度线程退出可留下活实例，且start_loop不重建死亡线程 | `script.py:747`；线程隔离实验 |
| 指南 `:539-541` / 旧报告 `:265`：6个page.py、110处Page说明迁移浅 | 51个静态构造调用点；48入口直接、4入口间接导航；47入口仍有过程式循环，两种状态并存 | §6 AST统计与调用链 |
| 指南 `:533`：构图只含当前/目标/global | 调用方还加入本任务category | `navigator.py:397` |
| 指南 `:404`：@interval_timer返回缓存结果 | BaseTask没有该装饰器；未到间隔直接False，到了才匹配 | `base_task.py:193-209`；限定源码搜索无装饰器定义/用法 |
| 旧报告 `:310`：标注器写接口缺路径校验 | 存在resolve+根目录校验+后缀限制；主要问题是未鉴权、监听范围及生成器信任输入 | `tool.py:833-867/931-963` |
| 旧报告 `:78/330`：Web默认22270 | 部署默认及本机配置22267；22270是fallback | `deploy/config.py:58`、`server.py:76` |
| 指南 `:247`：“只在本机用”可能被理解为当前绑定本机 | 当前配置是0.0.0.0，不是127.0.0.1 | `config/deploy.yaml:124` |
| 指南 `:754` / 旧报告 `:231`：argument目录只有args.json有引用，其余死代码 | settings.py读取setting-template.json；args引用存在于迁移空壳，不能证明活跃使用 | `gui/context/settings.py:17-25`、`config_updater.py:16-17` |
| 指南 `:758`：165处time.sleep | 排除注释的AST有效调用155；sleep总阻塞点还包括别名/封装，不能拿文本匹配数当运行次数 | §7 AST统计 |
| 指南 `:42/727`：其他cwd启动必然读不到配置 | logger import会主动改回仓库根；更准确风险是全局cwd副作用及相对路径依赖，不是该因果断言 | `logger.py:59`、`config_model.py:188` |
| AGENTS `:20`：其他分辨率直接失败 | 坐标约定确为1280×720，但检查会缓存成功，还对旋转截图、游戏未启动作临时放行 | `screenshot.py:211/222/236` |
| README `:62`：本仓GUI是Flutter | 本仓gui.py使用PySide6/QML | `fluent_app.py:7-8/50` |
| AGENTS开头/背景：所有任务均不注入 | 主游戏视觉路径成立，但大神签到任务使用Frida，需限定作用范围 | `AutoCheckinBigGod/script_task.py:36/458/658` |

尚不能认定为事实的旧结论：setuptools84必然使本仓主链崩溃、本机所有依赖已就绪、两份Qt生成资源完全相同、近90天活跃度、43 passed、跨平台绝对不可运行。尤其 `device.py:5-8` 在导入设备依赖前加载了自带pkg_resources替身，`module/device/pkg_resources/__init__.py:21-25` 改写sys.modules；这使“仅凭外部setuptools版本就断言必崩”证据不足。**未升级、未修改或验证这些依赖版本的兼容性。**

## 10. 二开决策与建议顺序

【推断】如果目标是增加/修正一个既有玩法，复用Component、BaseTask和GameUi有明显价值；证据是Orochi等任务通过多个组件组合完成流程（`Orochi/script_task.py:23`），导航已经覆盖大量入口（§6）。如果目标是提供稳定的第三方插件API、开放网络服务或跨平台产品，当前配置、生命周期与安全边界需要先处理。

在开始较大规模二开前，建议按以下具体问题形成验收项：

1. **先统一配置契约**：用一个包含标量、Enum、TimeDelta、可空字段、默认工厂的任务模型验证桌面/HTTP的展示和保存；修正schema适配与赋值校验。针对的是 §4 已确认的失败点。
2. **明确线程/进程状态机**：验证任务报错后的状态回传、重新开始、停止、实例重建；尤其是死亡loop线程和未await的stop。针对 `script.py:747` 与 `script_router.py:117`。
3. **让资源错误在生成前失败**：分型显式化、字段一致性、标识符/字符串安全、重复变量检查，避免“生成成功但类型错/旧规则被覆盖”。针对 `assets_extract.py:375` 与当前重复记录。
4. **把可离线验证的部分接入测试门禁**：配置schema、资源生成、导航寻路/分类、线程重启用替身验证；实际游戏成功率仍需实机验收。不要因没有模拟器就放弃这些纯逻辑测试。
5. **若运行服务，先界定信任边界**：核实HTTP/OCR监听、鉴权和数据反序列化，之后再考虑多用户或远程开放。依据 `app.py:36`、`rpc.py:59/135`。

上述均为建议；本次只生成报告，没有实施修复，也没有把未做的运行验证包装成通过。

