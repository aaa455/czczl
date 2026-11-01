# 桌面预览版验证记录

日期：2026年11月1日。功能代码提交：`cf2f616bda988e5d389b252c496fe8d2e211821b`。后续提交只调整打包核验脚本的动态题量读取并补充本报告，未改变应用功能。

环境：Windows 11 x64，Python 3.12.14，PySide6 Essentials 6.12.0，PyInstaller 6.22.3。依赖清单见requirements-lock.txt。

## 已执行

| 命令 | 范围 | 实际结果 |
|---|---|---|
| `.venv\Scripts\python.exe scripts/validate_data.py` | 节点、题目、答案、坐标、来源字段 | PASS，8站16题；内容仍为draft |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | 错误重试、首次成绩、解锁、复习、完整通关、可变题量、单选多选、判定扩展、存档恢复/备份/写失败、内容校验 | 18项全部通过 |
| `.venv\Scripts\python.exe scripts/smoke_desktop.py` | 实际Qt按钮完成全部关卡、先错后对、恢复、徽章和最小窗口 | PASS；首次答对15/16、掌握16/16，隔离测试存档 |
| `.venv\Scripts\python.exe -m PyInstaller --noconfirm ZuJiChangZheng.spec` | cf2f616源码构建Windows单文件exe | PASS |
| `.venv\Scripts\python.exe scripts/smoke_packaged.py` | 原生窗口、中文exe/目录、无Python PATH、替换外部内容、无效包受控退出 | PASS，包含默认8站16题与外部1站2题 |
| `git diff --cached --check` | 提交内容空白检查 | PASS |

单元与源码界面测试复用该业务实现的提交前验证；提交前仅清理了尾部空行。最终exe重新按cf2f616提交中的应用源码构建，并再次执行打包核验。

已人工查看：路线页、答题反馈、通关回顾、PNG徽章、1060×700最小窗口、最终exe原生启动截图。截图与机器报告保存在忽略的 `.artifacts/`，GitHub Actions也提供界面核验产物。

## exe标识

- 文件：`dist/ZuJiChangZheng.exe`
- 大小：38,962,154字节
- SHA256：`c17b86cab773b9f2b10aaa96c6a0664cb8bfd802c3aea08d64ee2f4bb8408997`

## 实际限制与剩余验证

- 尚未在另一台没有Python的电脑上执行验收；同机精简PATH测试不等同于干净系统测试。
- 当前史料、来源与题目为预览稿，需要A正式核验。
- 当前只支持单用户单实例进度；未实现多实例并发写入、云同步与图片音频内容字段。
- GitHub Actions结果以PR检查为准，不在尚未完成时声明通过。
- 已解决的打包问题：依赖搜索可能被其他工具同名ICU DLL影响，spec已优先Windows系统目录；最终exe核验通过。当前无未解决的自动测试失败。
