# MQTools-VTFCmd (集成版) v1.5

面向 Source 引擎材质的图形工具（集成版 GUI）。支持从贴图生成 VTF 与 VMT；Windows 提供可执行版。

## 下载与运行（推荐）
- 到 Release 页面下载：`MQTools-VTFCmd v1.5.exe`
- 确保 `vtfcmd.exe` 可用（加入 PATH 或与 exe 同目录）
- 建议安装 `ImageMagick (magick.exe)`（用于通道分析与发光贴图生成）

## 源码运行
- 在仓库根目录：
  - `pip install -r requirements_pyside6.txt`
  - `python vtf_material_tool_pyside6.py`

## 构建可执行文件
- 在仓库根目录：`pyinstaller VTF-Material-Tool-PySide6.spec`
- 产物位于 `dist/`，文件名：`MQTools-VTFCmd v1.5.exe`

## 使用说明
- 详见 `VTF-Material-Tool-Integrated/README.md`

## 致谢与来源
- PBR 转化算法参考并改写自：https://github.com/koerismo/PBR-2-Source
- VTFCmd 来自：https://github.com/Sky-rym/VTFEdit-Reloaded

如遇问题，请在 Issues 提交反馈。