# VTF-Material-Tool-Integrated

面向 Source 引擎材质的“一体化”图形工具。支持将常规贴图与 PBR 贴图快速转换为 `VTF`，并按需自动生成 `VMT`（含 patch 格式与标准格式）、发光材质（vmtE/自发光）与法线引用。内置 PySide6 GUI，集成 `VTFCmd` 命令行工具流，提供批量处理与智能融合能力，适合 L4D2 等基于 Source 的项目开发与移植。

> English: An integrated GUI for converting textures to VTF and generating VMT for Source Engine, featuring VTFCmd-based conversion, emissive materials, presets, and batch operations.

---

## 主要特性
- 一键生成：从图像到 `VTF` 与 `VMT` 的完整流水线
- VTFCmd 集成：自动探测 `vtfcmd.exe`，不依赖 `sourcepp`
- VMT 生成：支持标准与 `patch` 格式，含 `$alphatest`/`$translucent`、`$bumpmap`（法线）
- 发光材质：自动检测 Alpha 并生成 `_e` 贴图与发光 VMT（可融合现有 VMT）
- 预设系统：`presets.json` 自定义 PBR 通道映射（Metallic/Roughness/AO）
- 批量处理：扫描目录下 VMT/VTF，批量重建或融合，保留自定义参数
- 便捷编辑：内置 `vmt-base.vmt` 编辑器与路径助手
- 贴图支持：`PNG/JPG/JPEG/TGA/BMP/TIFF` 等常见格式

---

## 环境需求
- 操作系统：Windows（推荐）
- Python：3.10+（推荐 3.11/3.12）
- 依赖：`PySide6`, `numpy`, `Pillow`
- 工具：
  - `VTFCmd.exe`（必须）：用于 VTF 转换
  - `ImageMagick (magick.exe)`（强烈建议）：用于 Alpha 通道分析、E 贴图生成、图像尺寸调整等功能

安装提示：
- 安装 `VTFCmd`：将 `vtfcmd.exe` 放在程序目录或加入系统 PATH；参考根目录 `VTFCMD.txt`
- 安装 `ImageMagick`：确保 `magick` 命令在终端可用（添加到 PATH）

---

## 安装与运行

### 方式 A：直接使用发行版（推荐）
- 从 Releases 页面下载最新可执行文件（例如：`MQTools-VTFCmdv1.1.exe`）。
- 解压后运行，首次使用请确保 `vtfcmd.exe` 与 `magick.exe` 可被找到。

### 方式 B：源码运行
```bash
# 克隆仓库（将 <your-repo-url> 替换为你的GitHub地址）
git clone <your-repo-url>
cd VTF-Material-Tool-Integrated

# 安装依赖（建议使用虚拟环境）
pip install -r ..\requirements_pyside6.txt

# 运行集成版 GUI
python vtf_material_tool_pyside6.py
```

---

## VTFCmd 配置
本工具通过以下顺序查找 `vtfcmd.exe`：
- 当前目录下：`./vtfcmd.exe` 或 `./tools/VTFCmd.exe`
- 系统 PATH：`vtfcmd`
- 常见安装路径：`C:\Program Files\VTFEdit\VTFCmd.exe` 等

若提示“未找到 VTFCmd”：
- 将 `vtfcmd.exe` 放在程序同目录；或
- 将其所在目录加入系统 PATH；或
- 安装 VTFEdit（含 VTFCmd）。

参考：根目录 `VTFCMD.txt` 提供命令示例与参数说明。

---

## 快速开始
1. 启动应用，选择输入贴图（支持单图与批量）。
2. 选择输出目录（建议指向游戏的 `materials/...` 目录结构）。
3. 如需 PBR 通道重映射，打开“PBR贴图处理工具”并选择/保存预设。
4. 勾选需要的选项：生成 VMT、发光材质、法线检测、仅屏蔽 VMT 等。
5. 点击“开始处理”，在输出目录获得 `VTF/VMT`。

---

## VMT 生成与发光支持
- 标准/patch 格式：支持 `patch` 引用 `vmt-base.vmt` 的结构，以及标准 `VertexLitGeneric` 结构。
- Alpha 识别：自动根据贴图 Alpha 判断使用 `$alphatest` 或 `$translucent`。
- 法线引用：自动检测 `_n`/`_N`/`Normal` 等命名，添加 `$bumpmap`。
- 发光材质：
  - 自动生成 `_e` 贴图（保留 Alpha），并输出对应发光 VMT；
  - 对现有 VMT 执行智能融合，保留自定义参数并更新 PBR/发光参数；
  - 可选“修改 vmt-base”，在 `shader/vmt-base.vmt` 中注入/对齐 `$selfillum` 等参数。

提示：
- `vmt-base.vmt` 位于 `materials/<你的路径>/shader/vmt-base.vmt`，可在工具内编辑。
- 批量模式会扫描输出目录的 `.vmt` 文件，逐个融合/重建。

---

## PBR 预设（presets.json）
位于 `VTF-Material-Tool-Integrated/presets.json`。通过 GUI 可保存/删除自定义预设，或直接编辑文件。
示例：
```json
{
  "示例预设": {
    "metallic": { "source": "蓝色通道", "invert": false },
    "roughness": { "source": "绿色通道", "invert": false },
    "ao": { "source": "红色通道", "invert": false }
  }
}
```
内置预设包含：标准PBR、Unity标准、UE4标准。

---

## 常见问题
- 程序无法启动
  - 确认已安装 Python 3.10+ 与依赖
- 找不到 VTFCmd
  - 将 `vtfcmd.exe` 放在程序目录或添加到系统 PATH
- 贴图转换后 VMT 无效果
  - 检查输出路径与游戏引用一致
- 批量处理未识别 VMT
  - 只扫描当前输出目录下 `.vmt`
- 发光效果不显著
  - 检查源图 Alpha 通道；调整对比度或发光强度

---

## 构建与发布（可选）
使用 PyInstaller 打包：
```bash
pyinstaller VTF-Material-Tool-PySide6.spec
# 产物位于 dist/
```
可将 `VTFCmd.exe` 放入打包目录以保证运行环境可用。

---

## 目录指引（关键文件）
- `VTF-Material-Tool-Integrated/vtf_material_tool_pyside6.py`：集成版 GUI 主入口
- `VTF-Material-Tool-Integrated/pbr_texture_tool.py`：PBR 通道映射与预览工具
- `VTF-Material-Tool-Integrated/presets.json`：PBR 自定义预设
- `VTFCMD.txt`：VTFCmd 参数与用法参考

---

## 致谢
- VTFCmd（VTFEdit）：用于 VTF 转换的命令行工具
- PBR-2-Source / PBR-2-L4D2：相关流程与实现思路参考

如在使用中遇到问题或有改进建议，欢迎在 GitHub Issues 提交反馈。