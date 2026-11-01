# 足迹长征 Windows桌面版

参赛团队的原生桌面学习程序。采用纸墨配色、左侧路线与右侧内容面板，包含8个学习节点、16道题、顺序解锁、本地进度与PNG纪念徽章。

当前为 **v0.1 开发预览**：程序流程已实现；历史内容、题目措辞与来源仍需要A核验，视觉效果由C继续完善。不是最终参赛定稿。

## 运行

Windows 64位，团队统一使用Python 3.12。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py
```

只运行源码可安装 `requirements.txt`。依赖使用PySide6 Essentials，提供Qt Widgets、Gui、Core，无需安装完整的WebEngine组件。

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

外部目录内需有符合 [内容格式](docs/DATA.md) 的 `nodes.json`。参数缺省时使用内置内容和Windows用户应用数据目录；不向exe所在目录写进度。外部包是完整替换，不是增量合并。

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
app/storage.py               原子存档与异常备份
app/ui/route_map.py          原生路线绘图
app/ui/questions.py          题型视图注册
app/ui/window.py             窗口与面板注册
app/ui/badge.py              可替换的徽章导出
assets/content/nodes.json    内容包
assets/styles/theme.qss      视觉样式
scripts/                    校验、界面冒烟、打包脚本
tests/                      内容与学习规则测试
docs/                       数据、接口、协作与核验说明
```

扩展路径见 [架构与扩展接口](docs/ARCHITECTURE.md)。参考来源及调整见 [参考说明](docs/REFERENCE.md)，第三方组件见 [THIRD_PARTY.md](THIRD_PARTY.md)。
