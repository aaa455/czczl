# 学习过场模板验证记录

日期：2026年11月3日。应用代码版本：`f1ea44110bdc55dd2cff989a8feb842351ca9cf9`。本记录随后的文档提交不改变应用或测试代码。

环境：Windows 11 x64、Python 3.12.14、PySide6 Essentials 6.12.0、PyInstaller 6.22.3，无新增第三方依赖。

| 命令 | 实际范围 | 结果 |
|---|---|---|
| `.venv\Scripts\python.exe scripts/validate_data.py` | 原内容、分镜关联与数据格式 | PASS：8站16题24幕占位学习内容 |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | 学习门槛、学习记录保存、旧存档、配置变更、数据校验、图片替换与回退、动画暂停/恢复/终止、自动翻页、显式答题衔接、长文本、渲染器扩展、原答题规则 | 34项全部通过 |
| `.venv\Scripts\python.exe scripts/smoke_desktop.py` | 实际Qt控件完成8站学习、小结确认和16题；错误重试、恢复、徽章和最小窗口 | PASS，首次答对15/16、掌握16/16 |
| `.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZuJiChangZheng.spec` | 单文件Windows exe，内含学习配置和播放器 | PASS |
| `.venv\Scripts\python.exe scripts/smoke_packaged.py --output .artifacts/cutscene-packaged` | 冻结程序原生启动、中文路径、无Python PATH、学习过场预览、外部包替换、无效包受控退出 | PASS |
| `git diff --cached --check` | 空白检查 | PASS |

自动交互使用独立临时存档。已查看源码版分镜、小结与1060×700窗口截图，以及最终exe原生学习过场截图，文字和控制按钮可读。机器报告与截图在忽略的 `.artifacts/`；CI结果另见PR。

首次CI运行发现测试预期路径未统一解析Windows短路径：runner的临时目录使用RUNNER~1，而实际解析返回runneradmin。已将测试预期路径同样resolve；应用路径解析与图片接口无需修改。本地相关测试重新通过，后续CI结果见PR最新检查。

exe大小38,981,165字节，SHA256：`d3617753af9fce70ec331715cbce99da81ec725c257d8466f71c5394f824c12d`。

## 限制与待完成

- 全部学习过场图文是占位模板，需团队确认表现形式后填充；不会声称已完成正式学习内容。
- 只有image_text渲染器，支持淡入及画面轻微运动；没有旁白、视频或路线聚焦类型。
- 手动依次翻页可进入小结，不强制停留时长，学习标记不代表用户实际理解。
- 未确认小结就退出时不保留播放位置；下次从第一幕重看。
- 已学习标记随分镜配置变更而更新，但同路径图片文件内容替换不触发签名变化，建议使用新文件名。
- 尚未在另一台没有Python的Windows电脑上执行验收。
