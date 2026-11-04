# 架构与扩展接口

当前版本是Python与PySide6原生桌面程序，核心学习规则独立于Qt和磁盘。入口 `main.py` 是依赖组装处。没有HTTP服务、端口、浏览器或远程API依赖。

## 已实现的接口

| 扩展内容 | 接口/入口 | 实现方式 |
|---|---|---|
| 增加节点、题目、调整顺序 | `JsonContentRepository`、`assets/content/nodes.json` | 修改数据；节点及题数按内容动态计算，ID不要求连续数字 |
| 替换内容来源 | `ContentRepository.load() -> ContentPack` | 在入口注入实现；当前默认读取JSON，可用 `--content-dir` 更换完整包 |
| 新增题型判定 | `QuestionRegistry.register(kind, evaluator)` | evaluator接受 `Question` 与选中选项ID元组，返回bool |
| 新增题型界面 | `QuestionViewRegistry.register(kind, factory)` | factory返回 `AnswerWidget`，实现 `selected() -> tuple[str, ...]` |
| 调整每章抽题数量 | `ContentPack.quiz_size`、`LearningService.start_quiz/questions_for` | JSON内配置quiz_size，抽题和选项顺序保存在Progress.quiz_sessions，缺省保留全题模式 |
| 增加右侧页面 | `MainWindow.register_panel(name, factory)` | factory返回QWidget，之后 `show_panel(name)`；名称不能重复 |
| 更换存储 | `ProgressStore.load(pack_id, signature)`、`save(progress)` | 注入SQLite等实现，UI不应直接读写存档 |
| 通关纪念页面 | `app/ui/memorial.py`、`assets/content/martyrs.json` | 全部节点完成后开放献花；随机展示一位人物及对应性别的本地AI纪念立绘 |
| 调整整体视觉 | `assets/styles/theme.qss` | C修改样式；路线图在 `RouteMap` 中独立绘制 |
| 更换主界面背景与曲线路线 | `assets/images/long-march-landscape.png`、`assets/styles/route-map.json` | 背景、归一化节点位置、标签偏移和每段贝塞尔控制点分开维护；不改题库签名 |
| 调整底部章节行程栏 | `app/ui/journey_bar.py`、`JourneyBar.node_clicked`、`refresh(service)` | 章节名及数量来自内容包；点击信号交给窗口导航，状态从已保存的学习进度推导 |
| 调整顶部进度及功能工具栏 | `app/ui/journal_header.py`、`JournalProgress.refresh(summary)`、`JournalTools` | 环形进度及辅助说明从LearningSummary刷新，工具按钮交给窗口处理页面切换和重置 |
| 调整右侧章节手记 | `app/ui/journal_page.py`、`PaperPanel`、`ChapterPage` | 共享纸页外壳；章节图签、可滚动正文及固定底部操作，学习/答题/前进信号交给窗口处理 |
| 填充学习过场 | `JsonLessonRepository.load(pack)`、`assets/content/lessons.json` | 图文、时长、小结均为数据，缺少配置时生成三幕占位 |
| 新增分镜表现 | `SceneRendererRegistry.register(kind, factory)` | factory接受LearningScene、内容目录、节点名称，返回SceneVisual |

当前已提供单选 `single_choice` 与多选 `multiple_choice`。新增题型须同时注册判定和视图，并保证当前内容格式足以表达该题型。自由文本、拖拽题等可能需要新数据契约，应先讨论并升级schema，不声称任意题型都能仅靠JSON实现。

## 题型注册示例

在入口组装处创建 `default_registry()`，调用 `register("new_kind", evaluator)`；将其传入 `LearningService`。随后创建 `default_views()`，注册同名视图，传入 `MainWindow`。

默认类型名称不得覆盖。当前内容校验脚本使用内置注册表；添加新题型时也需更新脚本的组装入口。

## 学习规则

- 节点按数组顺序解锁，本轮抽中题目全部掌握后下一站开放。内置172道候选题，每章无重复抽10题，选项随机排列；首次抽题先写盘，退出和重启沿用本轮。复习不重抽，重新出发清空后重抽。
- 新学习者先经过分镜与小结确认，`complete_lesson(node_id)` 保存学习签名后可以答题；`submit` 同样检查学习门槛。已完成的旧节点允许直接复习，不损失原成绩。
- 错误可重试，首次结果保留；复习不重复累加正确数。
- 指标是学习进度、首次答对和已掌握题数，不把知识题成绩作为精神品质评定。
- 题目呈现、提交校验、完成判定与统计统一读取questions_for，避免UI显示抽题、后端仍要求做完整题库。内置统计分母为80，未抽中的候选题不能提交。Random对象可注入用于确定性测试，默认使用SystemRandom。
- 完成情况从题目状态推导；没有写死8站、每站2题或160分。
- 存档先原子写入成功，再更新内存状态；异常时保留原进度。
- 题目、答案、选项或顺序变化改变签名，旧档备份后重开；故事、解析、来源、配色调整不改变签名。
- 当前为单用户单实例存档，暂不支持多实例同时写入或云同步。

## 学习播放器与生命周期

