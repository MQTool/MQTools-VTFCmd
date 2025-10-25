#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PBR贴图处理工具
用于处理粗糙度、金属度、环境光遮蔽贴图的通道分离和重组
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QFileDialog, QComboBox,
    QGroupBox, QScrollArea, QSplitter, QTabWidget, QSpinBox,
    QCheckBox, QSlider, QProgressBar, QTextEdit, QFrame,
    QSizePolicy, QSpacerItem
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QPropertyAnimation,
    QEasingCurve, QRect, QSettings
)
from PySide6.QtGui import (
    QPixmap, QIcon, QPalette, QColor, QFont, QPainter,
    QLinearGradient, QBrush, QDragEnterEvent, QDropEvent
)

import numpy as np
from PIL import Image, ImageQt


class ModernButton(QPushButton):
    """现代化按钮组件"""
    
    def __init__(self, text: str, primary: bool = False, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.dark_mode = False
        self.setMinimumHeight(36)
        self.setFont(QFont("Segoe UI", 10))
        self.update_style()
    
    def set_dark_mode(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update_style()
    
    def update_style(self):
        if self.primary:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4A90E2, stop:1 #357ABD);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5BA0F2, stop:1 #4A90E2);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #357ABD, stop:1 #2E6BA8);
                }
            """)
        else:
            if self.dark_mode:
                self.setStyleSheet("""
                    QPushButton {
                        background: #404040;
                        color: #ffffff;
                        border: 1px solid #555555;
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background: #4A4A4A;
                        border-color: #666666;
                    }
                    QPushButton:pressed {
                        background: #353535;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QPushButton {
                        background: #F5F5F5;
                        color: #333333;
                        border: 1px solid #DDDDDD;
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background: #EEEEEE;
                        border-color: #CCCCCC;
                    }
                    QPushButton:pressed {
                        background: #E0E0E0;
                    }
                """)


class ImagePreviewWidget(QLabel):
    """图像预览组件"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.image_path = None
        self.original_pixmap = None
        self.dark_mode = False
        
        self.setMinimumSize(200, 200)
        self.setMaximumSize(350, 350)
        self.setAlignment(Qt.AlignCenter)
        # 设置大小策略确保正确的缩放行为
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_style()
        # 根据组件类型设置不同的提示文本
        if title == "输入贴图":
            self.setText(f"拖拽{title}到此处\n或点击选择文件")
        elif title == "MRAO输出":
            self.setText("输出预览\n根据配置自动生成")
        else:
            self.setText(f"{title}\n自动生成预览")
        
        # 根据标题决定是否启用拖拽（只有输入贴图和MRAO输出启用）
        if title in ["输入贴图", "MRAO输出"]:
            self.setAcceptDrops(True)
        else:
            self.setAcceptDrops(False)
    
    def set_dark_mode(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update_style()
    
    def update_style(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QLabel {
                    border: 2px dashed #555555;
                    border-radius: 8px;
                    background: #353535;
                    color: #CCCCCC;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    border: 2px dashed #CCCCCC;
                    border-radius: 8px;
                    background: #FAFAFA;
                    color: #666666;
                }
            """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files and self.is_image_file(files[0]):
            self.load_image(files[0])
    
    def is_image_file(self, file_path: str) -> bool:
        extensions = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff'}
        return Path(file_path).suffix.lower() in extensions
    
    def load_image(self, file_path: str):
        try:
            self.image_path = file_path
            image = Image.open(file_path)
            
            # 转换为RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 创建QPixmap
            qt_image = ImageQt.ImageQt(image)
            self.original_pixmap = QPixmap.fromImage(qt_image)
            
            # 更新显示
            self.update_display()
            
        except Exception as e:
            print(f"加载图像失败: {e}")
    
    def update_display(self):
        """更新图像显示，保持宽高比并居中"""
        if self.original_pixmap:
            # 获取当前组件大小
            widget_size = self.size()
            
            # 缩放图像保持宽高比
            scaled_pixmap = self.original_pixmap.scaled(
                widget_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            # 确保图像居中显示
            self.setAlignment(Qt.AlignCenter)
            self.setPixmap(scaled_pixmap)
    
    def resizeEvent(self, event):
        """窗口大小改变时重新缩放图像"""
        super().resizeEvent(event)
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            self.update_display()
    
    def mousePressEvent(self, event):
        # 只有输入贴图允许点击选择文件
        if event.button() == Qt.LeftButton and self.title == "输入贴图":
            file_path, _ = QFileDialog.getOpenFileName(
                self, f"选择{self.title}图像",
                "", "图像文件 (*.png *.jpg *.jpeg *.tga *.bmp *.tiff)"
            )
            if file_path:
                self.load_image(file_path)


class ChannelMappingWidget(QWidget):
    """通道映射配置组件"""
    
    # 配置改变信号
    config_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("通道映射规则")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title)
        
        # 通道映射配置
        mapping_group = QGroupBox("MRA通道配置")
        mapping_layout = QGridLayout(mapping_group)
        
        # 各通道配置 - MRA三通道格式
        channels = [
            ("M (金属度)", "metallic"),
            ("R (粗糙度)", "roughness"),
            ("AO (环境光遮蔽)", "ao")
        ]
        
        self.channel_combos = {}
        
        for i, (label, key) in enumerate(channels):
            # 标签
            mapping_layout.addWidget(QLabel(label), i, 0)
            
            # 源通道选择
            source_combo = QComboBox()
            source_combo.addItems(["红色通道", "绿色通道", "蓝色通道", "Alpha通道", "灰度", "白色", "黑色"])
            source_combo.currentTextChanged.connect(self.on_manual_config_change)
            mapping_layout.addWidget(QLabel("来源:"), i, 1)
            mapping_layout.addWidget(source_combo, i, 2)
            
            # 反转选项
            invert_check = QCheckBox("反转")
            invert_check.toggled.connect(self.on_manual_config_change)
            mapping_layout.addWidget(invert_check, i, 3)
            
            self.channel_combos[key] = {
                'source': source_combo,
                'invert': invert_check
            }
        
        layout.addWidget(mapping_group)
        
        # 预设配置
        preset_group = QGroupBox("预设配置")
        preset_layout = QVBoxLayout(preset_group)
        
        # 预设选择行
        preset_select_layout = QHBoxLayout()
        
        self.preset_combo = QComboBox()
        self.load_presets()  # 加载预设
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        
        preset_select_layout.addWidget(QLabel("预设:"))
        preset_select_layout.addWidget(self.preset_combo)
        preset_select_layout.addStretch()
        
        preset_layout.addLayout(preset_select_layout)
        
        # 预设管理按钮行
        preset_buttons_layout = QHBoxLayout()
        
        save_preset_btn = ModernButton("保存预设")
        save_preset_btn.clicked.connect(self.save_custom_preset)
        
        delete_preset_btn = ModernButton("删除预设")
        delete_preset_btn.clicked.connect(self.delete_custom_preset)
        
        preset_buttons_layout.addWidget(save_preset_btn)
        preset_buttons_layout.addWidget(delete_preset_btn)
        preset_buttons_layout.addStretch()
        
        preset_layout.addLayout(preset_buttons_layout)
        
        layout.addWidget(preset_group)
    

    
    def get_mapping_config(self) -> Dict:
        """获取当前映射配置"""
        config = {}
        for channel, widgets in self.channel_combos.items():
            config[channel] = {
                'source': widgets['source'].currentText(),
                'invert': widgets['invert'].isChecked()
            }
        return config
    
    def load_presets(self):
        """加载预设配置"""
        # 内置预设
        builtin_presets = [
            "自定义",
            "标准PBR (M=B, R=G, AO=R)",
            "Unity标准 (M=R, R=G, AO=B)",
            "UE4标准 (M=B, R=G, AO=R)"
        ]
        
        self.preset_combo.clear()
        self.preset_combo.addItems(builtin_presets)
        
        # 加载自定义预设
        presets_file = Path("presets.json")
        if presets_file.exists():
            try:
                with open(presets_file, 'r', encoding='utf-8') as f:
                    custom_presets = json.load(f)
                    for preset_name in custom_presets.keys():
                        self.preset_combo.addItem(f"[自定义] {preset_name}")
            except Exception as e:
                print(f"加载自定义预设失败: {e}")
    
    def save_custom_preset(self):
        """保存自定义预设"""
        from PySide6.QtWidgets import QInputDialog
        
        preset_name, ok = QInputDialog.getText(
            self, "保存预设", "请输入预设名称:"
        )
        
        if ok and preset_name.strip():
            preset_name = preset_name.strip()
            current_config = self.get_mapping_config()
            
            # 读取现有预设
            presets_file = Path("presets.json")
            custom_presets = {}
            
            if presets_file.exists():
                try:
                    with open(presets_file, 'r', encoding='utf-8') as f:
                        custom_presets = json.load(f)
                except Exception as e:
                    print(f"读取预设文件失败: {e}")
            
            # 保存新预设
            custom_presets[preset_name] = current_config
            
            try:
                with open(presets_file, 'w', encoding='utf-8') as f:
                    json.dump(custom_presets, f, ensure_ascii=False, indent=2)
                
                # 重新加载预设列表
                current_selection = self.preset_combo.currentText()
                self.load_presets()
                
                # 选择新保存的预设
                new_preset_name = f"[自定义] {preset_name}"
                index = self.preset_combo.findText(new_preset_name)
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
                    
            except Exception as e:
                print(f"保存预设失败: {e}")
    
    def delete_custom_preset(self):
        """删除自定义预设"""
        from PySide6.QtWidgets import QMessageBox
        
        current_preset = self.preset_combo.currentText()
        
        if not current_preset.startswith("[自定义]"):
            QMessageBox.information(self, "提示", "只能删除自定义预设")
            return
        
        preset_name = current_preset.replace("[自定义] ", "")
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除预设 '{preset_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            presets_file = Path("presets.json")
            
            if presets_file.exists():
                try:
                    with open(presets_file, 'r', encoding='utf-8') as f:
                        custom_presets = json.load(f)
                    
                    if preset_name in custom_presets:
                        del custom_presets[preset_name]
                        
                        with open(presets_file, 'w', encoding='utf-8') as f:
                            json.dump(custom_presets, f, ensure_ascii=False, indent=2)
                        
                        # 重新加载预设列表
                        self.load_presets()
                        self.preset_combo.setCurrentIndex(0)  # 选择"自定义"
                        
                except Exception as e:
                    print(f"删除预设失败: {e}")
    
    def apply_preset(self, preset_name: str):
        """应用预设配置"""
        # 内置预设
        builtin_presets = {
            "标准PBR (M=B, R=G, AO=R)": {
                'metallic': ('蓝色通道', False),
                'roughness': ('绿色通道', False),
                'ao': ('红色通道', False)
            },
            "Unity标准 (M=R, R=G, AO=B)": {
                'metallic': ('红色通道', False),
                'roughness': ('绿色通道', False),
                'ao': ('蓝色通道', False)
            },
            "UE4标准 (M=B, R=G, AO=R)": {
                'metallic': ('蓝色通道', False),
                'roughness': ('绿色通道', False),
                'ao': ('红色通道', False)
            }
        }
        
        if preset_name in builtin_presets:
            # 临时断开信号连接，避免触发on_manual_config_change
            for channel, widgets in self.channel_combos.items():
                try:
                    widgets['source'].currentTextChanged.disconnect(self.on_manual_config_change)
                    widgets['invert'].toggled.disconnect(self.on_manual_config_change)
                except:
                    pass  # 如果信号未连接，忽略错误
            
            preset = builtin_presets[preset_name]
            for channel, (source, invert) in preset.items():
                if channel in self.channel_combos:
                    self.channel_combos[channel]['source'].setCurrentText(source)
                    self.channel_combos[channel]['invert'].setChecked(invert)
            
            # 重新连接信号
            for channel, widgets in self.channel_combos.items():
                widgets['source'].currentTextChanged.connect(self.on_manual_config_change)
                widgets['invert'].toggled.connect(self.on_manual_config_change)
        
        elif preset_name.startswith("[自定义]"):
            # 自定义预设
            actual_name = preset_name.replace("[自定义] ", "")
            presets_file = Path("presets.json")
            
            if presets_file.exists():
                try:
                    with open(presets_file, 'r', encoding='utf-8') as f:
                        custom_presets = json.load(f)
                    
                    if actual_name in custom_presets:
                        preset = custom_presets[actual_name]
                        for channel, config in preset.items():
                            if channel in self.channel_combos:
                                self.channel_combos[channel]['source'].setCurrentText(config['source'])
                                self.channel_combos[channel]['invert'].setChecked(config['invert'])
                                
                except Exception as e:
                    print(f"加载自定义预设失败: {e}")
        
        # 应用预设后发出配置改变信号（除了"自定义"选项）
        if preset_name != "自定义":
            self.config_changed.emit()
    
    def on_manual_config_change(self):
        """用户手动调整配置时的处理"""
        # 自动切换到"自定义"预设
        if self.preset_combo.currentText() != "自定义":
            # 临时断开信号连接，避免递归调用
            self.preset_combo.currentTextChanged.disconnect()
            self.preset_combo.setCurrentText("自定义")
            self.preset_combo.currentTextChanged.connect(self.apply_preset)
        
        # 发出配置改变信号
        self.config_changed.emit()


class TextureProcessor(QThread):
    """贴图处理线程"""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished_processing = Signal(bool, str)
    
    def __init__(self, input_image_path: str, mapping_config: Dict, output_dir: str, output_format: str = "PNG"):
        super().__init__()
        self.input_image_path = input_image_path
        self.mapping_config = mapping_config
        self.output_dir = output_dir
        self.output_format = output_format.upper()


class BatchTextureProcessor(QThread):
    """批量贴图处理线程"""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    batch_progress_updated = Signal(str)  # 批量进度信号
    finished_processing = Signal(bool, str)
    
    def __init__(self, input_image_paths: List[str], mapping_config: Dict, output_dir: str, output_format: str = "PNG"):
        super().__init__()
        self.input_image_paths = input_image_paths
        self.mapping_config = mapping_config
        self.output_dir = output_dir
        self.output_format = output_format.upper()
        self.current_file_index = 0
        self.total_files = len(input_image_paths)
        self.success_count = 0
        self.error_count = 0
    
    def run(self):
        """批量处理图像"""
        try:
            for i, image_path in enumerate(self.input_image_paths):
                self.current_file_index = i + 1
                file_name = Path(image_path).name
                
                # 更新批量进度
                batch_progress = f"处理文件 {self.current_file_index}/{self.total_files}: {file_name}"
                self.batch_progress_updated.emit(batch_progress)
                self.status_updated.emit(f"正在处理: {file_name}")
                
                # 处理单个文件
                success = self.process_single_file(image_path)
                
                if success:
                    self.success_count += 1
                else:
                    self.error_count += 1
                
                # 更新总进度
                progress = int((i + 1) / self.total_files * 100)
                self.progress_updated.emit(progress)
            
            # 处理完成
            if self.error_count == 0:
                message = f"批量处理完成！成功处理 {self.success_count} 个文件"
                self.finished_processing.emit(True, message)
            else:
                message = f"批量处理完成！成功: {self.success_count}, 失败: {self.error_count}"
                self.finished_processing.emit(True, message)
                
        except Exception as e:
            self.finished_processing.emit(False, f"批量处理失败: {str(e)}")
    
    def process_single_file(self, image_path: str) -> bool:
        """处理单个文件"""
        try:
            # 加载图像
            image = Image.open(image_path)
            
            # 转换为RGBA模式以保留所有通道
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # 转换为numpy数组
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 分离通道
            channels = {
                'R': img_array[:, :, 0],
                'G': img_array[:, :, 1],
                'B': img_array[:, :, 2],
                'A': img_array[:, :, 3] if img_array.shape[2] > 3 else np.full((height, width), 255, dtype=np.uint8)
            }
            
            # 创建输出目录
            fake_pbr_dir = Path(self.output_dir) / "Fake PBR"
            pbr_dir = Path(self.output_dir) / "PBR"
            fake_pbr_dir.mkdir(parents=True, exist_ok=True)
            pbr_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存分离的通道 (Fake PBR)
            base_name = Path(image_path).stem
            file_ext = ".png" if self.output_format == "PNG" else ".tga"
            
            for channel_name, channel_data in channels.items():
                channel_image = Image.fromarray(channel_data, mode='L')
                channel_output_path = fake_pbr_dir / f"{base_name}_{channel_name}{file_ext}"
                channel_image.save(channel_output_path)
            
            # 合成MRAO贴图
            mrao_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            # 创建通道名称映射
            channel_mapping = {
                '红色通道': 'R',
                '绿色通道': 'G', 
                '蓝色通道': 'B',
                'Alpha通道': 'A'
            }
            
            for i, channel_key in enumerate(['metallic', 'roughness', 'ao']):
                if channel_key in self.mapping_config:
                    config = self.mapping_config[channel_key]
                    source = config['source']
                    invert = config['invert']
                    
                    # 将旧的通道名称映射到新的通道名称
                    mapped_source = channel_mapping.get(source, source)
                    
                    if mapped_source in channels:
                        channel_data = channels[mapped_source]
                    elif source == '灰度':
                        channel_data = np.dot(img_array[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                    elif source == '白色':
                        channel_data = np.full((height, width), 255, dtype=np.uint8)
                    elif source == '黑色':
                        channel_data = np.full((height, width), 0, dtype=np.uint8)
                    else:
                        channel_data = np.full((height, width), 128, dtype=np.uint8)
                    
                    if invert:
                        channel_data = 255 - channel_data
                    
                    mrao_array[:, :, i] = channel_data
            
            # 保存MRAO贴图 (PBR)
            mrao_image = Image.fromarray(mrao_array, mode='RGB')
            mrao_output_path = pbr_dir / f"{base_name}_MRAO{file_ext}"
            mrao_image.save(mrao_output_path)
            
            return True
            
        except Exception as e:
            print(f"处理文件 {image_path} 失败: {e}")
            return False


class TextureProcessor(QThread):
    """贴图处理线程"""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished_processing = Signal(bool, str)
    
    def __init__(self, input_image_path: str, mapping_config: Dict, output_dir: str):
        super().__init__()
        self.input_image_path = input_image_path
        self.mapping_config = mapping_config
        self.output_dir = output_dir
    
    def run(self):
        try:
            self.status_updated.emit("正在加载图像...")
            self.progress_updated.emit(10)
            
            # 加载图像
            image = Image.open(self.input_image_path)
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            self.status_updated.emit("正在分离通道...")
            self.progress_updated.emit(30)
            
            # 分离通道
            channels = {
                'R': img_array[:, :, 0],
                'G': img_array[:, :, 1],
                'B': img_array[:, :, 2],
                'A': img_array[:, :, 3] if img_array.shape[2] > 3 else np.full((height, width), 255, dtype=np.uint8)
            }
            
            # 创建输出目录
            fake_pbr_dir = Path(self.output_dir) / "Fake PBR"
            pbr_dir = Path(self.output_dir) / "PBR"
            fake_pbr_dir.mkdir(parents=True, exist_ok=True)
            pbr_dir.mkdir(parents=True, exist_ok=True)
            
            self.status_updated.emit("正在保存分离的通道...")
            self.progress_updated.emit(50)
            
            # 保存分离的通道 (Fake PBR)
            base_name = Path(self.input_image_path).stem
            file_ext = ".png" if self.output_format == "PNG" else ".tga"
            for channel_name, channel_data in channels.items():
                channel_image = Image.fromarray(channel_data, mode='L')
                output_path = fake_pbr_dir / f"{base_name}_{channel_name}{file_ext}"
                channel_image.save(output_path)
            
            self.status_updated.emit("正在合成MRAO贴图...")
            self.progress_updated.emit(70)
            
            # 合成MRAO贴图
            mrao_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            # 创建通道名称映射
            channel_mapping = {
                '红色通道': 'R',
                '绿色通道': 'G', 
                '蓝色通道': 'B',
                'Alpha通道': 'A'
            }
            
            # 处理MRAO三个通道
            for i, channel_key in enumerate(['metallic', 'roughness', 'ao']):
                if channel_key in self.mapping_config:
                    config = self.mapping_config[channel_key]
                    source_channel = config[0]
                    invert = config[1]
                    
                    # 将旧的通道名称映射到新的通道名称
                    mapped_source = channel_mapping.get(source_channel, source_channel)
                    
                    if mapped_source in channels:
                        channel_data = channels[mapped_source].copy()
                    elif source_channel == '灰度':
                        # 计算灰度
                        channel_data = np.dot(img_array[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                    elif source_channel == '白色':
                        channel_data = np.full((height, width), 255, dtype=np.uint8)
                    elif source_channel == '黑色':
                        channel_data = np.full((height, width), 0, dtype=np.uint8)
                    else:
                        channel_data = np.full((height, width), 128, dtype=np.uint8)
                    
                    if invert:
                        channel_data = 255 - channel_data
                    
                    mrao_array[:, :, i] = channel_data
            
            self.status_updated.emit("正在保存MRAO贴图...")
            self.progress_updated.emit(90)
            
            # 保存MRAO贴图
            mrao_image = Image.fromarray(mrao_array, mode='RGB')
            mrao_output_path = pbr_dir / f"{base_name}_MRAO{file_ext}"
            mrao_image.save(mrao_output_path)
            
            self.progress_updated.emit(100)
            self.status_updated.emit("处理完成!")
            self.finished_processing.emit(True, "贴图处理完成!")
            
        except Exception as e:
            self.finished_processing.emit(False, f"处理失败: {str(e)}")


class PBRTextureToolMainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("PBRTextureTool", "Settings")
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        
        self.init_ui()
        self.apply_theme()
    
    def init_ui(self):
        self.setWindowTitle("PBR贴图处理工具 v1.0")
        self.setMinimumSize(1200, 800)
        
        # 中央组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧面板
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割器比例和策略
        splitter.setStretchFactor(0, 0)  # 左侧面板不拉伸
        splitter.setStretchFactor(1, 1)  # 右侧面板可拉伸
        splitter.setSizes([420, 800])  # 初始大小
        splitter.setCollapsible(0, False)  # 左侧面板不可折叠
        splitter.setCollapsible(1, False)  # 右侧面板不可折叠
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
    
    def create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("PBR贴图处理工具")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 主题切换按钮
        self.theme_btn = ModernButton("🌙 切换主题")
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)
        
        layout.addSpacing(20)
        
        # 输入文件选择
        input_group = QGroupBox("输入文件")
        input_layout = QVBoxLayout(input_group)
        input_layout.setAlignment(Qt.AlignCenter)  # 设置布局居中对齐
        
        self.input_preview = ImagePreviewWidget("输入贴图")
        input_layout.addWidget(self.input_preview, 0, Qt.AlignCenter)  # 预览组件居中
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        
        self.select_input_btn = ModernButton("选择单个文件", primary=True)
        self.select_input_btn.clicked.connect(self.select_input_file)
        buttons_layout.addWidget(self.select_input_btn)
        
        self.select_batch_btn = ModernButton("批量选择")
        self.select_batch_btn.clicked.connect(self.select_batch_files)
        buttons_layout.addWidget(self.select_batch_btn)
        
        input_layout.addLayout(buttons_layout)
        
        # 批量文件列表
        self.batch_files = []
        self.batch_list_label = QLabel("批量文件: 未选择")
        self.batch_list_label.setWordWrap(True)
        self.batch_list_label.setMaximumHeight(60)
        input_layout.addWidget(self.batch_list_label)
        
        layout.addWidget(input_group)
        
        # 通道映射配置
        self.mapping_widget = ChannelMappingWidget()
        self.mapping_widget.config_changed.connect(self.update_output_preview)
        self.mapping_widget.config_changed.connect(self.update_all_batch_previews)
        layout.addWidget(self.mapping_widget)
        
        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout(output_group)
        
        self.output_dir_label = QLabel("输出目录: 未选择")
        output_layout.addWidget(self.output_dir_label)
        
        self.select_output_btn = ModernButton("选择输出目录")
        self.select_output_btn.clicked.connect(self.select_output_dir)
        output_layout.addWidget(self.select_output_btn)
        
        # 输出格式选择
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "TGA"])
        self.format_combo.setCurrentText("PNG")  # 默认选择PNG
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        
        output_layout.addLayout(format_layout)
        
        layout.addWidget(output_group)
        
        # 处理按钮
        layout.addSpacing(20)
        
        self.process_btn = ModernButton("开始处理", primary=True)
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        layout.addWidget(self.process_btn)
        
        # 批量处理进度显示
        self.batch_progress_label = QLabel("")
        self.batch_progress_label.setVisible(False)
        layout.addWidget(self.batch_progress_label)
        
        layout.addStretch()
        
        # 将面板设置到滚动区域中
        scroll_area.setWidget(panel)
        scroll_area.setMinimumWidth(420)  # 设置最小宽度确保控件不被挤压
        
        return scroll_area
    
    def create_right_panel(self) -> QWidget:
        """创建右侧预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 通道预览标签页
        channels_tab = QWidget()
        channels_layout = QGridLayout(channels_tab)
        
        # 创建通道预览 (只显示RGB三个通道)
        self.channel_previews = {}
        channel_names = ["红色通道", "绿色通道", "蓝色通道"]
        
        for i, name in enumerate(channel_names):
            preview = ImagePreviewWidget(name)
            preview.setMaximumSize(250, 250)
            self.channel_previews[name] = preview
            channels_layout.addWidget(preview, 0, i)  # 一行三列布局
        
        self.tab_widget.addTab(channels_tab, "通道预览")
        
        # 输出预览标签页
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        
        # 添加上方弹性空间
        output_layout.addStretch()
        
        # 创建水平布局用于居中
        output_h_layout = QHBoxLayout()
        output_h_layout.addStretch()
        
        self.output_preview = ImagePreviewWidget("MRAO输出")
        output_h_layout.addWidget(self.output_preview)
        
        output_h_layout.addStretch()
        output_layout.addLayout(output_h_layout)
        
        # 添加下方弹性空间
        output_layout.addStretch()
        
        self.tab_widget.addTab(output_tab, "输出预览")
        
        # 批量预览标签页
        self.batch_tab = QWidget()
        batch_layout = QVBoxLayout(self.batch_tab)
        
        # 创建滚动区域用于批量预览
        self.batch_scroll_area = QScrollArea()
        self.batch_scroll_area.setWidgetResizable(True)
        self.batch_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.batch_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 批量预览容器
        self.batch_preview_container = QWidget()
        self.batch_preview_layout = QVBoxLayout(self.batch_preview_container)
        self.batch_preview_layout.setSpacing(20)
        
        self.batch_scroll_area.setWidget(self.batch_preview_container)
        batch_layout.addWidget(self.batch_scroll_area)
        
        self.tab_widget.addTab(self.batch_tab, "批量预览")
        
        # 初始时隐藏批量预览标签页
        self.tab_widget.setTabVisible(2, False)
        
        layout.addWidget(self.tab_widget)
        
        return panel
    
    def select_input_file(self):
        """选择输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择输入贴图文件",
            "", "图像文件 (*.png *.jpg *.jpeg *.tga *.bmp *.tiff)"
        )
        if file_path:
            # 清空批量文件列表
            self.batch_files = []
            self.update_batch_list_display()
            
            # 更新批量预览（隐藏批量预览标签页）
            self.update_batch_previews()
            
            self.input_preview.load_image(file_path)
            self.update_channel_previews(file_path)
            self.update_output_preview()  # 添加输出预览更新
            self.check_ready_to_process()
    
    def create_batch_preview_group(self, image_path: str, index: int) -> QWidget:
        """创建单个批量预览组（包含图像名称、RGB通道和输出结果）"""
        group = QGroupBox(f"图像 {index + 1}: {Path(image_path).name}")
        group_layout = QGridLayout(group)
        group_layout.setSpacing(10)
        
        # 创建预览组件
        previews = {}
        
        # RGB通道预览
        channel_names = ["红色通道", "绿色通道", "蓝色通道"]
        for i, name in enumerate(channel_names):
            preview = ImagePreviewWidget(name)
            preview.setMaximumSize(180, 180)
            preview.setMinimumSize(150, 150)
            previews[name] = preview
            group_layout.addWidget(preview, 0, i)
        
        # 输出结果预览
        output_preview = ImagePreviewWidget("MRAO输出")
        output_preview.setMaximumSize(180, 180)
        output_preview.setMinimumSize(150, 150)
        previews["输出"] = output_preview
        group_layout.addWidget(output_preview, 0, 3)
        
        # 更新预览内容
        self.update_batch_preview_content(image_path, previews)
        
        return group
    
    def update_batch_preview_content(self, image_path: str, previews: dict):
        """更新批量预览内容"""
        try:
            # 加载图像
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            
            # 更新RGB通道预览
            channels = {
                "红色通道": img_array[:, :, 0],
                "绿色通道": img_array[:, :, 1],
                "蓝色通道": img_array[:, :, 2]
            }
            
            for name, channel_data in channels.items():
                if name in previews:
                    channel_image = Image.fromarray(channel_data, mode='L')
                    qt_image = ImageQt.ImageQt(channel_image)
                    pixmap = QPixmap.fromImage(qt_image)
                    previews[name].original_pixmap = pixmap
                    previews[name].update_display()
            
            # 更新输出预览
            self.update_batch_output_preview(image_path, previews["输出"])
            
        except Exception as e:
            print(f"更新批量预览失败: {e}")
    
    def update_batch_output_preview(self, image_path: str, output_preview: ImagePreviewWidget):
        """更新批量输出预览"""
        try:
            # 加载输入图像
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 获取当前映射配置
            mapping_config = self.mapping_widget.get_mapping_config()
            
            # 分离通道
            channels = {
                '红色通道': img_array[:, :, 0],
                '绿色通道': img_array[:, :, 1],
                '蓝色通道': img_array[:, :, 2]
            }
            
            # 合成MRAO贴图预览
            mrao_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            for i, channel_key in enumerate(['metallic', 'roughness', 'ao']):
                if channel_key in mapping_config:
                    config = mapping_config[channel_key]
                    source = config['source']
                    invert = config['invert']
                    
                    if source in channels:
                        channel_data = channels[source]
                    elif source == '灰度':
                        channel_data = np.dot(img_array[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                    elif source == '白色':
                        channel_data = np.full((height, width), 255, dtype=np.uint8)
                    elif source == '黑色':
                        channel_data = np.full((height, width), 0, dtype=np.uint8)
                    else:
                        channel_data = np.full((height, width), 128, dtype=np.uint8)
                    
                    if invert:
                        channel_data = 255 - channel_data
                    
                    mrao_array[:, :, i] = channel_data
            
            # 创建可视化预览图像
            preview_array = np.zeros((height, width, 3), dtype=np.uint8)
            preview_array[:, :, 0] = mrao_array[:, :, 0]  # M -> R
            preview_array[:, :, 1] = mrao_array[:, :, 1]  # R -> G  
            preview_array[:, :, 2] = mrao_array[:, :, 2]  # AO -> B
            
            preview_image = Image.fromarray(preview_array, mode='RGB')
            qt_image = ImageQt.ImageQt(preview_image)
            pixmap = QPixmap.fromImage(qt_image)
            
            output_preview.original_pixmap = pixmap
            output_preview.update_display()
            
        except Exception as e:
            print(f"更新批量输出预览失败: {e}")
    
    def update_batch_previews(self):
        """更新批量预览显示"""
        # 清空现有预览
        for i in reversed(range(self.batch_preview_layout.count())):
            child = self.batch_preview_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # 如果有批量文件，创建预览组
        if self.batch_files:
            # 显示批量预览标签页
            self.tab_widget.setTabVisible(2, True)
            
            for i, file_path in enumerate(self.batch_files):
                preview_group = self.create_batch_preview_group(file_path, i)
                self.batch_preview_layout.addWidget(preview_group)
            
            # 添加弹性空间
            self.batch_preview_layout.addStretch()
            
            # 切换到批量预览标签页
            self.tab_widget.setCurrentIndex(2)
        else:
            # 隐藏批量预览标签页
            self.tab_widget.setTabVisible(2, False)
            # 切换回通道预览标签页
            self.tab_widget.setCurrentIndex(0)
    
    def update_all_batch_previews(self):
        """更新所有批量预览的输出"""
        if not self.batch_files:
            return
        
        # 遍历所有批量预览组，更新输出预览
        for i in range(self.batch_preview_layout.count()):
            item = self.batch_preview_layout.itemAt(i)
            if item and item.widget():
                group_widget = item.widget()
                if hasattr(group_widget, 'layout') and group_widget.layout():
                    # 查找输出预览组件（第4个位置，索引3）
                    layout = group_widget.layout()
                    if layout.count() > 3:
                        output_item = layout.itemAtPosition(0, 3)
                        if output_item and output_item.widget():
                            output_preview = output_item.widget()
                            if isinstance(output_preview, ImagePreviewWidget):
                                # 获取对应的图像路径
                                if i < len(self.batch_files):
                                    self.update_batch_output_preview(self.batch_files[i], output_preview)
    
    def select_batch_files(self):
        """选择批量文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择批量输入贴图文件",
            "", "图像文件 (*.png *.jpg *.jpeg *.tga *.bmp *.tiff)"
        )
        if file_paths:
            self.batch_files = file_paths
            self.update_batch_list_display()
            
            # 更新批量预览
            self.update_batch_previews()
            
            # 加载第一个文件作为预览
            if file_paths:
                self.input_preview.load_image(file_paths[0])
                self.update_channel_previews(file_paths[0])
                self.update_output_preview()
            
            self.check_ready_to_process()
    
    def update_batch_list_display(self):
        """更新批量文件列表显示"""
        if not self.batch_files:
            self.batch_list_label.setText("批量文件: 未选择")
        else:
            file_names = [Path(f).name for f in self.batch_files]
            if len(file_names) <= 3:
                display_text = f"批量文件 ({len(file_names)}个): {', '.join(file_names)}"
            else:
                display_text = f"批量文件 ({len(file_names)}个): {', '.join(file_names[:3])}..."
            self.batch_list_label.setText(display_text)
    
    def select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_label.setText(f"输出目录: {dir_path}")
            self.output_dir = dir_path
            self.check_ready_to_process()
    
    def update_channel_previews(self, image_path: str):
        """更新通道预览"""
        try:
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            
            # 只显示RGB通道
            channels = {
                "红色通道": img_array[:, :, 0],
                "绿色通道": img_array[:, :, 1],
                "蓝色通道": img_array[:, :, 2]
            }
            
            for name, channel_data in channels.items():
                if name in self.channel_previews:
                    # 创建灰度图像
                    channel_image = Image.fromarray(channel_data, mode='L')
                    qt_image = ImageQt.ImageQt(channel_image)
                    pixmap = QPixmap.fromImage(qt_image)
                    
                    # 保存原始pixmap并更新显示
                    self.channel_previews[name].original_pixmap = pixmap
                    self.channel_previews[name].update_display()
            
            # 同时更新输出预览
            self.update_output_preview()
                    
        except Exception as e:
            print(f"更新通道预览失败: {e}")
    
    def update_output_preview(self):
        """根据当前配置更新输出预览"""
        if not hasattr(self.input_preview, 'image_path') or not self.input_preview.image_path:
            return
        
        try:
            # 加载输入图像
            image = Image.open(self.input_preview.image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 获取当前映射配置
            mapping_config = self.mapping_widget.get_mapping_config()
            
            # 分离通道
            channels = {
                '红色通道': img_array[:, :, 0],
                '绿色通道': img_array[:, :, 1],
                '蓝色通道': img_array[:, :, 2]
            }
            
            # 合成MRAO贴图预览
            mrao_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            for i, channel_key in enumerate(['metallic', 'roughness', 'ao']):
                if channel_key in mapping_config:
                    config = mapping_config[channel_key]
                    source = config['source']
                    invert = config['invert']
                    
                    if source in channels:
                        channel_data = channels[source]
                    elif source == '灰度':
                        # 计算灰度
                        channel_data = np.dot(img_array[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                    elif source == '白色':
                        channel_data = np.full((height, width), 255, dtype=np.uint8)
                    elif source == '黑色':
                        channel_data = np.full((height, width), 0, dtype=np.uint8)
                    else:
                        channel_data = np.full((height, width), 128, dtype=np.uint8)
                    
                    if invert:
                        channel_data = 255 - channel_data
                    
                    mrao_array[:, :, i] = channel_data
            
            # 创建可视化预览图像（将MRAO通道合成为可见的RGB图像）
            # 为了更好的预览效果，我们将MRAO的三个通道映射到RGB
            preview_array = np.zeros((height, width, 3), dtype=np.uint8)
            preview_array[:, :, 0] = mrao_array[:, :, 0]  # M -> R
            preview_array[:, :, 1] = mrao_array[:, :, 1]  # R -> G  
            preview_array[:, :, 2] = mrao_array[:, :, 2]  # AO -> B
            
            preview_image = Image.fromarray(preview_array, mode='RGB')
            qt_image = ImageQt.ImageQt(preview_image)
            pixmap = QPixmap.fromImage(qt_image)
            
            # 更新输出预览
            self.output_preview.original_pixmap = pixmap
            self.output_preview.update_display()
            
        except Exception as e:
            print(f"更新输出预览失败: {e}")
    
    def check_ready_to_process(self):
        """检查是否准备好处理"""
        has_single_input = bool(hasattr(self.input_preview, 'image_path') and self.input_preview.image_path)
        has_batch_input = bool(self.batch_files and len(self.batch_files) > 0)
        has_output = bool(hasattr(self, 'output_dir') and self.output_dir)
        
        self.process_btn.setEnabled((has_single_input or has_batch_input) and has_output)
    
    def start_processing(self):
        """开始处理"""
        if not hasattr(self, 'output_dir') or not self.output_dir:
            return
        
        # 获取映射配置
        mapping_config = self.mapping_widget.get_mapping_config()
        
        # 禁用处理按钮
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 判断是单个文件还是批量处理
        if self.batch_files and len(self.batch_files) > 0:
            # 批量处理
            self.batch_progress_label.setVisible(True)
            self.batch_progress_label.setText("准备批量处理...")
            
            self.batch_processor = BatchTextureProcessor(
                self.batch_files,
                mapping_config,
                self.output_dir,
                self.format_combo.currentText()
            )
            
            self.batch_processor.progress_updated.connect(self.progress_bar.setValue)
            self.batch_processor.status_updated.connect(self.statusBar().showMessage)
            self.batch_processor.batch_progress_updated.connect(self.batch_progress_label.setText)
            self.batch_processor.finished_processing.connect(self.on_processing_finished)
            
            self.batch_processor.start()
            
        else:
            # 单个文件处理
            if not hasattr(self.input_preview, 'image_path') or not self.input_preview.image_path:
                return
            
            self.processor = TextureProcessor(
                self.input_preview.image_path,
                mapping_config,
                self.output_dir,
                self.format_combo.currentText()
            )
            
            self.processor.progress_updated.connect(self.progress_bar.setValue)
            self.processor.status_updated.connect(self.statusBar().showMessage)
            self.processor.finished_processing.connect(self.on_processing_finished)
            
            self.processor.start()
    
    def on_processing_finished(self, success: bool, message: str):
        """处理完成回调"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.batch_progress_label.setVisible(False)
        
        if success:
            self.statusBar().showMessage(message, 5000)
            # 更新输出预览（仅在单个文件处理时）
            if not (self.batch_files and len(self.batch_files) > 0):
                self.update_output_preview()
        else:
            self.statusBar().showMessage(f"错误: {message}", 10000)
    
    def toggle_theme(self):
        """切换主题"""
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self.apply_theme()
    
    def apply_theme(self):
        """应用主题"""
        # 更新所有ModernButton组件
        for button in self.findChildren(ModernButton):
            button.set_dark_mode(self.dark_mode)
        
        # 更新所有ImagePreviewWidget组件
        for preview in self.findChildren(ImagePreviewWidget):
            preview.set_dark_mode(self.dark_mode)
        
        if self.dark_mode:
            # 暗色主题
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #555555;
                    border-radius: 8px;
                    margin-top: 1ex;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QLabel {
                    color: #ffffff;
                }
                QComboBox {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px;
                    color: #ffffff;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    background-color: #2b2b2b;
                }
                QTabBar::tab {
                    background-color: #404040;
                    color: #ffffff;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #4A90E2;
                }
                QProgressBar {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4A90E2;
                    border-radius: 3px;
                }
            """)
        else:
            # 浅色主题
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #ffffff;
                    color: #333333;
                }
                QWidget {
                    background-color: #ffffff;
                    color: #333333;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #DDDDDD;
                    border-radius: 8px;
                    margin-top: 1ex;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #DDDDDD;
                    border-radius: 4px;
                    padding: 4px;
                }
                QTabWidget::pane {
                    border: 1px solid #DDDDDD;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background-color: #F5F5F5;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #4A90E2;
                    color: #ffffff;
                }
                QProgressBar {
                    border: 1px solid #DDDDDD;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4A90E2;
                    border-radius: 3px;
                }
            """)


def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("PBR贴图处理工具")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("MOD制作工具")
    
    # 创建主窗口
    window = PBRTextureToolMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()