#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTF材质工具 - PySide6版本
整合VTF转换的一站式工具
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import json
import shutil
from PIL import Image
import numpy as np
import logging
import datetime

# VTF转换现在使用VTF CMD命令行工具，不再依赖sourcepp

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QLineEdit, QPushButton, QListWidget, QTextEdit,
    QGroupBox, QRadioButton, QCheckBox, QButtonGroup, QFileDialog,
    QMessageBox, QProgressBar, QStatusBar, QFrame, QGridLayout,
    QSizePolicy, QSpacerItem, QComboBox, QDialog, QPlainTextEdit, QMenuBar, QMenu,
    QSpinBox, QSplitter, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QDragEnterEvent, QDropEvent, QAction


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.settings = QSettings("VTFTool", "VTFMaterialTool")
        
    def get(self, key: str, default=None):
        return self.settings.value(key, default)
        
    def set(self, key: str, value):
        self.settings.setValue(key, value)
        
    def sync(self):
        self.settings.sync()


class DebugLogger:
    """调试日志管理器"""
    
    def __init__(self):
        self.logger = None
        self.log_file_path = None
        self.enabled = False
        
    def setup_logger(self, log_file_path: str):
        """设置日志记录器"""
        try:
            self.log_file_path = log_file_path
            
            # 创建logger
            self.logger = logging.getLogger('VTFDebugLogger')
            self.logger.setLevel(logging.DEBUG)
            
            # 清除现有的handlers
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
            # 创建文件handler
            file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # 创建formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # 添加handler到logger
            self.logger.addHandler(file_handler)
            
            self.enabled = True
            self.log_info("=== VTF材质工具调试日志开始 ===")
            self.log_info(f"日志文件路径: {log_file_path}")
            
            return True
            
        except Exception as e:
            print(f"设置日志记录器失败: {str(e)}")
            self.enabled = False
            return False
    
    def log_info(self, message: str):
        """记录信息日志"""
        if self.enabled and self.logger:
            self.logger.info(message)
            
    def log_warning(self, message: str):
        """记录警告日志"""
        if self.enabled and self.logger:
            self.logger.warning(message)
            
    def log_error(self, message: str):
        """记录错误日志"""
        if self.enabled and self.logger:
            self.logger.error(message)
            
    def log_debug(self, message: str):
        """记录调试日志"""
        if self.enabled and self.logger:
            self.logger.debug(message)
            
    def log_tga_operation(self, operation: str, file_path: str, success: bool, details: str = ""):
        """记录TGA文件操作日志"""
        status = "成功" if success else "失败"
        message = f"TGA操作 - {operation}: {file_path} - {status}"
        if details:
            message += f" - {details}"
        
        if success:
            self.log_info(message)
        else:
            self.log_error(message)
            
    def log_vmt_alignment(self, file_path: str, parameter: str, alignment_info: str):
        """记录VMT参数对齐日志"""
        message = f"VMT对齐 - 文件: {file_path} - 参数: {parameter} - 对齐信息: {alignment_info}"
        self.log_debug(message)
        
    def close(self):
        """关闭日志记录器"""
        if self.enabled and self.logger:
            self.log_info("=== VTF材质工具调试日志结束 ===")
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
            self.enabled = False


class PBRSourceAlgorithms:
    """PBR-2-Source项目的HL2 Phong+Envmap+alpha模式算法实现"""
    
    @staticmethod
    def make_phong_exponent(roughness_img: Image) -> Image:
        """生成Phong指数纹理 - 基于PBR-2-Source原版算法"""
        import numpy as np
        
        # 转换为numpy数组进行计算
        roughness_data = np.array(roughness_img.convert('L'))
        roughness_normalized = roughness_data.astype(np.float32) / 255.0
        
        # 原版算法: roughness^(-2) * (0.8 / 32)
        # 即: (0.8 / 32) / (roughness^2)
        MAX_EXPONENT = 32
        # 避免除零错误，设置最小值
        roughness_normalized = np.clip(roughness_normalized, 0.01, 1.0)
        exponent_data = (0.8 / MAX_EXPONENT) / np.power(roughness_normalized, 2)
        
        # 限制在合理范围内
        exponent_data = np.clip(exponent_data, 0.0, 1.0)
        
        # 转换回PIL图像
        exponent_data_uint8 = (exponent_data * 255).astype(np.uint8)
        return Image.fromarray(exponent_data_uint8, mode='L')
    
    @staticmethod
    def make_phong_mask(roughness_img: Image, ao_img: Image = None) -> Image:
        """生成Phong遮罩 - 基于PBR-2-Source原版算法"""
        import numpy as np
        
        # 转换为numpy数组
        roughness_data = np.array(roughness_img.convert('L'))
        roughness_normalized = roughness_data.astype(np.float32) / 255.0
        
        # 原版算法: ((1-roughness)^5.4) * 2
        smoothness = 1.0 - roughness_normalized
        mask_data = np.power(smoothness, 5.4) * 2
        
        # 如果有AO贴图，应用AO
        if ao_img is not None:
            ao_data = np.array(ao_img.convert('L'))
            ao_normalized = ao_data.astype(np.float32) / 255.0
            mask_data *= ao_normalized
        
        # 限制在合理范围内
        mask_data = np.clip(mask_data, 0.0, 1.0)
        
        # 转换回PIL图像
        mask_data_uint8 = (mask_data * 255).astype(np.uint8)
        return Image.fromarray(mask_data_uint8, mode='L')
    
    @staticmethod
    def make_envmask(metallic_img: Image, roughness_img: Image, ao_img: Image = None, has_phong: bool = True) -> Image:
        """生成环境贴图遮罩 - 基于PBR-2-Source原版算法"""
        import numpy as np
        
        # 转换为numpy数组
        metallic_data = np.array(metallic_img.convert('L'))
        metallic_normalized = metallic_data.astype(np.float32) / 255.0
        
        roughness_data = np.array(roughness_img.convert('L'))
        roughness_normalized = roughness_data.astype(np.float32) / 255.0
        
        # 原版算法: (metallic * 0.75 + 0.25) * ((1-roughness)^5)
        # Phong模式下使用指数5，否则使用指数3
        roughness_exp = 5 if has_phong else 3
        
        mask1 = metallic_normalized * 0.75 + 0.25
        smoothness = 1.0 - roughness_normalized
        mask2 = np.power(smoothness, roughness_exp)
        
        # 如果有AO贴图，应用AO
        if ao_img is not None:
            ao_data = np.array(ao_img.convert('L'))
            ao_normalized = ao_data.astype(np.float32) / 255.0
            mask2 *= ao_normalized
        
        result = mask1 * mask2
        
        # 限制在合理范围内
        result = np.clip(result, 0.0, 1.0)
        
        # 转换回PIL图像
        result_uint8 = (result * 255).astype(np.uint8)
        return Image.fromarray(result_uint8, mode='L')
    
    @staticmethod
    def make_basecolor(albedo_img: Image, metallic_img: Image, roughness_img: Image, ao_img: Image = None, preserve_alpha: bool = False) -> Image:
        """生成基础色纹理 - 基于PBR-2-Source原版算法
        
        Args:
            preserve_alpha: 是否保持原始图像的alpha通道
        """
        import numpy as np
        
        # 转换为numpy数组
        albedo_data = np.array(albedo_img.convert('RGB'))
        albedo_normalized = albedo_data.astype(np.float32) / 255.0
        
        metallic_data = np.array(metallic_img.convert('L'))
        metallic_normalized = metallic_data.astype(np.float32) / 255.0
        
        roughness_data = np.array(roughness_img.convert('L'))
        roughness_normalized = roughness_data.astype(np.float32) / 255.0
        
        # 原版算法: 用于暗化基础色的遮罩
        # mask = 1 - ((1-roughness) * metallic)
        smoothness = 1.0 - roughness_normalized
        mask = smoothness * metallic_normalized
        mask = 1.0 - mask
        
        # 如果有AO贴图，混合AO
        if ao_img is not None:
            ao_data = np.array(ao_img.convert('L'))
            ao_normalized = ao_data.astype(np.float32) / 255.0
            # AO混合: ao * 0.75 + 0.25
            ao_blend = ao_normalized * 0.75 + 0.25
            mask *= ao_blend
        
        # 应用遮罩到每个颜色通道
        result = albedo_normalized.copy()
        for i in range(3):  # RGB通道
            result[:, :, i] *= mask
        
        # 限制在合理范围内
        result = np.clip(result, 0.0, 1.0)
        
        # 转换回PIL图像
        result_uint8 = (result * 255).astype(np.uint8)
        
        if preserve_alpha and albedo_img.mode in ('RGBA', 'LA'):
            # 保持原始alpha通道
            original_alpha = np.array(albedo_img.convert('RGBA'))[:, :, 3]
            result_rgba = np.dstack([result_uint8, original_alpha])
            return Image.fromarray(result_rgba, mode='RGBA')
        elif preserve_alpha:
            # 原始图像没有alpha，但要求保持alpha格式
            alpha_channel = np.full((result_uint8.shape[0], result_uint8.shape[1]), 255, dtype=np.uint8)
            result_rgba = np.dstack([result_uint8, alpha_channel])
            return Image.fromarray(result_rgba, mode='RGBA')
        else:
            # 返回RGB格式
            return Image.fromarray(result_uint8, mode='RGB')
    
    @staticmethod
    def make_bumpmap_with_phong_mask(normal_img: Image, phong_mask_img: Image) -> Image:
        """生成带有Phong遮罩的法线贴图 - PhongEnvmapAlpha模式"""
        import numpy as np
        
        # 转换法线贴图为RGB
        normal_data = np.array(normal_img.convert('RGB'))
        
        # 转换Phong遮罩为灰度
        phong_mask_data = np.array(phong_mask_img.convert('L'))
        
        # 合并为RGBA：RGB来自法线贴图，Alpha来自Phong遮罩
        height, width = normal_data.shape[:2]
        result = np.zeros((height, width, 4), dtype=np.uint8)
        result[:, :, :3] = normal_data  # RGB通道
        result[:, :, 3] = phong_mask_data  # Alpha通道
        
        result_img = Image.fromarray(result, mode='RGBA')
        print(f"[调试] make_bumpmap_with_phong_mask 输出: 模式={result_img.mode}, 尺寸={result_img.size}, 通道数={len(result_img.getbands())}")
        return result_img
    
    @staticmethod
    def generate_default_normal(size: tuple) -> Image:
        """生成默认法线贴图 (0.5, 0.5, 1.0)"""
        import numpy as np
        
        width, height = size
        # 创建默认法线贴图：RGB = (128, 128, 255) 对应 (0.5, 0.5, 1.0)
        normal_data = np.full((height, width, 3), [128, 128, 255], dtype=np.uint8)
        return Image.fromarray(normal_data, mode='RGB')
    
    @staticmethod
    def generate_default_metallic(size: tuple, value: float = 0.0) -> Image:
        """生成默认金属度贴图"""
        import numpy as np
        
        width, height = size
        # 创建默认金属度贴图：通常为0（非金属）
        metallic_value = int(value * 255)
        metallic_data = np.full((height, width), metallic_value, dtype=np.uint8)
        return Image.fromarray(metallic_data, mode='L')
    
    @staticmethod
    def generate_default_ao(size: tuple, value: float = 1.0) -> Image:
        """生成默认AO贴图"""
        import numpy as np
        
        width, height = size
        # 创建默认AO贴图：通常为1（无遮蔽）
        ao_value = int(value * 255)
        ao_data = np.full((height, width), ao_value, dtype=np.uint8)
        return Image.fromarray(ao_data, mode='L')
    
    @staticmethod
    def make_emit(emit_img: Image, is_pbr_mode: bool = False) -> Image:
        """生成自发光纹理 - 基于PBR-2-Source原版算法"""
        import numpy as np
        
        # 如果是PBR模式，直接返回原图
        if is_pbr_mode:
            return emit_img
        
        # 非PBR模式需要进行伽马校正以匹配Strata PBR
        emit_data = np.array(emit_img.convert('RGB'))
        emit_normalized = emit_data.astype(np.float32) / 255.0
        
        # 应用伽马校正 2.2
        gamma_corrected = np.power(emit_normalized, 2.2)
        
        # 限制在合理范围内
        gamma_corrected = np.clip(gamma_corrected, 0.0, 1.0)
        
        # 转换回PIL图像
        result_uint8 = (gamma_corrected * 255).astype(np.uint8)
        return Image.fromarray(result_uint8, mode='RGB')
    
    @staticmethod
    def make_mrao(metallic_img: Image, roughness_img: Image, ao_img: Image = None) -> Image:
        """生成MRAO纹理 (Metallic-Roughness-AO) - 基于PBR-2-Source原版算法"""
        import numpy as np
        
        # 转换为numpy数组
        metallic_data = np.array(metallic_img.convert('L'))
        roughness_data = np.array(roughness_img.convert('L'))
        
        # 如果没有AO贴图，创建默认的白色AO
        if ao_img is None:
            height, width = metallic_data.shape
            ao_data = np.full((height, width), 255, dtype=np.uint8)
        else:
            ao_data = np.array(ao_img.convert('L'))
        
        # 合并为RGB：R=Metallic, G=Roughness, B=AO
        height, width = metallic_data.shape
        mrao_data = np.zeros((height, width, 3), dtype=np.uint8)
        mrao_data[:, :, 0] = metallic_data  # Red channel = Metallic
        mrao_data[:, :, 1] = roughness_data  # Green channel = Roughness
        mrao_data[:, :, 2] = ao_data  # Blue channel = AO
        
        return Image.fromarray(mrao_data, mode='RGB')


class ImageProcessingThread(QThread):
    """图像处理线程"""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    processing_finished = Signal(bool, str)
    
    def __init__(self, files: List[str], options: Dict[str, Any], debug_logger=None):
        super().__init__()
        self.files = files
        self.options = options
        self.is_cancelled = False
        self.debug_logger = debug_logger
        
    def run(self):
        try:
            total_files = len(self.files)
            for i, file_path in enumerate(self.files):
                if self.is_cancelled:
                    break
                    
                self.status_updated.emit(f"正在处理: {Path(file_path).name}")
                
                # 这里添加实际的图像处理逻辑
                self.process_single_file(file_path)
                
                progress = int((i + 1) / total_files * 100)
                self.progress_updated.emit(progress)
                
            if not self.is_cancelled:
                self.processing_finished.emit(True, "处理完成")
            else:
                self.processing_finished.emit(False, "处理已取消")
                
        except Exception as e:
            self.processing_finished.emit(False, f"处理失败: {str(e)}")
            
    def process_single_file(self, file_path: str):
        """处理单个文件"""
        # 模拟处理时间
        self.msleep(100)
        
    def cancel(self):
        self.is_cancelled = True


