# 第三方组件与开发资源

| 组件 | 当前版本 | 用途 | 官方来源 |
|---|---|---|---|
| CPython | 验证环境3.12.14 | 运行时 | https://www.python.org/ |
| PySide6 Essentials | 6.12.0 | Qt原生窗口、绘图、图片导出 | https://doc.qt.io/qtforpython-6/ |
| PySide6 Addons | 6.12.0 | Qt Multimedia背景音乐播放 | https://doc.qt.io/qtforpython-6/ |
| shiboken6 | 6.12.0 | PySide6绑定运行时 | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| PyInstaller | 6.22.3 | Windows exe打包 | https://pyinstaller.org/ |

PySide6 Essentials包元数据声明 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`。Qt具体组件许可见 https://doc.qt.io/qt-6/licensing.html 。PyInstaller许可与引导程序例外见 https://pyinstaller.org/en/stable/license.html 。交付时随完整源码、依赖/构建方法提供本文件及适用第三方许可文本。

交互路线与节点为程序绘制。通关纪念窗口使用两张AI创作的历史题材插画，作为非特定人物的纪念形象，不对应任何烈士真实肖像。主界面山水背景由用户提供的参考图经本地MCP调用gpt-image-2生成，作为历史主题美术使用；创作提示词与文件指纹见 `assets/images/landscape-provenance.json`。未将参考图原件或中转密钥加入源码交付。章节学习图片仍为占位。背景音乐《我和我的祖国》（华语群星）由用户提供，位于 `assets/audio/background.flac`；团队应在公开发布或分发前确认音乐的使用授权。中文字体调用Windows已安装字体；离屏截图测试只读取本机字体，不分发系统字体。

开发使用Codex/AI辅助编写、排错和测试。历史内容由团队核验，正式作品说明中应补充实际人工修改、核验与自主开发情况。
