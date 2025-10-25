# MQTools-VTFCmd v1.5

集成版 GUI 可执行文件（Windows）。

## 功能
- 一键从常规或 PBR 贴图生成 `VTF` 与 `VMT`（标准/patch 格式）
- 支持 PBR 通道映射（Metallic/Roughness/AO），可通过 `presets.json` 配置
- 自动检测并生成发光材质（`_e` 贴图）与法线引用
- 批量处理与路径映射，可融合现有 `VMT` 保留自定义参数
- 辅助处理：尺寸调整、通道提取（需 `magick.exe`）

## 运行要求
- `vtfcmd.exe` 可用（加入 PATH 或与 exe 同目录）
- 建议安装 `ImageMagick (magick.exe)`（用于通道分析与发光贴图生成）

## 使用
- 双击运行 `MQTools-VTFCmd v1.5.exe`
- 详细说明见仓库内 `VTF-Material-Tool-Integrated/README.md`

## 致谢与来源
- PBR 转化算法参考并改写自：https://github.com/koerismo/PBR-2-Source
- VTFCmd 来自：https://github.com/Sky-rym/VTFEdit-Reloaded

如遇问题，请在 Issues 提交反馈。