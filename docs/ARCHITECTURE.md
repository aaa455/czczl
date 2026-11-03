# 架构与扩展接口

当前版本是Python与PySide6原生桌面程序，核心学习规则独立于Qt和磁盘。入口 `main.py` 是依赖组装处。没有HTTP服务、端口、浏览器或远程API依赖。

## 已实现的接口

| 扩展内容 | 接口/入口 | 实现方式 |
|---|---|---|
| 增加节点、题目、调整顺序 | `JsonContentRepository`、`assets/content/nodes.json` | 修改数据；节点及题数按内容动态计算，ID不要求连续数字 |
| 替换内容来源 | `ContentRepository.load() -> ContentPack` | 在入口注入实现；当前默认读取JSON，可用 `--content-dir` 更换完整包 |
| 新增题型判定 | `QuestionRegistry.register(kind, evaluator)` | evaluator接受 `Question` 与选中选项ID元组，返回bool |
| 新增题型界面 | `QuestionViewRegistry.register(kind, factory)` | factory返回 `AnswerWidget`，实现 `selected() -> tuple[str, ...]` |
| 增加右侧页面 | `MainWindow.register_panel(name, factory)` | factory返回QWidget，之后 `show_panel(name)`；名称不能重复 |
| 更换存储 | `ProgressStore.load(pack_id, signature)`、`save(progress)` | 注入SQLite等实现，UI不应直接读写存档 |
| 更换徽章输出 | `BadgeExporter.export(path, name, summary)` | 注入新导出器，例如后续SVG；当前PNG使用Qt绘图 |
| 调整整体视觉 | `assets/styles/theme.qss` | C修改样式；路线图在 `RouteMap` 中独立绘制 |
| 填充学习过场 | `JsonLessonRepository.load(pack)`、`assets/content/lessons.json` | 图文、时长、小结均为数据，缺少配置时生成三幕占位 |
| 新增分镜表现 | `SceneRendererRegistry.register(kind, factory)` | factory接受LearningScene、内容目录、节点名称，返回SceneVisual |

当前已提供单选 `single_choice` 与多选 `multiple_choice`。新增题型须同时注册判定和视图，并保证当前内容格式足以表达该题型。自由文本、拖拽题等可能需要新数据契约，应先讨论并升级schema，不声称任意题型都能仅靠JSON实现。

## 题型注册示例

在入口组装处创建 `default_registry()`，调用 `register("new_kind", evaluator)`；将其传入 `LearningService`。随后创建 `default_views()`，注册同名视图，传入 `MainWindow`。

默认类型名称不得覆盖。当前内容校验脚本使用内置注册表；添加新题型时也需更新脚本的组装入口。

## 学习规则

- 节点按数组顺序解锁，全部题目掌握后下一站开放。
- 新学习者先经过分镜与小结确认，`complete_lesson(node_id)` 保存学习签名后可以答题；`submit` 同样检查学习门槛。已完成的旧节点允许直接复习，不损失原成绩。
- 错误可重试，首次结果保留；复习不重复累加正确数。
- 指标是学习进度、首次答对和已掌握题数，不把知识题成绩作为精神品质评定。
- 完成情况从题目状态推导；没有写死8站、每站2题或160分。
- 存档先原子写入成功，再更新内存状态；异常时保留原进度。
- 题目、答案、选项或顺序变化改变签名，旧档备份后重开；故事、解析、来源、配色调整不改变签名。
- 当前为单用户单实例存档，暂不支持多实例同时写入或云同步。

## 学习播放器与生命周期

`MainWindow` 用QStackedWidget在路线工作区与LearningPlayer之间切换。播放器不直接保存数据或判断答案；通过 `back_requested`、`quiz_requested` 信号交给窗口和学习服务处理。

播放器用一个QPropertyAnimation控制当前分镜的phase与进度，phase为0—1。默认图文渲染器用它控制淡入、图片轻微缩放或占位山形缓慢移动，阅读文字保持静止。暂停冻结同一动画时钟，手动翻页可继续；关掉自动翻页后，动画结束停在当前幕。

切出主窗口或隐藏播放器时暂停；切换页面、返回路线或关闭窗口时stop并销毁播放器，停止动画与翻页回调。最后一幕只进入小结，不自动开始答题。用户可以手动依次翻页，不强制等待固定时长；这记录学习流程，不证明实际理解。

学习签名单独记录在Progress.learned_lessons，兼容缺少该字段的旧存档。学习配置更新只影响对应学习标记，不改变现有答题签名与题目成绩。`ProgressStore` 实现需完整保存新增可选字段。

自定义分镜渲染器继承SceneVisual，在paintEvent中使用phase；在入口注册后通过 `MainWindow(..., scene_renderers=registry)` 注入。当前只提供 `image_text`，没有预先实现旁白、视频或交互题型。新增类型时需同步更新校验脚本注册检查。

## 文件归属

A改内容数据，B改模型、校验、学习与存档，C改样式及认领的UI模块。`models.py`、`main.py` 和schema属于共享接口，修改先说明影响、共同确认后进行。

## 待扩展而未实现

旁白/视频播放、精确GIS地图、更多学习章节、正式内容核验流程、数字签名、跨设备同步与安装向导。当前图片接口仅用于学习分镜；内容包相对路径图片可随包替换，不支持远程图片URL。
