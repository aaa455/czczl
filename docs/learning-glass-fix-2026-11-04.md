# 学习界面双框与翻页闪变修复（2026年11月4日）

用户确认“错位”表现为两个框。五张背景图本身带有半透明矩形横条，和程序绘制的真实文字框叠加。

## 图片替换

沿用用户配置的 ia_images MCP，使用 gpt-image-2 的参考图编辑，优先 b64_json 返回；五张均首次请求成功。清理提示要求只去除横条及上下水平边缘，恢复自然纹理，保留原场景与构图，不添加文字或UI。生成1920×1080 PNG，旧v1原图保留，新文件名使学习标记按现有规则更新。原画及编辑结果均为美术复原，不作为史料原件。

| 章节ID | 分幕ID | 原图 | 替换图 | MCP素材ID |
|---|---|---|---|---|
| departure | event | `images/departure/event-v1.jpg` | `images/departure/event-v2.png` | `ebb7c8e69d7d41318224c581332feabb` |
| liping | event | `images/liping/event-v1.jpg` | `images/liping/event-v2.png` | `0ec026b127c9474cafe4f354643cb8f1` |
| zunyi | event | `images/zunyi/event-v1.jpg` | `images/zunyi/event-v2.png` | `68a3f1bda6634bdeac54269b572dd0be` |
| zunyi | meaning | `images/zunyi/meaning-v1.jpg` | `images/zunyi/meaning-v2.png` | `bf074e5e1ff3478f8057cdbbca864417` |
| xiangjiang | meaning | `images/xiangjiang/meaning-v1.jpg` | `images/xiangjiang/meaning-v2.png` | `c07c07c0c509406a895f10308007bfc8` |

## 程序调整

- 磨砂背景缓存统一使用逻辑窗口坐标，避免150%等缩放下混用物理像素。
- 翻页、暂停提示和窗口缩放时立即同步文字框与背景缓存；相同字号不重复设置样式。
- 从最终背景生成磨砂缓存，磨砂层与背景共用淡入进度，取消600毫秒时的二次截图替换。
- 缩小磨砂处理区域后计算模糊，避免在淡入期间重算。

## 执行范围

程序修复阶段新增3项回归检查，用户要求停止测试前已运行72项测试；此后按用户要求直接替换图片和打包，没有重新运行测试、截图预览或打包版冒烟检查。局部图片编辑可能改变细微纹理，以团队最终审阅为准。
