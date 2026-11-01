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

当前已提供单选 `single_choice` 与多选 `multiple_choice`。新增题型须同时注册判定和视图，并保证当前内容格式足以表达该题型。自由文本、拖拽题等可能需要新数据契约，应先讨论并升级schema，不声称任意题型都能仅靠JSON实现。

## 题型注册示例

在入口组装处创建 `default_registry()`，调用 `register("new_kind", evaluator)`；将其传入 `LearningService`。随后创建 `default_views()`，注册同名视图，传入 `MainWindow`。

默认类型名称不得覆盖。当前内容校验脚本使用内置注册表；添加新题型时也需更新脚本的组装入口。

## 学习规则

- 节点按数组顺序解锁，全部题目掌握后下一站开放。
- 错误可重试，首次结果保留；复习不重复累加正确数。
- 指标是学习进度、首次答对和已掌握题数，不把知识题成绩作为精神品质评定。
- 完成情况从题目状态推导；没有写死8站、每站2题或160分。
- 存档先原子写入成功，再更新内存状态；异常时保留原进度。
- 题目、答案、选项或顺序变化改变签名，旧档备份后重开；故事、解析、来源、配色调整不改变签名。
- 当前为单用户单实例存档，暂不支持多实例同时写入或云同步。

## 文件归属

A改内容数据，B改模型、校验、学习与存档，C改样式及认领的UI模块。`models.py`、`main.py` 和schema属于共享接口，修改先说明影响、共同确认后进行。

## 待扩展而未实现

图片/音频字段与播放、精确GIS地图、更多学习章节、正式内容核验流程、数字签名、跨设备同步与安装向导。现阶段的外部内容包仅包含文本、题目和示意坐标，不会自动导入任意图片资源。