class NightglowProcessingThread(QThread):
    """夜光处理线程"""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    processing_finished = Signal(bool, str)
    
    def __init__(self, files: List[str], options: Dict[str, Any], debug_logger=None):
        super().__init__()
        self.files = files
        self.options = options
        self.is_cancelled = False
        self.debug_logger = debug_logger
        
    def run(self):
        try:
            total_files = len(self.files)
            processed_count = 0
            
            for i, file_path in enumerate(self.files):
                if self.is_cancelled:
                    break
                    
                self.status_updated.emit(f"正在处理: {Path(file_path).name}")
                
                # 处理单个文件
                if self.process_nightglow_file(file_path):
                    processed_count += 1
                
                progress = int((i + 1) / total_files * 100)
                self.progress_updated.emit(progress)
                
            if not self.is_cancelled:
                self.processing_finished.emit(True, f"处理完成，成功处理 {processed_count} 个文件")
            else:
                self.processing_finished.emit(False, "处理已取消")
                
        except Exception as e:
            self.processing_finished.emit(False, f"处理失败: {str(e)}")
            
    def process_nightglow_file(self, vtf_file: str) -> bool:
        """处理单个夜光文件"""
        try:
            vtf_path = Path(vtf_file)
            
            # 检查文件是否存在
            if not vtf_path.exists():
                print(f"文件不存在: {vtf_file}")
                return False
                
            # 获取文件名（不含扩展名）
            base_name = vtf_path.stem
            
            # 检查全局屏蔽词
            if self.is_blacklisted(base_name, self.options.get('preset_blacklist', []), 
                                 self.options.get('custom_blacklist', '')):
                print(f"跳过黑名单文件: {base_name}")
                return False
            
            # 优先处理vmtE发光生成，如果成功则跳过S发光处理
            e_glow_processed = False
            if self.options.get('vmte_glow', False):
                e_glow_processed = self.process_vmte_glow(vtf_file)
                if e_glow_processed:
                    print(f"已处理E发光，跳过S发光处理: {base_name}")
                    # 修改vmt-base（如果需要）
                    if self.options.get('modify_vmtbase', False):
                        self.modify_vmt_base(vtf_path.parent)
                    return True
            
            # 如果E发光未处理或处理失败，则进行S发光处理
            if not e_glow_processed:
                print(f"进行S发光处理: {base_name}")
                
                # 创建Selfillum目录
                selfillum_dir = vtf_path.parent / "Selfillum"
                selfillum_dir.mkdir(exist_ok=True)
                
                # VTF转TGA
                tga_file = selfillum_dir / f"{base_name}.tga"
                if not self.vtf_to_tga(vtf_file, str(tga_file)):
                    return False
                    
                # 使用ImageMagick调整Alpha通道
                if not self.adjust_alpha_channel(str(tga_file)):
                    return False
                    
                # TGA转回VTF
                output_vtf = selfillum_dir / f"{base_name}.vtf"
                if not self.tga_to_vtf(str(tga_file), str(output_vtf)):
                    return False
                    
                # 删除临时TGA文件
                if tga_file.exists():
                    tga_file.unlink()
                
                # 额外清理VTF文件所在目录中可能遗留的TGA文件
                self.cleanup_tga_files_in_vtf_directory(vtf_path)
                
                # 修改vmt-base
                if self.options.get('modify_vmtbase', False):
                    self.modify_vmt_base(vtf_path.parent)
                
            return True
            
        except Exception as e:
            print(f"处理文件 {vtf_file} 时出错: {str(e)}")
            return False
            
    def vtf_to_tga(self, vtf_file: str, tga_file: str) -> bool:
        """VTF转TGA"""
        try:
            vtfcmd_path = self.get_vtfcmd_path()
            if not vtfcmd_path:
                return False
                
            cmd = [vtfcmd_path, "-file", vtf_file, "-output", str(Path(tga_file).parent), "-exportformat", "tga"]
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            return result.returncode == 0 and Path(tga_file).exists()
            
        except Exception as e:
            print(f"VTF转TGA失败: {str(e)}")
            return False
            
    def tga_to_vtf(self, tga_file: str, vtf_file: str) -> bool:
        """TGA转VTF"""
        try:
            vtfcmd_path = self.get_vtfcmd_path()
            if not vtfcmd_path:
                return False
                
            # 获取VTF命令参数
            vtf_args = self.get_vtf_args(self.options.get('format', 'DXT5'))
            
            cmd = [vtfcmd_path, "-file", tga_file, "-output", str(Path(vtf_file).parent)] + vtf_args
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            return result.returncode == 0 and Path(vtf_file).exists()
            
        except Exception as e:
            print(f"TGA转VTF失败: {str(e)}")
            return False
            
    def adjust_alpha_channel(self, tga_file: str) -> bool:
        """使用ImageMagick调整Alpha通道"""
        try:
            # 添加全白Alpha通道并降低至5%
            cmd = [
                "magick", tga_file,
                "-alpha", "set",
                "-channel", "A",
                "-evaluate", "set", "100%",
                "+channel",
                "-channel", "A",
                "-evaluate", "multiply", "0.05",
                "+channel",
                tga_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.returncode == 0
            
        except Exception as e:
            print(f"调整Alpha通道失败: {str(e)}")
            return False
            
    def process_vmte_glow(self, vtf_file: str):
        """处理vmtE发光生成（支持PNG中转保留Alpha通道）"""
        try:
            vtf_path = Path(vtf_file)
            base_name = vtf_path.stem
            
            if self.debug_logger:
                self.debug_logger.log_info(f"开始处理E发光文件: {base_name}")
                self.debug_logger.log_debug(f"VTF文件路径: {vtf_file}")
            
            # 检查E发光专用屏蔽词
            e_blacklist = self.options.get('e_blacklist', '')
            if e_blacklist:
                e_words = [word.strip() for word in e_blacklist.split(',') if word.strip()]
                if any(word.lower() in base_name.lower() for word in e_words):
                    if self.debug_logger:
                        self.debug_logger.log_info(f"跳过E发光黑名单文件: {base_name}")
                    print(f"跳过E发光黑名单文件: {base_name}")
                    return
            
            # 使用临时目录处理文件
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 先检查VTF信息，确定是否支持Alpha
                vtfcmd_path = self.get_vtfcmd_path()
                if not vtfcmd_path:
                    if self.debug_logger:
                        self.debug_logger.log_error(f"未找到VTFCmd工具")
                    print(f"未找到VTFCmd工具")
                    return
                
                if self.debug_logger:
                    self.debug_logger.log_debug(f"使用VTFCmd路径: {vtfcmd_path}")
                    self.debug_logger.log_debug(f"检查VTF格式信息: {vtf_path.absolute()}")
                
                cmd_info = [vtfcmd_path, '-file', str(vtf_path.absolute())]
                info_result = subprocess.run(cmd_info, capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
                
                has_alpha = False
                if info_result.returncode == 0 and info_result.stdout:
                    vtf_info = info_result.stdout.lower()
                    if self.debug_logger:
                        self.debug_logger.log_debug(f"VTF信息: {info_result.stdout[:200]}...")  # 只记录前200字符
                    # 检查是否是支持Alpha的格式
                    if any(fmt in vtf_info for fmt in ['dxt5', 'dxt3', 'rgba8888', 'bgra8888']):
                        has_alpha = True
                        if self.debug_logger:
                            self.debug_logger.log_info(f"检测到支持Alpha的VTF格式")
                        print(f"检测到支持Alpha的VTF格式")
                else:
                    if self.debug_logger:
                        self.debug_logger.log_error(f"获取VTF信息失败: {info_result.stderr}")
                
                png_file = None
                if has_alpha:
                    # 对于有Alpha的格式，尝试使用PNG导出以保留Alpha信息
                    if self.debug_logger:
                        self.debug_logger.log_info(f"尝试PNG导出以保留Alpha通道")
                    cmd_png = [vtfcmd_path, '-file', str(vtf_path.absolute()), '-output', str(temp_path), '-exportformat', 'png']
                    result_png = subprocess.run(cmd_png, capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    if result_png.returncode == 0:
                        # PNG导出成功
                        png_files = list(temp_path.glob(f"{base_name}*.png"))
                        if not png_files:
                            png_files = list(temp_path.glob("*.png"))
                        
                        if png_files:
                            png_file = png_files[0]
                            if self.debug_logger:
                                self.debug_logger.log_info(f"PNG导出成功: {png_file.name}")
                            print(f"通过PNG导出成功保留Alpha通道")
                        else:
                            if self.debug_logger:
                                self.debug_logger.log_error(f"PNG导出失败，未找到PNG文件")
                            print(f"PNG导出失败，未找到PNG文件")
                    else:
                        if self.debug_logger:
                            self.debug_logger.log_error(f"PNG导出失败: {result_png.stderr}")
                        print(f"PNG导出失败: {result_png.stderr}")
                
                if not png_file:
                    # 如果PNG导出失败，使用TGA导出
                    if self.debug_logger:
                        self.debug_logger.log_info(f"PNG导出失败，尝试TGA导出")
                    cmd_tga = [vtfcmd_path, '-file', str(vtf_path.absolute()), '-output', str(temp_path), '-exportformat', 'tga']
                    result_tga = subprocess.run(cmd_tga, capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    if result_tga.returncode == 0:
                        # TGA导出成功，转换为PNG
                        tga_files = list(temp_path.glob(f"{base_name}*.tga"))
                        if not tga_files:
                            tga_files = list(temp_path.glob("*.tga"))
                        
                        if tga_files:
                            tga_file = tga_files[0]
                            png_file = temp_path / f"{base_name}.png"
                            
                            if self.debug_logger:
                                self.debug_logger.log_debug(f"TGA导出成功: {tga_file.name}，开始转换为PNG")
                            
                            # 使用ImageMagick将TGA转为PNG，保留Alpha
                            cmd_convert = ['magick', str(tga_file), str(png_file)]
                            convert_result = subprocess.run(cmd_convert, capture_output=True, text=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
                            
                            if convert_result.returncode == 0:
                                if self.debug_logger:
                                    self.debug_logger.log_info(f"TGA转PNG成功: {png_file.name}")
                                print(f"通过TGA中转成功保留Alpha通道")
                                # 删除TGA文件
                                if self.debug_logger:
                                    self.debug_logger.log_debug(f"删除临时TGA文件: {tga_file.name}")
                                tga_file.unlink()
                            else:
                                if self.debug_logger:
                                    self.debug_logger.log_error(f"TGA转PNG失败: {convert_result.stderr}")
                                print(f"TGA转PNG失败: {convert_result.stderr}")
                                return
                        else:
                            if self.debug_logger:
                                self.debug_logger.log_error(f"TGA导出失败，未找到TGA文件")
                            print(f"TGA导出失败，未找到TGA文件")
                            return
                    else:
                        if self.debug_logger:
                            self.debug_logger.log_error(f"TGA导出失败: {result_tga.stderr}")
                        print(f"TGA导出失败: {result_tga.stderr}")
                        return
                
                if not png_file or not png_file.exists():
                    if self.debug_logger:
                        self.debug_logger.log_error(f"无法获取有效的PNG文件")
                    print(f"无法获取有效的PNG文件")
                    return
                
                if self.debug_logger:
                    self.debug_logger.log_debug(f"开始检测Alpha通道: {png_file.name}")
                
                # 检测Alpha通道
                if self.detect_alpha_channel(str(png_file)):
                    if self.debug_logger:
                        self.debug_logger.log_info(f"检测到有效Alpha通道，开始生成E发光文件")
                    
                    # 修改vmt-base文件中的$selfillum参数
                    if self.options.get('modify_vmtbase', False):
                        if self.debug_logger:
                            self.debug_logger.log_info(f"开始修改vmt-base文件")
                        self.modify_vmt_base(vtf_path)
                    
                    # 创建EmissiveGlow文件夹
                    emissive_dir = vtf_path.parent / "EmissiveGlow"
                    emissive_dir.mkdir(exist_ok=True)
                    if self.debug_logger:
                        self.debug_logger.log_debug(f"创建EmissiveGlow文件夹: {emissive_dir}")
                    
                    # 生成E贴图
                    e_vtf_file = emissive_dir / f"{base_name}_E.vtf"
                    if self.debug_logger:
                        self.debug_logger.log_info(f"开始生成E贴图: {e_vtf_file.name}")
                    self.generate_e_texture(str(png_file), str(e_vtf_file))
                    
                    # 生成VMT文件
                    if self.debug_logger:
                        self.debug_logger.log_info(f"开始生成VMT文件")
                    self.generate_vmt_file(vtf_path)
                    
                    if self.debug_logger:
                        self.debug_logger.log_info(f"成功生成E发光文件: {base_name}")
                    print(f"成功生成E发光文件: {base_name}")
                    
                    # 清理VTF文件所在目录中可能生成的TGA文件
                    self.cleanup_tga_files_in_vtf_directory(vtf_path)
                    
                    return True
                else:
                    if self.debug_logger:
                        self.debug_logger.log_info(f"未检测到有效Alpha通道，跳过E发光处理: {base_name}")
                    print(f"跳过E发光处理: {base_name}")
                    
                    # 即使跳过处理，也要清理可能生成的TGA文件
                    self.cleanup_tga_files_in_vtf_directory(vtf_path)
                    
                    return False
                
        except Exception as e:
            print(f"处理vmtE发光时出错: {str(e)}")
            # 异常情况下也要清理TGA文件
            try:
                self.cleanup_tga_files_in_vtf_directory(vtf_path)
            except:
                pass
            return False
    
    def cleanup_tga_files_in_vtf_directory(self, vtf_path: Path):
        """清理VTF文件所在目录中可能生成的TGA文件"""
        try:
            vtf_dir = vtf_path.parent
            base_name = vtf_path.stem
            
            # 查找可能的TGA文件模式
            tga_patterns = [
                f"{base_name}.tga",  # 与VTF同名的TGA文件
                f"{base_name}_*.tga",  # 带后缀的TGA文件
                f"temp_{base_name}.tga",  # 临时TGA文件
            ]
            
            deleted_files = []
            for pattern in tga_patterns:
                tga_files = list(vtf_dir.glob(pattern))
                for tga_file in tga_files:
                    try:
                        tga_file.unlink()
                        deleted_files.append(str(tga_file))
                        if self.debug_logger:
                            self.debug_logger.log_tga_operation("清理VTF目录中的TGA文件", str(tga_file), True, "成功删除")
                        print(f"已删除TGA文件: {tga_file.name}")
                    except Exception as delete_error:
                        if self.debug_logger:
                            self.debug_logger.log_tga_operation("清理VTF目录中的TGA文件", str(tga_file), False, f"删除失败: {str(delete_error)}")
                        print(f"删除TGA文件失败: {tga_file.name} - {delete_error}")
            
            if deleted_files:
                if self.debug_logger:
                    self.debug_logger.log_info(f"清理完成，共删除{len(deleted_files)}个TGA文件")
                print(f"清理完成，共删除{len(deleted_files)}个TGA文件")
            else:
                if self.debug_logger:
                    self.debug_logger.log_debug(f"VTF目录中未找到需要清理的TGA文件")
                    
        except Exception as e:
            if self.debug_logger:
                self.debug_logger.log_error(f"清理TGA文件时出错: {str(e)}")
            print(f"清理TGA文件时出错: {str(e)}")
            
    def modify_vmt_base(self, vtf_path: Path):
        """修改vmt-base文件"""
        try:
            # 从VTF文件路径向上查找materials文件夹
            current_path = vtf_path.parent
            materials_dir = None
            
            while current_path.parent != current_path:
                if current_path.name == 'materials':
                    materials_dir = current_path
                    break
                current_path = current_path.parent
            
            if not materials_dir:
                print(f"未找到materials文件夹")
                return
                
            # 查找shader文件夹
            shader_dirs = list(materials_dir.rglob('shader'))
            if not shader_dirs:
                print(f"未找到shader文件夹")
                return
                
            for shader_dir in shader_dirs:
                vmt_base_file = shader_dir / "vmt-base.vmt"
                if vmt_base_file.exists():
                    # 读取并修改vmt-base文件
                    with open(vmt_base_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 查找并替换$selfillum行（包括注释和非注释的情况）
                    import re
                    modified = False
                    new_content = content
                    
                    # 模式1：匹配带注释的$selfillum "0"行
                    pattern1 = r'(\s*"\$selfillum"\s+)"0"(\s+//.*开启自发光.*不做自发光必须关掉.*)'
                    if re.search(pattern1, content):
                        new_content = re.sub(pattern1, r'\1"1"\2', content)
                        modified = True
                        print(f"找到并修改带注释的$selfillum行")
                    
                    # 模式2：匹配普通的$selfillum "0"行
                    elif re.search(r'"\$selfillum"\s+"0"', content):
                        new_content = re.sub(r'("\$selfillum"\s+)"0"', r'\1"1"', content)
                        modified = True
                        print(f"找到并修改普通的$selfillum行")
                    
                    # 模式3：匹配注释掉的$selfillum行
                    elif re.search(r'//\s*"\$selfillum"', content):
                        # 取消注释并设置为"1"
                        pattern3 = r'//\s*"\$selfillum"\s+"[01]"(.*开启自发光.*不做自发光必须关掉.*)'
                        replacement3 = '\t"$selfillum"\t\t\t\t\t"1"\t\t\t\t// 开启自发光。亮度区分取决于颜色贴图的 A 通道，越白则越亮。不做自发光必须关掉。'
                        if re.search(pattern3, content):
                            new_content = re.sub(pattern3, replacement3, content)
                            modified = True
                            print(f"找到并取消注释$selfillum行")
                    
                    if modified:
                        # 写回文件
                        with open(vmt_base_file, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        
                        print(f"已修改vmt-base.vmt文件: {vmt_base_file}")
                        return  # 修改成功后退出
                    else:
                        print(f"在vmt-base.vmt中未找到需要修改的$selfillum行: {vmt_base_file}")
                        
        except Exception as e:
            print(f"修改vmt-base失败: {str(e)}")
            
    def vtf_to_png(self, vtf_file: str, png_file: str) -> bool:
        """VTF转PNG（保留Alpha通道）"""
        try:
            vtfcmd_path = self.get_vtfcmd_path()
            if not vtfcmd_path:
                return False
                
            cmd = [vtfcmd_path, "-file", vtf_file, "-output", str(Path(png_file).parent), "-exportformat", "png"]
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            return result.returncode == 0 and Path(png_file).exists()
            
        except Exception as e:
            print(f"VTF转PNG失败: {str(e)}")
            return False
            
    def detect_alpha_channel(self, png_file: str) -> bool:
        """检测Alpha通道是否有效（使用多重检测方法）"""
        try:
            # 方法1: 检查Alpha通道的统计信息
            cmd_stats = ['magick', png_file, '-alpha', 'extract', '-format', '%[mean]\n%[min]\n%[max]\n%[standard-deviation]', 'info:']
            result_stats = subprocess.run(cmd_stats, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 方法2: 检查Alpha通道的直方图
            cmd_hist = ['magick', png_file, '-alpha', 'extract', '-format', '%[fx:mean<0.999?0:1]', 'info:']
            result_hist = subprocess.run(cmd_hist, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 方法3: 检查Alpha通道的像素值分布
            cmd_unique = ['magick', png_file, '-alpha', 'extract', '-unique-colors', '-format', '%[pixel:p{0,0}]\n', 'info:']
            result_unique = subprocess.run(cmd_unique, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result_stats.returncode != 0:
                print(f"ImageMagick统计检测失败: {result_stats.stderr}，默认进行处理")
                return True  # 默认进行处理
            
            lines = result_stats.stdout.strip().split('\n')
            if len(lines) >= 4:
                # ImageMagick返回的值通常是0-1范围或0-65535范围，需要归一化
                alpha_mean = float(lines[0])
                alpha_min = float(lines[1])
                alpha_max = float(lines[2])
                alpha_std = float(lines[3])
                
                # 如果值大于1，说明是16位格式，需要归一化到0-1
                if alpha_max > 1.0:
                    alpha_mean = alpha_mean / 65535.0
                    alpha_min = alpha_min / 65535.0
                    alpha_max = alpha_max / 65535.0
                    alpha_std = alpha_std / 65535.0
                
                print(f"Alpha通道统计 - 平均值: {alpha_mean:.6f}, 最小值: {alpha_min:.6f}, 最大值: {alpha_max:.6f}, 标准差: {alpha_std:.6f}")
                
                # 多重检测条件：
                # 1. 最小值必须非常接近1.0（>0.999）- 排除纯白
                # 2. 最大值必须等于1.0（>0.9999）- 排除纯白
                # 3. 标准差必须极小（<0.001）- 排除纯白
                # 4. 平均值必须非常接近1.0（>0.999）- 排除纯白
                # 5. 排除全黑Alpha通道（最大值<0.001且平均值<0.001）
                condition1 = alpha_min > 0.999
                condition2 = alpha_max > 0.9999
                condition3 = alpha_std < 0.001
                condition4 = alpha_mean > 0.999
                
                # 检查是否为全黑Alpha通道
                is_black_alpha = (alpha_max < 0.001 and alpha_mean < 0.001)
                if is_black_alpha:
                    print(f"检测到全黑Alpha通道，跳过发光处理")
                    return False  # 跳过处理
                
                # 额外检查：直方图方法
                hist_check = False
                if result_hist.returncode == 0:
                    hist_result = result_hist.stdout.strip()
                    hist_check = (hist_result == '1')
                    print(f"Alpha通道直方图检查: {hist_result} (1=纯白, 0=有变化)")
                
                # 额外检查：唯一颜色数量
                unique_check = True
                if result_unique.returncode == 0:
                    unique_colors = result_unique.stdout.strip().split('\n')
                    unique_count = len([c for c in unique_colors if c.strip()])
                    print(f"Alpha通道唯一颜色数量: {unique_count}")
                    # 如果唯一颜色超过3个，很可能不是纯白
                    if unique_count > 3:
                        unique_check = False
                
                # 检查标准差是否很小（可能是S发光而不是E发光）
                is_small_variation = alpha_std < 0.01  # 标准差小于0.01认为是S发光
                
                # 综合判断：所有条件都满足才认为是纯白Alpha
                is_pure_white_alpha = (condition1 and condition2 and condition3 and condition4 and hist_check and unique_check)
                
                print(f"Alpha检测结果 - 条件1(min>0.999): {condition1}, 条件2(max>0.9999): {condition2}, 条件3(std<0.001): {condition3}, 条件4(mean>0.999): {condition4}, 直方图检查: {hist_check}, 唯一色检查: {unique_check}")
                
                if is_small_variation and not is_black_alpha:
                    print(f"检测到标准差很小的Alpha通道(std={alpha_std:.6f})，建议作为S发光处理")
                    # 如果标准差很小且最小值不够高，跳过E发光处理
                    if not condition1:  # 最小值不够高，说明有透明区域
                        print(f"Alpha通道最小值过低({alpha_min:.6f})，跳过E发光处理，建议使用S发光")
                        return False  # 跳过E发光处理
                
                print(f"最终判断: {'跳过E发光处理' if is_pure_white_alpha else '进行E发光处理'}")
                
                # 返回是否应该进行E发光处理（与纯白Alpha判断相反）
                return not is_pure_white_alpha
            else:
                print(f"ImageMagick输出格式异常，默认进行处理")
                return True
                
        except Exception as e:
            print(f"Alpha通道检测异常: {str(e)}，默认进行处理")
            return True
            
    def generate_e_texture(self, png_file: str, e_vtf_file: str):
        """生成E贴图（将Alpha通道正片叠底到RGB通道）"""
        # 在VTF文件所在目录生成临时TGA文件
        vtf_dir = Path(e_vtf_file).parent
        tga_file = str(vtf_dir / f"temp_{Path(png_file).stem}.tga")
        
        if self.debug_logger:
            self.debug_logger.log_info(f"开始生成E贴图 - PNG源文件: {png_file}")
            self.debug_logger.log_info(f"临时TGA文件路径: {tga_file}")
            self.debug_logger.log_info(f"目标VTF文件: {e_vtf_file}")
        
        try:
            # 使用ImageMagick生成E贴图：将Alpha通道作为蒙版应用到RGB通道
            cmd_process = [
                'magick', png_file,
                '(', '+clone', '-alpha', 'extract', ')',
                '-channel', 'RGB', '-compose', 'multiply', '-composite',
                '+channel', png_file, '-compose', 'copy_opacity', '-composite',
                tga_file
            ]
            
            if self.debug_logger:
                self.debug_logger.log_debug(f"ImageMagick命令: {' '.join(cmd_process)}")
            
            result = subprocess.run(cmd_process, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0:
                if self.debug_logger:
                    self.debug_logger.log_tga_operation("ImageMagick生成TGA", tga_file, False, f"错误: {result.stderr}")
                raise Exception(f"生成E贴图失败: {result.stderr}")
            
            if self.debug_logger:
                self.debug_logger.log_tga_operation("ImageMagick生成TGA", tga_file, True, "成功生成E贴图TGA文件")
            
            print(f"成功生成E贴图TGA: {tga_file}")
            
            # 检查TGA文件是否真的存在
            if not Path(tga_file).exists():
                if self.debug_logger:
                    self.debug_logger.log_error(f"TGA文件生成后不存在: {tga_file}")
                raise Exception(f"TGA文件生成失败，文件不存在: {tga_file}")
            
            # TGA转VTF
            vtfcmd_path = self.get_vtfcmd_path()
            if not vtfcmd_path:
                if self.debug_logger:
                    self.debug_logger.log_error("未找到VTFCmd工具")
                raise Exception("未找到VTFCmd工具")
                
            e_format = self.options.get('e_format', 'DXT5')
            vtf_args = self.get_vtf_args(e_format)
            
            cmd_vtf = [vtfcmd_path, "-file", tga_file, "-output", str(Path(e_vtf_file).parent)] + vtf_args
            
            if self.debug_logger:
                self.debug_logger.log_debug(f"VTFCmd命令: {' '.join(cmd_vtf)}")
            
            result = subprocess.run(cmd_vtf, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode != 0:
                if self.debug_logger:
                    self.debug_logger.log_error(f"TGA转VTF失败: {result.stderr}")
                raise Exception(f"_E贴图转VTF失败: {result.stderr}")
            
            # VTFCmd会根据TGA文件名生成VTF文件，需要重命名为正确的E贴图名称
            temp_vtf_file = Path(e_vtf_file).parent / f"temp_{Path(png_file).stem}.vtf"
            if temp_vtf_file.exists():
                # 重命名为正确的E贴图文件名
                temp_vtf_file.rename(e_vtf_file)
                if self.debug_logger:
                    self.debug_logger.log_info(f"重命名VTF文件: {temp_vtf_file.name} -> {Path(e_vtf_file).name}")
                print(f"重命名VTF文件: {temp_vtf_file.name} -> {Path(e_vtf_file).name}")
                
            if self.debug_logger:
                self.debug_logger.log_info(f"成功转换E贴图为VTF格式: {e_format}")
                
            print(f"成功转换E贴图为VTF格式: {e_format}")
                
        except Exception as e:
            if self.debug_logger:
                self.debug_logger.log_error(f"生成E贴图失败: {str(e)}")
            print(f"生成E贴图失败: {str(e)}")
            raise e
        finally:
            # 无论成功还是失败，都删除VTF文件所在目录中的临时TGA文件
            if Path(tga_file).exists():
                try:
                    Path(tga_file).unlink()
                    if self.debug_logger:
                        self.debug_logger.log_tga_operation("删除VTF目录中的临时TGA文件", tga_file, True, "成功删除临时文件")
                    print(f"已删除VTF目录中的临时TGA文件: {tga_file}")
                except Exception as delete_error:
                    if self.debug_logger:
                        self.debug_logger.log_tga_operation("删除VTF目录中的临时TGA文件", tga_file, False, f"删除失败: {str(delete_error)}")
                    print(f"删除VTF目录中的临时TGA文件失败: {delete_error}")
            else:
                if self.debug_logger:
                    self.debug_logger.log_warning(f"VTF目录中的临时TGA文件不存在，无法删除: {tga_file}")
            
    def generate_vmt_file(self, vtf_path: Path):
        """生成发光VMT文件（支持patch格式和标准格式）"""
        try:
            base_name = vtf_path.stem
            original_vmt_file = vtf_path.with_suffix('.vmt')
            
            # 创建EmissiveGlow文件夹
            emissive_dir = vtf_path.parent / "EmissiveGlow"
            emissive_dir.mkdir(exist_ok=True)
            output_vmt_file = emissive_dir / f"{base_name}.vmt"
            
            # 查找材质路径
            materials_path = self.find_materials_path_for_nightglow(vtf_path.parent)
            if not materials_path:
                materials_path = "materials/unknown"
            
            # 移除materials/前缀
            if materials_path.startswith('materials/'):
                materials_path = materials_path[10:]
            
            if original_vmt_file.exists():
                # 读取现有VMT内容
                with open(original_vmt_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                
                # 检查是否已包含发光相关配置
                import re
                if (re.search(r'"\$EmissiveBlend', existing_content, re.IGNORECASE) or 
                    re.search(r'"\$selfillum"\s*"[01]"', existing_content, re.IGNORECASE)):
                    print(f"VMT文件已包含发光配置，跳过: {base_name}")
                    return
                
                # 解析patch格式的VMT文件
                if 'patch' in existing_content.lower():
                    self.generate_patch_vmt_with_emissive(existing_content, output_vmt_file, materials_path, base_name)
                else:
                    # 处理普通格式的VMT文件
                    self.generate_standard_vmt_with_emissive(existing_content, output_vmt_file, materials_path, base_name)
            else:
                # 创建新的patch格式VMT文件
                self.create_new_patch_vmt(output_vmt_file, materials_path, base_name)
                
        except Exception as e:
            print(f"生成VMT文件失败: {str(e)}")
            
    def generate_patch_vmt_with_emissive(self, existing_content: str, output_file: Path, materials_path: str, base_name: str):
        """为patch格式的VMT添加发光配置"""
        if self.debug_logger:
            self.debug_logger.log_info(f"开始生成patch格式VMT文件: {output_file}")
            self.debug_logger.log_debug(f"材质路径: {materials_path}, 基础名称: {base_name}")
        
        lines = existing_content.split('\n')
        new_lines = []
        
        insert_block_found = False
        replace_block_found = False
        
        i = 0
        while i < len(lines):
            line = lines[i].strip().lower()
            
            # 查找insert块
            if 'insert' in line:
                insert_block_found = True
                new_lines.append(lines[i])  # 添加insert行
                
                # 添加发光配置到insert块中 - 比$basetexture少一格对齐，使用单个制表符
                emissive_configs = [
                    '\t"$EmissiveBlendEnabled"\t\t\t\t\t\t"1"',
                    '\t"$EmissiveBlendStrength"\t\t\t\t\t\t"0.05"',
                    '\t"$EmissiveBlendTexture"\t\t\t\t\t\t"vgui/white"',
                    f'\t"$EmissiveBlendBaseTexture"\t\t\t\t"{materials_path}/{base_name}_E"',
                    '\t"$EmissiveBlendFlowTexture"\t\t\t\t\t"vgui/white"',
                    '\t"$EmissiveBlendTint"\t\t\t\t\t\t\t"[ 1 1 1 ]"',
                    '\t"$EmissiveBlendScrollVector"\t\t\t\t\t"[ 0 0 ]"'
                ]
                
                if self.debug_logger:
                    self.debug_logger.log_vmt_alignment(str(output_file), "insert块发光参数", "统一使用制表符对齐")
                    for config in emissive_configs:
                        param_name = config.split('"')[1]
                        tab_count = config.count('\t')
                        self.debug_logger.log_vmt_alignment(str(output_file), param_name, f"制表符数量: {tab_count}")
                
                # 找到insert块的开始大括号
                j = i + 1
                brace_count = 0
                insert_content = []
                
                # 先找到开始大括号
                while j < len(lines) and brace_count == 0:
                    if '{' in lines[j]:
                        brace_count = 1
                        new_lines.append(lines[j])  # 添加开始大括号行
                        j += 1
                        break
                    else:
                        new_lines.append(lines[j])  # 添加insert和大括号之间的行
                        j += 1
                
                # 处理insert块内容
                while j < len(lines) and brace_count > 0:
                    if '{' in lines[j]:
                        brace_count += 1
                    if '}' in lines[j]:
                        brace_count -= 1
                    
                    if brace_count > 0:  # 还在insert块内
                        insert_content.append(lines[j])
                    else:  # 找到结束大括号
                        # 添加现有内容（如果有的话）
                        for content_line in insert_content:
                            if content_line.strip():  # 只添加非空行
                                new_lines.append(content_line)
                        # 添加发光配置
                        for config in emissive_configs:
                            new_lines.append(config)
                        # 添加结束大括号
                        new_lines.append(lines[j])
                    j += 1
                
                i = j
                continue
            
            # 查找replace块并添加$selfillum
            elif 'replace' in line:
                replace_block_found = True
                new_lines.append(lines[i])  # 添加replace行
                
                # 找到replace块的开始大括号
                j = i + 1
                brace_count = 0
                replace_content = []
                
                # 先找到开始大括号
                while j < len(lines) and brace_count == 0:
                    if '{' in lines[j]:
                        brace_count = 1
                        new_lines.append(lines[j])  # 添加开始大括号行
                        j += 1
                        break
                    else:
                        new_lines.append(lines[j])  # 添加replace和大括号之间的行
                        j += 1
                
                # 处理replace块内容
                while j < len(lines) and brace_count > 0:
                    if '{' in lines[j]:
                        brace_count += 1
                    if '}' in lines[j]:
                        brace_count -= 1
                    
                    if brace_count > 0:  # 还在replace块内
                        replace_content.append(lines[j])
                    else:  # 找到结束大括号
                        # 添加现有内容
                        for content_line in replace_content:
                            new_lines.append(content_line)
                        # 添加$selfillum配置 - 比$basetexture少一格对齐，使用单个制表符
                        selfillum_line = '\t"$selfillum"\t\t\t\t\t\t"0"'
                        new_lines.append(selfillum_line)
                        
                        if self.debug_logger:
                            tab_count = selfillum_line.count('\t')
                            self.debug_logger.log_vmt_alignment(str(output_file), "$selfillum", f"replace块中制表符数量: {tab_count}")
                        
                        # 添加结束大括号
                        new_lines.append(lines[j])
                    j += 1
                
                i = j
                continue
            
            else:
                new_lines.append(lines[i])
                i += 1
        
        # 写入新的VMT文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        print(f"已生成patch格式VMT文件: {output_file}")
    
    def generate_standard_vmt_with_emissive(self, existing_content: str, output_file: Path, materials_path: str, base_name: str):
        """为标准格式的VMT添加发光配置"""
        if self.debug_logger:
            self.debug_logger.log_info(f"开始生成标准格式VMT文件: {output_file}")
            self.debug_logger.log_debug(f"材质路径: {materials_path}, 基础名称: {base_name}")
        
        lines = existing_content.split('\n')
        insert_index = -1
        
        # 从后往前找到最后一个有效参数行
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.startswith('}') and not line.startswith('//'):
                insert_index = i + 1
                break
        
        if insert_index > 0:
            # 插入发光配置
            emissive_config = [
                '\t"$selfillum"\t\t\t\t"0"',
                '\t"$EmissiveBlendEnabled"\t\t"1"',
                '\t"$EmissiveBlendStrength"\t\t"0.05"',
                '\t"$EmissiveBlendTexture"\t\t"vgui/white"',
                f'\t"$EmissiveBlendBaseTexture"\t"{materials_path}/{base_name}_E"',
                '\t"$EmissiveBlendFlowTexture"\t"vgui/white"',
                '\t"$EmissiveBlendTint"\t\t\t"[ 1 1 1 ]"',
                '\t"$EmissiveBlendScrollVector"\t"[ 0 0 ]"'
            ]
            
            if self.debug_logger:
                self.debug_logger.log_vmt_alignment(str(output_file), "标准格式发光参数", "使用制表符对齐")
                for config in emissive_config:
                    param_name = config.split('"')[1]
                    tab_count = config.count('\t')
                    self.debug_logger.log_vmt_alignment(str(output_file), param_name, f"制表符数量: {tab_count}")
            
            # 在指定位置插入配置
            for i, config_line in enumerate(emissive_config):
                lines.insert(insert_index + i, config_line)
            
            # 写回文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"已生成标准格式VMT文件: {output_file}")
    
    def create_new_patch_vmt(self, output_file: Path, materials_path: str, base_name: str):
        """创建新的patch格式VMT文件"""
        if self.debug_logger:
            self.debug_logger.log_info(f"开始创建新的patch格式VMT文件: {output_file}")
            self.debug_logger.log_debug(f"材质路径: {materials_path}, 基础名称: {base_name}")
        
        # 构建include路径
        include_path = f"materials/{materials_path}/shader/vmt-base.vmt"
        
        # 发光参数比$basetexture少一格对齐，使用单个制表符
        vmt_content = f'''patch
{{
\tinclude\t\t"{include_path}"
\tinsert
\t{{
\t"$EmissiveBlendEnabled"\t\t\t\t\t\t"1"
\t"$EmissiveBlendStrength"\t\t\t\t\t\t"0.05"
\t"$EmissiveBlendTexture"\t\t\t\t\t\t"vgui/white"
\t"$EmissiveBlendBaseTexture"\t\t\t\t"{materials_path}/{base_name}_E"
\t"$EmissiveBlendFlowTexture"\t\t\t\t\t"vgui/white"
\t"$EmissiveBlendTint"\t\t\t\t\t\t\t"[ 1 1 1 ]"
\t"$EmissiveBlendScrollVector"\t\t\t\t\t"[ 0 0 ]"
\t}}
\treplace
\t{{
\t"$basetexture"\t\t\t\t\t\t"{materials_path}/{base_name}"
\t"$selfillum"\t\t\t\t\t\t"0"
\t}}\n}}'''
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(vmt_content)
        
        if self.debug_logger:
            # 记录关键参数的对齐情况
            basetexture_line = f'\t\t"$basetexture"\t\t\t\t\t\t"{materials_path}/{base_name}"'
            selfillum_line = '\t"$selfillum"\t\t\t\t\t\t"0"'
            
            basetexture_tabs = basetexture_line.count('\t')
            selfillum_tabs = selfillum_line.count('\t')
            
            self.debug_logger.log_vmt_alignment(str(output_file), "$basetexture", f"使用制表符对齐，制表符数量: {basetexture_tabs}")
            self.debug_logger.log_vmt_alignment(str(output_file), "$selfillum", f"使用制表符对齐，制表符数量: {selfillum_tabs}")
            
            # 记录insert块中的发光参数对齐
            insert_params = [
                '"$EmissiveBlendEnabled"\t\t\t\t"1"',
                '"$EmissiveBlendStrength"\t\t\t\t"0.05"',
                '"$EmissiveBlendTexture"\t\t\t\t"vgui/white"',
                f'"$EmissiveBlendBaseTexture"\t\t\t"{materials_path}/{base_name}_E"',
                '"$EmissiveBlendFlowTexture"\t\t\t"vgui/white"',
                '"$EmissiveBlendTint"\t\t\t\t\t"[ 1 1 1 ]"',
                '"$EmissiveBlendScrollVector"\t\t\t"[ 0 0 ]"'
            ]
            
            for param in insert_params:
                param_name = param.split('"')[1]
                tab_count = param.count('\t')
                self.debug_logger.log_vmt_alignment(str(output_file), param_name, f"insert块中制表符数量: {tab_count}")
        
        print(f"已创建新的patch格式VMT文件: {output_file}")
    
    def find_materials_path_for_nightglow(self, work_dir: Path) -> str:
        """为夜光功能查找材质路径"""
        try:
            # 从当前路径向上查找materials文件夹
            current_path = Path(work_dir)
            while current_path.parent != current_path:
                if current_path.name == 'materials':
                    # 找到materials文件夹，返回相对路径
                    relative_path = work_dir.relative_to(current_path)
                    return f"materials/{relative_path}".replace('\\', '/')
                current_path = current_path.parent
            
            # 如果没找到materials文件夹，尝试从路径中推断
            path_parts = work_dir.parts
            if 'materials' in path_parts:
                materials_index = path_parts.index('materials')
                if materials_index + 1 < len(path_parts):
                    relative_parts = path_parts[materials_index + 1:]
                    return f"materials/{'/'.join(relative_parts)}"
            
            return None
            
        except Exception:
             return None
    
    def modify_vmt_base(self, vtf_path: Path):
        """修改vmt-base文件"""
        try:
            # 从VTF文件路径向上查找materials文件夹
            current_path = vtf_path.parent
            materials_dir = None
            
            while current_path.parent != current_path:
                if current_path.name == 'materials':
                    materials_dir = current_path
                    break
                current_path = current_path.parent
            
            if not materials_dir:
                print(f"未找到materials文件夹")
                return
                
            # 查找shader文件夹
            shader_dirs = list(materials_dir.rglob('shader'))
            if not shader_dirs:
                print(f"未找到shader文件夹")
                return
                
            for shader_dir in shader_dirs:
                vmt_base_file = shader_dir / "vmt-base.vmt"
                if vmt_base_file.exists():
                    # 读取并修改vmt-base文件
                    with open(vmt_base_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 查找并替换$selfillum行（包括注释和非注释的情况）
                    import re
                    modified = False
                    new_content = content
                    
                    # 模式1：匹配带注释的$selfillum "0"行
                    pattern1 = r'(\s*"\$selfillum"\s+)"0"(\s+//.*开启自发光.*不做自发光必须关掉.*)'
                    if re.search(pattern1, content):
                        new_content = re.sub(pattern1, r'\1"1"\2', content)
                        modified = True
                        print(f"找到并修改带注释的$selfillum行")
                    
                    # 模式2：匹配普通的$selfillum "0"行
                    elif re.search(r'"\$selfillum"\s+"0"', content):
                        new_content = re.sub(r'("\$selfillum"\s+)"0"', r'\1"1"', content)
                        modified = True
                        print(f"找到并修改普通的$selfillum行")
                    
                    # 模式3：匹配注释掉的$selfillum行
                    elif re.search(r'//\s*"\$selfillum"', content):
                        # 取消注释并设置为"1"
                        pattern3 = r'//\s*"\$selfillum"\s+"[01]"(.*开启自发光.*不做自发光必须关掉.*)'
                        replacement3 = '\t"$selfillum"\t\t\t\t\t"1"\t\t\t\t// 开启自发光。亮度区分取决于颜色贴图的 A 通道，越白则越亮。不做自发光必须关掉。'
                        if re.search(pattern3, content):
                            new_content = re.sub(pattern3, replacement3, content)
                            modified = True
                            print(f"找到并取消注释$selfillum行")
                    
                    if modified:
                        # 写回文件
                        with open(vmt_base_file, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        
                        print(f"已修改vmt-base.vmt文件: {vmt_base_file}")
                        return  # 修改成功后退出
                    else:
                        print(f"在vmt-base.vmt中未找到需要修改的$selfillum行: {vmt_base_file}")
                        
        except Exception as e:
            print(f"修改vmt-base失败: {str(e)}")
            
    def get_vtfcmd_path(self) -> str:
        """获取VTFCmd路径"""
        # 检查常见位置
        possible_paths = [
            "VTFCmd.exe",
            "./VTFCmd.exe",
            "./tools/VTFCmd.exe",
            "C:/Program Files/VTFCmd/VTFCmd.exe",
            "C:/Program Files (x86)/VTFCmd/VTFCmd.exe"
        ]
        
        for path in possible_paths:
            if Path(path).exists() or shutil.which(path):
                return path
                
        return ""
        
    def get_vtf_args(self, format_type: str) -> List[str]:
        """获取VTF命令参数"""
        format_map = {
            "RGBA8888": ["-format", "RGBA8888"],
            "DXT5": ["-format", "DXT5"],
            "DXT3": ["-format", "DXT3"],
            "DXT1": ["-format", "DXT1"]
        }
        
        return format_map.get(format_type, ["-format", "DXT5"])
        
    def is_blacklisted(self, filename: str, preset_blacklist: List[str], custom_blacklist: str) -> bool:
        """检查文件是否在黑名单中"""
        # 检查预设黑名单
        for word in preset_blacklist:
            if word.lower() in filename.lower():
                return True
                
        # 检查自定义黑名单
        if custom_blacklist:
            custom_words = [word.strip() for word in custom_blacklist.split(',') if word.strip()]
            for word in custom_words:
                if word.lower() in filename.lower():
                    return True
                    
        return False
        
    def cancel(self):
        self.is_cancelled = True


class DragDropListWidget(QListWidget):
    """支持拖拽的文件列表控件"""
    
    files_dropped = Signal(list)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                files.append(file_path)
            elif os.path.isdir(file_path):
                # 如果是文件夹，递归查找图像文件
                for ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']:
                    files.extend(Path(file_path).rglob(f'*{ext}'))
                    
        if files:
            self.files_dropped.emit([str(f) for f in files])


class ScrollableTab(QWidget):
    """可滚动的选项卡基类"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 内容容器
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(10)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)
        
        # 添加具体内容
        self.setup_content()
        
        # 添加弹性空间
        self.content_layout.addStretch()
        
    def setup_content(self):
        """子类重写此方法来添加具体内容"""
        pass
        
    def add_widget(self, widget):
        """添加控件到内容区域"""
        self.content_layout.insertWidget(self.content_layout.count() - 1, widget)


class NightglowTab(ScrollableTab):
    """夜光效果处理选项卡"""
    
    def __init__(self, config_manager: ConfigManager, debug_logger=None):
        self.config = config_manager
        self.debug_logger = debug_logger
        self.nightglow_files = []  # 存储选中的VTF文件列表
        super().__init__()
        
    def setup_content(self):
        # 说明文本
        desc_group = QGroupBox("功能说明")
        desc_layout = QVBoxLayout(desc_group)
        
        desc_text = QTextEdit()
        desc_text.setMaximumHeight(80)
        desc_text.setReadOnly(True)
        desc_text.setPlainText(
            "功能说明：将VTF文件转换为TGA，调整Alpha通道为夜光效果，然后转换回VTF格式。\n"
            "适用于需要夜光效果的材质，系统会自动处理Alpha通道。"
        )
        desc_layout.addWidget(desc_text)
        self.add_widget(desc_group)
        
        # 文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)
        
        # VTF文件选择
        vtf_layout = QHBoxLayout()
        vtf_layout.addWidget(QLabel("VTF文件:"))
        self.vtf_path_edit = QLineEdit()
        self.vtf_path_edit.setPlaceholderText("选择VTF文件或文件夹")
        vtf_layout.addWidget(self.vtf_path_edit)
        
        self.browse_file_btn = QPushButton("选择文件")
        self.browse_file_btn.clicked.connect(self.browse_vtf_file)
        vtf_layout.addWidget(self.browse_file_btn)
        
        self.browse_folder_btn = QPushButton("选择文件夹")
        self.browse_folder_btn.clicked.connect(self.browse_vtf_folder)
        vtf_layout.addWidget(self.browse_folder_btn)
        
        file_layout.addLayout(vtf_layout)
        
        # 已选择文件列表
        file_layout.addWidget(QLabel("已选择的文件:"))
        self.file_list = DragDropListWidget()
        self.file_list.setMaximumHeight(150)
        self.file_list.files_dropped.connect(self.add_files)
        file_layout.addWidget(self.file_list)
        
        # 文件管理按钮
        btn_layout = QHBoxLayout()
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.clicked.connect(self.remove_selected_files)
        btn_layout.addWidget(self.remove_btn)
        
        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.clicked.connect(self.clear_file_list)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)
        
        self.add_widget(file_group)
        
        # 压缩格式选择
        format_group = QGroupBox("压缩格式")
        format_layout = QVBoxLayout(format_group)
        
        self.format_group = QButtonGroup()
        formats = [("RGBA8888", "最高质量，文件较大"), 
                  ("DXT5", "高质量，支持渐变透明"), 
                  ("DXT3", "中等质量，支持黑白透明"), 
                  ("DXT1", "最小文件，无透明或黑白透明")]
        
        for i, (fmt, desc) in enumerate(formats):
            radio = QRadioButton(f"{fmt} - {desc}")
            if i == 1:  # 默认选择DXT5
                radio.setChecked(True)
            self.format_group.addButton(radio, i)
            format_layout.addWidget(radio)
            
        self.add_widget(format_group)
        
        # 夜光增强功能选项
        enhance_group = QGroupBox("夜光增强功能")
        enhance_layout = QVBoxLayout(enhance_group)
        
        # vmtE发光生成开关
        vmte_layout = QHBoxLayout()
        self.vmte_glow_checkbox = QCheckBox("vmtE发光生成")
        self.vmte_glow_checkbox.setToolTip("检测Alpha通道，生成带夜光效果的VMT和_E贴图")
        vmte_layout.addWidget(self.vmte_glow_checkbox)
        
        vmte_desc = QLabel("检测Alpha通道，生成带夜光效果的VMT和_E贴图")
        vmte_desc.setStyleSheet("color: #888888;")
        vmte_layout.addWidget(vmte_desc)
        vmte_layout.addStretch()
        enhance_layout.addLayout(vmte_layout)
        
        # E贴图压缩格式选择
        e_format_layout = QHBoxLayout()
        e_format_layout.addWidget(QLabel("E贴图格式:"))
        
        self.e_format_group = QButtonGroup()
        e_formats = [("RGBA8888", "最高质量"), ("DXT5", "高质量"), ("DXT3", "中等质量"), ("DXT1", "最小文件")]
        
        for i, (fmt, desc) in enumerate(e_formats):
            radio = QRadioButton(fmt)
            if i == 1:  # 默认选择DXT5
                radio.setChecked(True)
            radio.setToolTip(desc)
            self.e_format_group.addButton(radio, i)
            e_format_layout.addWidget(radio)
            
        e_format_layout.addStretch()
        enhance_layout.addLayout(e_format_layout)
        
        # 全局屏蔽词系统
        blacklist_subgroup = QGroupBox("全局屏蔽词系统")
        blacklist_layout = QVBoxLayout(blacklist_subgroup)
        
        # 常用屏蔽词
        preset_header_layout = QHBoxLayout()
        preset_header_layout.addWidget(QLabel("常用屏蔽词:"))
        preset_header_layout.addStretch()
        
        # 自定义预设按钮
        self.manage_presets_btn = QPushButton("管理预设")
        self.manage_presets_btn.setMaximumWidth(80)
        self.manage_presets_btn.clicked.connect(self.manage_nightglow_presets)
        preset_header_layout.addWidget(self.manage_presets_btn)
        
        blacklist_layout.addLayout(preset_header_layout)
        
        self.preset_checkboxes = {}
        # 移植TK版本的完整预设屏蔽词列表
        preset_words = ['_N', '_Normal', '_emi', '_n', 'phongexp', 'envmap', 'bump', 'eye', 'ambient', 'toon_light', 'warp']
        
        checkbox_layout = QGridLayout()
        for i, word in enumerate(preset_words):
            checkbox = QCheckBox(word)
            if word in ['_N', '_Normal', '_emi']:  # 默认选中前三个（原有的默认屏蔽词）
                checkbox.setChecked(True)
            self.preset_checkboxes[word] = checkbox
            checkbox_layout.addWidget(checkbox, i // 4, i % 4)
            
        blacklist_layout.addLayout(checkbox_layout)
        
        # 自定义屏蔽词
        blacklist_layout.addWidget(QLabel("自定义屏蔽词:"))
        self.custom_blacklist_edit = QLineEdit()
        self.custom_blacklist_edit.setPlaceholderText("用逗号分隔多个屏蔽词")
        blacklist_layout.addWidget(self.custom_blacklist_edit)
        
        enhance_layout.addWidget(blacklist_subgroup)
        
        # E发光专用屏蔽词设置
        e_blacklist_subgroup = QGroupBox("E发光专用屏蔽词设置")
        e_blacklist_sublayout = QVBoxLayout(e_blacklist_subgroup)
        
        e_blacklist_sublayout.addWidget(QLabel("自定义屏蔽词:"))
        self.e_blacklist_edit = QLineEdit()
        self.e_blacklist_edit.setPlaceholderText("用逗号分隔多个屏蔽词")
        e_blacklist_sublayout.addWidget(self.e_blacklist_edit)
        
        e_blacklist_desc = QLabel("用逗号分隔多个屏蔽词")
        e_blacklist_desc.setStyleSheet("color: #888888;")
        e_blacklist_sublayout.addWidget(e_blacklist_desc)
        
        enhance_layout.addWidget(e_blacklist_subgroup)
        
        # 修改vmt-base开关
        vmtbase_layout = QHBoxLayout()
        self.modify_vmtbase_checkbox = QCheckBox("修改vmt-base")
        self.modify_vmtbase_checkbox.setToolTip("自动修改父级文件夹shader中的vmt-base.vmt文件")
        vmtbase_layout.addWidget(self.modify_vmtbase_checkbox)
        
        vmtbase_desc = QLabel("自动修改父级文件夹shader中的vmt-base.vmt文件")
        vmtbase_desc.setStyleSheet("color: #888888;")
        vmtbase_layout.addWidget(vmtbase_desc)
        vmtbase_layout.addStretch()
        enhance_layout.addLayout(vmtbase_layout)
        
        self.add_widget(enhance_group)
        
        # 处理按钮
        self.process_btn = QPushButton("开始处理夜光效果")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.setToolTip("开始处理选中的VTF文件，生成夜光效果和相关材质")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        self.process_btn.clicked.connect(self.start_processing)
        self.add_widget(self.process_btn)
        
    def browse_vtf_file(self):
        """浏览VTF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择VTF文件", 
            self.config.get("last_vtf_dir", ""),
            "VTF文件 (*.vtf)"
        )
        if file_path:
            self.vtf_path_edit.setText(file_path)
            self.add_files([file_path])
            self.config.set("last_vtf_dir", str(Path(file_path).parent))
            
    def browse_vtf_folder(self):
        """浏览VTF文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含VTF文件的文件夹",
            self.config.get("last_vtf_dir", "")
        )
        if folder_path:
            self.vtf_path_edit.setText(folder_path)
            # 查找文件夹中的所有VTF文件
            vtf_files = list(Path(folder_path).rglob("*.vtf"))
            self.add_files([str(f) for f in vtf_files])
            self.config.set("last_vtf_dir", folder_path)
            
    def add_files(self, files: List[str]):
        """添加文件到列表"""
        for file_path in files:
            if file_path.lower().endswith('.vtf'):
                # 检查是否已存在
                existing_items = [self.file_list.item(i).text() 
                                for i in range(self.file_list.count())]
                if file_path not in existing_items:
                    self.file_list.addItem(file_path)
                    
    def remove_selected_files(self):
        """删除选中的文件"""
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
            
    def clear_file_list(self):
        """清空文件列表"""
        self.file_list.clear()
        
    def start_processing(self):
        """开始处理"""
        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        if not files:
            QMessageBox.warning(self, "警告", "请先选择要处理的文件")
            return
            
        # 检查所有文件是否存在
        invalid_files = [f for f in files if not os.path.exists(f)]
        if invalid_files:
            QMessageBox.critical(self, "错误", f"以下文件不存在：\n{chr(10).join(invalid_files)}")
            return
            
        # 获取选项
        options = {
            'format': self.get_selected_format(),
            'vmte_glow': self.vmte_glow_checkbox.isChecked(),
            'e_format': self.get_selected_e_format(),
            'preset_blacklist': [word for word, cb in self.preset_checkboxes.items() if cb.isChecked()],
            'custom_blacklist': self.custom_blacklist_edit.text(),
            'e_blacklist': self.e_blacklist_edit.text(),
            'modify_vmtbase': self.modify_vmtbase_checkbox.isChecked()
        }
        
        # 启动处理线程
        self.process_thread = NightglowProcessingThread(files, options, self.debug_logger)
        self.process_thread.status_updated.connect(self.update_status)
        self.process_thread.progress_updated.connect(self.update_progress)
        self.process_thread.processing_finished.connect(self.on_processing_finished)
        
        # 启动进度条
        main_window = self.window()
        if hasattr(main_window, 'start_progress'):
            main_window.start_progress()
        
        self.process_thread.start()
        
        # 禁用处理按钮
        self.process_btn.setEnabled(False)
        self.process_btn.setText("处理中...")
        
    def get_selected_format(self) -> str:
        """获取选中的格式"""
        formats = ["RGBA8888", "DXT5", "DXT3", "DXT1"]
        checked_id = self.format_group.checkedId()
        return formats[checked_id] if checked_id >= 0 else "DXT5"
        
    def get_selected_e_format(self) -> str:
        """获取选中的E贴图格式"""
        e_formats = ["RGBA8888", "DXT5", "DXT3", "DXT1"]
        checked_id = self.e_format_group.checkedId()
        return e_formats[checked_id] if checked_id >= 0 else "DXT5"
        
    def update_status(self, message: str):
        """更新状态信息"""
        # 连接到主窗口的状态栏
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(message)
        
    def update_progress(self, value: int):
        """更新进度"""
        # 连接到主窗口的进度条
        main_window = self.window()
        if hasattr(main_window, 'progress_bar'):
            main_window.progress_bar.setValue(value)
            if value > 0:
                main_window.progress_bar.setVisible(True)
            if value >= 100:
                main_window.progress_bar.setVisible(False)
        
    def on_processing_finished(self, success: bool, message: str):
        """处理完成回调"""
        # 停止进度条
        main_window = self.window()
        if hasattr(main_window, 'stop_progress'):
            main_window.stop_progress()
        
        # 恢复处理按钮
        self.process_btn.setEnabled(True)
        self.process_btn.setText("开始处理夜光效果")
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", message)
    
    def manage_nightglow_presets(self):
        """管理夜光处理预设屏蔽词"""
        # 获取当前预设词列表
        current_presets = ["_N", "_Normal", "_emi", "_n", "phongexp", "envmap", "bump", "eye", "ambient", "toon_light", "warp"]
        
        dialog = PresetManagerDialog(self, current_presets, "夜光处理预设屏蔽词")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 更新预设屏蔽词
            self.update_nightglow_presets(dialog.get_presets())
    
    def update_nightglow_presets(self, presets):
        """更新夜光处理预设屏蔽词"""
        # 清除现有的复选框
        for checkbox in self.preset_checkboxes.values():
            checkbox.setParent(None)
        self.preset_checkboxes.clear()
        
        # 重新创建复选框布局
        # 找到原来的布局并清除
        blacklist_subgroup = None
        for child in self.findChildren(QGroupBox):
            if child.title() == "全局屏蔽词系统":
                blacklist_subgroup = child
                break
        
        if blacklist_subgroup:
            layout = blacklist_subgroup.layout()
            # 找到复选框布局（第二个布局项）
            if layout.count() > 1:
                old_checkbox_layout = layout.itemAt(1).layout()
                if old_checkbox_layout:
                    # 清除旧布局
                    while old_checkbox_layout.count():
                        child = old_checkbox_layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                    
                    # 添加新的复选框
                    for i, word in enumerate(presets):
                        checkbox = QCheckBox(word)
                        if word in ['_N', '_Normal', '_emi']:  # 保持默认选中
                            checkbox.setChecked(True)
                        self.preset_checkboxes[word] = checkbox
                        old_checkbox_layout.addWidget(checkbox, i // 4, i % 4)





class MaterialConfigTab(ScrollableTab):
    """材质配置生成选项卡"""
    
    def __init__(self, config_manager: ConfigManager, status_bar: QStatusBar):
        self.config = config_manager
        self.status_bar = status_bar
        super().__init__()
        # 在UI设置完成后恢复设置
        self.restore_experimental_settings()
        
    def setup_content(self):
        # 说明文本
        desc_label = QLabel("功能说明：将图像文件转换为VTF格式，并自动生成对应的VMT材质文件。\n支持普通材质和眼部材质的自动识别和配置。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #cccccc; padding: 10px; background-color: #353535; border-radius: 5px;")
        self.add_widget(desc_label)
        
        # 文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)
        
        # 图像文件选择
        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("图像文件:"))
        self.material_img_edit = QLineEdit()
        self.select_material_file_btn = QPushButton("选择文件")
        self.select_material_folder_btn = QPushButton("选择文件夹")
        
        img_layout.addWidget(self.material_img_edit)
        img_layout.addWidget(self.select_material_file_btn)
        img_layout.addWidget(self.select_material_folder_btn)
        file_layout.addLayout(img_layout)
        
        # 已选择文件列表
        file_layout.addWidget(QLabel("已选择的文件:"))
        self.material_files_listbox = QListWidget()
        self.material_files_listbox.setMaximumHeight(120)
        file_layout.addWidget(self.material_files_listbox)
        
        # 文件管理按钮
        file_btn_layout = QHBoxLayout()
        self.remove_selected_btn = QPushButton("删除选中")
        self.clear_list_btn = QPushButton("清空列表")
        file_btn_layout.addWidget(self.remove_selected_btn)
        file_btn_layout.addWidget(self.clear_list_btn)
        file_btn_layout.addStretch()
        file_layout.addLayout(file_btn_layout)
        
        # 输出目录
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit()
        self.browse_output_btn = QPushButton("浏览")
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.browse_output_btn)
        file_layout.addLayout(output_layout)
        
        # QCI文件选择
        qci_layout = QHBoxLayout()
        qci_layout.addWidget(QLabel("QCI文件（可选）:"))
        self.qci_file_edit = QLineEdit()
        self.browse_qci_btn = QPushButton("浏览")
        qci_layout.addWidget(self.qci_file_edit)
        qci_layout.addWidget(self.browse_qci_btn)
        file_layout.addLayout(qci_layout)
        
        # 材质路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("材质路径:"))
        self.cdmaterials_edit = QLineEdit()
        self.read_qci_btn = QPushButton("从QCI读取")
        path_layout.addWidget(self.cdmaterials_edit)
        path_layout.addWidget(self.read_qci_btn)
        file_layout.addLayout(path_layout)
        
        self.add_widget(file_group)
        
        # 配置选项
        config_group = QGroupBox("配置选项")
        config_layout = QVBoxLayout(config_group)
        
        # Lightwarp文件
        lightwarp_layout = QHBoxLayout()
        lightwarp_layout.addWidget(QLabel("Lightwarp文件:"))
        self.lightwarp_edit = QLineEdit()
        self.browse_lightwarp_btn = QPushButton("浏览")
        lightwarp_layout.addWidget(self.lightwarp_edit)
        lightwarp_layout.addWidget(self.browse_lightwarp_btn)
        config_layout.addLayout(lightwarp_layout)
        
        # 材质生成屏蔽词系统
        blacklist_group = QGroupBox("材质生成屏蔽词系统")
        blacklist_layout = QVBoxLayout(blacklist_group)
        
        # 完全跳过生成的屏蔽词
        skip_group = QGroupBox("完全跳过生成")
        skip_layout = QVBoxLayout(skip_group)
        
        # 预设屏蔽词（完全跳过）
        skip_preset_header_layout = QHBoxLayout()
        skip_preset_header_layout.addWidget(QLabel("常用屏蔽词（完全跳过）:"))
        skip_preset_header_layout.addStretch()
        
        # 自定义预设按钮
        self.manage_skip_presets_btn = QPushButton("管理预设")
        self.manage_skip_presets_btn.setMaximumWidth(80)
        self.manage_skip_presets_btn.clicked.connect(self.manage_skip_presets)
        skip_preset_header_layout.addWidget(self.manage_skip_presets_btn)
        
        skip_layout.addLayout(skip_preset_header_layout)
        
        self.skip_preset_layout = QGridLayout()
        
        self.skip_preset_blacklist_vars = {}
        # 从配置中获取预设词列表，如果没有则使用默认值
        default_skip_words = ['_N', '_Normal', '_emi', '_n', 'phongexp', 'envmap', 'bump']
        skip_preset_words = self.config.get('skip_presets', default_skip_words)
        
        for i, word in enumerate(skip_preset_words):
            checkbox = QCheckBox(word)
            # 从配置中恢复选中状态，如果没有则使用默认值
            default_checked = word in ['_N', '_Normal', '_emi']
            is_checked = self.config.get(f'skip_preset_{word}_checked', default_checked)
            # 确保is_checked是布尔值
            if isinstance(is_checked, str):
                is_checked = is_checked.lower() in ('true', '1', 'yes')
            checkbox.setChecked(bool(is_checked))
            # 连接信号以保存状态变化
            checkbox.stateChanged.connect(lambda state, w=word: self.save_skip_preset_state(w, state))
            self.skip_preset_blacklist_vars[word] = checkbox
            self.skip_preset_layout.addWidget(checkbox, i // 4, i % 4)
        
        skip_layout.addLayout(self.skip_preset_layout)
        
        # 自定义屏蔽词（完全跳过）
        skip_layout.addWidget(QLabel("自定义屏蔽词（完全跳过）:"))
        self.skip_custom_blacklist_edit = QLineEdit()
        self.skip_custom_blacklist_edit.setPlaceholderText("用逗号分隔多个屏蔽词，匹配的文件将完全跳过生成")
        skip_layout.addWidget(self.skip_custom_blacklist_edit)
        
        blacklist_layout.addWidget(skip_group)
        
        # 仅屏蔽VMT生成的屏蔽词
        vmt_only_group = QGroupBox("仅屏蔽VMT生成")
        vmt_only_layout = QVBoxLayout(vmt_only_group)
        
        # 预设屏蔽词（仅屏蔽VMT）
        vmt_preset_header_layout = QHBoxLayout()
        vmt_preset_header_layout.addWidget(QLabel("常用屏蔽词（仅屏蔽VMT）:"))
        vmt_preset_header_layout.addStretch()
        
        # 自定义预设按钮
        self.manage_vmt_presets_btn = QPushButton("管理预设")
        self.manage_vmt_presets_btn.setMaximumWidth(80)
        self.manage_vmt_presets_btn.clicked.connect(self.manage_vmt_presets)
        vmt_preset_header_layout.addWidget(self.manage_vmt_presets_btn)
        
        vmt_only_layout.addLayout(vmt_preset_header_layout)
        
        self.vmt_preset_layout = QGridLayout()
        
        self.vmt_preset_blacklist_vars = {}
        # 从配置中获取预设词列表，如果没有则使用默认值
        default_vmt_words = ['test', 'temp', 'backup', 'old']
        vmt_preset_words = self.config.get('vmt_presets', default_vmt_words)
        
        for i, word in enumerate(vmt_preset_words):
            checkbox = QCheckBox(word)
            # 从配置中恢复选中状态
            is_checked = self.config.get(f'vmt_preset_{word}_checked', False)
            # 确保is_checked是布尔值
            if isinstance(is_checked, str):
                is_checked = is_checked.lower() in ('true', '1', 'yes')
            checkbox.setChecked(bool(is_checked))
            # 连接信号以保存状态变化
            checkbox.stateChanged.connect(lambda state, w=word: self.save_vmt_preset_state(w, state))
            self.vmt_preset_blacklist_vars[word] = checkbox
            self.vmt_preset_layout.addWidget(checkbox, i // 4, i % 4)
        
        vmt_only_layout.addLayout(self.vmt_preset_layout)
        
        # 自定义屏蔽词（仅屏蔽VMT）
        vmt_only_layout.addWidget(QLabel("自定义屏蔽词（仅屏蔽VMT）:"))
        self.vmt_custom_blacklist_edit = QLineEdit()
        self.vmt_custom_blacklist_edit.setPlaceholderText("用逗号分隔多个屏蔽词，匹配的文件将生成VTF但不生成VMT")
        vmt_only_layout.addWidget(self.vmt_custom_blacklist_edit)
        
        blacklist_layout.addWidget(vmt_only_group)
        
        # 说明文本
        info_label = QLabel("说明：\n• 完全跳过生成：匹配的文件将完全跳过，不生成VTF和VMT\n• 仅屏蔽VMT生成：匹配的文件将生成VTF但不生成VMT文件")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-size: 11px; padding: 5px;")
        blacklist_layout.addWidget(info_label)
        
        # 实验性功能：自动法线贴图写入
        experimental_group = QGroupBox("实验性功能")
        experimental_layout = QVBoxLayout(experimental_group)
        
        self.auto_normal_checkbox = QCheckBox("自动法线贴图写入")
        self.auto_normal_checkbox.setToolTip("自动检测并在VMT中添加法线贴图($bumpmap)参数")
        experimental_layout.addWidget(self.auto_normal_checkbox)
        
        # 匹配阈值设置
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("文件名匹配阈值:"))
        self.normal_threshold_spinbox = QSpinBox()
        self.normal_threshold_spinbox.setRange(30, 90)
        self.normal_threshold_spinbox.setValue(50)
        self.normal_threshold_spinbox.setSuffix("%")
        self.normal_threshold_spinbox.setToolTip("当文件名相似度超过此阈值时，自动识别为法线贴图")
        threshold_layout.addWidget(self.normal_threshold_spinbox)
        threshold_layout.addStretch()
        experimental_layout.addLayout(threshold_layout)
        
        exp_info_label = QLabel("说明：自动检测_n、_N、Normal等法线贴图，并在VMT中添加$bumpmap参数")
        exp_info_label.setWordWrap(True)
        exp_info_label.setStyleSheet("color: #888888; font-size: 10px; padding: 3px;")
        experimental_layout.addWidget(exp_info_label)
        
        blacklist_layout.addWidget(experimental_group)
        
        config_layout.addWidget(blacklist_group)
        self.add_widget(config_group)
        
        # 压缩格式选择
        format_group = QGroupBox("压缩格式选择")
        format_layout = QVBoxLayout(format_group)
        
        # 格式选择模式
        mode_layout = QHBoxLayout()
        self.format_mode_auto = QRadioButton("智能检测（推荐）")
        self.format_mode_custom = QRadioButton("自定义规则")
        self.format_mode_manual = QRadioButton("手动选择")
        self.format_mode_auto.setChecked(True)
        
        mode_layout.addWidget(self.format_mode_auto)
        mode_layout.addWidget(self.format_mode_custom)
        mode_layout.addWidget(self.format_mode_manual)
        mode_layout.addStretch()
        format_layout.addLayout(mode_layout)
        
        # 智能检测说明
        self.auto_info_label = QLabel("将自动检测图像Alpha通道并选择最佳压缩格式")
        self.auto_info_label.setStyleSheet("color: #0078d4;")
        format_layout.addWidget(self.auto_info_label)
        
        # 自定义规则选择
        self.custom_format_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_format_widget)
        
        alpha_types = [("无透明", "no_alpha"), ("黑白透明", "binary_alpha"), ("渐变透明", "gradient_alpha")]
        formats = ["DXT1", "DXT3", "DXT5", "RGBA8888"]
        default_formats = ["DXT1", "DXT3", "DXT5"]
        
        self.custom_format_vars = {}
        for i, (type_name, type_key) in enumerate(alpha_types):
            type_layout = QHBoxLayout()
            type_layout.addWidget(QLabel(f"{type_name}:"))
            
            format_group_widget = QWidget()
            format_group_layout = QHBoxLayout(format_group_widget)
            format_group_layout.setContentsMargins(0, 0, 0, 0)
            
            button_group = QButtonGroup()
            self.custom_format_vars[type_key] = {}
            
            for fmt in formats:
                radio = QRadioButton(fmt)
                if fmt == default_formats[i]:
                    radio.setChecked(True)
                button_group.addButton(radio)
                self.custom_format_vars[type_key][fmt] = radio
                format_group_layout.addWidget(radio)
            
            format_group_layout.addStretch()
            type_layout.addWidget(format_group_widget)
            custom_layout.addLayout(type_layout)
        
        self.custom_format_widget.setVisible(False)
        format_layout.addWidget(self.custom_format_widget)
        
        # 手动格式选择
        self.manual_format_widget = QWidget()
        manual_layout = QHBoxLayout(self.manual_format_widget)
        
        self.manual_format_group = QButtonGroup()
        self.manual_format_vars = {}
        for fmt in ["RGBA8888", "DXT5", "DXT3", "DXT1"]:
            radio = QRadioButton(fmt)
            if fmt == "DXT1":
                radio.setChecked(True)
            self.manual_format_group.addButton(radio)
            self.manual_format_vars[fmt] = radio
            manual_layout.addWidget(radio)
        
        manual_layout.addStretch()
        self.manual_format_widget.setVisible(False)
        format_layout.addWidget(self.manual_format_widget)
        
        # 格式说明
        format_desc = QLabel("格式说明：\n• DXT1: 无透明或黑白透明，文件最小\n• DXT3: 黑白透明，适中文件大小\n• DXT5: 渐变透明，较大文件\n• RGBA8888: 最高质量，文件最大")
        format_desc.setStyleSheet("color: #888888; background-color: #f8f8f8; padding: 5px; border-radius: 3px;")
        format_layout.addWidget(format_desc)
        
        self.add_widget(format_group)
        

        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.generate_material_btn = QPushButton("生成材质配置")
        self.generate_material_btn.setToolTip("开始处理选中的图像文件，生成VTF和VMT材质配置")
        self.generate_material_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        
        self.edit_vmt_base_btn = QPushButton("编辑主VMT")
        self.edit_vmt_base_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        
        button_layout.addWidget(self.generate_material_btn)
        button_layout.addWidget(self.edit_vmt_base_btn)
        button_layout.addStretch()
        
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        self.add_widget(button_widget)
        
        # 连接信号
        self.connect_signals()
        
    def connect_signals(self):
        """连接信号"""
        self.select_material_file_btn.clicked.connect(self.select_material_file)
        self.select_material_folder_btn.clicked.connect(self.select_material_folder)
        self.remove_selected_btn.clicked.connect(self.remove_selected_file)
        self.clear_list_btn.clicked.connect(self.clear_file_list)
        self.browse_output_btn.clicked.connect(self.browse_output_dir)
        self.browse_qci_btn.clicked.connect(self.browse_qci_file)
        self.read_qci_btn.clicked.connect(self.read_cdmaterials_from_qci)
        self.browse_lightwarp_btn.clicked.connect(self.browse_lightwarp_file)
        self.generate_material_btn.clicked.connect(self.process_material)
        self.edit_vmt_base_btn.clicked.connect(self.edit_vmt_base)
        
        # 格式模式切换
        self.format_mode_auto.toggled.connect(self.on_format_mode_change)
        self.format_mode_custom.toggled.connect(self.on_format_mode_change)
        self.format_mode_manual.toggled.connect(self.on_format_mode_change)
        
    def restore_experimental_settings(self):
        """恢复实验性功能设置"""
        # 恢复自动法线贴图设置
        if hasattr(self, 'auto_normal_checkbox'):
            auto_normal_enabled = self.config.get("auto_normal_enabled", False)
            if isinstance(auto_normal_enabled, str):
                auto_normal_enabled = auto_normal_enabled.lower() == 'true'
            self.auto_normal_checkbox.setChecked(auto_normal_enabled)
        
        if hasattr(self, 'normal_threshold_spinbox'):
            normal_threshold = self.config.get("normal_threshold", 50)
            try:
                normal_threshold = int(normal_threshold)
            except (ValueError, TypeError):
                normal_threshold = 50
            self.normal_threshold_spinbox.setValue(normal_threshold)
        
    def select_material_file(self):
        """选择材质文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图像文件",
            self.config.get("last_material_dir", ""),
            "图像文件 (*.png *.jpg *.jpeg *.tga *.bmp *.vtf)"
        )
        if file_paths:
            for file_path in file_paths:
                self.material_files_listbox.addItem(file_path)
            self.config.set("last_material_dir", str(Path(file_paths[0]).parent))
            
    def select_material_folder(self):
        """选择材质文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含图像文件的文件夹",
            self.config.get("last_material_dir", "")
        )
        if folder_path:
            # 查找文件夹中的所有图像文件
            extensions = ['*.png', '*.jpg', '*.jpeg', '*.tga', '*.bmp', '*.vtf']
            for ext in extensions:
                files = list(Path(folder_path).rglob(ext))
                for file_path in files:
                    self.material_files_listbox.addItem(str(file_path))
            self.config.set("last_material_dir", folder_path)
            
    def remove_selected_file(self):
        """删除选中的文件"""
        current_row = self.material_files_listbox.currentRow()
        if current_row >= 0:
            self.material_files_listbox.takeItem(current_row)
            
    def clear_file_list(self):
        """清空文件列表"""
        self.material_files_listbox.clear()
        
    def browse_output_dir(self):
        """浏览输出目录"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录",
            self.output_dir_edit.text()
        )
        if folder_path:
            self.output_dir_edit.setText(folder_path)
            
    def browse_qci_file(self):
        """浏览QCI文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择QCI文件",
            self.config.get("last_qci_dir", ""),
            "QCI文件 (*.qci)"
        )
        if file_path:
            self.qci_file_edit.setText(file_path)
            self.config.set("last_qci_dir", str(Path(file_path).parent))
            
    def read_cdmaterials_from_qci(self):
        """从QCI文件读取$cdmaterials路径"""
        qci_file = self.qci_file_edit.text().strip()
        if not qci_file or not Path(qci_file).exists():
            QMessageBox.warning(self, "警告", "请先选择有效的QCI文件")
            return
            
        try:
            with open(qci_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 查找$cdmaterials行
            import re
            # 支持带引号和不带引号的格式
            pattern1 = r'\$cdmaterials\s+"([^"]+)"'  # 带引号格式: $cdmaterials "path"
            pattern2 = r'\$cdmaterials\s+([^\s\r\n]+)'  # 不带引号格式: $cdmaterials path
            
            match = re.search(pattern1, content, re.IGNORECASE)
            if not match:
                match = re.search(pattern2, content, re.IGNORECASE)
            
            if match:
                cdmaterials_path = match.group(1)
                # 转换为materials路径格式
                materials_path = f"materials/{cdmaterials_path}"
                self.cdmaterials_edit.setText(materials_path)
                self.status_bar.showMessage(f"已读取材质路径: {materials_path}")
            else:
                QMessageBox.information(self, "提示", "QCI文件中未找到$cdmaterials路径")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取QCI文件失败: {str(e)}")
            
    def browse_lightwarp_file(self):
        """浏览Lightwarp文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Lightwarp文件",
            self.config.get("last_lightwarp_dir", ""),
            "VTF文件 (*.vtf)"
        )
        if file_path:
            self.lightwarp_edit.setText(file_path)
            self.config.set("last_lightwarp_dir", str(Path(file_path).parent))
            

    def browse_qci_file(self):
        """浏览QCI文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择QCI文件",
            "",
            "QCI文件 (*.qci)"
        )
        if file_path:
            self.qci_file_edit.setText(file_path)
            
    def read_cdmaterials_from_qci(self):
        """从QCI文件读取$cdmaterials路径"""
        qci_file = self.qci_file_edit.text().strip()
        if not qci_file or not Path(qci_file).exists():
            QMessageBox.warning(self, "警告", "请先选择有效的QCI文件")
            return
            
        try:
            with open(qci_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 查找$cdmaterials行
            import re
            # 支持带引号和不带引号的格式
            pattern1 = r'\$cdmaterials\s+"([^"]+)"'  # 带引号格式: $cdmaterials "path"
            pattern2 = r'\$cdmaterials\s+([^\s\r\n]+)'  # 不带引号格式: $cdmaterials path
            
            match = re.search(pattern1, content, re.IGNORECASE)
            if not match:
                match = re.search(pattern2, content, re.IGNORECASE)
            
            if match:
                cdmaterials_path = match.group(1)
                # 直接使用cdmaterials路径，不添加materials前缀
                self.cdmaterials_edit.setText(cdmaterials_path)
                QMessageBox.information(self, "成功", f"已读取材质路径: {cdmaterials_path}")
            else:
                QMessageBox.information(self, "提示", "QCI文件中未找到$cdmaterials路径")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取QCI文件失败: {str(e)}")

    def on_format_mode_change(self):
        """格式模式切换"""
        if self.format_mode_auto.isChecked():
            self.custom_format_widget.setVisible(False)
            self.manual_format_widget.setVisible(False)
            self.auto_info_label.setVisible(True)
        elif self.format_mode_custom.isChecked():
            self.custom_format_widget.setVisible(True)
            self.manual_format_widget.setVisible(False)
            self.auto_info_label.setVisible(False)
        elif self.format_mode_manual.isChecked():
            self.custom_format_widget.setVisible(False)
            self.manual_format_widget.setVisible(True)
            self.auto_info_label.setVisible(False)
        
    def process_material(self):
        """处理材质配置生成"""
        if self.material_files_listbox.count() == 0:
            QMessageBox.warning(self, "警告", "请先选择图像文件")
            return
            
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请设置输出目录")
            return
            
        # 获取所有选中的文件
        files = []
        for i in range(self.material_files_listbox.count()):
            files.append(self.material_files_listbox.item(i).text())
            
        # 获取两种类型的屏蔽词列表
        skip_blacklist = self.get_skip_blacklist()
        vmt_blacklist = self.get_vmt_blacklist()
        
        # 调试输出屏蔽词列表
        print(f"完全跳过生成屏蔽词: {skip_blacklist}")
        print(f"仅屏蔽VMT生成屏蔽词: {vmt_blacklist}")
        
        # 启动进度条
        main_window = self.window()
        if hasattr(main_window, 'start_progress'):
            main_window.start_progress()
        
        # 禁用处理按钮
        self.generate_material_btn.setEnabled(False)
        self.generate_material_btn.setText("处理中...")
        
        # 开始处理
        self.status_bar.showMessage("开始处理材质配置...")
        
        try:
            success_count = 0
            total_files = len(files)
            
            for i, file_path in enumerate(files):
                # 更新进度
                progress = int((i / total_files) * 100)
                if hasattr(main_window, 'progress_bar'):
                    main_window.progress_bar.setValue(progress)
                    main_window.progress_bar.setVisible(True)
                
                # 更新状态
                self.status_bar.showMessage(f"正在处理: {Path(file_path).name} ({i+1}/{total_files})")
                
                # 检查是否完全跳过
                if self.should_skip_file(file_path, skip_blacklist):
                    print(f"完全跳过文件: {Path(file_path).name} (匹配完全跳过屏蔽词)")
                    continue
                
                # 检查是否仅屏蔽VMT生成
                skip_vmt = self.should_skip_file(file_path, vmt_blacklist)
                if skip_vmt:
                    print(f"仅生成VTF，跳过VMT: {Path(file_path).name} (匹配VMT屏蔽词)")
                else:
                    print(f"正常处理文件: {Path(file_path).name} (生成VTF和VMT)")
                    
                if self.process_single_material(file_path, output_dir, skip_vmt):
                    success_count += 1
            
            # 完成处理
            if hasattr(main_window, 'progress_bar'):
                main_window.progress_bar.setValue(100)
                main_window.progress_bar.setVisible(False)
            
            if hasattr(main_window, 'stop_progress'):
                main_window.stop_progress()
                    
            QMessageBox.information(self, "完成", f"成功处理 {success_count}/{len(files)} 个文件")
            self.status_bar.showMessage("材质配置生成完成")
            
        except Exception as e:
            # 停止进度条
            if hasattr(main_window, 'stop_progress'):
                main_window.stop_progress()
            if hasattr(main_window, 'progress_bar'):
                main_window.progress_bar.setVisible(False)
            
            QMessageBox.critical(self, "错误", f"处理过程中发生错误: {str(e)}")
            self.status_bar.showMessage("处理失败")
        
        finally:
            # 恢复处理按钮
            self.generate_material_btn.setEnabled(True)
            self.generate_material_btn.setText("生成材质配置")
            
    def get_skip_blacklist(self):
        """获取完全跳过生成的屏蔽词列表"""
        blacklist = []
        
        # 添加预设屏蔽词（完全跳过）
        for word, checkbox in self.skip_preset_blacklist_vars.items():
            if checkbox.isChecked():
                blacklist.append(word)
                
        # 添加自定义屏蔽词（完全跳过）
        custom_words = self.skip_custom_blacklist_edit.text().strip()
        if custom_words:
            for word in custom_words.split(','):
                word = word.strip()
                if word:
                    blacklist.append(word)
                    
        return blacklist
    
    def get_vmt_blacklist(self):
        """获取仅屏蔽VMT生成的屏蔽词列表"""
        blacklist = []
        
        # 添加预设屏蔽词（仅屏蔽VMT）
        for word, checkbox in self.vmt_preset_blacklist_vars.items():
            if checkbox.isChecked():
                blacklist.append(word)
                
        # 添加自定义屏蔽词（仅屏蔽VMT）
        custom_words = self.vmt_custom_blacklist_edit.text().strip()
        if custom_words:
            for word in custom_words.split(','):
                word = word.strip()
                if word:
                    blacklist.append(word)
                    
        return blacklist
    
    def get_blacklist(self):
        """获取屏蔽词列表（保持向后兼容）"""
        return self.get_skip_blacklist()
        
    def should_skip_file(self, file_path, blacklist):
        """检查文件是否应该被屏蔽"""
        file_name = Path(file_path).name.lower()
        print(f"检查文件: {file_name}, 屏蔽词列表: {[word.lower() for word in blacklist]}")
        for word in blacklist:
            word_lower = word.lower()
            if word_lower in file_name:
                print(f"匹配到屏蔽词: '{word_lower}' 在文件名 '{file_name}' 中")
                return True
        print(f"文件 '{file_name}' 未匹配任何屏蔽词")
        return False
    
    def detect_normal_map(self, diffuse_file_path, materials_path):
        """检测对应的法线贴图文件"""
        try:
            diffuse_path = Path(diffuse_file_path)
            diffuse_dir = diffuse_path.parent
            diffuse_stem = diffuse_path.stem
            
            # 常见的法线贴图后缀
            normal_suffixes = ['_n', '_N', '_normal', '_Normal', '_NORMAL', '_norm', '_Norm']
            
            # 1. 首先检查明确的法线贴图命名
            for suffix in normal_suffixes:
                # 移除diffuse后缀（如_d）并添加法线后缀
                if diffuse_stem.endswith('_d') or diffuse_stem.endswith('_D'):
                    base_name = diffuse_stem[:-2]
                    normal_name = base_name + suffix
                else:
                    normal_name = diffuse_stem + suffix
                
                # 检查各种图像格式
                for ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']:
                    normal_file = diffuse_dir / (normal_name + ext)
                    if normal_file.exists():
                        # 返回相对于materials的路径
                        relative_path = materials_path + '/' + normal_name
                        print(f"找到法线贴图: {normal_file.name} -> {relative_path}")
                        return relative_path
            
            # 2. 如果没有找到明确命名的法线贴图，进行模糊匹配
            threshold = self.normal_threshold_spinbox.value() / 100.0
            best_match = None
            best_score = 0
            
            # 获取目录中的所有图像文件
            image_extensions = ['.png', '.jpg', '.jpeg', '.tga', '.bmp']
            for file in diffuse_dir.iterdir():
                if file.is_file() and file.suffix.lower() in image_extensions and file != diffuse_path:
                    # 计算文件名相似度
                    similarity = self.calculate_filename_similarity(diffuse_stem, file.stem)
                    
                    # 检查是否包含法线贴图关键词
                    filename_lower = file.stem.lower()
                    has_normal_keyword = any(keyword in filename_lower for keyword in ['normal', 'norm', '_n'])
                    
                    if similarity > threshold and has_normal_keyword and similarity > best_score:
                        best_match = file
                        best_score = similarity
            
            if best_match:
                relative_path = materials_path + '/' + best_match.stem
                print(f"模糊匹配法线贴图: {best_match.name} (相似度: {best_score:.2f}) -> {relative_path}")
                return relative_path
            
            return None
            
        except Exception as e:
            print(f"检测法线贴图时出错: {e}")
            return None
    
    def calculate_filename_similarity(self, name1, name2):
        """计算两个文件名的相似度（使用简单的字符匹配算法）"""
        try:
            # 转换为小写进行比较
            name1 = name1.lower()
            name2 = name2.lower()
            
            # 移除常见的后缀以便更好地比较
            suffixes_to_remove = ['_d', '_n', '_normal', '_norm', '_diffuse', '_diff']
            for suffix in suffixes_to_remove:
                if name1.endswith(suffix):
                    name1 = name1[:-len(suffix)]
                if name2.endswith(suffix):
                    name2 = name2[:-len(suffix)]
            
            # 计算最长公共子序列长度
            def lcs_length(s1, s2):
                m, n = len(s1), len(s2)
                dp = [[0] * (n + 1) for _ in range(m + 1)]
                
                for i in range(1, m + 1):
                    for j in range(1, n + 1):
                        if s1[i-1] == s2[j-1]:
                            dp[i][j] = dp[i-1][j-1] + 1
                        else:
                            dp[i][j] = max(dp[i-1][j], dp[i][j-1])
                
                return dp[m][n]
            
            # 计算相似度
            lcs_len = lcs_length(name1, name2)
            max_len = max(len(name1), len(name2))
            
            if max_len == 0:
                return 0
            
            return lcs_len / max_len
            
        except Exception:
            return 0
        
    def is_normal_map_file(self, file_path):
        """检测当前文件是否为法线贴图"""
        try:
            file_stem = Path(file_path).stem.lower()
            
            # 检查文件名是否包含法线贴图标识
            normal_indicators = ['_n', '_normal', '_norm', '_bump', '_height']
            
            for indicator in normal_indicators:
                if indicator in file_stem:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def process_single_material(self, file_path, output_dir, skip_vmt=False):
        """处理单个材质文件"""
        try:
            file_path = Path(file_path)
            output_dir = Path(output_dir)
            
            # 获取材质路径并构建完整的输出路径
            materials_path = self.cdmaterials_edit.text().strip()
            if not materials_path:
                raise Exception("请输入材质路径或从QCI文件读取")
            
            # 移除开头的materials/前缀（如果存在）
            if materials_path.startswith('materials/'):
                materials_path = materials_path[10:]
            
            # 构建完整的materials路径结构
            full_materials_path = output_dir / "materials" / materials_path
            full_materials_path.mkdir(parents=True, exist_ok=True)
            
            base_name = file_path.stem
            
            # 检测是否为法线贴图，如果是则强制使用RGBA8888格式
            is_normal_map = self.is_normal_map_file(file_path)
            
            if is_normal_map:
                # 法线贴图强制使用RGBA8888格式以避免图像损坏
                format_name = "RGBA8888"
                format_params = self.get_vtf_command_params(format_name)
                self.vmt_alpha_config = ""
                print(f"法线贴图检测: {file_path.name} -> 强制使用RGBA8888格式")
            else:
                # 根据模式选择格式
                if self.format_mode_auto.isChecked():
                    # 智能检测alpha通道
                    alpha_type = self.analyze_alpha_channel(str(file_path))
                    format_name, vmt_config = self.get_optimal_format_and_vmt(alpha_type)
                    self.vmt_alpha_config = vmt_config
                    format_params = self.get_vtf_command_params(format_name)
                    print(f"智能检测: {file_path.name} -> {alpha_type} -> {format_name}")
                elif self.format_mode_custom.isChecked():
                    # 自定义规则模式
                    alpha_type = self.analyze_alpha_channel(str(file_path))
                    format_name, vmt_config = self.get_custom_format_and_vmt(alpha_type)
                    self.vmt_alpha_config = vmt_config
                    format_params = self.get_vtf_command_params(format_name)
                    print(f"自定义规则: {file_path.name} -> {alpha_type} -> {format_name}")
                else:
                    # 手动模式，使用用户选择的格式
                    format_name = self.get_selected_manual_format()
                    format_params = self.get_vtf_command_params(format_name)
                    self.vmt_alpha_config = ""
                    print(f"手动模式: {file_path.name} -> {format_name}")
            
            # 1. 图像转VTF - 直接输出到materials路径
            vtfcmd_path = self.get_vtfcmd_path()
            if not vtfcmd_path:
                raise Exception("未找到VTFCmd工具")
                
            cmd = [vtfcmd_path, '-file', str(file_path), '-output', str(full_materials_path)] + format_params
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                raise Exception(f"图像转VTF失败 ({base_name}): {result.stderr}")
            
            # 2. 生成VMT文件（如果不跳过）
            if not skip_vmt:
                # 检测法线贴图
                normal_map_path = None
                if self.auto_normal_checkbox.isChecked():
                    normal_map_path = self.detect_normal_map(file_path, materials_path)
                
                self.generate_vmt_files(full_materials_path, base_name, materials_path, normal_map_path)
            else:
                print(f"跳过VMT生成: {base_name}")
            
            self.status_bar.showMessage(f"已处理: {file_path.name}")
            return True
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"处理 {file_path.name} 失败: {str(e)}")
            return False
            
    def analyze_alpha_channel(self, img_file):
        """分析单个图像的Alpha通道类型"""
        try:
            # 首先检查图像是否有alpha通道
            cmd = ['magick', 'identify', '-format', '%[channels]', img_file]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"检测通道失败: {result.stderr}")
                return "无透明"
            
            channels = result.stdout.strip().lower()
            print(f"图像通道: {channels}")
            
            # 如果没有alpha通道
            if 'alpha' not in channels and 'rgba' not in channels:
                return "无透明"
            
            # 提取alpha通道并分析其统计信息
            cmd = ['magick', img_file, '-alpha', 'extract', '-format', '%[fx:mean] %[fx:standard_deviation]', 'info:']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"提取alpha通道失败: {result.stderr}")
                return "渐变透明"  # 默认假设有渐变
            
            stats = result.stdout.strip().split()
            if len(stats) < 2:
                return "渐变透明"
            
            alpha_mean = float(stats[0])
            alpha_std = float(stats[1])
            
            print(f"Alpha统计 - 均值: {alpha_mean:.3f}, 标准差: {alpha_std:.3f}")
            
            # 如果标准差很小，说明alpha值比较均匀
            if alpha_std < 0.01:
                if alpha_mean < 0.1:
                    return "无透明"  # 几乎全透明
                elif alpha_mean > 0.9:
                    return "无透明"  # 几乎不透明
                else:
                    return "渐变透明"  # 均匀的半透明
            
            # 对于有明显通道变化的贴图，进行像素级分析
            if alpha_std > 0.1:  # 标准差大于0.1时进行像素级分析
                print("检测到明显Alpha通道变化，启用像素级分析...")
                pixel_analysis_result = self.analyze_alpha_pixels(img_file, alpha_mean, alpha_std)
                if pixel_analysis_result:
                    return pixel_analysis_result
            
            # 检查是否主要是0和1值（二值化alpha）
            cmd = ['magick', img_file, '-alpha', 'extract', '-threshold', '50%', '-format', '%[fx:mean]', 'info:']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                threshold_mean = float(result.stdout.strip())
                print(f"阈值化后均值: {threshold_mean:.3f}")
                
                # 调整判断阈值，提高准确性
                if abs(alpha_mean - threshold_mean) < 0.1 and alpha_std > 0.25:
                    return "黑白透明"
            
            return "渐变透明"
            
        except (ValueError, IndexError) as e:
            print(f"Alpha分析异常: {e}")
            return "渐变透明"
    
    def analyze_alpha_pixels(self, img_file, alpha_mean, alpha_std):
        """像素级Alpha通道分析，仅对有明显通道变化的贴图使用"""
        try:
            # 获取Alpha通道的像素值分布直方图
            cmd = ['magick', img_file, '-alpha', 'extract', '-format', '%c', 'histogram:info:']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"获取像素分布失败: {result.stderr}")
                return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
            
            print(f"ImageMagick直方图原始输出:\n{result.stdout}")
            
            # 解析直方图数据
            histogram_lines = result.stdout.strip().split('\n')
            pixel_counts = {}
            total_pixels = 0
            
            for line in histogram_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # 尝试多种解析格式
                parsed = False
                
                # 格式1: "1234: (128,128,128) #808080 gray(128)" - 标准灰度格式
                if ':' in line and 'gray(' in line:
                    try:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            count = int(parts[0].strip())
                            gray_start = line.find('gray(') + 5
                            gray_end = line.find(')', gray_start)
                            if gray_end > gray_start:
                                gray_value = int(line[gray_start:gray_end])
                                pixel_counts[gray_value] = count
                                total_pixels += count
                                parsed = True
                    except (ValueError, IndexError):
                        pass
                
                # 格式2: "1234: (128,128,128) #808080 grey50" - 命名灰度格式
                if not parsed and ':' in line and ('grey' in line or 'gray' in line or 'Gray' in line):
                    try:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            count = int(parts[0].strip())
                            # 从RGB值中提取灰度值
                            rgb_match = line.find('(')
                            if rgb_match != -1:
                                rgb_end = line.find(')', rgb_match)
                                if rgb_end > rgb_match:
                                    rgb_str = line[rgb_match+1:rgb_end]
                                    rgb_parts = rgb_str.split(',')
                                    if len(rgb_parts) >= 3:
                                        # 对于灰度图像，RGB三个值应该相等，取第一个值
                                        gray_value = int(rgb_parts[0].strip())
                                        pixel_counts[gray_value] = count
                                        total_pixels += count
                                        parsed = True
                    except (ValueError, IndexError):
                        pass
                
                # 格式3: "1234: (128,128,128) #808080 srgb(128,128,128)" - RGB格式但实际是灰度
                if not parsed and ':' in line and '(' in line:
                    try:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            count = int(parts[0].strip())
                            # 从RGB值中提取灰度值
                            rgb_match = line.find('(')
                            if rgb_match != -1:
                                rgb_end = line.find(')', rgb_match)
                                if rgb_end > rgb_match:
                                    rgb_str = line[rgb_match+1:rgb_end]
                                    rgb_parts = rgb_str.split(',')
                                    if len(rgb_parts) >= 3:
                                        r = int(rgb_parts[0].strip())
                                        g = int(rgb_parts[1].strip())
                                        b = int(rgb_parts[2].strip())
                                        # 检查是否为灰度值（RGB相等）
                                        if r == g == b:
                                            gray_value = r
                                            pixel_counts[gray_value] = count
                                            total_pixels += count
                                            parsed = True
                    except (ValueError, IndexError):
                        pass
                
                # 如果都无法解析，输出调试信息（仅前几行）
                if not parsed and ':' in line and len([k for k in pixel_counts.keys()]) < 5:
                    print(f"无法解析的直方图行: {line}")
            
            if total_pixels == 0:
                print("无法解析像素分布数据，使用备用方法")
                return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
            
            print(f"总像素数: {total_pixels}")
            print(f"解析到的像素值: {sorted(pixel_counts.keys())}")
            
            # 统计不同灰度级别的数量
            unique_values = len(pixel_counts)
            print(f"唯一Alpha值数量: {unique_values}")
            
            # 用户建议的新判断逻辑：
            # 若Alpha值包含10个及以上不同值（非0或255），则判定为渐变透明，否则为黑白透明
            # 若所有Alpha值均为255（完全不透明）或0（完全透明），则不视为渐变透明
            
            # 统计非0和非255的Alpha值数量
            non_binary_values = [value for value in pixel_counts.keys() if value != 0 and value != 255]
            non_binary_count = len(non_binary_values)
            
            print(f"非0和非255的Alpha值数量: {non_binary_count}")
            print(f"非0和非255的Alpha值: {sorted(non_binary_values)}")
            
            # 检查是否所有Alpha值都是0或255
            all_binary = all(value == 0 or value == 255 for value in pixel_counts.keys())
            
            if all_binary:
                print(f"像素级分析结果: 黑白透明 (所有Alpha值均为0或255)")
                return "黑白透明"
            elif non_binary_count >= 10:
                print(f"像素级分析结果: 渐变透明 (包含{non_binary_count}个非0/255的Alpha值)")
                return "渐变透明"
            else:
                print(f"像素级分析结果: 黑白透明 (仅包含{non_binary_count}个非0/255的Alpha值，少于10个)")
                return "黑白透明"
            
        except Exception as e:
            print(f"像素级分析异常: {e}")
            return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
    
    def get_optimal_format_and_vmt(self, alpha_type):
        """根据Alpha通道类型获取最佳格式和VMT配置"""
        if alpha_type == "无透明":
            return "DXT1", ""
        elif alpha_type == "黑白透明":
            return "DXT3", '"$alphatest" "1"'
        elif alpha_type == "渐变透明":
            return "DXT5", '"$translucent" "1"'
        else:
            return "DXT1", ""
    
    def get_custom_format_and_vmt(self, alpha_type):
        """根据自定义规则获取格式和VMT配置"""
        # 映射alpha类型到变量键
        type_map = {
            "无透明": "no_alpha",
            "黑白透明": "binary_alpha", 
            "渐变透明": "gradient_alpha"
        }
        
        type_key = type_map.get(alpha_type, "no_alpha")
        
        # 获取用户选择的格式
        format_name = "DXT1"  # 默认值
        if type_key in self.custom_format_vars:
            for fmt, radio in self.custom_format_vars[type_key].items():
                if radio.isChecked():
                    format_name = fmt
                    break
        
        # 根据格式和alpha类型确定VMT配置
        vmt_config = ""
        if alpha_type == "黑白透明" and format_name in ["DXT3", "DXT5"]:
            vmt_config = '"$alphatest" "1"'
        elif alpha_type == "渐变透明" and format_name in ["DXT5", "RGBA8888"]:
            vmt_config = '"$translucent" "1"'
        
        return format_name, vmt_config
    
    def get_selected_manual_format(self):
        """获取手动选择的格式"""
        for fmt, radio in self.manual_format_vars.items():
            if radio.isChecked():
                return fmt
        return "DXT1"  # 默认值
    
    def get_vtf_command_params(self, format_name):
        """获取VTF命令参数，包括format和alphaformat"""
        format_map = {
            "RGBA8888": "rgba8888",
            "DXT5": "dxt5",
            "DXT3": "dxt3",
            "DXT1": "dxt1"
        }
        
        format_param = format_map.get(format_name, "dxt1")
        
        # 对于RGBA8888，强制使用rgba8888格式，不使用压缩
        if format_name == "RGBA8888":
            return ['-format', 'rgba8888', '-alphaformat', 'rgba8888']
        # 对于其他格式，使用相同的format和alphaformat
        else:
            return ['-format', format_param, '-alphaformat', format_param]
    
    def generate_vmt_files(self, output_path, base_name, materials_path=None, normal_map_path=None):
        """生成VMT文件"""
        # 获取材质路径
        if materials_path is None:
            materials_path = self.cdmaterials_edit.text().strip()
            if not materials_path:
                # 如果用户没有输入路径，尝试自动查找
                materials_path = self.find_materials_path(output_path)
                if not materials_path:
                    raise Exception("无法确定materials相对路径，请在材质路径中输入或从QCI文件读取")
            else:
                # 移除开头的materials/前缀（如果存在）
                if materials_path.startswith('materials/'):
                    materials_path = materials_path[10:]
        
        # 创建shader目录
        shader_dir = output_path / "shader"
        shader_dir.mkdir(exist_ok=True)
        
        # 处理lightwarp贴图
        lightwarp_file = self.lightwarp_edit.text().strip()
        if lightwarp_file and Path(lightwarp_file).exists():
            # 复制lightwarp文件到shader目录
            import shutil
            lightwarp_filename = Path(lightwarp_file).name
            lightwarp_dest = shader_dir / lightwarp_filename
            shutil.copy2(lightwarp_file, lightwarp_dest)
            lightwarp_path = f"{materials_path}/shader/{Path(lightwarp_filename).stem}"
        else:
            lightwarp_path = f"{materials_path}/shader/toon_light"
        
        # 生成vmt-base.vmt内容
        vmt_base_content = f'''"VertexLitGeneric"
{{
	"$basetexture" "basetexture"
	//"$bumpmap"					"normal"	// 法线贴图，没有用到就不要启用。
																	// 特别注意：错误的法线贴图可能会导致 UV 边缘出现奇怪的异常。

	"$lightwarptexture" 			"{lightwarp_path}"			// 色调校正，卡通渲染元素加成。不推荐更改，一般有格式错误导致效果异常。

    "$nocull" 						"1"			// 双面渲染，避免模型内部看到外部的黑色。一般都启用，模型的背面漏色可以关闭。
	"$nodecal" 						"1"			// 避免贴花，关闭血迹等贴花以防止一些视觉问题。
	"$phong" 						"1"			// 材质反射开关。半透明或全息材质可关闭。
	"$halflambert" 					"1"			// 半兰伯特光照。让光照看起来更自然，可以关闭

	"$phongboost"					".04"       // 材质反射强度。数值越高，取决于法线贴图的A通道，越白越反射
														// 因为我们修改了该通道，所以数值应该要低一点，参考值 100 改为 .04 即 4 倍
														// 启用 $phongexponenttexture 之后，数值可能要低一点，参考值 20 改为 4 到 80 不等
	
	//"$phongexponenttexture"		"ko/vrc/lime/def/ppp_exp"		// 高光密度贴图 / 高光贴图，原理类似于法线，但是的确有一般不启用。
																	// 为启用 $phongalbedotint，我们让法线贴图高光贴图，这样是可以接受的。

	"$phongalbedotint"				"1" 				// 基础色贴图影响反射颜色，配合启用 $phongexponenttexture 有效，效果需要仔细观察。
	//"$phongexponent" 				"5.0" 				// 材质反射密度。启用后将覆盖 $phongexponenttexture，默认即5.0，一般不需修改。
	//"$phongtint" 					"[1 1 1]" 			// 全局反射颜色通道强度。启用后将覆盖 $phongalbedotint，为避免冲突只能单色。
	"$phongfresnelranges"			"[1 .1 .1]" 		// 材质反射菲涅尔范围，原理类似于法线，但是的确需要找到。

	//"$envmap"						"env_cubemap" 		// 环境反射。与反射不同，这个依赖贴图位置等多种因素有关。不建议启用。
	"$normalmapalphaenvmapmask"		"1" 				// 使用法线贴图 A 通道作为环境反射遮罩。环境反射效果强弱取决于法线贴图的A通道，越白越反射，不建议启用。
	"$envmapfresnel"				"1" 				// 启用环境反射菲涅尔效果，数值依赖反射，需要配合其他参数需要找到。
	"$envmaptint"					"[ 0.4 0.4 0.4 ]" 	// 环境反射通道强度。数值越大，环境反射越明显。不建议为避免冲突只能单色。

	//"$selfillum" 					"1" 				// 启用自发光。数值依赖取决于基础色贴图 A 通道，越白越自发光，自发光会发光。
	//"$selfillummask"                "diyu2024/share/selfillum/mask"         //自发光通道，如果不使用A透明，可以夜光共享。
	//"$additive"					"1"					// 加法混色，具有半透明效果，透明度固定，取决于基础色贴图 RGB 通道灰度，黑色为完全透明。
																	// 与自发光一同启用，可以产生全息效果。
	//"$translucent"				"1" 				// 启用半透明，透明度固定，取决于基础色贴图 A 通道，越白越半透明，与自发光冲突。
	//"$alpha" 						"0.5" 				// 透明度数值。半透明效果，会影响阴影效果。
																	// 特别注意：通过材质创建阴影贴花时，该数值会阴影贴花失效。


	// 文档：https://developer.valvesoftware.com/wiki/$phong/en // 材质反射
}}
'''
        
        # 写入vmt-base.vmt文件
        vmt_base_file = shader_dir / "vmt-base.vmt"
        with open(vmt_base_file, 'w', encoding='utf-8') as f:
            f.write(vmt_base_content)
        
        # 检查是否为眼部材质
        if base_name.lower() == "eye":
            self.generate_eye_vmt_files(output_path, base_name, materials_path)
        else:
            self.generate_normal_vmt_file(output_path, base_name, materials_path, normal_map_path)
    
    def generate_normal_vmt_file(self, output_path, base_name, materials_path, normal_map_path=None):
        """生成普通材质VMT文件"""
        # 获取alpha配置
        alpha_config = getattr(self, 'vmt_alpha_config', None)
        insert_lines = []
        
        # 处理透明度参数
        if alpha_config:
            if isinstance(alpha_config, dict):
                # 新格式：字典形式的配置
                for key, value in alpha_config.items():
                    insert_lines.append(f'\t"{key}" "{value}"')
            elif isinstance(alpha_config, str) and alpha_config.strip():
                # 旧格式：字符串形式的配置
                insert_lines.append(f'\t{alpha_config}')
        
        # 如果有法线贴图，添加到insert部分
        if normal_map_path:
            insert_lines.append(f'\t"$bumpmap" "{normal_map_path}"')
        
        # 生成VMT内容 - 始终保留insert块
        if insert_lines:
            insert_content = "\n".join(insert_lines)
        else:
            insert_content = ""  # 空的insert内容，但保留insert块结构
        
        vmt_content = f'''patch
{{
	include	"materials/{materials_path}/shader/vmt-base.vmt"
	insert
	{{
{insert_content}
	}}
	replace
	{{
	"$basetexture"						"{materials_path}/{base_name}"
	}}
}}
'''
        
        vmt_file = output_path / f"{base_name}.vmt"
        with open(vmt_file, 'w', encoding='utf-8') as f:
            f.write(vmt_content)
    
    def generate_eye_vmt_files(self, output_path, base_name, materials_path):
        """生成眼部材质VMT文件"""
        shader_dir = output_path / "shader"
        
        # 生成eye_base.vmt
        eye_base_content = f'''"EyeRefract"
{{
	"$iris" 			  "{materials_path}/eye"	  //虹膜贴图路径
	"$AmbientOcclTexture" "{materials_path}/ambient"  // RGB的环境遮蔽，Alpha未使用
	"$Envmap"             "Engine/eye-reflection-cubemap-"   		  // Reflection environment map
	"$CorneaTexture"      "Engine/eye-cornea"                 		  // Special texture that has 2D cornea normal in RG and other data in BA
	"$EyeballRadius" "0.5"				// 默认 0.5
	"$AmbientOcclColor" "[0.1 0.1 0.1]"	// 默认 0.33, 0.33, 0.33
	"$Dilation" "0.5"					// 默认 0.5
	"$ParallaxStrength" "0.30"          // 默认 0.25
	"$CorneaBumpStrength" "0.5"			// 默认 1.0
	"$NoDecal" "1"
	// 这些效果需要ps.2.0b或以后版本才可用
	"$RaytraceSphere" "0"	 // 默认 1 - 启用光线追色，但是会导致光线追踪，使用需要谨慎
	"$SphereTexkillCombo" "0"// 默认 1 - Enables killing pixels that don't ray-intersect the sphere
	"$lightwarptexture" 			"{materials_path}/shader/toon_light"
	"$EmissiveBlendEnabled" 		"1"
	"$EmissiveBlendStrength" 		"0.05"
	"$EmissiveBlendTexture" 		"vgui/white"
	"$EmissiveBlendBaseTexture" 	"{materials_path}/Eye"
	"$EmissiveBlendFlowTexture" 	"vgui/white"
	"$EmissiveBlendTint" 			" [ 1 1 1 ] "
	"$EmissiveBlendScrollVector" 	" [ 0 0 ] "
}}
'''
        
        eye_base_file = shader_dir / "eye_base.vmt"
        with open(eye_base_file, 'w', encoding='utf-8') as f:
            f.write(eye_base_content)
        
        # 生成eye_r.vmt和eye_l.vmt
        for suffix in ['_r', '_l']:
            eye_vmt_content = f'''patch
{{
	include	"materials/{materials_path}/shader/eye_base.vmt"
	insert
	{{
	}}
	replace
	{{
	"$iris" "{materials_path}/{base_name}"
	}}
}}
'''
            
            eye_vmt_file = output_path / f"{base_name}{suffix}.vmt"
            with open(eye_vmt_file, 'w', encoding='utf-8') as f:
                f.write(eye_vmt_content)
    
    def find_materials_path(self, output_path):
        """查找materials相对路径"""
        import re
        path_str = str(output_path).replace('\\', '/')
        if 'materials' in path_str.lower():
            # 提取materials之后的路径
            match = re.search(r'materials[/\\](.+)', path_str, re.IGNORECASE)
            if match:
                return match.group(1).replace('\\', '/')
        return None
    
    def get_vtfcmd_path(self):
        """获取VTFCmd工具路径"""
        # 首先检查当前目录
        current_dir = Path.cwd()
        vtfcmd_exe = current_dir / "vtfcmd.exe"
        if vtfcmd_exe.exists():
            return str(vtfcmd_exe)
        
        # 检查系统PATH
        import shutil
        vtfcmd_path = shutil.which("vtfcmd")
        if vtfcmd_path:
            return vtfcmd_path
        
        # 检查常见安装位置
        common_paths = [
            "C:\\Program Files\\Steam\\steamapps\\common\\GarrysMod\\bin\\vtfcmd.exe",
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\GarrysMod\\bin\\vtfcmd.exe",
            "vtfcmd.exe"  # 相对路径
        ]
        
        for path in common_paths:
            if Path(path).exists():
                return path
        
        return None
    
    def get_blacklist(self):
        """获取屏蔽词列表"""
        blacklist = set()
        
        # 添加预设屏蔽词
        for keyword, checkbox in self.preset_blacklist_vars.items():
            if checkbox.isChecked():
                blacklist.add(keyword.lower())
        
        # 添加自定义屏蔽词
        custom_text = self.custom_blacklist_edit.text().strip()
        if custom_text:
            # QLineEdit使用逗号分隔多个屏蔽词
            custom_words = [word.strip().lower() for word in custom_text.split(',') if word.strip()]
            blacklist.update(custom_words)
        
        return blacklist
    

    
    def edit_vmt_base(self):
        """编辑主VMT文件"""
        # 获取输出目录
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请先设置输出目录")
            return
        
        # 获取材质路径
        materials_path = self.cdmaterials_edit.text().strip()
        if not materials_path:
            QMessageBox.warning(self, "警告", "请先输入材质路径或从QCI文件读取")
            return
        
        # 移除开头的materials/前缀（如果存在）
        if materials_path.startswith('materials/'):
            materials_path = materials_path[10:]
        
        # 构建vmt-base.vmt文件路径
        output_path = Path(output_dir)
        full_materials_path = output_path / "materials" / materials_path
        shader_dir = full_materials_path / "shader"
        vmt_base_file = shader_dir / "vmt-base.vmt"
        
        # 获取lightwarp路径
        lightwarp_file = self.lightwarp_edit.text().strip()
        if lightwarp_file and Path(lightwarp_file).exists():
            lightwarp_filename = Path(lightwarp_file).name
            lightwarp_path = f"{materials_path}/shader/{Path(lightwarp_filename).stem}"
        else:
            lightwarp_path = f"{materials_path}/shader/toon_light"
        
        # 默认的vmt-base.vmt内容
        default_content = f'''"VertexLitGeneric"
{{
	"$basetexture" "basetexture"
	//"$bumpmap"					"normal"	// 法线贴图，没有用到就不要启用。
																		// 特别注意：错误的法线贴图可能会导致 UV 边缘出现奇怪的异常。

	"$lightwarptexture" 			"{lightwarp_path}"			// 色调校正，卡通渲染元素加成。不推荐更改，一般有格式错误导致效果异常。

    "$nocull" 						"1"			// 双面渲染，避免模型内部看到外部的黑色。一般都启用，模型的背面漏色可以关闭。
	"$nodecal" 						"1"			// 避免贴花，关闭血迹等贴花以防止一些视觉问题。
	"$phong" 						"1"			// 材质反射开关。半透明或全息材质可关闭。
	"$halflambert" 					"1"			// 半兰伯特光照。让光照看起来更自然，可以关闭

	"$phongboost"					".04"       // 材质反射强度。数值越高，取决于法线贴图的A通道，越白越反射
																		// 因为我们修改了该通道，所以数值应该要低一点，参考值 100 改为 .04 即 4 倍
																		// 启用 $phongexponenttexture 之后，数值可能要低一点，参考值 20 改为 4 到 80 不等
	
	//"$phongexponenttexture"		"ko/vrc/lime/def/ppp_exp"		// 高光密度贴图 / 高光贴图，原理类似于法线，但是的确有一般不启用。
																			// 为启用 $phongalbedotint，我们让法线贴图高光贴图，这样是可以接受的。

	"$phongalbedotint"				"1" 				// 基础色贴图影响反射颜色，配合启用 $phongexponenttexture 有效，效果需要仔细观察。
	//"$phongexponent" 				"5.0" 				// 材质反射密度。启用后将覆盖 $phongexponenttexture，默认即5.0，一般不需修改。
	//"$phongtint" 					"[1 1 1]" 			// 全局反射颜色通道强度。启用后将覆盖 $phongalbedotint，为避免冲突只能单色。
	"$phongfresnelranges"			"[1 .1 .1]" 		// 材质反射菲涅尔范围，原理类似于法线，但是的确需要找到。

	//"$envmap"						"env_cubemap" 		// 环境反射。与反射不同，这个依赖贴图位置等多种因素有关。不建议启用。
	"$normalmapalphaenvmapmask"		"1" 				// 使用法线贴图 A 通道作为环境反射遮罩。环境反射效果强弱取决于法线贴图的A通道，越白越反射，不建议启用。
	"$envmapfresnel"				"1" 				// 启用环境反射菲涅尔效果，数值依赖反射，需要配合其他参数需要找到。
	"$envmaptint"					"[ 0.4 0.4 0.4 ]" 	// 环境反射通道强度。数值越大，环境反射越明显。不建议为避免冲突只能单色。

	//"$selfillum" 					"1" 				// 启用自发光。数值依赖取决于基础色贴图 A 通道，越白越自发光，自发光会发光。
	//"$selfillummask"                "diyu2024/share/selfillum/mask"         //自发光通道，如果不使用A透明，可以夜光共享。
	//"$additive"					"1"					// 加法混色，具有半透明效果，透明度固定，取决于基础色贴图 RGB 通道灰度，黑色为完全透明。
																			// 与自发光一同启用，可以产生全息效果。
	//"$translucent"				"1" 				// 启用半透明，透明度固定，取决于基础色贴图 A 通道，越白越半透明，与自发光冲突。
	//"$alpha" 						"0.5" 				// 透明度数值。半透明效果，会影响阴影效果。
																			// 特别注意：通过材质创建阴影贴花时，该数值会阴影贴花失效。


	// 文档：https://developer.valvesoftware.com/wiki/$phong/en // 材质反射
}}
'''
        
        # 如果文件已存在，读取现有内容
        current_content = default_content
        if vmt_base_file.exists():
            try:
                with open(vmt_base_file, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except Exception as e:
                QMessageBox.warning(self, "警告", f"读取现有vmt-base.vmt文件失败: {str(e)}\n将使用默认内容")
        
        # 创建编辑器对话框
        dialog = VMTBaseEditor(self, current_content, vmt_base_file)
        dialog.exec()
    
    def manage_skip_presets(self):
        """管理完全跳过生成的预设屏蔽词"""
        # 从配置中获取当前预设词列表，如果没有则使用默认值
        default_presets = ["_N", "_Normal", "_emi", "_n", "phongexp", "envmap", "bump"]
        current_presets = self.config.get("skip_presets", default_presets)
        
        # 创建预设管理对话框
        dialog = PresetManagerDialog(self, current_presets, "完全跳过生成预设屏蔽词")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 更新预设词列表
            new_presets = dialog.get_presets()
            # 保存到配置
            self.config.set("skip_presets", new_presets)
            self.config.sync()
            self.update_skip_presets(new_presets)
    
    def manage_vmt_presets(self):
        """管理仅屏蔽VMT生成的预设屏蔽词"""
        # 从配置中获取当前预设词列表，如果没有则使用默认值
        default_presets = ["test", "temp", "backup", "old"]
        current_presets = self.config.get("vmt_presets", default_presets)
        
        # 创建预设管理对话框
        dialog = PresetManagerDialog(self, current_presets, "仅屏蔽VMT生成预设屏蔽词")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 更新预设词列表
            new_presets = dialog.get_presets()
            # 保存到配置
            self.config.set("vmt_presets", new_presets)
            self.config.sync()
            self.update_vmt_presets(new_presets)
    
    def manage_material_presets(self):
        """管理材质配置预设屏蔽词（保持向后兼容）"""
        self.manage_skip_presets()
    
    def save_skip_preset_state(self, word, state):
        """保存完全跳过预设的选中状态"""
        self.config.set(f'skip_preset_{word}_checked', state == 2)  # 2表示选中
        self.config.sync()
    
    def save_vmt_preset_state(self, word, state):
        """保存VMT预设的选中状态"""
        self.config.set(f'vmt_preset_{word}_checked', state == 2)  # 2表示选中
        self.config.sync()
    
    def update_skip_presets(self, new_presets):
        """更新完全跳过生成预设屏蔽词UI"""
        # 清除旧的复选框
        for i in reversed(range(self.skip_preset_layout.count())):
            child = self.skip_preset_layout.itemAt(i).widget()
            if child and isinstance(child, QCheckBox):
                child.setParent(None)
        
        # 重新创建复选框
        self.skip_preset_blacklist_vars = {}
        default_checked = ["_N", "_Normal", "_emi"]
        
        for i, word in enumerate(new_presets):
            checkbox = QCheckBox(word)
            # 从配置中恢复选中状态，如果没有则使用默认值
            default_state = word in default_checked
            is_checked = self.config.get(f'skip_preset_{word}_checked', default_state)
            # 确保is_checked是布尔值
            if isinstance(is_checked, str):
                is_checked = is_checked.lower() in ('true', '1', 'yes')
            checkbox.setChecked(bool(is_checked))
            # 连接信号以保存状态变化
            checkbox.stateChanged.connect(lambda state, w=word: self.save_skip_preset_state(w, state))
            self.skip_preset_blacklist_vars[word] = checkbox
            self.skip_preset_layout.addWidget(checkbox, i // 4, i % 4)
    
    def update_vmt_presets(self, new_presets):
        """更新仅屏蔽VMT生成预设屏蔽词UI"""
        # 清除旧的复选框
        for i in reversed(range(self.vmt_preset_layout.count())):
            child = self.vmt_preset_layout.itemAt(i).widget()
            if child and isinstance(child, QCheckBox):
                child.setParent(None)
        
        # 重新创建复选框
        self.vmt_preset_blacklist_vars = {}
        
        for i, word in enumerate(new_presets):
            checkbox = QCheckBox(word)
            # 从配置中恢复选中状态
            is_checked = self.config.get(f'vmt_preset_{word}_checked', False)
            # 确保is_checked是布尔值
            if isinstance(is_checked, str):
                is_checked = is_checked.lower() in ('true', '1', 'yes')
            checkbox.setChecked(bool(is_checked))
            # 连接信号以保存状态变化
            checkbox.stateChanged.connect(lambda state, w=word: self.save_vmt_preset_state(w, state))
            self.vmt_preset_blacklist_vars[word] = checkbox
            self.vmt_preset_layout.addWidget(checkbox, i // 4, i % 4)
    
    def update_material_presets(self, new_presets):
        """更新材质配置预设屏蔽词UI（保持向后兼容）"""
        self.update_skip_presets(new_presets)


class ResizeTab(ScrollableTab):
    """静态图像调整选项卡"""
    
    def __init__(self, config_manager: ConfigManager, status_bar):
        self.config = config_manager
        self.status_bar = status_bar
        self.resize_files = []
        super().__init__()
        
    def setup_content(self):
        """设置内容"""
        # 说明文本
        desc_label = QLabel("功能说明：调整图像文件尺寸并转换为VTF格式，可选择生成对应的VMT材质文件。\n支持批量处理和多种压缩格式。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #cccccc; padding: 10px; background-color: #353535; border-radius: 5px;")
        self.add_widget(desc_label)
        
        # 文件选择组
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)
        
        # 文件选择按钮
        button_layout = QHBoxLayout()
        self.select_file_btn = QPushButton("选择图像文件")
        self.select_folder_btn = QPushButton("选择文件夹")
        button_layout.addWidget(self.select_file_btn)
        button_layout.addWidget(self.select_folder_btn)
        button_layout.addStretch()
        file_layout.addLayout(button_layout)
        
        # 文件列表
        self.files_listbox = QListWidget()
        self.files_listbox.setMaximumHeight(120)
        file_layout.addWidget(self.files_listbox)
        
        # 文件管理按钮
        manage_layout = QHBoxLayout()
        self.remove_selected_btn = QPushButton("删除选中")
        self.clear_list_btn = QPushButton("清空列表")
        manage_layout.addWidget(self.remove_selected_btn)
        manage_layout.addWidget(self.clear_list_btn)
        manage_layout.addStretch()
        file_layout.addLayout(manage_layout)
        
        self.add_widget(file_group)
        
        # 尺寸设置组
        size_group = QGroupBox("尺寸设置")
        size_layout = QVBoxLayout(size_group)
        
        size_input_layout = QHBoxLayout()
        size_input_layout.addWidget(QLabel("宽度:"))
        self.width_edit = QLineEdit("1024")
        self.width_edit.setMaximumWidth(100)
        size_input_layout.addWidget(self.width_edit)
        
        size_input_layout.addWidget(QLabel("高度:"))
        self.height_edit = QLineEdit("1024")
        self.height_edit.setMaximumWidth(100)
        size_input_layout.addWidget(self.height_edit)
        
        size_input_layout.addStretch()
        size_layout.addLayout(size_input_layout)
        
        # 尺寸说明
        size_desc = QLabel("建议使用2的幂次方尺寸，如：512, 1024, 2048等")
        size_desc.setStyleSheet("color: #888888; font-style: italic;")
        size_layout.addWidget(size_desc)
        
        self.add_widget(size_group)
        
        # 压缩格式组
        format_group = QGroupBox("压缩格式")
        format_layout = QVBoxLayout(format_group)
        
        # 格式模式选择
        mode_layout = QHBoxLayout()
        self.format_mode_group = QButtonGroup()
        
        self.format_mode_auto = QRadioButton("智能检测")
        self.format_mode_auto.setChecked(True)
        self.format_mode_group.addButton(self.format_mode_auto)
        mode_layout.addWidget(self.format_mode_auto)
        
        self.format_mode_custom = QRadioButton("自定义规则")
        self.format_mode_group.addButton(self.format_mode_custom)
        mode_layout.addWidget(self.format_mode_custom)
        
        self.format_mode_manual = QRadioButton("手动选择")
        self.format_mode_group.addButton(self.format_mode_manual)
        mode_layout.addWidget(self.format_mode_manual)
        
        mode_layout.addStretch()
        format_layout.addLayout(mode_layout)
        
        # 智能检测说明
        self.auto_info_label = QLabel("智能检测：自动分析图像透明度类型并选择最优格式")
        self.auto_info_label.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        format_layout.addWidget(self.auto_info_label)
        
        # 自定义规则选择（默认隐藏）
        self.custom_format_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_format_widget)
        
        alpha_types = [("无透明", "no_alpha"), ("黑白透明", "binary_alpha"), ("渐变透明", "gradient_alpha")]
        formats = ["DXT1", "DXT3", "DXT5", "RGBA8888"]
        default_formats = ["DXT1", "DXT3", "DXT5"]
        
        self.custom_format_vars = {}
        for i, (type_name, type_key) in enumerate(alpha_types):
            type_layout = QHBoxLayout()
            type_layout.addWidget(QLabel(f"{type_name}:"))
            
            format_group_inner = QButtonGroup()
            self.custom_format_vars[type_key] = {}
            
            for fmt in formats:
                radio = QRadioButton(fmt)
                if fmt == default_formats[i]:
                    radio.setChecked(True)
                format_group_inner.addButton(radio)
                self.custom_format_vars[type_key][fmt] = radio
                type_layout.addWidget(radio)
            
            type_layout.addStretch()
            custom_layout.addLayout(type_layout)
        
        self.custom_format_widget.setVisible(False)
        format_layout.addWidget(self.custom_format_widget)
        
        # 手动格式选择（默认隐藏）
        self.manual_format_widget = QWidget()
        manual_layout = QHBoxLayout(self.manual_format_widget)
        
        self.manual_format_group = QButtonGroup()
        self.manual_format_vars = {}
        for fmt in ["RGBA8888", "DXT5", "DXT3", "DXT1"]:
            radio = QRadioButton(fmt)
            if fmt == "DXT1":
                radio.setChecked(True)
            self.manual_format_group.addButton(radio)
            self.manual_format_vars[fmt] = radio
            manual_layout.addWidget(radio)
        
        manual_layout.addStretch()
        self.manual_format_widget.setVisible(False)
        format_layout.addWidget(self.manual_format_widget)
        
        # 格式说明
        format_desc = QLabel("格式说明：\n• DXT1: 无透明或黑白透明，文件最小\n• DXT3: 黑白透明，适中文件大小\n• DXT5: 渐变透明，较大文件\n• RGBA8888: 最高质量，文件最大")
        format_desc.setStyleSheet("color: #888888; background-color: #f8f8f8; padding: 5px; border-radius: 3px;")
        format_layout.addWidget(format_desc)
        
        self.add_widget(format_group)
        
        # VMT生成选项
        vmt_group = QGroupBox("VMT材质文件生成")
        vmt_layout = QVBoxLayout(vmt_group)
        
        # VMT生成开关
        self.generate_vmt_checkbox = QCheckBox("生成VMT材质文件（透明度自动检测）")
        self.generate_vmt_checkbox.setToolTip("勾选后将自动生成对应的VMT材质文件，透明度类型由工具自动判断")
        vmt_layout.addWidget(self.generate_vmt_checkbox)
        
        # QCI文件选择
        qci_layout = QHBoxLayout()
        qci_layout.addWidget(QLabel("QCI文件（可选）:"))
        self.qci_file_edit = QLineEdit()
        self.browse_qci_btn = QPushButton("浏览")
        qci_layout.addWidget(self.qci_file_edit)
        qci_layout.addWidget(self.browse_qci_btn)
        vmt_layout.addLayout(qci_layout)
        
        # 材质路径设置
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("材质路径:"))
        self.materials_path_edit = QLineEdit("models/player")
        self.materials_path_edit.setPlaceholderText("例如: models/player")
        self.read_qci_btn = QPushButton("从QCI读取")
        path_layout.addWidget(self.materials_path_edit)
        path_layout.addWidget(self.read_qci_btn)
        vmt_layout.addLayout(path_layout)
        
        self.add_widget(vmt_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.process_btn = QPushButton("调整图像尺寸")
        self.process_btn.setToolTip("开始处理选中的图像文件，调整尺寸并转换为VTF格式")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #106ebe;
                cursor: pointer;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #cccccc;
            }
        """)
        
        button_layout.addWidget(self.process_btn)
        button_layout.addStretch()
        
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        self.add_widget(button_widget)
        
        # 连接信号
        self.connect_signals()
        
    def connect_signals(self):
        """连接信号"""
        self.select_file_btn.clicked.connect(self.select_resize_file)
        self.select_folder_btn.clicked.connect(self.select_resize_folder)
        self.remove_selected_btn.clicked.connect(self.remove_selected_file)
        self.clear_list_btn.clicked.connect(self.clear_file_list)
        self.process_btn.clicked.connect(self.process_resize)
        
        # QCI文件相关
        self.browse_qci_btn.clicked.connect(self.browse_qci_file)
        self.read_qci_btn.clicked.connect(self.read_cdmaterials_from_qci)
        
        # 格式模式切换
        self.format_mode_auto.toggled.connect(self.on_format_mode_change)
        self.format_mode_custom.toggled.connect(self.on_format_mode_change)
        self.format_mode_manual.toggled.connect(self.on_format_mode_change)
        

    def select_resize_file(self):
        """选择调整尺寸的图像文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图像文件",
            self.config.get("last_resize_dir", ""),
            "图像文件 (*.png *.jpg *.jpeg *.tga *.bmp)"
        )
        if file_paths:
            for file_path in file_paths:
                if file_path not in self.resize_files:
                    self.resize_files.append(file_path)
                    self.files_listbox.addItem(Path(file_path).name)
            self.config.set("last_resize_dir", str(Path(file_paths[0]).parent))
            
    def select_resize_folder(self):
        """选择调整尺寸的图像文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含图像文件的文件夹",
            self.config.get("last_resize_dir", "")
        )
        if folder_path:
            # 查找文件夹中的所有图像文件
            extensions = ['*.png', '*.jpg', '*.jpeg', '*.tga', '*.bmp']
            added_count = 0
            for ext in extensions:
                files = list(Path(folder_path).rglob(ext))
                for file_path in files:
                    file_str = str(file_path)
                    if file_str not in self.resize_files:
                        self.resize_files.append(file_str)
                        self.files_listbox.addItem(file_path.name)
                        added_count += 1
            
            if added_count > 0:
                QMessageBox.information(self, "成功", f"从文件夹中找到并添加了 {added_count} 个图像文件")
            else:
                QMessageBox.warning(self, "警告", "选择的文件夹中没有找到图像文件")
            
            self.config.set("last_resize_dir", folder_path)
            
    def remove_selected_file(self):
        """删除选中的文件"""
        current_row = self.files_listbox.currentRow()
        if current_row >= 0:
            self.files_listbox.takeItem(current_row)
            del self.resize_files[current_row]
            
    def clear_file_list(self):
        """清空文件列表"""
        self.files_listbox.clear()
        self.resize_files.clear()
        
    def on_format_mode_change(self):
        """格式模式切换"""
        if self.format_mode_auto.isChecked():
            self.custom_format_widget.setVisible(False)
            self.manual_format_widget.setVisible(False)
            self.auto_info_label.setVisible(True)
        elif self.format_mode_custom.isChecked():
            self.custom_format_widget.setVisible(True)
            self.manual_format_widget.setVisible(False)
            self.auto_info_label.setVisible(False)
        elif self.format_mode_manual.isChecked():
            self.custom_format_widget.setVisible(False)
            self.manual_format_widget.setVisible(True)
            self.auto_info_label.setVisible(False)
        
    def process_resize(self):
        """处理静态图像调整"""
        if not self.resize_files:
            QMessageBox.warning(self, "警告", "请先选择图像文件")
            return
            
        # 检查所有文件是否存在
        invalid_files = [f for f in self.resize_files if not Path(f).exists()]
        if invalid_files:
            QMessageBox.critical(self, "错误", f"以下文件不存在：\n{chr(10).join(invalid_files)}")
            return
            
        width_text = self.width_edit.text().strip()
        height_text = self.height_edit.text().strip()
        
        if not width_text or not height_text:
            QMessageBox.warning(self, "警告", "请输入有效的宽度和高度")
            return
            
        try:
            width = int(width_text)
            height = int(height_text)
        except ValueError:
            QMessageBox.warning(self, "警告", "宽度和高度必须是数字")
            return
            
        # 启动进度条
        main_window = self.window()
        if hasattr(main_window, 'start_progress'):
            main_window.start_progress()
        
        # 禁用处理按钮
        self.process_btn.setEnabled(False)
        self.process_btn.setText("处理中...")
        
        # 开始处理
        self.status_bar.showMessage("开始处理静态图像调整...")
        
        try:
            total_files = len(self.resize_files)
            processed_files = 0
            output_dirs = []
            
            for img_file in self.resize_files:
                processed_files += 1
                
                # 更新进度
                progress = int((processed_files / total_files) * 100)
                if hasattr(main_window, 'progress_bar'):
                    main_window.progress_bar.setValue(progress)
                    main_window.progress_bar.setVisible(True)
                
                self.status_bar.showMessage(f"正在处理静态图像调整... ({processed_files}/{total_files})")
                
                img_path = Path(img_file)
                output_dir = img_path.parent / "resized"
                output_dir.mkdir(exist_ok=True)
                
                if output_dir not in output_dirs:
                    output_dirs.append(output_dir)
                
                base_name = img_path.stem
                
                # 1. 使用ImageMagick调整图像尺寸
                self.status_bar.showMessage(f"调整图像尺寸... ({processed_files}/{total_files})")
                resized_img = output_dir / f"{base_name}_resized.tga"
                
                cmd1 = ['magick', str(img_path), '-resize', f'{width}x{height}!', str(resized_img)]
                result = subprocess.run(cmd1, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode != 0:
                    raise Exception(f"调整图像尺寸失败 ({img_path.name}): {result.stderr}")
                
                # 2. 转换为VTF
                self.status_bar.showMessage(f"转换为VTF格式... ({processed_files}/{total_files})")
                
                # 根据模式选择格式
                format_params = self.get_format_params(str(img_file))
                
                # 查找vtfcmd路径
                vtfcmd_path = self.get_vtfcmd_path()
                if not vtfcmd_path:
                    raise Exception("未找到VTFCmd工具，请确保已安装并可访问")
                
                cmd2 = [vtfcmd_path, '-file', str(resized_img), '-output', str(output_dir)] + format_params
                result = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode != 0:
                    raise Exception(f"转换为VTF失败 ({img_path.name}): {result.stderr}")
                
                # 重命名VTF文件以移除_resized后缀
                generated_vtf = output_dir / f"{base_name}_resized.vtf"
                target_vtf = output_dir / f"{base_name}.vtf"
                if generated_vtf.exists():
                    if target_vtf.exists():
                        target_vtf.unlink()
                    generated_vtf.rename(target_vtf)
                
                # 生成VMT文件（如果启用）
                if self.generate_vmt_checkbox.isChecked():
                    self.status_bar.showMessage(f"生成VMT材质文件... ({processed_files}/{total_files})")
                    
                    # 自动检测透明度类型
                    alpha_type = self.analyze_alpha_channel(str(img_file))
                    print(f"自动检测透明度类型: {img_path.name} -> {alpha_type}")
                    
                    # 获取材质路径
                    materials_path = self.materials_path_edit.text().strip()
                    if not materials_path:
                        materials_path = "models/player"
                    
                    # 移除开头的materials/前缀（如果存在）
                    if materials_path.startswith('materials/'):
                        materials_path = materials_path[10:]
                    
                    try:
                        # 生成具体的VMT文件（不生成shader文件夹和vmt-base文件）
                        vmt_content = self.generate_vmt_content(base_name, alpha_type, materials_path)
                        
                        # 写入VMT文件
                        vmt_file = output_dir / f"{base_name}.vmt"
                        with open(vmt_file, 'w', encoding='utf-8') as f:
                            f.write(vmt_content)
                        print(f"生成VMT文件: {vmt_file}")
                        
                    except Exception as vmt_error:
                        print(f"生成VMT文件失败: {vmt_error}")
                        # 继续处理，不中断整个流程
                
                # 清理临时文件
                if resized_img.exists():
                    resized_img.unlink()
            
            # 完成处理
            if hasattr(main_window, 'progress_bar'):
                main_window.progress_bar.setValue(100)
                main_window.progress_bar.setVisible(False)
            
            if hasattr(main_window, 'stop_progress'):
                main_window.stop_progress()
            
            self.status_bar.showMessage("静态图像调整完成")
            output_info = "\n".join([f"- {dir}" for dir in output_dirs])
            QMessageBox.information(self, "成功", f"静态图像调整完成！\n处理了 {total_files} 个文件\n输出目录:\n{output_info}")
            
        except Exception as e:
            # 停止进度条
            if hasattr(main_window, 'stop_progress'):
                main_window.stop_progress()
            if hasattr(main_window, 'progress_bar'):
                main_window.progress_bar.setVisible(False)
            
            self.status_bar.showMessage("处理失败")
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")
        
        finally:
            # 恢复处理按钮
            self.process_btn.setEnabled(True)
            self.process_btn.setText("开始处理")
            
    def get_format_params(self, img_file):
        """获取格式参数"""
        if self.format_mode_auto.isChecked():
            # 智能检测模式
            alpha_type = self.analyze_alpha_channel(img_file)
            format_name, _ = self.get_optimal_format_and_vmt(alpha_type)
            format_params = self.get_vtf_command_params(format_name)
            print(f"智能检测: {Path(img_file).name} -> {alpha_type} -> {format_name}")
            return format_params
        elif self.format_mode_custom.isChecked():
            # 自定义规则模式
            alpha_type = self.analyze_alpha_channel(img_file)
            format_name, _ = self.get_custom_format_and_vmt(alpha_type)
            format_params = self.get_vtf_command_params(format_name)
            print(f"自定义规则: {Path(img_file).name} -> {alpha_type} -> {format_name}")
            return format_params
        else:
            # 手动模式
            for fmt, radio in self.manual_format_vars.items():
                if radio.isChecked():
                    format_params = self.get_vtf_command_params(fmt)
                    print(f"手动模式: {Path(img_file).name} -> {fmt}")
                    return format_params
            return ['-format', 'dxt1']
            
    def analyze_alpha_channel(self, img_file):
        """分析单个图像的Alpha通道类型（统一算法）"""
        try:
            # 首先检查图像是否有alpha通道
            cmd = ['magick', 'identify', '-format', '%[channels]', img_file]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"检测通道失败: {result.stderr}")
                return "no_alpha"
            
            channels = result.stdout.strip().lower()
            print(f"图像通道: {channels}")
            
            # 如果没有alpha通道
            if 'alpha' not in channels and 'rgba' not in channels:
                return "no_alpha"
            
            # 获取Alpha通道的统计信息
            cmd = ['magick', img_file, '-alpha', 'extract', '-format', '%[mean]\n%[standard-deviation]', 'info:']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"获取Alpha统计信息失败: {result.stderr}")
                return "no_alpha"
            
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return "no_alpha"
            
            try:
                alpha_mean = float(lines[0])
                alpha_std = float(lines[1])
            except ValueError:
                print(f"解析Alpha统计信息失败: {lines}")
                return "no_alpha"
            
            print(f"Alpha统计: 均值={alpha_mean:.4f}, 标准差={alpha_std:.4f}")
            
            # 判断逻辑
            if alpha_mean > 0.95 and alpha_std < 0.1:
                return "no_alpha"  # 几乎全白，视为无透明
            elif alpha_std < 0.15:  # 标准差很小，可能是纯色或接近纯色
                if alpha_mean < 0.1:
                    return "no_alpha"  # 几乎全黑，视为无透明
                else:
                    return "binary_alpha"  # 可能是黑白透明
            else:
                # 标准差较大，需要进一步分析
                return self.analyze_alpha_pixels(img_file, alpha_mean, alpha_std)
                
        except Exception as e:
            print(f"Alpha通道分析出错: {str(e)}")
            return "no_alpha"
    
    def analyze_alpha_pixels(self, img_file, alpha_mean, alpha_std):
        """像素级Alpha通道分析，仅对有明显通道变化的贴图使用"""
        try:
            # 获取Alpha通道的像素值分布直方图
            cmd = ['magick', img_file, '-alpha', 'extract', '-format', '%c', 'histogram:info:']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"获取像素分布失败: {result.stderr}")
                return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
            
            histogram_output = result.stdout.strip()
            if not histogram_output:
                return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
            
            # 解析直方图输出
            unique_values = set()
            total_pixels = 0
            
            for line in histogram_output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 尝试多种格式解析
                pixel_count, alpha_value = self.parse_histogram_line(line)
                if pixel_count is not None and alpha_value is not None:
                    unique_values.add(alpha_value)
                    total_pixels += pixel_count
            
            if not unique_values:
                return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
            
            print(f"检测到 {len(unique_values)} 个唯一Alpha值")
            
            # 分析唯一值的分布
            if len(unique_values) <= 2:
                # 只有1-2个值，很可能是黑白透明
                if 0 in unique_values or 255 in unique_values:
                    return "binary_alpha"
                else:
                    return "gradient_alpha"
            elif len(unique_values) <= 10:
                # 少量离散值，可能是黑白透明或简单渐变
                extreme_values = sum(1 for v in unique_values if v <= 25 or v >= 230)
                if extreme_values >= len(unique_values) * 0.7:
                    return "binary_alpha"
                else:
                    return "gradient_alpha"
            else:
                # 大量唯一值，很可能是渐变透明
                return "gradient_alpha"
                
        except Exception as e:
            print(f"像素级分析出错: {str(e)}")
            return self.analyze_alpha_pixels_fallback(img_file, alpha_mean, alpha_std)
    
    def parse_histogram_line(self, line):
        """解析ImageMagick直方图输出的单行"""
        import re
        
        # 格式1: "     123: (128,128,128) #808080 gray(128)"
        pattern1 = r'^\s*(\d+):\s*\(([^)]+)\)'
        match1 = re.match(pattern1, line)
        if match1:
            pixel_count = int(match1.group(1))
            values = match1.group(2).split(',')
            if len(values) >= 1:
                try:
                    alpha_value = int(values[0].strip())
                    return pixel_count, alpha_value
                except ValueError:
                    pass
        
        # 格式2: "123: gray(128)"
        pattern2 = r'^\s*(\d+):\s*gray\((\d+)\)'
        match2 = re.match(pattern2, line)
        if match2:
            pixel_count = int(match2.group(1))
            alpha_value = int(match2.group(2))
            return pixel_count, alpha_value
        
        # 格式3: "123: #808080"
        pattern3 = r'^\s*(\d+):\s*#([0-9a-fA-F]{2})'
        match3 = re.match(pattern3, line)
        if match3:
            pixel_count = int(match3.group(1))
            alpha_value = int(match3.group(2), 16)
            return pixel_count, alpha_value
        
        return None, None
    
    def analyze_alpha_pixels_fallback(self, img_file, alpha_mean, alpha_std):
        """Alpha像素分析的后备方案"""
        # 基于统计信息的简单判断
        if alpha_std < 0.3:
            return "binary_alpha"
        else:
            return "gradient_alpha"
    
    def get_optimal_format_and_vmt(self, alpha_type):
        """根据Alpha通道类型获取最佳格式和VMT配置"""
        # 统一返回值格式映射
        type_mapping = {
            "无透明": "no_alpha",
            "黑白透明": "binary_alpha", 
            "渐变透明": "gradient_alpha"
        }
        
        # 如果是中文格式，转换为英文
        mapped_type = type_mapping.get(alpha_type, alpha_type)
        
        format_map = {
            "no_alpha": ("DXT1", {}),  # 无透明时不添加透明度参数
            "binary_alpha": ("DXT3", {"$alphatest": "1"}),
            "gradient_alpha": ("DXT5", {"$translucent": "1"})
        }
        return format_map.get(mapped_type, ("DXT1", {}))
    
    def get_custom_format_and_vmt(self, alpha_type):
        """根据自定义规则获取格式和VMT配置"""
        # 获取用户为该Alpha类型选择的格式
        if alpha_type in self.custom_format_vars:
            for fmt, radio in self.custom_format_vars[alpha_type].items():
                if radio.isChecked():
                    # 根据格式和Alpha类型返回相应的VMT配置
                    if alpha_type == "no_alpha":
                        return fmt, {}  # 无透明时不添加透明度参数
                    elif alpha_type == "binary_alpha":
                        return fmt, {"$alphatest": "1"}
                    else:  # gradient_alpha
                        return fmt, {"$translucent": "1"}
        
        # 默认返回DXT1，无透明时不添加透明度参数
        return "DXT1", {}
    
    def get_vtf_command_params(self, format_name):
        """获取VTF命令参数"""
        format_params = {
            "DXT1": ["-format", "dxt1"],
            "DXT3": ["-format", "dxt3"],
            "DXT5": ["-format", "dxt5"],
            "RGBA8888": ["-format", "rgba8888"]
        }
        return format_params.get(format_name, ["-format", "dxt1"])
    

    
    def get_vtfcmd_path(self):
        """获取VTFCmd工具路径"""
        # 首先尝试直接调用vtfcmd
        try:
            result = subprocess.run(["vtfcmd", "-help"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0 or "vtfcmd" in result.stdout.lower():
                return "vtfcmd"
        except (FileNotFoundError, UnicodeDecodeError):
            pass
        
        # 尝试常见的VTFCmd.exe路径
        common_paths = [
            "VTFCmd.exe",
            "D:\\VTFEdit_Reloaded_v2.0.9\\VTFCmd.exe",
            "C:\\Program Files\\VTFEdit\\VTFCmd.exe",
            "C:\\Program Files (x86)\\VTFEdit\\VTFCmd.exe"
        ]
        
        for path in common_paths:
            try:
                result = subprocess.run([path, "-help"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode == 0 or "vtfcmd" in result.stdout.lower():
                    return path
            except (FileNotFoundError, UnicodeDecodeError):
                continue
        
        return None
    
    def generate_vmt_content(self, base_name, alpha_type, materials_path):
        """生成patch格式VMT内容（依赖vmt-base.vmt）"""
        # 根据透明度类型确定透明度参数
        transparency_params = ""
        if alpha_type == "binary_alpha":
            transparency_params = '\t"$alphatest"\t\t\t\t\t\t"1"\n'
        elif alpha_type == "gradient_alpha":
            transparency_params = '\t"$translucent"\t\t\t\t\t\t"1"\n'
        
        # 生成patch格式的VMT内容，类似MaterialConfigTab的逻辑
        vmt_content = f'''patch
{{
\tinclude\t\t"materials/{materials_path}/shader/vmt-base.vmt"
\tinsert
\t{{
{transparency_params}\t}}
\treplace
\t{{
\t"$basetexture"\t\t\t\t\t\t"{materials_path}/{base_name}"
\t}}
}}'''
        
        return vmt_content
    
    def generate_vmt_base_file(self, output_dir, materials_path):
        """生成vmt-base.vmt文件（与MaterialConfigTab保持一致）"""
        # 创建shader目录
        shader_dir = output_dir / "shader"
        shader_dir.mkdir(exist_ok=True)
        
        # 生成vmt-base.vmt内容（与MaterialConfigTab完全一致）
        lightwarp_path = f"{materials_path}/shader/toon_light"
        
        vmt_base_content = f'''"VertexLitGeneric"
{{
\t"$basetexture" "basetexture"
\t//"$bumpmap"\t\t\t\t\t"normal"\t// 法线贴图，没有用到就不要启用。
\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t// 特别注意：错误的法线贴图可能会导致 UV 边缘出现奇怪的异常。

\t"$lightwarptexture" \t\t\t"{lightwarp_path}"\t\t\t// 色调校正，卡通渲染元素加成。不推荐更改，一般有格式错误导致效果异常。

    "$nocull" \t\t\t\t\t\t"1"\t\t\t// 双面渲染，避免模型内部看到外部的黑色。一般都启用，模型的背面漏色可以关闭。
\t"$nodecal" \t\t\t\t\t\t"1"\t\t\t// 避免贴花，关闭血迹等贴花以防止一些视觉问题。
\t"$phong" \t\t\t\t\t\t"1"\t\t\t// 材质反射开关。半透明或全息材质可关闭。
\t"$halflambert" \t\t\t\t\t"1"\t\t\t// 半兰伯特光照。让光照看起来更自然，可以关闭

\t"$phongboost"\t\t\t\t\t".04"       // 材质反射强度。数值越高，取决于法线贴图的A通道，越白越反射
\t\t\t\t\t\t\t\t\t\t\t\t\t\t// 因为我们修改了该通道，所以数值应该要低一点，参考值 100 改为 .04 即 4 倍
\t\t\t\t\t\t\t\t\t\t\t\t\t\t// 启用 $phongexponenttexture 之后，数值可能要低一点，参考值 20 改为 4 到 80 不等
\t
\t//"$phongexponenttexture"\t\t"ko/vrc/lime/def/ppp_exp"\t\t// 高光密度贴图 / 高光贴图，原理类似于法线，但是的确有一般不启用。
\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t// 为启用 $phongalbedotint，我们让法线贴图高光贴图，这样是可以接受的。

\t"$phongalbedotint"\t\t\t\t"1" \t\t\t\t// 基础色贴图影响反射颜色，配合启用 $phongexponenttexture 有效，效果需要仔细观察。
\t//"$phongexponent" \t\t\t\t"5.0" \t\t\t\t// 材质反射密度。启用后将覆盖 $phongexponenttexture，默认即5.0，一般不需修改。
\t//"$phongtint" \t\t\t\t\t"[1 1 1]" \t\t\t// 全局反射颜色通道强度。启用后将覆盖 $phongalbedotint，为避免冲突只能单色。
\t"$phongfresnelranges"\t\t\t"[1 .1 .1]" \t\t// 材质反射菲涅尔范围，原理类似于法线，但是的确需要找到。

\t//"$envmap"\t\t\t\t\t\t"env_cubemap" \t\t// 环境反射。与反射不同，这个依赖贴图位置等多种因素有关。不建议启用。
\t"$normalmapalphaenvmapmask"\t\t"1" \t\t\t\t// 使用法线贴图 A 通道作为环境反射遮罩。环境反射效果强弱取决于法线贴图的A通道，越白越反射，不建议启用。
\t"$envmapfresnel"\t\t\t\t"1" \t\t\t\t// 启用环境反射菲涅尔效果，数值依赖反射，需要配合其他参数需要找到。
\t"$envmaptint"\t\t\t\t\t"[ 0.4 0.4 0.4 ]" \t// 环境反射通道强度。数值越大，环境反射越明显。不建议为避免冲突只能单色。

\t//"$selfillum" \t\t\t\t\t"1" \t\t\t\t// 启用自发光。数值依赖取决于基础色贴图 A 通道，越白越自发光，自发光会发光。
\t//"$selfillummask"                "diyu2024/share/selfillum/mask"         //自发光通道，如果不使用A透明，可以夜光共享。
\t//"$additive"\t\t\t\t\t"1"\t\t\t\t\t// 加法混色，具有半透明效果，透明度固定，取决于基础色贴图 RGB 通道灰度，黑色为完全透明。
\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t// 与自发光一同启用，可以产生全息效果。
\t//"$translucent"\t\t\t\t"1" \t\t\t\t// 启用半透明，透明度固定，取决于基础色贴图 A 通道，越白越半透明，与自发光冲突。
\t//"$alpha" \t\t\t\t\t\t"0.5" \t\t\t\t// 透明度数值。半透明效果，会影响阴影效果。
\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t// 特别注意：通过材质创建阴影贴花时，该数值会阴影贴花失效。


\t// 文档：https://developer.valvesoftware.com/wiki/$phong/en // 材质反射
}}'''
        
        # 写入vmt-base.vmt文件
        vmt_base_file = shader_dir / "vmt-base.vmt"
        with open(vmt_base_file, 'w', encoding='utf-8') as f:
            f.write(vmt_base_content)
        
        return vmt_base_file
    
    def browse_qci_file(self):
        """浏览QCI文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择QCI文件",
            "",
            "QCI文件 (*.qci)"
        )
        if file_path:
            self.qci_file_edit.setText(file_path)
            
    def read_cdmaterials_from_qci(self):
        """从QCI文件读取$cdmaterials路径"""
        qci_file = self.qci_file_edit.text().strip()
        if not qci_file or not Path(qci_file).exists():
            QMessageBox.warning(self, "警告", "请先选择有效的QCI文件")
            return
            
        try:
            with open(qci_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 查找$cdmaterials行
            import re
            # 支持带引号和不带引号的格式
            pattern1 = r'\$cdmaterials\s+"([^"]+)"'  # 带引号格式: $cdmaterials "path"
            pattern2 = r'\$cdmaterials\s+([^\s\r\n]+)'  # 不带引号格式: $cdmaterials path
            
            match = re.search(pattern1, content, re.IGNORECASE)
            if not match:
                match = re.search(pattern2, content, re.IGNORECASE)
            
            if match:
                cdmaterials_path = match.group(1)
                # 直接使用cdmaterials路径，不添加materials前缀
                self.materials_path_edit.setText(cdmaterials_path)
                QMessageBox.information(self, "成功", f"已读取材质路径: {cdmaterials_path}")
            else:
                QMessageBox.information(self, "提示", "QCI文件中未找到$cdmaterials路径")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取QCI文件失败: {str(e)}")


class LogSettingsDialog(QDialog):
    """日志设置对话框"""
    
    def __init__(self, parent=None, debug_logger=None):
        super().__init__(parent)
        self.debug_logger = debug_logger
        self.setWindowTitle("调试日志设置")
        self.setModal(True)
        self.resize(500, 200)
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 说明标签
        info_label = QLabel("设置调试日志文件路径，用于记录TGA文件删除和VMT参数对齐的详细信息：")
        info_label.setStyleSheet("color: #ffffff; font-weight: bold; margin-bottom: 8px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 文件路径选择
        path_layout = QHBoxLayout()
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择日志文件保存路径...")
        if self.debug_logger and self.debug_logger.log_file_path:
            self.path_edit.setText(self.debug_logger.log_file_path)
        path_layout.addWidget(self.path_edit)
        
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_log_path)
        path_layout.addWidget(browse_btn)
        
        layout.addLayout(path_layout)
        
        # 状态显示
        self.status_label = QLabel()
        self.update_status_label()
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        enable_btn = QPushButton("启用日志")
        enable_btn.clicked.connect(self.enable_logging)
        button_layout.addWidget(enable_btn)
        
        disable_btn = QPushButton("禁用日志")
        disable_btn.clicked.connect(self.disable_logging)
        button_layout.addWidget(disable_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def update_status_label(self):
        """更新状态标签"""
        if self.debug_logger and self.debug_logger.enabled:
            self.status_label.setText(f"状态: 已启用 - 日志文件: {self.debug_logger.log_file_path}")
            self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        else:
            self.status_label.setText("状态: 未启用")
            self.status_label.setStyleSheet("color: #ff6666; font-weight: bold;")
            
    def browse_log_path(self):
        """浏览日志文件路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择日志文件保存路径",
            "vtf_debug.log",
            "日志文件 (*.log);;所有文件 (*.*)"
        )
        if file_path:
            self.path_edit.setText(file_path)
            
    def enable_logging(self):
        """启用日志记录"""
        log_path = self.path_edit.text().strip()
        if not log_path:
            QMessageBox.warning(self, "警告", "请先选择日志文件路径")
            return
            
        if self.debug_logger:
            if self.debug_logger.setup_logger(log_path):
                QMessageBox.information(self, "成功", "日志记录已启用")
                self.update_status_label()
            else:
                QMessageBox.critical(self, "错误", "启用日志记录失败")
                
    def disable_logging(self):
        """禁用日志记录"""
        if self.debug_logger:
            self.debug_logger.close()
            QMessageBox.information(self, "成功", "日志记录已禁用")
            self.update_status_label()


class VTFMaterialTool(QMainWindow):
    """VTF材质工具主窗口"""
    
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.processing_thread = None
        self.debug_logger = DebugLogger()
        self.setup_ui()
        self.setup_style()
        self.restore_settings()
        
    def setup_ui(self):
        self.setWindowTitle("VTF材质工具 v1.0 - PySide6版本")
        self.setMinimumSize(800, 600)
        # 设置默认窗口大小和位置，避免遮挡左侧内容
        self.resize(1200, 800)
        # 将窗口移动到屏幕中央偏右的位置
        screen = QApplication.primaryScreen().geometry()
        x = max(100, (screen.width() - 1200) // 2)
        y = max(50, (screen.height() - 800) // 2)
        self.move(x, y)
        
        # 创建菜单栏
        self.setup_menu_bar()
        
        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标题区域
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        
        # 上边框线
        top_line = QFrame()
        top_line.setFrameShape(QFrame.Shape.HLine)
        top_line.setStyleSheet("QFrame { color: #404040; background-color: #404040; height: 1px; }")
        title_layout.addWidget(top_line)
        
        # 标题
        title_label = QLabel("VTF材质工具")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 27px;
                font-weight: bold;
                color: #ffffff;
                background-color: #2b2b2b;
                padding: 9px 0px;
            }
        """)
        title_layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel("整合VTF转换的一站式工具")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #cccccc;
                background-color: #2b2b2b;
                padding: 3px 0px;
            }
        """)
        title_layout.addWidget(subtitle_label)
        
        # 下边框线
        bottom_line = QFrame()
        bottom_line.setFrameShape(QFrame.Shape.HLine)
        bottom_line.setStyleSheet("QFrame { color: #404040; background-color: #404040; height: 1px; }")
        title_layout.addWidget(bottom_line)
        
        layout.addWidget(title_widget)
        
        # 状态栏（需要先创建，因为选项卡需要使用）
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_bar.showMessage("就绪")
        
        # 选项卡
        self.tab_widget = QTabWidget()
        
        # 夜光效果处理选项卡
        self.nightglow_tab = NightglowTab(self.config, self.debug_logger)
        self.tab_widget.addTab(self.nightglow_tab, "夜光效果处理")
        
        # 材质配置生成选项卡
        self.material_tab = MaterialConfigTab(self.config, self.status_bar)
        self.tab_widget.addTab(self.material_tab, "材质配置生成")
        
        # 静态图像调整选项卡
        self.resize_tab = ResizeTab(self.config, self.status_bar)
        self.tab_widget.addTab(self.resize_tab, "静态图像调整")
        
        # PBR贴图处理选项卡
        self.pbr_tab = PBRTextureTab(self.config, self.status_bar)
        self.tab_widget.addTab(self.pbr_tab, "PBR贴图处理")
        
        # L4D2 PBR转换选项卡
        self.l4d2_tab = L4D2ConversionTab(self.config, self.status_bar)
        self.tab_widget.addTab(self.l4d2_tab, "L4D2 PBR转换")
        
        layout.addWidget(self.tab_widget)
        
    def setup_menu_bar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 调试菜单
        debug_menu = menubar.addMenu('调试')
        
        # 日志设置动作
        log_action = QAction('日志设置', self)
        log_action.triggered.connect(self.show_log_settings)
        debug_menu.addAction(log_action)
        
        # 打开日志文件动作
        open_log_action = QAction('打开日志文件', self)
        open_log_action.triggered.connect(self.open_log_file)
        debug_menu.addAction(open_log_action)
        
    def show_log_settings(self):
        """显示日志设置对话框"""
        dialog = LogSettingsDialog(self, self.debug_logger)
        dialog.exec()
        
    def open_log_file(self):
        """打开日志文件"""
        if self.debug_logger.log_file_path and Path(self.debug_logger.log_file_path).exists():
            try:
                import subprocess
                subprocess.run(['notepad.exe', self.debug_logger.log_file_path], check=False)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开日志文件: {str(e)}")
        else:
            QMessageBox.information(self, "提示", "日志文件不存在或未设置日志路径")
        
    def setup_style(self):
        """设置深色主题样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                padding: 0px;
                margin: 0px;
                spacing: 0px;
            }
            
            QMenuBar::item {
                background-color: transparent;
                padding: 2px 8px;
                margin: 0px;
            }
            
            QMenuBar::item:selected {
                background-color: #404040;
            }
            
            QMenu {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #606060;
            }
            
            QMenu::item {
                padding: 4px 16px;
            }
            
            QMenu::item:selected {
                background-color: #0078d4;
            }
            
            QTabWidget::pane {
                border: 1px solid #404040;
                background-color: #2b2b2b;
            }
            
            QTabBar::tab {
                background-color: #404040;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #2b2b2b;
                border-bottom: 2px solid #0078d4;
            }
            
            QTabBar::tab:hover {
                background-color: #505050;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #353535;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }
            
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
            }
            
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            
            QLineEdit {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
            
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            
            QTextEdit {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px;
            }
            
            QListWidget {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #505050;
            }
            
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            
            QCheckBox::indicator:unchecked {
                border: 2px solid #606060;
                background-color: #404040;
                border-radius: 3px;
            }
            
            QCheckBox::indicator:checked {
                border: 2px solid #0078d4;
                background-color: #0078d4;
                border-radius: 3px;
            }
            
            QRadioButton {
                color: #ffffff;
                spacing: 8px;
            }
            
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            
            QRadioButton::indicator:unchecked {
                border: 2px solid #606060;
                background-color: #404040;
                border-radius: 8px;
            }
            
            QRadioButton::indicator:checked {
                border: 2px solid #0078d4;
                background-color: #0078d4;
                border-radius: 8px;
            }
            
            QScrollArea {
                border: none;
                background-color: #2b2b2b;
            }
            
            QScrollBar:vertical {
                background-color: #404040;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #606060;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #707070;
            }
            
            QStatusBar {
                background-color: #404040;
                color: #ffffff;
                border-top: 1px solid #606060;
            }
            
            QProgressBar {
                border: 1px solid #606060;
                border-radius: 4px;
                text-align: center;
                background-color: #404040;
                color: #ffffff;
                height: 20px;
            }
            
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0078d4, stop:1 #106ebe);
                border-radius: 3px;
                margin: 1px;
            }
            
            QSlider::groove:horizontal {
                border: 2px solid #a0a0a0;
                height: 12px;
                background-color: #000000;
                border-radius: 6px;
            }
            
            QSlider::handle:horizontal {
                background-color: #0078d4;
                border: 2px solid #ffffff;
                width: 18px;
                height: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }
            
            QSlider::handle:horizontal:hover {
                background-color: #106ebe;
                border: 2px solid #ffffff;
            }
            
            QSlider::handle:horizontal:pressed {
                background-color: #005a9e;
                border: 2px solid #ffffff;
            }
            
            QSlider::sub-page:horizontal {
                background-color: #00aaff;
                border-radius: 6px;
                height: 12px;
            }
            
            QSlider::add-page:horizontal {
                background-color: #cccccc;
                border-radius: 6px;
                height: 12px;
            }
            
            QSpinBox {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
                min-width: 60px;
            }
            
            QSpinBox:focus {
                border: 2px solid #0078d4;
            }
            
            QSpinBox::up-button {
                background-color: #505050;
                border: none;
                border-radius: 2px;
                width: 16px;
            }
            
            QSpinBox::up-button:hover {
                background-color: #0078d4;
            }
            
            QSpinBox::down-button {
                background-color: #505050;
                border: none;
                border-radius: 2px;
                width: 16px;
            }
            
            QSpinBox::down-button:hover {
                background-color: #0078d4;
            }
        """)
        
    def restore_settings(self):
        """恢复窗口设置"""
        geometry = self.config.get("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        state = self.config.get("window_state")
        if state:
            self.restoreState(state)
        
        # 恢复自动法线贴图设置
        if hasattr(self, 'auto_normal_checkbox'):
            auto_normal_enabled = self.config.get("auto_normal_enabled", False)
            if isinstance(auto_normal_enabled, str):
                auto_normal_enabled = auto_normal_enabled.lower() == 'true'
            self.auto_normal_checkbox.setChecked(auto_normal_enabled)
        
        if hasattr(self, 'normal_threshold_spinbox'):
            normal_threshold = self.config.get("normal_threshold", 50)
            try:
                normal_threshold = int(normal_threshold)
            except (ValueError, TypeError):
                normal_threshold = 50
            self.normal_threshold_spinbox.setValue(normal_threshold)
            
    def closeEvent(self, event):
        """关闭事件"""
        # 保存窗口设置
        self.config.set("window_geometry", self.saveGeometry())
        self.config.set("window_state", self.saveState())
        
        # 保存自动法线贴图设置
        if hasattr(self, 'auto_normal_checkbox'):
            self.config.set("auto_normal_enabled", self.auto_normal_checkbox.isChecked())
        if hasattr(self, 'normal_threshold_spinbox'):
            self.config.set("normal_threshold", self.normal_threshold_spinbox.value())
        
        self.config.sync()
        
        # 停止处理线程
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel()
            self.processing_thread.wait(3000)  # 等待3秒
            
        event.accept()





class PresetManagerDialog(QDialog):
    """预设管理对话框"""
    
    def __init__(self, parent=None, title="预设管理", current_presets=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 400)
        
        # 当前预设列表
        self.presets = list(current_presets.keys()) if current_presets else []
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QListWidget {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            
            QLineEdit {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px;
            }
            
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
            }
            
            QPushButton#remove_btn {
                background-color: #dc3545;
            }
            
            QPushButton#remove_btn:hover {
                background-color: #c82333;
            }
            
            QPushButton#cancel_btn {
                background-color: #666666;
            }
            
            QPushButton#cancel_btn:hover {
                background-color: #777777;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 说明标签
        info_label = QLabel("管理预设屏蔽词列表：")
        info_label.setStyleSheet("color: #ffffff; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(info_label)
        
        # 预设列表
        self.preset_list = QListWidget()
        self.preset_list.addItems(self.presets)
        layout.addWidget(self.preset_list)
        
        # 添加新预设
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("添加新预设:"))
        
        self.new_preset_edit = QLineEdit()
        self.new_preset_edit.setPlaceholderText("输入新的屏蔽词")
        add_layout.addWidget(self.new_preset_edit)
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_preset)
        add_layout.addWidget(add_btn)
        
        layout.addLayout(add_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        remove_btn = QPushButton("删除选中")
        remove_btn.setObjectName("remove_btn")
        remove_btn.clicked.connect(self.remove_selected)
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        
        # 确定和取消按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # 连接回车键添加预设
        self.new_preset_edit.returnPressed.connect(self.add_preset)
        
    def add_preset(self):
        """添加新预设"""
        text = self.new_preset_edit.text().strip()
        if text and text not in self.presets:
            self.presets.append(text)
            self.preset_list.addItem(text)
            self.new_preset_edit.clear()
        elif text in self.presets:
            QMessageBox.warning(self, "警告", "该预设已存在")
    
    def remove_selected(self):
        """删除选中的预设"""
        current_item = self.preset_list.currentItem()
        if current_item:
            text = current_item.text()
            self.presets.remove(text)
            self.preset_list.takeItem(self.preset_list.row(current_item))
    
    def get_presets(self):
        """获取当前预设列表"""
        return self.presets


class PresetManagerDialog(QDialog):
    """预设管理对话框"""
    
    def __init__(self, parent=None, presets=None, title="预设管理"):
        super().__init__(parent)
        self.presets = presets.copy() if presets else []
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 500)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QLabel {
                color: #ffffff;
            }
            
            QListWidget {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            
            QLineEdit {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px;
            }
            
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
            }
            
            QPushButton#remove_btn {
                background-color: #dc3545;
            }
            
            QPushButton#remove_btn:hover {
                background-color: #c82333;
            }
            
            QPushButton#cancel_btn {
                background-color: #666666;
            }
            
            QPushButton#cancel_btn:hover {
                background-color: #777777;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 说明标签
        info_label = QLabel("管理预设屏蔽词列表：")
        info_label.setStyleSheet("color: #ffffff; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(info_label)
        
        # 预设列表
        self.preset_list = QListWidget()
        self.preset_list.addItems(self.presets)
        layout.addWidget(self.preset_list)
        
        # 添加新预设
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("添加新预设:"))
        
        self.new_preset_edit = QLineEdit()
        self.new_preset_edit.setPlaceholderText("输入新的屏蔽词")
        add_layout.addWidget(self.new_preset_edit)
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_preset)
        add_layout.addWidget(add_btn)
        
        layout.addLayout(add_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        remove_btn = QPushButton("删除选中")
        remove_btn.setObjectName("remove_btn")
        remove_btn.clicked.connect(self.remove_selected)
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        
        # 确定和取消按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # 连接回车键添加预设
        self.new_preset_edit.returnPressed.connect(self.add_preset)
        
    def add_preset(self):
        """添加新预设"""
        text = self.new_preset_edit.text().strip()
        if text and text not in self.presets:
            self.presets.append(text)
            self.preset_list.addItem(text)
            self.new_preset_edit.clear()
        elif text in self.presets:
            QMessageBox.warning(self, "警告", "该预设已存在")
    
    def remove_selected(self):
        """删除选中的预设"""
        current_item = self.preset_list.currentItem()
        if current_item:
            text = current_item.text()
            self.presets.remove(text)
            self.preset_list.takeItem(self.preset_list.row(current_item))
    
    def get_presets(self):
        """获取当前预设列表"""
        return self.presets


class VMTBaseEditor(QDialog):
    """VMT Base文件编辑器对话框"""
    
    def __init__(self, parent=None, content="", file_path=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle("编辑 vmt-base.vmt")
        self.setModal(True)
        self.resize(800, 600)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QPlainTextEdit {
                background-color: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                padding: 8px;
            }
            
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
            }
            
            QPushButton#cancel_btn {
                background-color: #666666;
            }
            
            QPushButton#cancel_btn:hover {
                background-color: #777777;
            }
        """)
        
        self.setup_ui(content)
        
    def setup_ui(self, content):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 说明标签
        info_label = QLabel("编辑 vmt-base.vmt 文件内容：")
        info_label.setStyleSheet("color: #ffffff; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(info_label)
        
        # 文件路径显示
        if self.file_path:
            path_label = QLabel(f"文件路径: {self.file_path}")
            path_label.setStyleSheet("color: #cccccc; font-size: 9pt; margin-bottom: 8px;")
            layout.addWidget(path_label)
        
        # 文本编辑器
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(content)
        layout.addWidget(self.text_edit)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_file)
        button_layout.addWidget(save_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
    def save_file(self):
        """保存文件"""
        try:
            content = self.text_edit.toPlainText()
            
            if self.file_path:
                # 确保目录存在
                Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
                
                # 保存文件
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                QMessageBox.information(self, "成功", f"文件已保存到:\n{self.file_path}")
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "文件路径无效")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存文件失败:\n{str(e)}")


class PBRTextureTab(QWidget):
    """PBR贴图处理标签页"""
    
    def __init__(self, config: ConfigManager, status_bar: QStatusBar):
        super().__init__()
        self.config = config
        self.status_bar = status_bar
        self.batch_files = []
        self.current_input_file = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # 设置分割器样式，去除边框和分割线
        splitter.setStyleSheet("""
            QSplitter {
                border: none;
                background: transparent;
            }
            QSplitter::handle {
                background: transparent;
                width: 1px;
            }
        """)
        layout.addWidget(splitter)
        
        # 左侧控制面板
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧预览面板
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割器比例 - 优化小窗口显示
        splitter.setStretchFactor(0, 1)  # 左侧面板可适度拉伸
        splitter.setStretchFactor(1, 2)  # 右侧面板拉伸比例为2
        splitter.setSizes([500, 600])  # 调整初始比例，左侧占更多空间
        splitter.setCollapsible(0, False)  # 左侧面板不可折叠
        splitter.setCollapsible(1, False)  # 右侧面板不可折叠
        
        # 初始化预设下拉框
        self.refresh_preset_combo()
        
    def create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # 去除滚动区域边框，解决黑线问题
        scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("PBR贴图处理工具")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # 输入文件选择
        input_group = QGroupBox("输入文件")
        input_layout = QVBoxLayout(input_group)
        
        # 文件选择按钮
        buttons_layout = QHBoxLayout()
        
        self.select_input_btn = QPushButton("选择单个文件")
        self.select_input_btn.clicked.connect(self.select_input_file)
        buttons_layout.addWidget(self.select_input_btn)
        
        self.select_batch_btn = QPushButton("批量选择")
        self.select_batch_btn.clicked.connect(self.select_batch_files)
        buttons_layout.addWidget(self.select_batch_btn)
        
        input_layout.addLayout(buttons_layout)
        
        # 文件列表显示
        self.file_list_label = QLabel("未选择文件")
        self.file_list_label.setWordWrap(True)
        self.file_list_label.setMaximumHeight(80)
        self.file_list_label.setStyleSheet("QLabel { background-color: #3c3c3c; color: #cccccc; padding: 8px; border-radius: 4px; border: 1px solid #555; }")
        input_layout.addWidget(self.file_list_label)
        
        layout.addWidget(input_group)
        
        # 通道映射配置
        self.mapping_widget = self.create_channel_mapping_widget()
        layout.addWidget(self.mapping_widget)
        
        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout(output_group)
        
        self.output_dir_label = QLabel("输出目录: 未选择")
        output_layout.addWidget(self.output_dir_label)
        
        self.select_output_btn = QPushButton("选择输出目录")
        self.select_output_btn.clicked.connect(self.select_output_dir)
        output_layout.addWidget(self.select_output_btn)
        
        # 输出格式选择
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "TGA", "JPG"])
        format_layout.addWidget(self.format_combo)
        
        output_layout.addLayout(format_layout)
        
        layout.addWidget(output_group)
        
        # 处理按钮
        self.process_btn = QPushButton("开始处理")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.process_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.process_btn)
        
        layout.addStretch()
        
        scroll_area.setWidget(panel)
        scroll_area.setMinimumWidth(480)  # 设置最小宽度确保控件不被挤压
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
        
        # 创建通道预览
        self.channel_previews = {}
        channel_names = ["红色通道", "绿色通道", "蓝色通道"]
        
        for i, name in enumerate(channel_names):
            preview = QLabel(name)
            preview.setMaximumSize(250, 250)
            preview.setMinimumSize(200, 200)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setStyleSheet("QLabel { border: 1px solid #555; background-color: #3c3c3c; color: #cccccc; }")
            self.channel_previews[name] = preview
            channels_layout.addWidget(preview, 0, i)
        
        self.tab_widget.addTab(channels_tab, "通道预览")
        
        # 输出预览标签页
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        
        output_layout.addStretch()
        
        output_h_layout = QHBoxLayout()
        output_h_layout.addStretch()
        
        self.output_preview = QLabel("MRAO输出")
        self.output_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_preview.setMinimumSize(300, 300)
        self.output_preview.setMaximumSize(400, 400)
        self.output_preview.setStyleSheet("QLabel { border: 1px solid #555; background-color: #3c3c3c; color: #cccccc; }")
        output_h_layout.addWidget(self.output_preview)
        
        output_h_layout.addStretch()
        output_layout.addLayout(output_h_layout)
        
        output_layout.addStretch()
        
        self.tab_widget.addTab(output_tab, "输出预览")
        
        # 批量预览标签页
        self.batch_tab = QWidget()
        batch_layout = QVBoxLayout(self.batch_tab)
        
        # 创建滚动区域用于批量预览
        self.batch_scroll_area = QScrollArea()
        self.batch_scroll_area.setWidgetResizable(True)
        self.batch_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.batch_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
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
        
    def create_channel_mapping_widget(self) -> QWidget:
        """创建通道映射配置组件"""
        group = QGroupBox("通道映射规则")
        layout = QVBoxLayout(group)
        
        # 通道映射配置
        mapping_group = QGroupBox("MRA通道配置")
        mapping_layout = QGridLayout(mapping_group)
        
        channels = [
            ("M (金属度)", "metallic"),
            ("R (粗糙度)", "roughness"),
            ("AO (环境光遮蔽)", "ao")
        ]
        
        self.channel_combos = {}
        
        for i, (label, key) in enumerate(channels):
            mapping_layout.addWidget(QLabel(label), i, 0)
            
            source_combo = QComboBox()
            source_combo.addItems(["红色通道", "绿色通道", "蓝色通道", "Alpha通道", "灰度", "白色", "黑色"])
            mapping_layout.addWidget(QLabel("来源:"), i, 1)
            mapping_layout.addWidget(source_combo, i, 2)
            
            invert_check = QCheckBox("反转")
            mapping_layout.addWidget(invert_check, i, 3)
            
            self.channel_combos[key] = {
                'source': source_combo,
                'invert': invert_check
            }
            
            # 连接信号以更新预览
            source_combo.currentTextChanged.connect(self.update_all_previews)
            invert_check.toggled.connect(self.update_all_previews)
        
        layout.addWidget(mapping_group)
        
        # 预设配置
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设:"))
        
        self.preset_combo = QComboBox()
        self.load_presets()  # 加载预设
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        preset_layout.addWidget(self.preset_combo)
        
        # 预设保存/删除按钮
        save_preset_btn = QPushButton("保存预设")
        save_preset_btn.clicked.connect(self.save_custom_preset)
        preset_layout.addWidget(save_preset_btn)
        
        delete_preset_btn = QPushButton("删除预设")
        delete_preset_btn.clicked.connect(self.delete_custom_preset)
        preset_layout.addWidget(delete_preset_btn)
        
        layout.addLayout(preset_layout)
        
        return group
        
    def select_input_file(self):
        """选择单个输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PBR贴图文件", "",
            "图像文件 (*.png *.tga *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.current_input_file = file_path
            self.batch_files = []
            self.file_list_label.setText(f"单个文件: {Path(file_path).name}")
            # 隐藏批量预览标签页
            if hasattr(self, 'batch_tab'):
                self.tab_widget.setTabVisible(2, False)
            self.update_previews()
            
    def select_batch_files(self):
        """选择批量文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择PBR贴图文件", "",
            "图像文件 (*.png *.tga *.jpg *.jpeg *.bmp)"
        )
        if file_paths:
            self.batch_files = file_paths
            self.current_input_file = None
            file_names = [Path(f).name for f in file_paths[:3]]
            if len(file_paths) > 3:
                file_names.append(f"... 等{len(file_paths)}个文件")
            self.file_list_label.setText(f"批量文件: {', '.join(file_names)}")
            # 更新批量预览
            self.update_batch_previews()
            
    def select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_label.setText(f"输出目录: {dir_path}")
            
    def apply_preset(self, preset_name):
        """应用预设配置"""
        # 如果预设名称为空，直接返回
        if not preset_name or preset_name.strip() == "":
            return
        
        # 临时断开信号连接，避免在设置过程中触发多次更新
        for channel, widgets in self.channel_combos.items():
            try:
                widgets['source'].currentTextChanged.disconnect(self.update_all_previews)
                widgets['invert'].toggled.disconnect(self.update_all_previews)
            except:
                pass  # 如果信号未连接，忽略错误
        
        if preset_name == "标准PBR (M=B, R=G, AO=R)":
            self.channel_combos['metallic']['source'].setCurrentText("蓝色通道")
            self.channel_combos['roughness']['source'].setCurrentText("绿色通道")
            self.channel_combos['ao']['source'].setCurrentText("红色通道")
        elif preset_name == "Unity标准 (M=R, R=G, AO=B)":
            self.channel_combos['metallic']['source'].setCurrentText("红色通道")
            self.channel_combos['roughness']['source'].setCurrentText("绿色通道")
            self.channel_combos['ao']['source'].setCurrentText("蓝色通道")
        elif preset_name == "UE4标准 (M=B, R=G, AO=R)":
            self.channel_combos['metallic']['source'].setCurrentText("蓝色通道")
            self.channel_combos['roughness']['source'].setCurrentText("绿色通道")
            self.channel_combos['ao']['source'].setCurrentText("红色通道")
        elif preset_name.startswith("[自定义]"):
            # 自定义预设
            actual_name = preset_name.replace("[自定义] ", "")
            presets_file = Path("presets.json")
            
            if presets_file.exists():
                try:
                    import json
                    with open(presets_file, 'r', encoding='utf-8') as f:
                        custom_presets = json.load(f)
                    
                    if actual_name in custom_presets:
                        preset = custom_presets[actual_name]
                        # 重置所有反转状态
                        for channel in self.channel_combos:
                            self.channel_combos[channel]['invert'].setChecked(False)
                        
                        # 应用预设配置
                        for channel, config in preset.items():
                            if channel in self.channel_combos:
                                self.channel_combos[channel]['source'].setCurrentText(config['source'])
                                self.channel_combos[channel]['invert'].setChecked(config['invert'])
                                
                except Exception as e:
                    print(f"加载自定义预设失败: {e}")
        
        # 重新连接信号
        for channel, widgets in self.channel_combos.items():
            widgets['source'].currentTextChanged.connect(self.update_all_previews)
            widgets['invert'].toggled.connect(self.update_all_previews)
        
        # 应用预设后更新所有预览
        if preset_name != "自定义":
            self.update_all_previews()
        else:
            # 如果选择了"自定义"，不做任何配置更改，保持当前设置
            pass
            
    def load_presets(self):
        """加载预设配置"""
        # 临时断开信号连接，避免在加载过程中触发apply_preset
        try:
            self.preset_combo.currentTextChanged.disconnect()
        except:
            pass
        
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
                import json
                with open(presets_file, 'r', encoding='utf-8') as f:
                    custom_presets = json.load(f)
                    for preset_name in custom_presets.keys():
                        display_name = f"[自定义] {preset_name}"
                        self.preset_combo.addItem(display_name)
            except Exception as e:
                print(f"加载自定义预设失败: {e}")
        
        # 重新连接信号
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
                
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
                    import json
                    with open(presets_file, 'r', encoding='utf-8') as f:
                        custom_presets = json.load(f)
                except Exception as e:
                    print(f"读取预设文件失败: {e}")
            
            # 保存新预设
            custom_presets[preset_name] = current_config
            
            try:
                import json
                with open(presets_file, 'w', encoding='utf-8') as f:
                    json.dump(custom_presets, f, ensure_ascii=False, indent=2)
                
                # 重新加载预设列表
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
        
        if not current_preset.startswith("[自定义] "):
            QMessageBox.information(self, "提示", "只能删除自定义预设")
            return
        
        preset_name = current_preset.replace("[自定义] ", "")
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除预设 '{preset_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            presets_file = Path("presets.json")
            
            if presets_file.exists():
                try:
                    import json
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
            
    def update_previews(self):
        """更新预览"""
        if self.current_input_file:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(self.current_input_file)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 更新通道预览
                channels = img.split()
                channel_names = ["红色通道", "绿色通道", "蓝色通道"]
                
                for i, name in enumerate(channel_names):
                    if i < len(channels):
                        channel_img = channels[i]
                        # 转换为QPixmap并显示
                        from PySide6.QtGui import QPixmap
                        from PIL.ImageQt import ImageQt
                        qimg = ImageQt(channel_img)
                        pixmap = QPixmap.fromImage(qimg)
                        scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.channel_previews[name].setPixmap(scaled_pixmap)
                
                # 更新输出预览
                self.update_single_output_preview()
                        
            except Exception as e:
                self.status_bar.showMessage(f"预览更新失败: {str(e)}")
                
    def update_single_output_preview(self):
        """更新单个文件的输出预览"""
        if not self.current_input_file:
            return
            
        try:
            from PIL import Image as PILImage
            from PIL.ImageQt import ImageQt
            from PySide6.QtGui import QPixmap
            import numpy as np
            
            # 加载输入图像
            image = PILImage.open(self.current_input_file)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 获取当前映射配置
            mapping_config = self.get_mapping_config()
            
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
            
            preview_image = PILImage.fromarray(preview_array, mode='RGB')
            qt_image = ImageQt(preview_image)
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            self.output_preview.setPixmap(scaled_pixmap)
            
        except Exception as e:
            print(f"更新单个输出预览失败: {e}")
                
    def start_processing(self):
        """开始处理"""
        if not (self.current_input_file or self.batch_files):
            QMessageBox.warning(self, "警告", "请先选择输入文件")
            return
            
        if "未选择" in self.output_dir_label.text():
            QMessageBox.warning(self, "警告", "请先选择输出目录")
            return
            
        # 获取输出目录
        output_dir = self.output_dir_label.text().replace("输出目录: ", "")
        
        # 获取映射配置
        mapping_config = self.get_mapping_config()
        
        # 禁用处理按钮
        self.process_btn.setEnabled(False)
        self.status_bar.showMessage("开始处理PBR贴图...")
        
        try:
            # 判断是单个文件还是批量处理
            if self.batch_files and len(self.batch_files) > 0:
                # 批量处理
                self.process_batch_files(self.batch_files, mapping_config, output_dir)
            else:
                # 单个文件处理
                if self.current_input_file:
                    self.process_single_file(self.current_input_file, mapping_config, output_dir)
                    
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")
        finally:
            # 重新启用处理按钮
            self.process_btn.setEnabled(True)
            self.status_bar.showMessage("就绪")
        
    def create_batch_preview_group(self, image_path: str, index: int) -> QWidget:
        """创建单个批量预览组（包含图像名称、RGB通道和输出结果）"""
        from pathlib import Path
        
        group = QGroupBox(f"图像 {index + 1}: {Path(image_path).name}")
        group_layout = QGridLayout(group)
        group_layout.setSpacing(10)
        
        # 存储文件路径到组件属性中
        group.file_path = image_path
        
        # 创建预览组件
        previews = {}
        
        # RGB通道预览
        channel_names = ["红色通道", "绿色通道", "蓝色通道"]
        for i, name in enumerate(channel_names):
            preview = QLabel(name)
            preview.setMaximumSize(180, 180)
            preview.setMinimumSize(150, 150)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setStyleSheet("QLabel { border: 1px solid #555; background-color: #3c3c3c; color: #cccccc; }")
            previews[name] = preview
            group_layout.addWidget(preview, 0, i)
        
        # 输出结果预览
        output_preview = QLabel("MRAO输出")
        output_preview.setMaximumSize(180, 180)
        output_preview.setMinimumSize(150, 150)
        output_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        output_preview.setStyleSheet("QLabel { border: 1px solid #555; background-color: #3c3c3c; color: #cccccc; }")
        output_preview.setObjectName('output_preview')  # 设置对象名称以便查找
        previews["输出"] = output_preview
        group_layout.addWidget(output_preview, 0, 3)
        
        # 更新预览内容
        self.update_batch_preview_content(image_path, previews)
        
        return group
        
    def update_batch_preview_content(self, image_path: str, previews: dict):
        """更新批量预览内容"""
        try:
            from PIL import Image as PILImage
            from PIL.ImageQt import ImageQt
            from PySide6.QtGui import QPixmap
            import numpy as np
            
            # 加载图像
            image = PILImage.open(image_path)
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
                    channel_image = PILImage.fromarray(channel_data, mode='L')
                    qt_image = ImageQt(channel_image)
                    pixmap = QPixmap.fromImage(qt_image)
                    scaled_pixmap = pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    previews[name].setPixmap(scaled_pixmap)
            
            # 更新输出预览
            self.update_batch_output_preview(image_path, previews["输出"])
            
        except Exception as e:
            print(f"更新批量预览失败: {e}")
            
    def update_batch_output_preview(self, image_path: str, output_preview: QLabel):
        """更新批量输出预览"""
        try:
            from PIL import Image as PILImage
            from PIL.ImageQt import ImageQt
            from PySide6.QtGui import QPixmap
            import numpy as np
            
            # 加载输入图像
            image = PILImage.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 获取当前映射配置
            mapping_config = self.get_mapping_config()
            
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
            
            preview_image = PILImage.fromarray(preview_array, mode='RGB')
            qt_image = ImageQt(preview_image)
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            output_preview.setPixmap(scaled_pixmap)
            
        except Exception as e:
            print(f"更新批量输出预览失败: {e}")
            
    def get_mapping_config(self) -> dict:
        """获取当前通道映射配置"""
        config = {}
        for key, combos in self.channel_combos.items():
            config[key] = {
                'source': combos['source'].currentText(),
                'invert': combos['invert'].isChecked()
            }
        return config
        
    def update_batch_previews(self):
        """更新批量预览显示状态"""
        try:
            if hasattr(self, 'batch_files') and self.batch_files:
                # 显示批量预览标签页
                if hasattr(self, 'batch_tab'):
                    self.tab_widget.setTabVisible(2, True)
                    
                # 清空现有预览
                if hasattr(self, 'batch_preview_container'):
                    # 清除所有子组件
                    for i in reversed(range(self.batch_preview_layout.count())):
                        child = self.batch_preview_layout.itemAt(i)
                        if child.widget():
                            child.widget().deleteLater()
                        elif child.layout():
                            self.clear_layout(child.layout())
                    
                    # 为每个文件创建预览组
                    for index, file_path in enumerate(self.batch_files):
                        preview_group = self.create_batch_preview_group(file_path, index)
                        self.batch_preview_layout.addWidget(preview_group)
                        
                    # 添加弹性空间
                    self.batch_preview_layout.addStretch()
            else:
                # 隐藏批量预览标签页
                if hasattr(self, 'batch_tab'):
                    self.tab_widget.setTabVisible(2, False)
                    
        except Exception as e:
            print(f"更新批量预览显示失败: {e}")
            
    def clear_layout(self, layout):
        """递归清空布局"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())
                
    def update_all_batch_previews(self):
        """更新所有批量预览（当配置改变时调用）"""
        try:
            if hasattr(self, 'batch_files') and self.batch_files and hasattr(self, 'batch_preview_container'):
                # 遍历所有批量预览组，更新输出预览
                for i in range(self.batch_preview_layout.count()):
                    item = self.batch_preview_layout.itemAt(i)
                    if item and item.widget():
                        group_widget = item.widget()
                        if hasattr(group_widget, 'layout') and group_widget.layout() and hasattr(group_widget, 'file_path'):
                            # 查找输出预览组件（第4个位置，索引3）
                            layout = group_widget.layout()
                            if layout.count() > 3:
                                output_item = layout.itemAtPosition(0, 3)
                                if output_item and output_item.widget():
                                    output_preview = output_item.widget()
                                    if isinstance(output_preview, QLabel):
                                        # 更新输出预览
                                        self.update_batch_output_preview(group_widget.file_path, output_preview)
                                
        except Exception as e:
             print(f"更新所有批量预览失败: {e}")
             
    def update_all_previews(self):
        """更新所有预览（单个文件和批量文件）"""
        # 更新单个文件的输出预览
        if self.current_input_file:
            self.update_single_output_preview()
        
        # 更新批量预览
        self.update_all_batch_previews()
        
    def save_preset(self):
        """保存当前通道映射配置为预设"""
        try:
            # 获取当前配置
            current_config = {}
            for key, controls in self.channel_combos.items():
                current_config[key] = {
                    'source': controls['source'].currentText(),
                    'invert': controls['invert'].isChecked()
                }
            
            # 弹出对话框让用户输入预设名称
            name, ok = QInputDialog.getText(self, '保存预设', '请输入预设名称:')
            if ok and name.strip():
                # 保存到配置文件
                import json
                import os
                
                preset_file = 'presets.json'
                presets = {}
                
                # 读取现有预设
                if os.path.exists(preset_file):
                    try:
                        with open(preset_file, 'r', encoding='utf-8') as f:
                            presets = json.load(f)
                    except:
                        presets = {}
                
                # 添加新预设
                presets[name.strip()] = current_config
                
                # 保存到文件
                with open(preset_file, 'w', encoding='utf-8') as f:
                    json.dump(presets, f, ensure_ascii=False, indent=2)
                
                # 更新预设下拉框
                self.refresh_preset_combo()
                
                QMessageBox.information(self, '成功', f'预设 "{name.strip()}" 已保存')
                
        except Exception as e:
            QMessageBox.warning(self, '错误', f'保存预设失败: {e}')
    
    def load_preset(self):
        """加载预设配置"""
        try:
            import json
            import os
            
            preset_file = 'presets.json'
            if not os.path.exists(preset_file):
                QMessageBox.information(self, '提示', '没有找到预设文件')
                return
            
            # 读取预设文件
            with open(preset_file, 'r', encoding='utf-8') as f:
                presets = json.load(f)
            
            if not presets:
                QMessageBox.information(self, '提示', '没有可用的预设')
                return
            
            # 弹出对话框让用户选择预设
            preset_names = list(presets.keys())
            name, ok = QInputDialog.getItem(self, '加载预设', '请选择预设:', preset_names, 0, False)
            
            if ok and name in presets:
                config = presets[name]
                
                # 应用配置
                for key, settings in config.items():
                    if key in self.channel_combos:
                        controls = self.channel_combos[key]
                        
                        # 设置来源
                        source_index = controls['source'].findText(settings['source'])
                        if source_index >= 0:
                            controls['source'].setCurrentIndex(source_index)
                        
                        # 设置反转
                        controls['invert'].setChecked(settings['invert'])
                
                # 设置预设下拉框为自定义
                self.preset_combo.setCurrentText('自定义')
                
                QMessageBox.information(self, '成功', f'预设 "{name}" 已加载')
                
        except Exception as e:
            QMessageBox.warning(self, '错误', f'加载预设失败: {e}')
    
    def refresh_preset_combo(self):
        """刷新预设下拉框"""
        try:
            import json
            import os
            
            preset_file = 'presets.json'
            base_items = [
                "自定义",
                "标准PBR (M=B, R=G, AO=R)",
                "Unity标准 (M=R, R=G, AO=B)",
                "UE4标准 (M=B, R=G, AO=R)"
            ]
            
            items = base_items.copy()
            
            # 添加用户自定义预设
            if os.path.exists(preset_file):
                try:
                    with open(preset_file, 'r', encoding='utf-8') as f:
                        presets = json.load(f)
                    items.extend([f"[自定义] {name}" for name in presets.keys()])
                except:
                    pass
            
            # 更新下拉框
            current_text = self.preset_combo.currentText()
            self.preset_combo.clear()
            self.preset_combo.addItems(items)
            
            # 尝试恢复之前的选择
            index = self.preset_combo.findText(current_text)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
                
        except Exception as e:
             print(f"刷新预设下拉框失败: {e}")
    
    def delete_preset(self):
        """删除预设配置"""
        try:
            import json
            import os
            
            preset_file = 'presets.json'
            if not os.path.exists(preset_file):
                QMessageBox.information(self, '提示', '没有找到预设文件')
                return
            
            # 读取预设文件
            with open(preset_file, 'r', encoding='utf-8') as f:
                presets = json.load(f)
            
            if not presets:
                QMessageBox.information(self, '提示', '没有可删除的预设')
                return
            
            # 弹出对话框让用户选择要删除的预设
            preset_names = list(presets.keys())
            name, ok = QInputDialog.getItem(self, '删除预设', '请选择要删除的预设:', preset_names, 0, False)
            
            if ok and name in presets:
                # 确认删除
                reply = QMessageBox.question(self, '确认删除', f'确定要删除预设 "{name}" 吗？', 
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    # 删除预设
                    del presets[name]
                    
                    # 保存到文件
                    with open(preset_file, 'w', encoding='utf-8') as f:
                        json.dump(presets, f, ensure_ascii=False, indent=2)
                    
                    # 更新预设下拉框
                    self.refresh_preset_combo()
                    
                    QMessageBox.information(self, '成功', f'预设 "{name}" 已删除')
                    
        except Exception as e:
            QMessageBox.warning(self, '错误', f'删除预设失败: {e}')
    

    
    def process_single_file(self, input_file, mapping_config, output_dir, show_message=True):
        """处理单个文件"""
        try:
            import numpy as np
            from PIL import Image
            from pathlib import Path
            
            # 加载图像
            image = Image.open(input_file)
            
            # 转换为RGBA模式以保留所有通道
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # 转换为numpy数组
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 分离通道
            channels = {
                '红色通道': img_array[:, :, 0],
                '绿色通道': img_array[:, :, 1],
                '蓝色通道': img_array[:, :, 2],
                'Alpha通道': img_array[:, :, 3] if img_array.shape[2] > 3 else np.full((height, width), 255, dtype=np.uint8),
                '灰度': np.mean(img_array[:, :, :3], axis=2).astype(np.uint8),
                '白色': np.full((height, width), 255, dtype=np.uint8),
                '黑色': np.full((height, width), 0, dtype=np.uint8)
            }
            
            # 创建输出目录
            output_path = Path(output_dir)
            fake_pbr_dir = output_path / "Fake PBR"
            pbr_dir = output_path / "PBR"
            fake_pbr_dir.mkdir(parents=True, exist_ok=True)
            pbr_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存分离的通道 (Fake PBR)
            base_name = Path(input_file).stem
            
            # 使用与原始程序一致的命名规则
            channel_mapping = {
                '红色通道': 'R',
                '绿色通道': 'G',
                '蓝色通道': 'B',
                'Alpha通道': 'A'
            }
            
            for channel_name, channel_data in channels.items():
                if channel_name in channel_mapping:
                    channel_image = Image.fromarray(channel_data, mode='L')
                    mapped_name = channel_mapping[channel_name]
                    channel_output_path = fake_pbr_dir / f"{base_name}_{mapped_name}.png"
                    channel_image.save(channel_output_path)
            
            # 创建MRA贴图
            mra_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            # 根据映射配置填充MRA通道
            for i, channel_key in enumerate(['metallic', 'roughness', 'ao']):
                if channel_key in mapping_config:
                    source = mapping_config[channel_key]['source']
                    invert = mapping_config[channel_key]['invert']
                    
                    # 获取源数据
                    if source in channels:
                        data = channels[source].copy()
                        if invert:
                            data = 255 - data
                        mra_array[:, :, i] = data
            
            # 保存MRAO贴图（与原始程序命名一致）
            mra_image = Image.fromarray(mra_array, mode='RGB')
            mra_output_path = pbr_dir / f"{base_name}_MRAO.png"
            mra_image.save(mra_output_path)
            
            self.status_bar.showMessage(f"处理完成: {base_name}")
            # 只在单个文件处理时显示消息框，批量处理时不显示
            if show_message:
                QMessageBox.information(self, "成功", f"文件处理完成！\n输出目录: {output_dir}")
            
        except Exception as e:
            raise Exception(f"处理文件 {input_file} 时出错: {str(e)}")
    
    def process_batch_files(self, file_list, mapping_config, output_dir):
        """批量处理文件"""
        success_count = 0
        error_count = 0
        
        for i, file_path in enumerate(file_list):
            try:
                self.status_bar.showMessage(f"处理文件 {i+1}/{len(file_list)}: {Path(file_path).name}")
                self.process_single_file(file_path, mapping_config, output_dir, show_message=False)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"处理文件失败: {file_path}, 错误: {str(e)}")
        
        # 显示批量处理结果
        message = f"批量处理完成！\n成功: {success_count} 个文件\n失败: {error_count} 个文件\n输出目录: {output_dir}"
        if error_count > 0:
            QMessageBox.warning(self, "批量处理完成", message)
        else:
            QMessageBox.information(self, "批量处理完成", message)


class L4D2ConversionTab(QWidget):
    """L4D2 PBR转换标签页"""
    
    def __init__(self, config: ConfigManager, status_bar: QStatusBar):
        super().__init__()
        self.config = config
        self.status_bar = status_bar
        self.texture_paths = {}
        self.processing_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("PBR-2-L4D2 - 求生之路2专用PBR材质转换工具")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("QLabel { color: #2c3e50; margin-bottom: 10px; }")
        layout.addWidget(title)
        
        # 副标题
        subtitle = QLabel("专为Left 4 Dead 2优化的一键化PBR材质转换")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("QLabel { color: #7f8c8d; margin-bottom: 20px; }")
        layout.addWidget(subtitle)
        
        # 主要内容区域
        content_layout = QHBoxLayout()
        
        # 左侧：贴图输入
        left_panel = self.create_texture_input_panel()
        content_layout.addWidget(left_panel, 1)
        
        # 右侧：输出设置和处理
        right_panel = self.create_output_panel()
        content_layout.addWidget(right_panel, 1)
        
        layout.addLayout(content_layout)
        
        # 底部：日志区域
        self.create_log_section(layout)
        
    def create_texture_input_panel(self) -> QWidget:
        """创建贴图输入面板"""
        group = QGroupBox("贴图输入")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QGridLayout(group)
        
        textures = [
            ('albedo', '基础色 (Albedo) *', True),
            ('normal', '法线 (Normal)', False), 
            ('metallic', '金属度 (Metallic)', False),
            ('roughness', '粗糙度 (Roughness) *', True),
            ('ao', 'AO环境光遮蔽', False)
        ]
        
        self.texture_inputs = {}
        
        for i, (key, label, required) in enumerate(textures):
            # 标签
            label_widget = QLabel(label)
            if required:
                label_widget.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            layout.addWidget(label_widget, i, 0)
            
            # 输入框
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"选择{label.split('(')[0].strip()}贴图...")
            line_edit.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #bdc3c7;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QLineEdit:focus {
                    border-color: #3498db;
                }
            """)
            layout.addWidget(line_edit, i, 1)
            
            # 浏览按钮
            browse_btn = QPushButton("浏览")
            browse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            browse_btn.clicked.connect(lambda checked, k=key: self.browse_texture(k))
            layout.addWidget(browse_btn, i, 2)
            
            self.texture_inputs[key] = line_edit
        
        return group
    
    def create_output_panel(self) -> QWidget:
        """创建输出设置面板"""
        group = QGroupBox("输出设置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QVBoxLayout(group)
        
        # 输出目录
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("输出目录:"))
        
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("选择输出目录...")
        self.output_dir_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
        """)
        dir_layout.addWidget(self.output_dir_input)
        
        browse_output_btn = QPushButton("浏览")
        browse_output_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        browse_output_btn.clicked.connect(self.browse_output_dir)
        dir_layout.addWidget(browse_output_btn)
        
        layout.addLayout(dir_layout)
        
        # 材质名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("材质名称:"))
        
        self.material_name_input = QLineEdit()
        self.material_name_input.setPlaceholderText("如: weapon_ak47")
        self.material_name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
        """)
        name_layout.addWidget(self.material_name_input)
        
        layout.addLayout(name_layout)
        
        # 批量处理选项
        batch_layout = QHBoxLayout()
        
        self.batch_mode_checkbox = QCheckBox("批量处理模式")
        self.batch_mode_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #2c3e50;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #e67e22;
                background-color: #e67e22;
                border-radius: 3px;
            }
        """)
        self.batch_mode_checkbox.toggled.connect(self.on_batch_mode_toggled)
        self.batch_mode_checkbox.setVisible(False)
        batch_layout.addWidget(self.batch_mode_checkbox)
        
        # Patch格式支持开关
        self.patch_format_checkbox = QCheckBox("支持Patch格式VMT")
        self.patch_format_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #2c3e50;
                margin-left: 20px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #27ae60;
                background-color: #27ae60;
                border-radius: 3px;
            }
        """)
        self.patch_format_checkbox.setToolTip("启用后可处理patch格式的VMT文件（包含include、insert、replace语法）")
        self.patch_format_checkbox.setVisible(False)
        batch_layout.addWidget(self.patch_format_checkbox)
        
        batch_layout.addStretch()
        
        layout.addLayout(batch_layout)
        
        # 批量处理说明
        self.batch_info = QLabel("💡 批量模式：自动扫描输出目录中的所有VMT文件进行转换")
        self.batch_info.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; margin: 5px 0; }")
        self.batch_info.setVisible(False)
        layout.addWidget(self.batch_info)
        
        layout.addSpacing(20)
        
        # VMT智能融合说明
        merge_info = QLabel("💡 智能VMT融合：如果输出目录存在同名VMT文件，将自动保留自定义参数并更新PBR参数")
        merge_info.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; margin: 5px 0; }")
        merge_info.setVisible(False)
        layout.addWidget(merge_info)
        
        layout.addSpacing(10)
        
        # 处理按钮
        self.process_btn = QPushButton("🚀 一键转换为L4D2材质")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.process_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.process_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        
        return group
    
    def create_log_section(self, parent_layout):
        """创建日志区域"""
        group = QGroupBox("处理日志")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.log_text)
        
        parent_layout.addWidget(group)
        
        self.log("L4D2 PBR转换工具已就绪")
        self.log("支持的贴图类型: 基础色、法线、金属度、粗糙度、AO")
    
    def browse_texture(self, texture_type):
        """浏览贴图文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{texture_type}贴图", "", 
            "图像文件 (*.png *.tga *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.texture_inputs[texture_type].setText(file_path)
            self.texture_paths[texture_type] = file_path
            self.log(f"已选择{texture_type}贴图: {Path(file_path).name}")
    
    def browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_input.setText(dir_path)
            self.log(f"输出目录: {dir_path}")
    
    def start_processing(self):
        """开始处理"""
        if not self.output_dir_input.text():
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return
        
        # 检查是否为批量模式
        if self.batch_mode_checkbox.isChecked():
            self.start_batch_processing()
        else:
            self.start_single_processing()
    
    def start_single_processing(self):
        """开始单个材质处理"""
        # 验证必需的贴图（只有基础色和粗糙度是必需的）
        required_textures = ['albedo', 'roughness']
        missing_textures = []
        
        for texture in required_textures:
            if texture not in self.texture_paths or not self.texture_paths[texture]:
                missing_textures.append(texture)
        
        if missing_textures:
            QMessageBox.warning(self, "警告", f"请选择以下必需的贴图: {', '.join(missing_textures)}")
            return
        
        if not self.material_name_input.text():
            QMessageBox.warning(self, "警告", "请输入材质名称")
            return
        
        # 检查是否存在现有VMT文件
        output_dir = self.output_dir_input.text()
        material_name = self.material_name_input.text()
        existing_vmt_path = Path(output_dir) / f"{material_name}.vmt"
        
        if existing_vmt_path.exists():
            self.log(f"检测到现有VMT文件: {existing_vmt_path.name}")
        else:
            self.log("未检测到现有VMT文件，将生成新的VMT文件")
        
        self.log("开始L4D2 PBR材质转换...")
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动处理线程
        self.processing_thread = L4D2ProcessingThread(
            self.texture_paths,
            output_dir,
            material_name,
            str(existing_vmt_path) if existing_vmt_path.exists() else None
        )
        self.processing_thread.progress.connect(self.log)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.error.connect(self.on_processing_error)
        self.processing_thread.start()
    
    def start_batch_processing(self):
        """开始批量处理"""
        output_dir = self.output_dir_input.text()
        
        # 扫描VMT文件
        vmt_files = self.scan_vmt_files(output_dir)
        
        if not vmt_files:
            QMessageBox.warning(self, "警告", "在输出目录中未找到VMT文件")
            return
        
        self.log(f"开始批量处理 {len(vmt_files)} 个VMT文件...")
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动批量处理线程
        self.processing_thread = L4D2BatchProcessingThread(
            vmt_files,
            output_dir
        )
        self.processing_thread.progress.connect(self.log)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.error.connect(self.on_processing_error)
        self.processing_thread.start()
    
    def log(self, message: str):
        """添加日志消息"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.ensureCursorVisible()
    
    def on_processing_finished(self, success: bool, message: str):
        """处理完成回调"""
        self.process_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.log(f"✅ {message}")
            QMessageBox.information(self, "成功", message)
        else:
            self.log(f"❌ {message}")
            QMessageBox.warning(self, "处理失败", message)
    
    def on_processing_error(self, error_message: str):
        """处理错误回调"""
        self.process_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log(f"❌ 处理出错: {error_message}")
        QMessageBox.critical(self, "错误", f"处理过程中发生错误:\n{error_message}")
    
    def on_batch_mode_toggled(self, checked: bool):
        """批量模式切换"""
        self.batch_info.setVisible(checked)
        
        # 批量模式下禁用材质名称输入
        self.material_name_input.setEnabled(not checked)
        
        if checked:
            self.log("已启用批量处理模式")
            self.material_name_input.setPlaceholderText("批量模式下自动识别材质名称")
        else:
            self.log("已禁用批量处理模式")
            self.material_name_input.setPlaceholderText("如: weapon_ak47")
    
    def scan_vmt_files(self, directory: str) -> list:
        """扫描目录中的VMT文件"""
        vmt_files = []
        try:
            dir_path = Path(directory)
            for vmt_file in dir_path.glob("*.vmt"):
                if vmt_file.is_file():
                    vmt_files.append(str(vmt_file))
            
            self.log(f"扫描到 {len(vmt_files)} 个VMT文件")
            return vmt_files
            
        except Exception as e:
            self.log(f"扫描VMT文件失败: {str(e)}")
            return []
    
    def merge_vmt_files(self, original_vmt_path: str, generated_vmt_content: str) -> str:
        """融合VMT文件"""
        try:
            # 读取原始VMT文件
            with open(original_vmt_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 解析原始VMT参数
            original_params = self.parse_vmt_parameters(original_content)
            generated_params = self.parse_vmt_parameters(generated_vmt_content)
            
            # 融合参数：保留原始的自定义参数，更新PBR相关参数
            pbr_params = {
                '$basetexture', '$bumpmap', '$phong', '$phongexponent',
                '$phongexponenttexture', '$phongboost', '$phongfresnelranges',
                '$envmap', '$envmaptint', '$envmapcontrast', '$normalmapalphaenvmapmask',
                '$envmapfresnel', '$phongalbedotint', '$halflambert', '$model', '$surfaceprop'
            }
            
            # 合并参数
            merged_params = original_params.copy()
            for key, value in generated_params.items():
                if key.lower() in pbr_params:
                    merged_params[key] = value
                    
            # 生成融合后的VMT内容
            return self.generate_vmt_from_params(merged_params)
            
        except Exception as e:
            self.log(f"VMT融合失败: {str(e)}")
            return generated_vmt_content
    
    def parse_vmt_parameters(self, vmt_content: str) -> dict:
        """解析VMT参数"""
        params = {}
        lines = vmt_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('"$') and '"' in line[2:]:
                # 找到参数行
                parts = line.split('"')
                if len(parts) >= 4:
                    param_name = parts[1]
                    param_value = parts[3]
                    params[param_name] = param_value
                    
        return params
    
    def generate_vmt_from_params(self, params: dict) -> str:
        """从参数字典生成VMT内容"""
        vmt_lines = ['"VertexLitGeneric"', '{']
        
        for param_name, param_value in params.items():
            vmt_lines.append(f'\t"{param_name}"\t\t"{param_value}"')
            
        vmt_lines.append('}')
        return '\n'.join(vmt_lines)


class L4D2ProcessingThread(QThread):
    """L4D2处理线程"""
    progress = Signal(str)
    finished = Signal(bool, str)
    error = Signal(str)
    
    def __init__(self, texture_paths: dict, output_dir: str, material_name: str, existing_vmt_path: str = None):
        super().__init__()
        self.texture_paths = texture_paths
        self.output_dir = output_dir
        self.material_name = material_name
        self.existing_vmt_path = existing_vmt_path
    
    def run(self):
        try:
            self.progress.emit("正在加载贴图...")
            
            # 检查必需的贴图
            if 'albedo' not in self.texture_paths or not self.texture_paths['albedo']:
                self.error.emit("缺少必需的基础色贴图")
                return
                
            if 'roughness' not in self.texture_paths or not self.texture_paths['roughness']:
                self.error.emit("缺少必需的粗糙度贴图")
                return
            
            # 加载必需贴图
            from PIL import Image
            import numpy as np
            
            # 保持原始PNG的通道数，不强制转换为RGBA
            albedo_img = Image.open(self.texture_paths['albedo'])
            # 检查原始图像是否有透明通道
            has_alpha = albedo_img.mode in ('RGBA', 'LA') or 'transparency' in albedo_img.info
            roughness_img = Image.open(self.texture_paths['roughness']).convert('L')
            
            # 检查可选贴图并加载或生成默认值
            has_normal = 'normal' in self.texture_paths and self.texture_paths['normal']
            has_metallic = 'metallic' in self.texture_paths and self.texture_paths['metallic']
            has_ao = 'ao' in self.texture_paths and self.texture_paths['ao']
            
            if has_normal:
                normal_img = Image.open(self.texture_paths['normal']).convert('RGB')
            else:
                self.progress.emit("法线贴图缺失，生成默认法线贴图")
                normal_img = PBRSourceAlgorithms.generate_default_normal(albedo_img.size)
            
            if has_metallic:
                metallic_img = Image.open(self.texture_paths['metallic']).convert('L')
            else:
                self.progress.emit("金属度贴图缺失，生成默认金属度贴图")
                metallic_img = PBRSourceAlgorithms.generate_default_metallic(albedo_img.size)
            
            if has_ao:
                ao_img = Image.open(self.texture_paths['ao']).convert('L')
            else:
                self.progress.emit("AO贴图缺失，生成默认AO贴图")
                ao_img = PBRSourceAlgorithms.generate_default_ao(albedo_img.size)
            
            self.progress.emit("正在处理PBR材质...")
            
            # 使用PBR-2-Source算法生成HL2 Phong+Envmap+alpha模式贴图
            self.progress.emit("生成Phong指数贴图...")
            phong_exponent_img = PBRSourceAlgorithms.make_phong_exponent(roughness_img)
            
            self.progress.emit("生成Phong遮罩...")
            phong_mask_img = PBRSourceAlgorithms.make_phong_mask(roughness_img, ao_img)
            
            self.progress.emit("生成环境贴图遮罩...")
            envmap_mask_img = PBRSourceAlgorithms.make_envmask(metallic_img, roughness_img, ao_img)
            
            self.progress.emit("生成基础色贴图...")
            base_texture_img = PBRSourceAlgorithms.make_basecolor(albedo_img, metallic_img, roughness_img, ao_img, preserve_alpha=has_alpha)
            
            self.progress.emit("生成法线贴图（嵌入Phong遮罩）...")
            normal_with_phong_img = PBRSourceAlgorithms.make_bumpmap_with_phong_mask(normal_img, phong_mask_img)
            
            self.progress.emit("正在保存VTF文件...")
            
            # 保存处理后的贴图 - 按照PBR-2-Source的标准输出4个文件，转换为VTF格式
            output_path = Path(self.output_dir)
            
            # 转换并保存为VTF格式 - 使用固定的贴图格式
            # Basecolor: DXT5/DXT1 (根据通道数和lossy参数)
            # Bumpmap: RGBA8888 (固定格式) 
            # PhongExp: I8 (固定格式)
            # EnvmapMask: I8 (固定格式)
            self.convert_pil_to_vtf(base_texture_img, str(output_path / f"{self.material_name}_basecolor.vtf"), lossy=True, texture_type="basecolor")
            self.convert_pil_to_vtf(normal_with_phong_img, str(output_path / f"{self.material_name}_bump.vtf"), lossy=False, texture_type="normal")
            self.convert_pil_to_vtf(phong_exponent_img, str(output_path / f"{self.material_name}_phongexp.vtf"), lossy=False, texture_type="phong")
            self.convert_pil_to_vtf(envmap_mask_img, str(output_path / f"{self.material_name}_envmask.vtf"), lossy=False, texture_type="envmap")
            
            self.progress.emit("正在生成VMT文件...")
            
            # 检测materials目录并生成相应的VMT内容
            vmt_content = self.generate_l4d2_vmt_with_materials_detection()
            
            # 检查是否需要VMT融合
            if self.existing_vmt_path:
                self.progress.emit("正在进行智能VMT融合...")
                vmt_content = self.smart_merge_vmt(vmt_content)
            
            # 直接保存到输出目录，不创建子文件夹
            output_path = Path(self.output_dir)
            
            # 保存VMT文件
            vmt_output_path = output_path / f"{self.material_name}.vmt"
            with open(vmt_output_path, 'w', encoding='utf-8') as f:
                f.write(vmt_content)
            
            # 如果存在原始VMT文件，创建备份
            if self.existing_vmt_path:
                self.create_original_backup()
            
            self.progress.emit("处理完成！")
            self.finished.emit(True, f"L4D2 PBR材质转换完成！\n输出目录: {self.output_dir}\n文件已保存")
            
        except Exception as e:
            self.error.emit(str(e))
    
    def create_protected_output_dir(self) -> str:
        """创建保护性输出目录"""
        protected_dir = Path(self.output_dir) / "pbr_converted"
        protected_dir.mkdir(exist_ok=True)
        
        self.progress.emit(f"创建保护目录: {protected_dir.name}")
        return str(protected_dir)
    
    def create_original_backup(self):
        """备份原始VMT文件"""
        try:
            original_path = Path(self.existing_vmt_path)
            protected_dir = Path(self.output_dir) / "pbr_converted"
            backup_path = protected_dir / f"{self.material_name}_original.vmt"
            
            # 复制原始文件到保护目录
            import shutil
            shutil.copy2(original_path, backup_path)
            
            self.progress.emit(f"已备份原始VMT文件: {backup_path.name}")
            
        except Exception as e:
            self.progress.emit(f"备份原始文件失败: {str(e)}")
    
    def has_real_transparency(self, pil_image):
        """检查图像是否真正包含透明信息"""
        if pil_image.mode not in ['RGBA', 'LA']:
            return False
        
        # 获取Alpha通道
        if pil_image.mode == 'RGBA':
            alpha_channel = pil_image.split()[3]
        else:  # LA模式
            alpha_channel = pil_image.split()[1]
        
        # 转换为numpy数组进行分析
        alpha_array = np.array(alpha_channel)
        
        # 检查是否所有像素都是完全不透明(255)
        unique_values = np.unique(alpha_array)
        
        # 如果只有255这一个值，说明没有透明信息
        if len(unique_values) == 1 and unique_values[0] == 255:
            return False
        
        # 如果有其他值，说明有透明信息
        return True
    
    def convert_pil_to_vtf(self, pil_image, output_path: str, lossy: bool = True, texture_type: str = "auto"):
        """将PIL图像转换为VTF格式，使用VTF CMD命令行工具
        
        Args:
            pil_image: PIL图像对象
            output_path: 输出VTF文件路径
            lossy: 是否使用有损压缩（仅对basecolor有效）
            texture_type: 贴图类型 ("basecolor", "normal", "phong", "envmap", "auto")
        """
        try:
            # 详细调试信息
            self.progress.emit(f"VTF转换调试: texture_type={texture_type}, lossy={lossy}, 输出文件={Path(output_path).name}")
            # 获取VTF CMD路径
            vtfcmd_path = self.get_vtfcmd_path()
            if not vtfcmd_path:
                # 如果VTF CMD不可用，保存为TGA格式
                tga_path = output_path.replace('.vtf', '.tga')
                pil_image.save(tga_path)
                self.progress.emit(f"VTF CMD不可用，保存为TGA格式: {Path(tga_path).name}")
                return tga_path
            
            # 先保存为临时TGA文件
            temp_tga_path = output_path.replace('.vtf', '_temp.tga')
            pil_image.save(temp_tga_path)
            
            # 构建VTF CMD命令
            cmd = [vtfcmd_path, '-file', temp_tga_path, '-output', str(Path(output_path).parent)]
            
            # 根据贴图类型选择固定格式
            if texture_type == "normal":
                # 法线贴图固定使用RGBA8888
                cmd.extend(['-format', 'rgba8888'])
                cmd.extend(['-alphaformat', 'rgba8888'])  # 明确指定alpha格式
                # 添加详细的调试信息
                img_array = np.array(pil_image)
                bands = img_array.shape[2] if len(img_array.shape) == 3 else 1
                self.progress.emit(f"法线贴图调试: 模式={pil_image.mode}, 通道数={bands}, 尺寸={pil_image.size}")
                self.progress.emit(f"法线贴图使用RGBA8888格式")
            elif texture_type == "phong":
                # Phong指数贴图固定使用I8（灰度）
                cmd.extend(['-format', 'i8'])
                self.progress.emit(f"Phong指数贴图使用I8格式")
            elif texture_type == "envmap":
                # 环境贴图遮罩固定使用I8（灰度）
                cmd.extend(['-format', 'i8'])
                self.progress.emit(f"环境贴图遮罩使用I8格式")
            elif texture_type == "basecolor":
                # 基础色贴图根据真实透明度和lossy参数选择
                img_array = np.array(pil_image)
                bands = img_array.shape[2] if len(img_array.shape) == 3 else 1
                has_transparency = self.has_real_transparency(pil_image)
                self.progress.emit(f"基础色贴图调试: 模式={pil_image.mode}, 通道数={bands}, 尺寸={pil_image.size}, lossy={lossy}, 真实透明度={has_transparency}")
                if lossy:
                    if has_transparency:  # 真正有透明信息
                        cmd.extend(['-format', 'dxt5'])
                        cmd.extend(['-alphaformat', 'dxt5'])  # 明确指定alpha格式
                        self.progress.emit(f"基础色贴图(有透明)使用DXT5格式")
                    elif bands >= 3:  # RGB或伪RGBA
                        cmd.extend(['-format', 'dxt1'])
                        if bands == 4:  # 有Alpha通道但无透明信息
                            cmd.extend(['-alphaformat', 'dxt1'])  # 强制alpha格式也用DXT1
                        self.progress.emit(f"基础色贴图(无透明)使用DXT1格式")
                    else:  # 灰度图
                        cmd.extend(['-format', 'i8'])
                        self.progress.emit(f"基础色贴图(灰度)使用I8格式")
                else:
                    if has_transparency:  # 真正有透明信息
                        cmd.extend(['-format', 'rgba8888'])
                        cmd.extend(['-alphaformat', 'rgba8888'])  # 明确指定alpha格式
                        self.progress.emit(f"基础色贴图(有透明)使用RGBA8888格式")
                    elif bands >= 3:  # RGB或伪RGBA
                        cmd.extend(['-format', 'rgb888'])
                        if bands == 4:  # 有Alpha通道但无透明信息
                            cmd.extend(['-alphaformat', 'rgb888'])  # 强制alpha格式也用RGB888
                        self.progress.emit(f"基础色贴图(无透明)使用RGB888格式")
                    else:  # 灰度图
                        cmd.extend(['-format', 'i8'])
                        self.progress.emit(f"基础色贴图(灰度)使用I8格式")
            else:
                # auto模式：使用真实透明度检测
                img_array = np.array(pil_image)
                bands = img_array.shape[2] if len(img_array.shape) == 3 else 1
                has_transparency = self.has_real_transparency(pil_image)
                self.progress.emit(f"Auto模式调试: 模式={pil_image.mode}, 通道数={bands}, 真实透明度={has_transparency}, lossy={lossy}")
                
                if lossy:
                    if has_transparency:  # 真正有透明信息
                        cmd.extend(['-format', 'dxt5'])
                        self.progress.emit(f"Auto模式(有透明)使用DXT5格式")
                    elif bands >= 3:  # RGB或伪RGBA
                        cmd.extend(['-format', 'dxt1'])
                        self.progress.emit(f"Auto模式(无透明)使用DXT1格式")
                    else:  # 灰度图
                        cmd.extend(['-format', 'i8'])
                        self.progress.emit(f"Auto模式(灰度)使用I8格式")
                else:
                    if has_transparency:  # 真正有透明信息
                        cmd.extend(['-format', 'rgba8888'])
                        self.progress.emit(f"Auto模式(有透明)使用RGBA8888格式")
                    elif bands >= 3:  # RGB或伪RGBA
                        cmd.extend(['-format', 'rgb888'])
                        self.progress.emit(f"Auto模式(无透明)使用RGB888格式")
                    else:  # 灰度图
                        cmd.extend(['-format', 'i8'])
                        self.progress.emit(f"Auto模式(灰度)使用I8格式")
            
            # 执行VTF CMD命令
            self.progress.emit(f"执行VTF命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            # 输出VTF命令的结果
            if result.stdout:
                self.progress.emit(f"VTF命令输出: {result.stdout}")
            if result.stderr:
                self.progress.emit(f"VTF命令错误: {result.stderr}")
            
            # 删除临时TGA文件
            try:
                os.remove(temp_tga_path)
            except:
                pass
            
            # 检查VTF CMD是否成功生成了VTF文件
            expected_vtf_path = Path(output_path).parent / f"{Path(temp_tga_path).stem}.vtf"
            if expected_vtf_path.exists():
                # 如果生成的文件名不匹配，重命名
                if str(expected_vtf_path) != output_path:
                    os.rename(str(expected_vtf_path), output_path)
                
                self.progress.emit(f"已转换为VTF: {Path(output_path).name}")
                return output_path
            else:
                raise Exception(f"VTF CMD执行失败: {result.stderr}")
            
        except Exception as e:
            # 如果VTF转换失败，回退到TGA格式
            tga_path = output_path.replace('.vtf', '.tga')
            pil_image.save(tga_path)
            self.progress.emit(f"VTF转换失败，保存为TGA格式: {Path(tga_path).name} (错误: {str(e)})")
            return tga_path
    
    def get_vtfcmd_path(self):
        """获取VTF CMD工具路径"""
        # 首先尝试直接调用vtfcmd
        try:
            result = subprocess.run(["vtfcmd", "-help"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0 or "vtfcmd" in result.stdout.lower():
                return "vtfcmd"
        except:
            pass
        
        # 尝试常见的VTFCmd.exe路径
        possible_paths = [
            "VTFCmd.exe",
            "D:\\VTFEdit_Reloaded_v2.0.9\\VTFCmd.exe",
            "C:\\Program Files\\VTFEdit\\VTFCmd.exe",
            "C:\\Program Files (x86)\\VTFEdit\\VTFCmd.exe"
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, "-help"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode == 0 or "vtfcmd" in result.stdout.lower():
                    return path
            except:
                continue
        
        return None
    
    def generate_l4d2_vmt(self) -> str:
        """生成VMT内容 - 严格按照PBR-2-Source原版格式"""
        return f'''"VertexLitGeneric"
{{
\t$basetexture\t\t"{self.material_name}_basecolor"
\t$bumpmap\t\t\t"{self.material_name}_bump"

\t$envmap\t\t\t\t\t"env_cubemap"
\t$envmaptint\t\t\t\t"[0.1 0.1 0.1]"
\t$envmapcontrast\t\t\t1.0
\t$envmapmask\t\t\t\t"{self.material_name}_envmask"
\t$envmapfresnel\t\t\t1

\t$phong 1
\t$phongexponenttexture\t"{self.material_name}_phongexp"
\t$phongexponentfactor\t32.0
\t$phongboost\t\t\t\t5.0
\t$phongfresnelranges\t\t"[0.1 0.8 1.0]"
}}'''
    
    def detect_materials_directory(self) -> tuple[bool, str]:
        """检测当前输出目录是否在materials目录下，返回(是否在materials下, 相对路径)"""
        output_path = Path(self.output_dir).resolve()
        
        # 向上查找materials目录
        for parent in output_path.parents:
            if parent.name.lower() == 'materials':
                # 计算相对于materials的路径
                relative_path = output_path.relative_to(parent)
                return True, str(relative_path).replace('\\', '/')
        
        return False, ""
    
    def generate_l4d2_vmt_with_materials_detection(self) -> str:
        """生成VMT内容 - 带materials目录检测，按照PBR-2-Source原版逻辑"""
        is_in_materials, relative_path = self.detect_materials_directory()
        
        if is_in_materials and relative_path:
            # 在materials目录下，使用相对路径
            material_path = f"{relative_path}/{self.material_name}"
            self.progress.emit(f"检测到materials目录，使用相对路径: {material_path}")
        else:
            # 不在materials目录下，使用材质名称
            material_path = self.material_name
            self.progress.emit(f"未检测到materials目录，使用材质名称: {material_path}")
        
        return f'''"VertexLitGeneric"
{{
\t$basetexture\t\t"{material_path}_basecolor"
\t$bumpmap\t\t\t"{material_path}_bump"

\t$envmap\t\t\t\t\t"env_cubemap"
\t$envmaptint\t\t\t\t"[0.1 0.1 0.1]"
\t$envmapcontrast\t\t\t1.0
\t$envmapmask\t\t\t\t"{material_path}_envmask"
\t$envmapfresnel\t\t\t1

\t$phong 1
\t$phongexponenttexture\t"{material_path}_phongexp"
\t$phongexponentfactor\t32.0
\t$phongboost\t\t\t\t5.0
\t$phongfresnelranges\t\t"[0.1 0.8 1.0]"
}}'''
    
    def smart_merge_vmt(self, generated_vmt: str) -> str:
        """智能VMT融合 - 基于贴图引用分析而非硬编码"""
        try:
            # 读取现有VMT文件
            with open(self.existing_vmt_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            
            # 解析参数
            existing_params = self.parse_vmt_params(existing_content)
            generated_params = self.parse_vmt_params(generated_vmt)
            
            # 智能识别PBR相关参数
            pbr_related_params = self.identify_pbr_parameters(existing_params, generated_params)
            
            # 智能融合：保留非PBR参数，更新PBR参数
            merged_params = existing_params.copy()
            
            for param, value in generated_params.items():
                param_lower = param.lower()
                # 如果是PBR相关参数，则更新
                if param_lower in pbr_related_params:
                    merged_params[param] = value
                    self.progress.emit(f"更新PBR参数: {param}")
                # 如果是新参数（原VMT中没有），则添加
                elif param not in existing_params:
                    merged_params[param] = value
                    self.progress.emit(f"添加新参数: {param}")
                # 否则保留原有参数
                else:
                    self.progress.emit(f"保留原有参数: {param}")
            
            # 生成融合后的VMT
            return self.build_vmt_from_params(merged_params)
            
        except Exception as e:
            self.progress.emit(f"VMT融合失败，使用默认生成: {str(e)}")
            return generated_vmt
    
    def identify_pbr_parameters(self, existing_params: dict, generated_params: dict) -> set:
        """智能识别PBR相关参数 - 基于贴图引用分析"""
        pbr_params = set()
        
        # 1. 分析贴图引用模式
        material_base_name = self.material_name
        
        # 检查现有VMT中是否有相同基础名称的贴图引用
        for param, value in existing_params.items():
            param_lower = param.lower()
            value_lower = value.lower() if value else ""
            
            # 如果参数值包含当前材质的基础名称，认为是相关的贴图参数
            if material_base_name.lower() in value_lower:
                pbr_params.add(param_lower)
                self.progress.emit(f"检测到相关贴图参数: {param} = {value}")
        
        # 2. 分析生成的VMT中的贴图引用
        for param, value in generated_params.items():
            param_lower = param.lower()
            value_lower = value.lower() if value else ""
            
            # 如果是贴图相关参数（包含材质名称）
            if material_base_name.lower() in value_lower:
                pbr_params.add(param_lower)
        
        # 3. 基于参数语义识别PBR相关参数
        pbr_semantic_keywords = {
            'phong', 'envmap', 'bump', 'normal', 'metallic', 'roughness',
            'basetexture', 'albedo', 'specular', 'reflection'
        }
        
        for param in generated_params.keys():
            param_lower = param.lower()
            # 检查参数名是否包含PBR相关关键词
            for keyword in pbr_semantic_keywords:
                if keyword in param_lower:
                    pbr_params.add(param_lower)
                    break
        
        # 4. 添加常见的PBR渲染参数
        common_pbr_params = {
            '$model', '$surfaceprop', '$halflambert', '$phongfresnelranges',
            '$phongboost', '$phongalbedotint', '$envmapfresnel', '$envmapcontrast',
            '$envmaptint', '$normalmapalphaenvmapmask'
        }
        
        for param in generated_params.keys():
            if param.lower() in common_pbr_params:
                pbr_params.add(param.lower())
        
        self.progress.emit(f"识别到 {len(pbr_params)} 个PBR相关参数")
        return pbr_params
    
    def parse_vmt_params(self, vmt_content: str) -> dict:
        """解析VMT参数 - 支持标准格式和patch格式"""
        # 检测是否为patch格式
        if 'patch' in vmt_content.lower() and 'include' in vmt_content.lower():
            return self.parse_patch_vmt(vmt_content)
        else:
            return self.parse_standard_vmt(vmt_content)
    
    def parse_standard_vmt(self, vmt_content: str) -> dict:
        """解析标准格式VMT参数"""
        params = {}
        lines = vmt_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('"$') and '"' in line[2:]:
                try:
                    # 简单的参数解析
                    parts = line.split('"')
                    if len(parts) >= 4:
                        param_name = parts[1]
                        param_value = parts[3]
                        params[param_name] = param_value
                except:
                    continue
                    
        return params
    
    def parse_patch_vmt(self, vmt_content: str) -> dict:
        """解析patch格式VMT文件"""
        params = {}
        
        try:
            # 解析include的基础文件
            include_match = None
            for line in vmt_content.split('\n'):
                line = line.strip()
                if 'include' in line.lower() and '.vmt' in line.lower():
                    # 提取include的文件路径
                    start = line.find('"')
                    end = line.rfind('"')
                    if start != -1 and end != -1 and start != end:
                        include_path = line[start+1:end]
                        include_match = include_path
                        break
            
            # 如果找到include文件，尝试读取基础参数
            if include_match:
                self.progress.emit(f"检测到include文件: {include_match}")
                # 这里可以扩展为实际读取include文件的逻辑
                # 目前先记录，实际项目中需要递归解析
            
            # 解析replace块
            in_replace_block = False
            for line in vmt_content.split('\n'):
                line = line.strip()
                
                if 'replace' in line.lower() and '{' in line:
                    in_replace_block = True
                    continue
                elif in_replace_block and '}' in line:
                    in_replace_block = False
                    continue
                elif in_replace_block and line.startswith('"$'):
                    try:
                        parts = line.split('"')
                        if len(parts) >= 4:
                            param_name = parts[1]
                            param_value = parts[3]
                            params[param_name] = param_value
                    except:
                        continue
            
            # 解析insert块
            in_insert_block = False
            for line in vmt_content.split('\n'):
                line = line.strip()
                
                if 'insert' in line.lower() and '{' in line:
                    in_insert_block = True
                    continue
                elif in_insert_block and '}' in line:
                    in_insert_block = False
                    continue
                elif in_insert_block and line.startswith('"$'):
                    try:
                        parts = line.split('"')
                        if len(parts) >= 4:
                            param_name = parts[1]
                            param_value = parts[3]
                            params[param_name] = param_value
                    except:
                        continue
            
            self.progress.emit(f"解析patch格式VMT，提取到 {len(params)} 个参数")
            
        except Exception as e:
            self.progress.emit(f"patch格式解析失败，回退到标准解析: {str(e)}")
            return self.parse_standard_vmt(vmt_content)
        
        return params
    
    def build_vmt_from_params(self, params: dict) -> str:
        """从参数构建VMT内容"""
        lines = ['"VertexLitGeneric"', '{']
        
        for param, value in params.items():
            lines.append(f'\t"{param}"\t\t"{value}"')
            
        lines.append('}')
        return '\n'.join(lines)


class L4D2BatchProcessingThread(QThread):
    """L4D2批量处理线程"""
    progress = Signal(str)
    finished = Signal(bool, str)
    error = Signal(str)
    
    def __init__(self, vmt_files: list, output_dir: str):
        super().__init__()
        self.vmt_files = vmt_files
        self.output_dir = output_dir
        self.processed_count = 0
        self.failed_count = 0
    
    def run(self):
        try:
            self.progress.emit(f"开始批量处理 {len(self.vmt_files)} 个VMT文件...")
            
            # 直接使用输出目录，不创建子文件夹
            output_path_base = Path(self.output_dir)
            self.progress.emit(f"批量处理输出目录: {output_path_base}")
            
            for i, vmt_file_path in enumerate(self.vmt_files):
                try:
                    vmt_path = Path(vmt_file_path)
                    material_name = vmt_path.stem
                    
                    self.progress.emit(f"[{i+1}/{len(self.vmt_files)}] 处理材质: {material_name}")
                    
                    # 读取现有VMT文件
                    with open(vmt_file_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    
                    # 生成PBR VMT内容（带materials目录检测）
                    generated_vmt = self.generate_batch_l4d2_vmt_with_materials_detection(material_name, str(output_path_base))
                    
                    # 智能融合
                    merged_vmt = self.smart_merge_batch_vmt(existing_content, generated_vmt, material_name, str(vmt_file_path))
                    
                    # 直接保存到输出目录
                    output_path = output_path_base / f"{material_name}.vmt"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(merged_vmt)
                    
                    # 备份原始文件
                    backup_path = output_path_base / f"{material_name}_original.vmt"
                    import shutil
                    shutil.copy2(vmt_file_path, backup_path)
                    
                    self.processed_count += 1
                    self.progress.emit(f"✅ {material_name} 处理完成")
                    
                except Exception as e:
                    self.failed_count += 1
                    self.progress.emit(f"❌ {material_name} 处理失败: {str(e)}")
                    continue
            
            success_msg = f"批量处理完成！\n成功: {self.processed_count} 个\n失败: {self.failed_count} 个\n输出目录: {output_path_base}"
            self.finished.emit(True, success_msg)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def detect_batch_materials_directory(self, output_path: str) -> str:
        """检测批量处理的materials目录并返回相对路径前缀"""
        try:
            output_path_obj = Path(output_path)
            
            # 检查当前目录或父目录是否包含materials
            current_path = output_path_obj
            while current_path.parent != current_path:  # 避免无限循环
                if current_path.name.lower() == 'materials':
                    # 找到materials目录，计算相对路径
                    relative_parts = output_path_obj.relative_to(current_path).parts
                    if relative_parts:
                        return '/'.join(relative_parts) + '/'
                    else:
                        return ''
                current_path = current_path.parent
            
            return ''
        except Exception:
            return ''
    
    def generate_batch_l4d2_vmt_with_materials_detection(self, material_name: str, output_path: str) -> str:
        """为批量处理生成带materials目录检测的L4D2 VMT内容"""
        # 检测materials目录
        materials_prefix = self.detect_batch_materials_directory(output_path)
        
        # 构建纹理路径
        basetexture_path = f"{materials_prefix}{material_name}_basetexture"
        normal_path = f"{materials_prefix}{material_name}_normal"
        phongexponent_path = f"{materials_prefix}{material_name}_phongexponent"
        
        return f'''"VertexLitGeneric"
{{
\t"$basetexture" "{basetexture_path}"
\t"$bumpmap" "{normal_path}"
\t
\t"$envmap" "env_cubemap"
\t"$envmaptint" "[0.1 0.1 0.1]"
\t"$envmapcontrast" "1.0"
\t"$normalmapalphaenvmapmask" "1"
\t"$envmapfresnel" "1"
\t
\t"$phong" "1"
\t"$phongexponenttexture" "{phongexponent_path}"
\t"$phongboost" "5.0"
\t"$phongfresnelranges" "[0.1 0.8 1.0]"
\t"$phongalbedotint" "1"
\t"$halflambert" "1"
\t
\t"$model" "1"
\t"$surfaceprop" "default"
}}'''

    def generate_batch_l4d2_vmt(self, material_name: str) -> str:
        """为批量处理生成L4D2 VMT内容（保留向后兼容）"""
        return f'''"VertexLitGeneric"
{{
\t"$basetexture" "{material_name}_basetexture"
\t"$bumpmap" "{material_name}_normal"
\t
\t"$envmap" "env_cubemap"
\t"$envmaptint" "[0.1 0.1 0.1]"
\t"$envmapcontrast" "1.0"
\t"$normalmapalphaenvmapmask" "1"
\t"$envmapfresnel" "1"
\t
\t"$phong" "1"
\t"$phongexponenttexture" "{material_name}_phongexponent"
\t"$phongboost" "5.0"
\t"$phongfresnelranges" "[0.1 0.8 1.0]"
\t"$phongalbedotint" "1"
\t"$halflambert" "1"
\t
\t"$model" "1"
\t"$surfaceprop" "default"
}}'''
    
    def smart_merge_batch_vmt(self, existing_content: str, generated_vmt: str, material_name: str, vmt_file_path: str = "") -> str:
        """批量处理的智能VMT融合"""
        try:
            # 解析现有和生成的参数
            existing_params = self.parse_batch_vmt_params(existing_content, vmt_file_path)
            generated_params = self.parse_batch_vmt_params(generated_vmt)
            
            # 检查是否为patch格式
            is_patch_format = (hasattr(self, 'patch_format_checkbox') and 
                             self.patch_format_checkbox.isChecked() and 
                             (existing_content.strip().lower().startswith('patch') or 
                              'include' in existing_content.lower()))
            
            # 智能识别相关参数
            pbr_params = set()
            
            # 基于材质名称识别相关参数
            for param, value in existing_params.items():
                if material_name.lower() in value.lower():
                    pbr_params.add(param.lower())
            
            # 添加PBR语义参数
            pbr_keywords = {'phong', 'envmap', 'bump', 'basetexture', 'normal'}
            for param in generated_params.keys():
                for keyword in pbr_keywords:
                    if keyword in param.lower():
                        pbr_params.add(param.lower())
                        break
            
            # 融合参数
            merged_params = existing_params.copy()
            for param, value in generated_params.items():
                if param.lower() in pbr_params or param not in existing_params:
                    merged_params[param] = value
            
            # 根据原始格式构建VMT
            if is_patch_format:
                # 保持patch格式结构
                return self._build_patch_vmt(existing_content, merged_params, vmt_file_path)
            else:
                # 标准VMT格式
                lines = ['"VertexLitGeneric"', '{']
                for param, value in merged_params.items():
                    lines.append(f'\t"{param}"\t\t"{value}"')
                lines.append('}')
                return '\n'.join(lines)
            
        except Exception as e:
            self.progress.emit(f"融合失败，使用生成的VMT: {str(e)}")
            return generated_vmt
    
    def parse_batch_vmt_params(self, vmt_content: str, vmt_file_path: str = "") -> dict:
        """批量处理的VMT参数解析"""
        # 检查是否启用patch格式支持
        if hasattr(self, 'patch_format_checkbox') and self.patch_format_checkbox.isChecked():
            # 检查是否为patch格式
            if vmt_content.strip().lower().startswith('patch') or 'include' in vmt_content.lower():
                base_dir = Path(vmt_file_path).parent if vmt_file_path else ""
                return self.parse_patch_vmt_params(vmt_content, str(base_dir))
        
        # 标准VMT格式解析
        params = {}
        lines = vmt_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('"$') and '"' in line[2:]:
                try:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        param_name = parts[1]
                        param_value = parts[3]
                        params[param_name] = param_value
                except:
                    continue
                    
        return params
    
    def parse_patch_vmt_params(self, vmt_content: str, base_dir: str = "") -> dict:
        """解析patch格式VMT文件"""
        params = {}
        lines = vmt_content.split('\n')
        current_section = None
        brace_level = 0
        
        try:
            for line in lines:
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                
                # 处理大括号层级
                if '{' in line:
                    brace_level += line.count('{')
                if '}' in line:
                    brace_level -= line.count('}')
                    if brace_level <= 1 and current_section:
                        current_section = None
                    continue
                
                # 识别patch块开始
                if line.lower().startswith('patch') and brace_level == 0:
                    continue
                
                # 处理include指令
                if line.startswith('include') and '"' in line:
                    include_path = self._extract_quoted_value(line)
                    if include_path:
                        # 解析包含的基础文件
                        base_params = self._load_include_file(include_path, base_dir)
                        params.update(base_params)
                
                # 识别insert/replace块
                elif line.lower() in ['insert', 'replace']:
                    current_section = line.lower()
                
                # 解析参数
                elif current_section and line.startswith('"$') and '"' in line[2:]:
                    param_name, param_value = self._parse_vmt_line(line)
                    if param_name and param_value:
                        if current_section == 'replace' or param_name not in params:
                            params[param_name] = param_value
                        # insert模式下，如果参数已存在则不覆盖
                
        except Exception as e:
            self.progress.emit(f"解析patch格式失败: {str(e)}")
            
        return params
    
    def _extract_quoted_value(self, line: str) -> str:
        """从行中提取引号内的值"""
        try:
            start = line.find('"')
            if start != -1:
                end = line.find('"', start + 1)
                if end != -1:
                    return line[start + 1:end]
        except:
            pass
        return ""
    
    def _load_include_file(self, include_path: str, base_dir: str) -> dict:
        """加载include文件并解析参数"""
        params = {}
        try:
            # 构建完整路径
            if base_dir:
                full_path = Path(base_dir) / include_path
            else:
                full_path = Path(include_path)
            
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 递归解析（支持嵌套include）
                if content.strip().startswith('patch'):
                    params = self.parse_patch_vmt_params(content, str(full_path.parent))
                else:
                    params = self.parse_batch_vmt_params(content, str(full_path))
            else:
                self.progress.emit(f"警告: 无法找到include文件: {include_path}")
                
        except Exception as e:
            self.progress.emit(f"加载include文件失败: {str(e)}")
            
        return params
    
    def _parse_vmt_line(self, line: str) -> tuple:
        """解析VMT参数行"""
        try:
            parts = line.split('"')
            if len(parts) >= 4:
                param_name = parts[1]
                param_value = parts[3]
                return param_name, param_value
        except:
            pass
        return None, None
    
    def _build_patch_vmt(self, original_content: str, merged_params: dict, vmt_file_path: str = "") -> str:
        """构建patch格式的VMT文件"""
        try:
            lines = original_content.split('\n')
            result_lines = []
            current_section = None
            brace_level = 0
            in_replace_section = False
            
            for line in lines:
                stripped = line.strip()
                
                # 处理大括号层级
                if '{' in line:
                    brace_level += line.count('{')
                if '}' in line:
                    brace_level -= line.count('}')
                    if brace_level <= 1 and current_section:
                        current_section = None
                        in_replace_section = False
                
                # 识别section
                if stripped.lower() in ['insert', 'replace']:
                    current_section = stripped.lower()
                    in_replace_section = (current_section == 'replace')
                    result_lines.append(line)
                    continue
                
                # 处理参数行
                if (current_section and stripped.startswith('"$') and 
                    '"' in stripped[2:] and brace_level > 1):
                    param_name, _ = self._parse_vmt_line(stripped)
                    if param_name and param_name in merged_params:
                        # 使用融合后的参数值
                        indent = line[:len(line) - len(line.lstrip())]
                        new_line = f'{indent}"{param_name}"\t\t"{merged_params[param_name]}"'
                        result_lines.append(new_line)
                        # 从merged_params中移除已处理的参数
                        del merged_params[param_name]
                    else:
                        result_lines.append(line)
                else:
                    result_lines.append(line)
            
            # 添加剩余的新参数到replace section
            if merged_params and in_replace_section:
                # 在最后一个}前插入新参数
                insert_index = len(result_lines) - 1
                while insert_index >= 0 and not result_lines[insert_index].strip().endswith('}'):
                    insert_index -= 1
                
                if insert_index >= 0:
                    for param, value in merged_params.items():
                        new_param_line = f'\t\t"{param}"\t\t"{value}"'
                        result_lines.insert(insert_index, new_param_line)
                        insert_index += 1
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            self.progress.emit(f"构建patch格式失败: {str(e)}")
            # 降级为标准格式
            lines = ['"VertexLitGeneric"', '{']
            for param, value in merged_params.items():
                lines.append(f'\t"{param}"\t\t"{value}"')
            lines.append('}')
            return '\n'.join(lines)


def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("VTF材质工具")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("VTFTool")
    
    # 创建主窗口
    window = VTFMaterialTool()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()