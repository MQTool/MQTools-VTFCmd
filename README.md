# VTF-CMD 工具集（Monorepo）

一个面向 Source 引擎材质制作的多工具合集，包含：
- VTF 材质一体化 GUI（集成版）
- PBR-2-Source（Upstream 参考与工具）
- PBR-2-L4D2（面向 L4D2 的专用流程）

支持将图像快速转换为 `VTF`，并自动生成 `VMT`（标准与 patch 格式）、发光材质（_e 贴图）与法线引用；集成批量处理与智能融合，适合 Source 系列游戏的开发与移植。

---

## 仓库结构
- `VTF-Material-Tool-Integrated/` 集成版 PySide6 GUI，统一转换与生成流程（推荐使用）
- `PBR-2-Source/` 上游项目参考与工具，内含独立 README
- `PBR-2-L4D2/` L4D2 专用 PBR 流程与工具，内含独立 README/使用说明
- 根目录脚本与批处理：常用快捷任务（如夜光、静态调整）

---

## 快速开始（集成版）

### 环境准备
- 操作系统：Windows（推荐）
- Python：3.10+（推荐 3.11/3.12）
- 依赖：`PySide6`, `numpy`, `Pillow`
- 工具：
  - `VTFCmd.exe`（必须，用于 VTF 转换）：可放同目录或在 PATH 中
  - `ImageMagick (magick.exe)`（建议，启用发光生成、尺寸调整、通道分析）

### 运行
```bash
cd VTF-Material-Tool-Integrated
pip install -r ..\requirements_pyside6.txt
python vtf_material_tool_pyside6.py
```

### 使用流程
1. 选择输入贴图（单个或批量）
2. 选择输出目录（建议指向游戏 `materials/...` 结构）
3. 勾选需要的选项：生成 VMT、发光材质、法线检测、仅屏蔽 VMT 等
4. 开始处理，完成后在输出目录获得 `VTF/VMT`

更多细节与预设说明，见 `VTF-Material-Tool-Integrated/README.md`。

---

## 关键能力（集成版）
- 标准/patch VMT 生成，支持 `$alphatest`/`$translucent` 与 `$bumpmap`
- 自动发光材质：生成 `_e` 贴图并输出发光 VMT，可融合现有 VMT
- PBR 通道映射预设：`presets.json` 支持 Metallic/Roughness/AO 重映射
- 批量处理与智能融合：扫描目录 VMT，保留自定义参数，更新 PBR/发光配置
- 便捷编辑：内置 `vmt-base.vmt` 编辑器

---

## 常见问题
- 未找到 `VTFCmd`
  - 将 `vtfcmd.exe` 放同目录或加入 PATH；参考 `VTFCMD.txt`
- 发光生成/尺寸调整异常
  - 安装并保证 `magick.exe` 可用（ImageMagick）
- VMT 无效果
  - 检查输出路径与游戏引用一致，确认 `materials` 目录结构

---

## 构建发布（集成版）
在仓库根目录执行：
```bash
pyinstaller VTF-Material-Tool-PySide6.spec
# 产物位于 dist/
```
可将 `VTFCmd.exe` 放入打包目录以保证运行环境。

---

## 子项目入口
- `PBR-2-Source/README.md`：上游工具的说明与构建指南
- `PBR-2-L4D2/README.md` 与 `README_L4D2.md`：L4D2 专用流程与 GUI 使用说明

---

## 许可与致谢
- VTFCmd（VTFEdit）：用于 VTF 转换的命令行工具
- PBR-2-Source / PBR-2-L4D2：流程与实现思路参考

如在使用中遇到问题，欢迎在 Issues 中反馈与交流。