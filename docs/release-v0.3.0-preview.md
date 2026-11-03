# v0.3.0-preview 交付与核验记录

日期：2026年11月3日。Windows x64预览版，学习分镜仍为占位图文，题库为待核验草稿。

## 构建对应关系

- exe对应源码提交：`8e0e1a048b4385501daf78294221231949a94140`。
- 环境：Windows 11 x64、Python 3.12.14、PySide6 Essentials 6.12.0、PyInstaller 6.22.3。
- 命令：`.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZuJiChangZheng.spec`。
- 文件：`ZuJiChangZheng.exe`，39,018,053字节。
- SHA256：`e1235f8a63343b1298d43ab96281fc285b3bf6de01b6aa134bce33155cb2d42e`。
- 发布标签后增加的提交仅记录交付文档，程序源码与上述构建提交一致。

## 已通过检查

| 范围 | 结果 |
|---|---|
| 内容校验 | 8章、172道候选题、每章随机10题、完整80题、24幕学习模板 |
| 单元测试 | 50项通过 |
| 源码真实Qt交互 | 全部8章学习与80题，含错题重试、持久化题序与选项、徽章导出 |
| exe原生启动 | frozen=true，8章、80题 |
| 中文路径 | exe复制为中文文件名、使用中文工作目录后正常启动 |
| 无Python PATH | 从PATH移除Python及相关环境变量后正常启动 |
| exe学习预览 | 全窗背景、退出按钮、横贯底部的渐变玻璃文字框显示正常，已查看截图 |
| 外部内容包 | 完整替换为单章题库，按10题统计 |
| 无效外部目录 | 可控退出并输出错误记录 |

机器报告和截图保存在本地忽略目录 `.artifacts/release-v0.3/ui/` 与 `.artifacts/release-v0.3/packaged/`。打包核验在当前电脑隔离目录运行，尚未在另一台干净Windows电脑上验收。

## 下载与使用

从[GitHub预发布版本](https://github.com/aaa455/czczl/releases/tag/v0.3.0-preview)下载exe直接运行，或下载包含exe、源码、使用说明与第三方许可的Windows交付ZIP。校验文件列出发布资产的SHA256。

学习结束后点击底部文字框或按Enter进入答题。随机题目和选项会保存；退出重启、重试或复习继续本轮。需要全部重新抽题时使用“重新出发”。普通运行使用用户应用数据目录存档，不向exe所在目录写入。

## 内容状态

图文接口与外部内容包接口保留，正式素材可以后续填入。题库来源、史实与措辞仍需内容负责人逐题核验，详情见[导入记录](question-bank-import.md)。本版用于团队体验与联调。