主界面根画布为RouteMap，绘制独立山水底图、曲线路径、可点击节点与标签；导航、底部JourneyBar行程栏和右侧浮动滚动面板叠在画布上。图片绘制、路径及点击命中使用同一绘图区变换，避开顶部导航和底部行程栏，不依赖固定像素位置。内置8章使用route-map.json的曲线；节点ID或顺序不同的外部包使用其node.position和直线路径。详见[路线说明](ROUTE_MAP.md)。

JourneyBar独立绘制纸色渐变背景和连接线，StationButton继承QAbstractButton绘制圆点、勾选及章节名，保留Tab聚焦、空格/回车激活与辅助说明。refresh读取service，已完成优先于当前站；回看旧章节不改变下一待完成站，全部通关后不再显示当前站。标准8章行程栏高124像素；较多章节可横向滚动，键盘焦点自动进入可见区。它不另存进度，不控制地图的描线动画。

顶部JournalProgress绘制已完成站数的环形进度，并展示首次答对计数；JournalTools使用Qt原生绘制的小图标，提供学习回顾、使用与来源、重新出发。右侧PaperPanel用Qt绘制叠层纸页，所有页面共用同一外壳。ChapterPage接收Node与当前学习状态，发出learn_requested、quiz_requested、advance_requested，不直接写存档。历史记事与精神内核在内部阅读区域滚动，底部学习/继续按钮固定；已学习后保留重看入口，通关后保留复习入口。长文字经过HTML转义后用于带行距的正文排版。详见[手记界面说明](JOURNAL_UI.md)。

RouteMap.sync_progress从已保存的连续通关节点推导目标；新通关时用独立QPropertyAnimation在1600毫秒内推进travel，按曲线弧长逐步描红，移动光点与路径共用采样点。到站或完成最终章时播放850毫秒光圈。刷新或复习不重新开始；存档启动直接恢复完成路段；重置、学习播放器切换与窗口关闭停止动画。进度不另存第二份动画状态。

`MainWindow` 用QStackedWidget在路线工作区与LearningPlayer之间切换。播放器不直接保存数据或判断答案；通过 `back_requested`、`quiz_requested` 信号交给窗口和学习服务处理。

进入学习前捕获路线画面，在窗口边框切换后交给LearningEntrance叠层，保持窗口位置和客户区尺寸。入场使用独立、可暂停的850毫秒动画：0—180毫秒路线压暗，180—630毫秒背景交叠，500—850毫秒文字框淡入并上移12像素。文字框入场以快照绘制，完成后交还真实GlassTextPanel，避免Qt嵌套透明度与阴影效果引起显示丢失。真实分镜动画时钟在入场完成后才启动，不消耗阅读时长。过渡期间拦截翻页、重看和重复进入；退出/Esc仍可用。失焦暂停入场，点击过渡画面或空格恢复；stop同时清理两种动画和叠层。

播放器用一个QPropertyAnimation控制当前分镜的phase，phase为0—1。默认图文渲染器用它控制淡入，图片按窗口大小拉伸；不再缩放图片或移动占位山形。暂停冻结同一动画时钟，点击文字框翻页，空格暂停 / 继续，左右方向键切换。分镜按时长自动播放，最后停在小结。

播放期间MainWindow隐藏标题栏、顶部导航和状态栏，退出或进入题目后恢复窗口。画面渲染器铺满播放器，GlassTextPanel在下方横贯窗口，以烟绿色蒙层与模糊采样形成两侧浅、中间深的玻璃渐变，并保留柔和投影；文字阅读区仍居中、沿用此前宽度，唯一可见按钮为退出。小结沿用同一背景和文字框，点击文字框或回车确认后发出quiz_requested。长文字使用透明滚动区域，原title与image_alt继续保留在配置与辅助说明中。图片、文字与SceneRendererRegistry接口均未改变。

切出主窗口或隐藏播放器时暂停；切换页面、返回路线或关闭窗口时stop并销毁播放器，停止动画与翻页回调。最后一幕只进入小结，不自动开始答题。用户可以手动依次翻页，不强制等待固定时长；这记录学习流程，不证明实际理解。

学习签名单独记录在Progress.learned_lessons，随机题目及选项顺序记录在Progress.quiz_sessions，兼容缺少这些字段的旧存档。学习配置更新只影响对应学习标记，不改变现有答题签名与题目成绩；quiz_size进入答题签名，变更时按题库更新规则备份旧档重开。`ProgressStore` 实现需完整保存新增可选字段。

自定义分镜渲染器继承SceneVisual，在paintEvent中使用phase；在入口注册后通过 `MainWindow(..., scene_renderers=registry)` 注入。当前只提供 `image_text`，没有预先实现旁白、视频或交互题型。新增类型时需同步更新校验脚本注册检查。

## 文件归属

A改内容数据，B改模型、校验、学习与存档，C改样式及认领的UI模块。`models.py`、`main.py` 和schema属于共享接口，修改先说明影响、共同确认后进行。

## 待扩展而未实现

旁白/视频播放、精确GIS地图、更多学习章节、正式内容核验流程、数字签名、跨设备同步与安装向导。主界面背景属于应用视觉素材，外部内容包暂不替换该背景；学习分镜图片仍可使用内容包相对路径随包替换，不支持远程图片URL。
