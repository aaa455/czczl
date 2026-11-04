# 章节学习内容交接：给 dsh 的上手提示词

2026年11月3日。仓库：https://github.com/aaa455/czczl 。本次交接源码位于 `codex/learning-cutscene-template` 分支，不要直接从旧main开始。

以下内容可整体复制给 dsh 或其使用的AI开发助手。

---

你现在接手《足迹长征》Windows桌面学习程序，任务是将每章学习界面的占位文案与占位背景图替换为团队提供的正式内容。请直接检查项目并完成接入，保持已确认的界面设计和学习流程。

## 先拿到正确源码

仓库为 https://github.com/aaa455/czczl ，交接分支为 `codex/learning-cutscene-template`。先读取仓库内的 `CONTRIBUTING.md`。

新电脑可以执行：

```powershell
git clone --branch codex/learning-cutscene-template https://github.com/aaa455/czczl.git
cd czczl
git switch -c codex/lesson-content-dsh
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

如果已有仓库，先检查 `git status` 并保留本机工作，再执行 `git fetch origin`。在确认本机没有未保存改动后，从 `origin/codex/learning-cutscene-template` 新建工作分支；不要重置或覆盖别人的本地改动。如果后续该交接分支已合入main，先核对main包含手记界面、山水路线和第一章三幕文案，再选择对应的新基线。

## 先了解当前状态

项目为Python 3.12 + PySide6原生Qt桌面程序，使用PyInstaller打包单文件exe。没有网页前端、浏览器服务和远程素材依赖。

已经实现并确认的界面：山水路线背景、通关红线动画、底部横向八站行程栏、B版“行军手记”顶部进度与工具栏、右侧叠层纸页。学习播放器将图片拉伸铺满窗口，仅保留右上角退出按钮；下方文字框横贯窗口，两侧浅、中间深、烟绿色半透明玻璃，正文阅读区域居中。

学习流程是：选择章节 → 开始学习 → 3—4幕图文 → 学习小结 → 用户确认后进入答题。入场动画约850毫秒，完成后开始阅读计时。支持暂停、手动翻页、重看与退出。答题每章从题库随机抽10题，同时打乱选项，本轮题目与选项顺序持久化；掌握本轮全部题目后解锁下一站。

目前内容状态：

- 第一章三幕文案已经由用户提供并接入，标题为“战略转移背景”“于都集结渡河”“出发后的思考”，时长分别为45000、35000、35000毫秒，学习小结已填入。保留这些已确认文字，除非团队明确提供修订稿。
- 第一章三张学习配图仍为空，显示程序绘制的占位背景。
- 第二至第八章，每章三幕文案、学习小结与图片仍为占位，需要接入团队材料。
- 当前共8章、172候选题、每轮完整80题、24幕。若新增第四幕，总幕数随配置变化，无需维持24幕。
- 最新本地exe是在第一章文案接入之前构建，不能用它判断最新源码内容。GitHub发布版也不代表本次交接源码。
- 上次已通过69项测试及真实Qt界面八章80题完整流程。你的修改完成后按实际结果重新验证。

## 先读这些文件

1. `README.md`：运行、抽题和打包方式。
2. `docs/LESSONS.md`：学习图文格式、图片路径、播放与存档规则。
3. `assets/content/lessons.json`：这次主要编辑的数据文件。
4. `assets/content/nodes.json`：章节顺序、背景资料及完整题库，作为知识点覆盖对照。
5. `docs/ARCHITECTURE.md`：程序边界与扩展接口。
6. `docs/JOURNAL_UI.md`、`docs/ROUTE_MAP.md`：已经确定的界面与动画。
7. `docs/question-bank-import.md`：题库待核验事项。

除非接入过程中发现真实功能缺陷，否则优先仅编辑内容、图片和来源文档。不要顺手改UI样式、地图、题库答案、抽题规则或存档实现。

## 八章对应关系

| 章 | node_id | 主题 | 当前待办 |
|---|---|---|---|
| 1 | `departure` | 瑞金·于都出发 | 配置三幕图片，保留现有文案与小结 |
| 2 | `xiangjiang` | 湘江战役 | 替换文案、小结与图片 |
| 3 | `liping` | 通道转兵·黎平会议 | 替换文案、小结与图片，区分两个地点和事件 |
| 4 | `zunyi` | 遵义会议 | 替换文案、小结与图片 |
| 5 | `chishui` | 四渡赤水 | 替换文案、小结与图片，重点讲清事件顺序和方向变化 |
| 6 | `river-crossings` | 巧渡金沙江·飞夺泸定桥 | 替换文案、小结与图片，区分金沙江、大渡河及相关行动 |
| 7 | `snow-grassland` | 翻雪山·过草地 | 替换文案、小结与图片 |
| 8 | `reunion` | 会宁·将台堡会师 | 替换文案、小结与图片，区分1935年到达陕北和1936年三大主力会师 |

## 接入步骤

1. 先检查团队交付的文字与图片目录，建立“章节—分镜—正文—图片—来源”的对应清单。不根据文件顺序猜测图片归属。
2. 长文按因果和时间顺序整理为3—4幕，一般为背景、经过、结果与意义；两个关键事件可拆为两幕经过。文字以团队确认稿为准；不要捏造史实、引语、日期或精确数字。
3. 如需整理尚未确认的文字，每幕建议90—150字，以可读为先；必要时保留更完整内容并利用现有滚动阅读。对照整章候选题库检查知识点覆盖，不能只覆盖一次抽出的10题。遗漏或冲突写入交接清单，请内容负责人补充，不擅自改答案。
4. 在 `assets/content/lessons.json` 找到对应 `node_id`，替换每幕 `title`、`text`、`image`、`image_alt`、`duration_ms` 和章节 `summary`。保留既有 `node_id`、已有场景id、`schema_version: 1`、`type: "image_text"` 与已确认的转场。添加第四幕时使用同章唯一的新id，并放入正确的场景顺序。
5. 图片放入 `assets/content/images/<node_id>/`。例如第一章首幕用 `assets/content/images/departure/background-v1.jpg`，JSON填写 `images/departure/background-v1.jpg`。路径相对于内容包目录，统一使用正斜杠，不写电脑盘符、上级目录或网络URL。确认文件真实存在且Qt可解码；空路径或坏图会回退为占位，不能仅凭程序未报错就认定接入完成。
6. 优先PNG/JPG，横向16:9，建议1920×1080或更高；避免把每张图都保存成体积巨大的无压缩文件。画面主体放中上部，底部约25%—30%留给学习文字框，右上避开退出按钮。图片内部不要烘焙标题、字幕、按钮和文字框，程序负责叠加文字。
7. 风格统一，历史场景中的装备、服饰和环境与资料匹配。AI创作图片标注为美术复原，不能冒充档案照片。新增 `docs/lesson-content-sources.md` 记录每章每幕的文字出处、图片文件名、来源/作者、生成提示词及使用说明；不编造来源或授权。
8. `duration_ms`为毫秒，允许1000—120000，按字数与难度调整，不照搬占位12秒；用户仍可以暂停或手动翻页。只替换图片时不要顺手改变已确认的第一章时长。更新同一幕图片时优先使用新文件名，便于表达学习配置更新。
9. 学习小结只归纳本章，不引入未讲过的新事实。保留“看完小结后由用户确认进入答题”的流程。

单幕数据结构示例，仅说明字段，不要复制示例正文覆盖正式内容：

```json
{
  "id": "background",
  "title": "战略转移背景",
  "text": "这里是团队确认的学习文案。",
  "image": "images/departure/background-v1.jpg",
  "image_alt": "配图的具体场景说明，AI创作时注明美术复原",
  "duration_ms": 45000,
  "transition": "fade",
  "type": "image_text"
}
```

`summary`填写在对应章节条目上，与 `node_id`、`scenes` 同级。不要添加当前加载器不认识的新字段来替代正文或来源记录。

## 验证与交付

```powershell
.\.venv\Scripts\python.exe scripts/validate_data.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_desktop.py --output .artifacts/dsh/ui
git diff --check
```

先运行源码检查：

```powershell
.\.venv\Scripts\python.exe main.py --data-dir .artifacts/dsh/manual-save
```

使用隔离演示存档，逐章完成学习和答题，核对所有分镜实际加载正确图片、正文完整、小结正确、确认后正常答题。检查至少1060×700和1240×820两种窗口；检查空格暂停、左右翻页、R重看、Esc返回和重新进入。不要清空团队成员自己的存档。

`main.py --preview-lesson`只预览当前学习节点，不能据此认定八章都已验收。全流程脚本会跳转动画来检查状态，也不能替代逐幕看图与阅读排版检查。你可以在 `.artifacts/` 写临时预览脚本定位章节，避免为了预览向生产代码添加后门或解锁逻辑。

修改学习配置只改变相应章节的学习签名，可能要求未通关章节重新学习；不会清空已有题目成绩。不要修改nodes.json的题目、答案或顺序来配合文案，这会改变题库签名并影响旧档。

交付前检查所有章节是否仍有占位文本、占位小结、空图片路径或失效图片，列出尚未拿到的材料。图片不齐时明确报告缺口，不以复用无关图片或编造内容伪装完成。继续已提供材料的接入，不因某一幕缺图停止其他可完成工作。

完成后提交实际修改的JSON、学习图片、来源文档与必要说明，推送自己的分支，通过PR合入交接分支或团队约定的main。不要强推。不要提交 `.venv`、`.artifacts`、`build`、`dist`、个人存档或任何密钥。最终报告每章完成状态、配图数量、验证结果、缺失资料，以及是否重新打包。

本任务优先交付内容源码。只有团队明确要求时再重新打包exe；内置内容更新必须重新打包才会进入exe。需要打包时：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZuJiChangZheng.spec
.\.venv\Scripts\python.exe scripts/smoke_packaged.py
```

产物为 `dist/ZuJiChangZheng.exe`。exe通过团队约定的Release或构建产物共享，不塞入源码提交。

请先回复你检查到的章节材料与缺口，然后按已提供的资料开始接入，完成后给出可复核的修改清单。
