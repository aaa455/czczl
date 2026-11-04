# 行军手记本地构建记录

日期：2026年11月3日。Windows x64，按用户请求打包当前工作目录，包含尚未提交的界面改动；未推送或发布GitHub版本。

- 文件：`dist/ZuJiChangZheng.exe`，42,800,815字节。
- SHA256：`31d945cbfb043a17a061c3a9ee1999d85dad8d3fbcec8c05a33df0b021358472`。
- 环境：Python 3.12.14、PySide6 Essentials 6.12.0、PyInstaller 6.22.3。
- 命令：`.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZuJiChangZheng.spec`。
- 包含：山水路线背景、通关描线、横向行程栏、B版行军手记界面，以及原有随机题库和学习过场模板。正式章节学习图文尚未填入。

## 验证结果

- 69项测试通过；8章、172候选题、每章10题、完整80题与24幕模板校验通过。
- 真实Qt控件完成8章学习及80题，覆盖展开内容、小窗口操作、错题重试、存档恢复、通关进度及徽章输出。
- exe在中文路径及移除Python的PATH环境下启动正常；已检查实际exe主界面和学习预览截图。
- exe外部单章内容包正常替换；无效内容目录按预期可控退出。

机器报告和截图保存在`.artifacts/journal-build/ui`及`.artifacts/journal-build/packaged`。构建清单与校验文件在dist目录。核验在当前电脑的隔离目录完成，尚未在另一台干净Windows电脑上验收。
