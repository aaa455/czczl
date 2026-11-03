# 足迹长征 Windows桌面版

参赛团队的原生桌面学习程序。采用纸墨配色、左侧路线与右侧内容面板，包含8个学习节点、24幕学习过场模板、172道候选题；每章随机抽10题、选项随机排列，一次完整学习共80题，支持顺序解锁、本地进度与PNG纪念徽章。

当前版本为 **v0.3.0-preview 沉浸式学习与随机题库预览**：背景铺满窗口，仅保留退出按钮，底部文字框横贯窗口，两侧浅、中间深，采用渐变磨砂玻璃效果与居中浅色文字。Windows exe通过仓库的[Releases页面](https://github.com/aaa455/czczl/releases)提供。题库已从团队提供的Word导入，过场图文尚为占位，历史内容、题目措辞与来源仍需要A核验。不是最终参赛定稿。

## 运行

Windows 64位，团队统一使用Python 3.12。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py
```

只运行源码可安装 `requirements.txt`。依赖使用PySide6 Essentials，提供Qt Widgets、Gui、Core，无需安装完整的WebEngine组件。

## 学习过场模板

点击“开始本段学习”进入沉浸式播放器：历史背景、事件经过、理解与思考，共三幕，每幕默认12秒，按时自动切换。图片拉伸至整个窗口，播放期间隐藏原窗口标题栏、顶部导航与底部状态栏，退出后恢复路线窗口。

进入学习时约850毫秒过渡：路线先压暗，随后学习背景淡入，最后玻璃文字框淡入并上移12像素。第一幕阅读时间从入场完成后计算；过渡时禁止重复进入或翻页，退出仍可用。切出窗口会暂停入场动画，点击画面或按空格继续。

点击文字框或按右方向键翻页，左方向键回看，空格暂停 / 继续，R键从头重看，退出按钮或Esc返回路线。切出窗口自动暂停，点击文字框或按空格继续，不会因此跳过当前分镜。长文字可在框内滚动阅读。最后显示学习小结及“学习完毕 · 点击此处开始答题”，点击文字框或按回车后保存学习标记并进入题目；不会自动开始答题或提交答案。

所有过场现为占位图文，方便先确认展示形式。A/C在 `assets/content/lessons.json` 修改每幕的 `title`、`text`、`image`、`image_alt`、`duration_ms`，以及每站 `summary` 即可填充内容。`image` 留空或图片加载失败时显示占位画面。详细格式与填充步骤见 [学习过场配置](docs/LESSONS.md)。

直接预览当前站的过场：

```powershell
.\.venv\Scripts\python.exe main.py --preview-lesson
# 或打包后
.\dist\ZuJiChangZheng.exe --preview-lesson
```

学过的节点可直接继续答题，也可重新观看。未确认完成的过场退出后从第一幕重看。旧答题记录保留；已通关节点仍可直接复习。替换分镜配置会使该站学习标记需要更新，但不清空题目成绩。更换同路径图片的文件内容不会自动改变标记，正式替换时建议使用新文件名。

## 随机题库

内置172题（164道单选、8道多选），各章21—22题；每章第一次进入答题时随机抽取10道不重复的题，并打乱每题选项。题目和选项顺序先保存再显示，返回、重启或错题重试都沿用本轮，继续答题定位至未掌握题目。答对本轮10题即可解锁下一章，不要求做完候选题库。多选须完全选对，少选、多选不通过。

统计与徽章按本轮共80题计算；已完成章节的复习沿用本轮，“重新出发”清空进度后重新抽取。`quiz_size`缺省的外部包保持原来的全部题目模式，少于配置题量的小内容包使用全部题目。题库或抽题规则修改会备份旧存档并重新开始，建议用`--data-dir`提供独立演示目录。

Word导入格式为`chapters`，每章包含`chapterId`、`title`、`questions`和可选`mustTeach`。导入工具将题目映射到现有章节，不改变地图和学习模板：

```powershell
.\.venv\Scripts\python.exe scripts/import_question_bank.py "C:\路径\题库.docx"
.\.venv\Scripts\python.exe scripts/validate_data.py
```

题库导入、明显文字修正、待核验问题与文档附带必讲清单见[题库导入记录](docs/question-bank-import.md)。来源尚未逐题补齐，`review_status`保持`draft`；数据校验不代替史实审核。学习模板仍待正式文案填充。

## 打包exe

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZuJiChangZheng.spec
```

产物：`dist/ZuJiChangZheng.exe`。目标电脑无需安装Python，源码与打包文件使用同一内容包。开发者应在未安装Python的另一台Windows电脑验收，不能用“打包成功”代替独立电脑核验。

打包后检查独立启动、中文路径和外部内容包：

```powershell
.\.venv\Scripts\python.exe scripts/smoke_packaged.py
```

该检查会在同一台电脑的隔离目录运行exe，移除PATH中的Python；仍不等同于在另一台无Python电脑验收。

v0.3.0-preview的构建提交、文件校验值与核验结果见[交付记录](docs/release-v0.3.0-preview.md)。

## 检查

```powershell
.\.venv\Scripts\python.exe scripts/validate_data.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_desktop.py
```

最后一条驱动真实Qt按钮完成错误重试、全部节点、进度恢复和徽章导出，隔离测试存档，截图保存在忽略的 `.artifacts/ui/`。它是自动交互检查，不代替C的人工体验测试。

## 外部内容包与独立演示存档

```powershell
.\dist\ZuJiChangZheng.exe --content-dir "D:\我的内容包" --data-dir "D:\演示存档"
```

外部目录内需有符合 [内容格式](docs/DATA.md) 的 `nodes.json`，可同时提供 `lessons.json` 和它引用的相对路径图片。缺少学习配置的节点自动使用三幕占位模板。参数缺省时使用内置内容和Windows用户应用数据目录；不向exe所在目录写进度。外部包是完整替换，不是增量合并。

题目、选项或顺序变化会保留旧存档备份并重新开始；仅修改故事、来源或界面样式不清空进度。同一时刻请只打开一个使用相同存档的程序实例；当前没有并发存档合并功能。

## 三人分工

| 成员 | 主责 | 入口 |
|---|---|---|
| A 内容 | 故事、题目、来源核验 | `assets/content/nodes.json`、`docs/content-sources.md` |
| B 开发与集成 | 规则、存档、窗口、依赖、打包 | `app/`、`main.py`、`.spec` |
| C 视觉与测试 | 配色、路线绘图、题目布局、体验与材料 | `assets/styles/`、`app/ui/route_map.py`、`docs/test-records.md` |

开始修改前先认领文件；C要改窗口或答题界面时先与B约定。所有工作通过短期任务分支和PR进入 `main`。

## 项目结构

```text
main.py                     组装内容、存档、规则与界面
app/models.py               类型与Protocol接口
app/content.py              JSON内容加载与校验
app/learning.py              解锁、答题、统计与题型注册
app/lessons.py               学习分镜加载、校验、占位与签名
app/storage.py               原子存档与异常备份
app/ui/route_map.py          原生路线绘图
app/ui/questions.py          题型视图注册
app/ui/window.py             窗口与面板注册
app/ui/lesson_player.py      大画面学习播放器、动画与渲染器接口
app/ui/badge.py              可替换的徽章导出
assets/content/nodes.json    内容包
assets/content/lessons.json  分镜图文、时长与学习小结
assets/styles/theme.qss      视觉样式
scripts/                    校验、界面冒烟、打包脚本
tests/                      内容与学习规则测试
docs/                       数据、接口、协作与核验说明
```

扩展路径见 [架构与扩展接口](docs/ARCHITECTURE.md)。参考来源及调整见 [参考说明](docs/REFERENCE.md)，第三方组件见 [THIRD_PARTY.md](THIRD_PARTY.md)。
