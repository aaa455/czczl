# 三人协作约定

1. `main` 保持可运行，修改通过PR合入；由B整合，至少另一名成员检查相关内容。
2. 新任务从最新 `main` 建分支，例如 `codex/content-sources`、`codex/ui-theme`。
3. A维护内容；C维护样式与明确认领的绘图/界面文件；B维护规则、存档及入口。共享字段与公共接口有变更时先写Issue说明，再讨论后实施。
4. 不提交 `.venv`、`dist`、`build`、本机存档、临时截图和视频。exe通过Release或Actions构建产物共享。
5. 内容修改跑数据校验；规则/存档修改跑相关单元测试；界面修改跑桌面冒烟并人工检查。相同相关代码及环境已经通过的检查不无故重复。
6. 提交前检查 `git status` 和 `git diff`。提交信息写清改动，不使用强制推送覆盖他人的提交。
7. PR写明改动、验证命令和实际结果、已知问题。没有运行的测试注明未运行。
8. 合并使用Squash，合并后同步 `main`，再建下一任务分支。

## 示例

```powershell
git switch main
git pull --ff-only
git switch -c codex/content-sources
# 编辑内容后执行校验，再提交相关文件
git add assets/content/nodes.json docs/content-sources.md
git commit -m "docs(content): 核实节点史料与出处"
git push -u origin codex/content-sources
```

本地任务分支需要其他人已合并的更新时：`git fetch origin`，然后在任务分支执行 `git merge origin/main`。有未提交工作时先处理好，再合并或切换分支。
