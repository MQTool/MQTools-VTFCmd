#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTF材质工具 - 整合VTF处理功能的GUI应用
功能包括：夜光效果处理、材质配置生成、静态图像调整
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import threading
from pathlib import Path
import re

class VTFMaterialTool:
    def __init__(self, root):
        self.root = root
        self.root.title("VTF材质工具 v1.0")
        self.root.geometry("800x600")
        self.root.configure(bg='#2b2b2b')
        
        # 设置样式
        self.setup_styles()
        
        # 创建主界面
        self.create_main_interface()
        
        # 初始化变量
        self.vmt_alpha_config = ""
        
        # 检查依赖
        self.check_dependencies()
        
        # 延迟初始化格式模式
        self.root.after(100, self.on_format_mode_change)
    
    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置样式
        style.configure('Title.TLabel', 
                       background='#2b2b2b', 
                       foreground='#ffffff', 
                       font=('Microsoft YaHei', 16, 'bold'))
        
        style.configure('Subtitle.TLabel', 
                       background='#2b2b2b', 
                       foreground='#cccccc', 
                       font=('Microsoft YaHei', 10))
        
        style.configure('Custom.TButton',
                       background='#404040',
                       foreground='#ffffff',
                       font=('Microsoft YaHei', 9),
                       borderwidth=1)
        
        style.map('Custom.TButton',
                 background=[('active', '#505050'),
                           ('pressed', '#303030')])
    
    def create_main_interface(self):
        """创建主界面"""
        # 主标题
        title_frame = tk.Frame(self.root, bg='#2b2b2b')
        title_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(title_frame, text="VTF材质工具", style='Title.TLabel').pack()
        ttk.Label(title_frame, text="整合VTF处理功能的一站式工具", style='Subtitle.TLabel').pack()
        
        # 创建选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 夜光效果处理选项卡
        self.create_nightglow_tab()
        
        # 材质配置选项卡
        self.create_material_tab()
        
        # 静态图像调整选项卡
        self.create_resize_tab()
        
        # 状态栏
        self.create_status_bar()
    
    def create_nightglow_tab(self):
        """创建夜光效果处理选项卡"""
        # 创建主框架
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="夜光效果处理")
        
        # 创建Canvas和滚动条
        canvas = tk.Canvas(main_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 使用scrollable_frame作为内容容器
        frame = scrollable_frame
        
        # 说明文本
        desc_frame = tk.Frame(frame, bg='#2b2b2b')
        desc_frame.pack(fill='x', padx=10, pady=5)
        
        desc_text = tk.Text(desc_frame, height=3, bg='#2b2b2b', fg='#ffffff', 
                           font=('Microsoft YaHei', 9), wrap='word')
        desc_text.pack(fill='x', padx=5, pady=5)
        desc_text.insert('1.0', "功能说明：将VTF文件转换为TGA，调整Alpha通道为5%透明度实现夜光效果，然后转换回VTF格式。\n适用于需要自发光效果的材质贴图。")
        desc_text.config(state='disabled')
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(scrollable_frame, text="文件选择")
        file_frame.pack(fill='x', padx=10, pady=5)
        
        # VTF文件选择
        vtf_frame = tk.Frame(file_frame)
        vtf_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(vtf_frame, text="VTF文件:").pack(side='left')
        self.nightglow_vtf_var = tk.StringVar()
        vtf_entry = ttk.Entry(vtf_frame, textvariable=self.nightglow_vtf_var, width=40)
        vtf_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(vtf_frame, text="选择文件", command=self.browse_nightglow_vtf).pack(side='right', padx=(0, 5))
        ttk.Button(vtf_frame, text="选择文件夹", command=self.browse_nightglow_folder).pack(side='right')
        
        # 初始化文件列表
        self.nightglow_files = []
        self.material_files = []
        self.resize_files = []
        files_list_frame = tk.Frame(file_frame)
        files_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        ttk.Label(files_list_frame, text="已选择的文件:").pack(anchor='w')
        
        # 创建滚动文本框显示选择的文件
        list_frame = tk.Frame(files_list_frame)
        list_frame.pack(fill='both', expand=True)
        
        self.files_listbox = tk.Listbox(list_frame, height=6)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.files_listbox.yview)
        self.files_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.files_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 删除选中文件按钮
        remove_frame = tk.Frame(files_list_frame)
        remove_frame.pack(fill='x', pady=5)
        ttk.Button(remove_frame, text="删除选中", command=self.remove_selected_file).pack(side='left')
        ttk.Button(remove_frame, text="清空列表", command=self.clear_file_list).pack(side='left', padx=(10, 0))
        
        # 压缩格式选择
        format_frame = ttk.LabelFrame(frame, text="压缩格式")
        format_frame.pack(fill='x', padx=10, pady=5)
        
        self.nightglow_format_var = tk.StringVar(value="DXT5")
        formats = ["RGBA8888", "DXT5", "DXT3", "DXT1"]
        for i, fmt in enumerate(formats):
            ttk.Radiobutton(format_frame, text=fmt, variable=self.nightglow_format_var, 
                           value=fmt).grid(row=0, column=i, padx=10, pady=5, sticky='w')
        
        # 夜光增强功能选项
        enhance_frame = ttk.LabelFrame(frame, text="夜光增强功能")
        enhance_frame.pack(fill='x', padx=10, pady=5)
        
        # vmtE发光生成开关
        self.vmte_glow_var = tk.BooleanVar(value=False)
        vmte_frame = tk.Frame(enhance_frame)
        vmte_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Checkbutton(vmte_frame, text="vmtE发光生成", variable=self.vmte_glow_var).pack(side='left')
        vmte_desc = ttk.Label(vmte_frame, text="检测Alpha通道，生成带夜光效果的VMT和_E贴图", foreground='gray')
        vmte_desc.pack(side='left', padx=(10, 0))
        
        # E贴图压缩格式选择
        e_format_frame = tk.Frame(enhance_frame)
        e_format_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(e_format_frame, text="E贴图格式:").pack(side='left')
        self.e_texture_format_var = tk.StringVar(value="DXT5")
        e_formats = ["RGBA8888", "DXT5", "DXT3", "DXT1"]
        for i, fmt in enumerate(e_formats):
            ttk.Radiobutton(e_format_frame, text=fmt, variable=self.e_texture_format_var, 
                           value=fmt).pack(side='left', padx=(10, 0))
        
        # 全局屏蔽词设置
        global_blacklist_frame = ttk.LabelFrame(enhance_frame, text="全局屏蔽词系统")
        global_blacklist_frame.pack(fill='x', padx=5, pady=5)
        
        # 预设屏蔽词复选框
        preset_frame = tk.Frame(global_blacklist_frame)
        preset_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(preset_frame, text="常用屏蔽词:").pack(anchor='w')
        
        # 创建预设屏蔽词变量
        self.preset_blacklist_vars = {}
        preset_words = ['_n', 'phongexp', 'envmap', 'bump', 'eye', 'ambient', 'toon_light', 'warp']
        
        preset_checkboxes_frame = tk.Frame(preset_frame)
        preset_checkboxes_frame.pack(fill='x', pady=5)
        
        for i, word in enumerate(preset_words):
            self.preset_blacklist_vars[word] = tk.BooleanVar()
            ttk.Checkbutton(preset_checkboxes_frame, text=word, 
                           variable=self.preset_blacklist_vars[word]).grid(row=i//3, column=i%3, sticky='w', padx=10)
        
        # 自定义屏蔽词输入
        custom_frame = tk.Frame(global_blacklist_frame)
        custom_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(custom_frame, text="自定义屏蔽词:").pack(anchor='w')
        self.custom_blacklist_var = tk.StringVar()
        custom_entry = ttk.Entry(custom_frame, textvariable=self.custom_blacklist_var, width=50)
        custom_entry.pack(fill='x', pady=5)
        custom_desc = ttk.Label(custom_frame, text="用逗号分隔多个屏蔽词", foreground='gray')
        custom_desc.pack(anchor='w')
        
        # E发光专用屏蔽词设置
        e_blacklist_frame = tk.Frame(enhance_frame)
        e_blacklist_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(e_blacklist_frame, text="E发光屏蔽词:").pack(side='left')
        self.blacklist_var = tk.StringVar()
        blacklist_entry = ttk.Entry(e_blacklist_frame, textvariable=self.blacklist_var, width=40)
        blacklist_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        blacklist_desc = ttk.Label(e_blacklist_frame, text="用逗号分隔多个屏蔽词", foreground='gray')
        blacklist_desc.pack(side='left', padx=(10, 0))
        
        # 修改vmt-base开关
        self.modify_vmtbase_var = tk.BooleanVar(value=False)
        vmtbase_frame = tk.Frame(enhance_frame)
        vmtbase_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Checkbutton(vmtbase_frame, text="修改vmt-base", variable=self.modify_vmtbase_var).pack(side='left')
        vmtbase_desc = ttk.Label(vmtbase_frame, text="自动修改父级文件夹shader中的vmt-base.vmt文件", foreground='gray')
        vmtbase_desc.pack(side='left', padx=(10, 0))
        
        # 处理按钮
        button_frame = tk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="开始处理夜光效果", 
                  command=self.process_nightglow, style='Custom.TButton').pack()
    
    def create_material_tab(self):
        """创建材质配置选项卡"""
        # 创建主框架
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="材质配置生成")
        
        # 创建Canvas和滚动条
        canvas = tk.Canvas(main_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 使用scrollable_frame作为内容容器
        frame = scrollable_frame
        
        # 说明文本
        desc_frame = tk.Frame(frame, bg='#2b2b2b')
        desc_frame.pack(fill='x', padx=10, pady=5)
        
        desc_text = tk.Text(desc_frame, height=3, bg='#2b2b2b', fg='#ffffff', 
                           font=('Microsoft YaHei', 9), wrap='word')
        desc_text.pack(fill='x', padx=5, pady=5)
        desc_text.insert('1.0', "功能说明：将图像文件转换为VTF格式，并自动生成对应的VMT材质文件。\n支持普通材质和眼部材质的自动识别和配置。")
        desc_text.config(state='disabled')
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(scrollable_frame, text="文件选择")
        file_frame.pack(fill='x', padx=10, pady=5)
        
        # 图像文件选择
        img_frame = tk.Frame(file_frame)
        img_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(img_frame, text="图像文件:").pack(side='left')
        self.material_img_var = tk.StringVar()
        img_entry = ttk.Entry(img_frame, textvariable=self.material_img_var, width=40)
        img_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(img_frame, text="选择文件", command=self.browse_material_image).pack(side='right', padx=(0, 5))
        ttk.Button(img_frame, text="选择文件夹", command=self.browse_material_folder).pack(side='right')
        
        # 已选择文件列表
        list_frame = tk.Frame(file_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        ttk.Label(list_frame, text="已选择的文件:").pack(anchor='w')
        
        # 文件列表框和滚动条
        listbox_frame = tk.Frame(list_frame)
        listbox_frame.pack(fill='both', expand=True)
        
        self.material_files_listbox = tk.Listbox(listbox_frame, height=6)
        scrollbar2 = tk.Scrollbar(listbox_frame, orient='vertical', command=self.material_files_listbox.yview)
        self.material_files_listbox.configure(yscrollcommand=scrollbar2.set)
        
        self.material_files_listbox.pack(side='left', fill='both', expand=True)
        scrollbar2.pack(side='right', fill='y')
        
        # 文件管理按钮
        btn_frame2 = tk.Frame(list_frame)
        btn_frame2.pack(fill='x', pady=(5, 0))
        
        ttk.Button(btn_frame2, text="删除选中", command=self.remove_selected_material_file).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame2, text="清空列表", command=self.clear_material_file_list).pack(side='left')
        
        # 输出目录选择
        output_frame = tk.Frame(file_frame)
        output_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(output_frame, text="输出目录:").pack(side='left')
        self.material_output_var = tk.StringVar()
        output_entry = ttk.Entry(output_frame, textvariable=self.material_output_var, width=50)
        output_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(output_frame, text="浏览", command=self.browse_material_output).pack(side='right')
        
        # QCI文件选择（可选）
        qci_frame = tk.Frame(file_frame)
        qci_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(qci_frame, text="QCI文件（可选）:").pack(side='left')
        self.qci_file_var = tk.StringVar()
        qci_entry = ttk.Entry(qci_frame, textvariable=self.qci_file_var, width=50)
        qci_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(qci_frame, text="浏览", command=self.browse_qci_file).pack(side='right')
        
        # 材质路径输入
        path_frame = tk.Frame(file_frame)
        path_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(path_frame, text="材质路径:").pack(side='left')
        self.cdmaterials_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.cdmaterials_var, width=50)
        path_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(path_frame, text="从QCI读取", command=self.read_cdmaterials_from_qci).pack(side='right')
        
        # 配置选项
        config_frame = ttk.LabelFrame(frame, text="配置选项")
        config_frame.pack(fill='x', padx=10, pady=5)
        
        # Lightwarp路径
        lightwarp_frame = tk.Frame(config_frame)
        lightwarp_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(lightwarp_frame, text="Lightwarp文件:").pack(side='left')
        self.lightwarp_var = tk.StringVar()
        lightwarp_entry = ttk.Entry(lightwarp_frame, textvariable=self.lightwarp_var, width=50)
        lightwarp_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(lightwarp_frame, text="浏览", command=self.browse_lightwarp_file).pack(side='right')
        
        # 材质生成屏蔽词系统
        material_blacklist_frame = ttk.LabelFrame(config_frame, text="材质生成屏蔽词系统")
        material_blacklist_frame.pack(fill='x', padx=5, pady=5)
        
        # 预设屏蔽词复选框
        material_preset_frame = tk.Frame(material_blacklist_frame)
        material_preset_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(material_preset_frame, text="常用屏蔽词:").pack(anchor='w')
        
        # 创建材质预设屏蔽词变量
        self.material_preset_blacklist_vars = {}
        material_preset_words = ['_N', '_Normal', '_emi', '_n', 'phongexp', 'envmap', 'bump']
        
        material_preset_checkboxes_frame = tk.Frame(material_preset_frame)
        material_preset_checkboxes_frame.pack(fill='x', pady=5)
        
        for i, word in enumerate(material_preset_words):
            self.material_preset_blacklist_vars[word] = tk.BooleanVar()
            # 默认选中前三个（原有的默认屏蔽词）
            if word in ['_N', '_Normal', '_emi']:
                self.material_preset_blacklist_vars[word].set(True)
            ttk.Checkbutton(material_preset_checkboxes_frame, text=word, 
                           variable=self.material_preset_blacklist_vars[word]).grid(row=i//4, column=i%4, sticky='w', padx=10)
        
        # 自定义屏蔽词输入
        material_custom_frame = tk.Frame(material_blacklist_frame)
        material_custom_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(material_custom_frame, text="自定义屏蔽词:").pack(anchor='w')
        self.material_custom_blacklist_var = tk.StringVar()
        material_custom_entry = ttk.Entry(material_custom_frame, textvariable=self.material_custom_blacklist_var, width=50)
        material_custom_entry.pack(fill='x', pady=5)
        material_custom_desc = ttk.Label(material_custom_frame, text="用逗号分隔多个屏蔽词", foreground='gray')
        material_custom_desc.pack(anchor='w')
        
        # 智能压缩格式选择
        format_frame = ttk.LabelFrame(scrollable_frame, text="压缩格式选择")
        format_frame.pack(fill='x', padx=10, pady=5)
        
        # 格式选择模式
        mode_frame = tk.Frame(format_frame)
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        self.material_format_mode_var = tk.StringVar(value="auto")
        ttk.Radiobutton(mode_frame, text="智能检测（推荐）", variable=self.material_format_mode_var, 
                       value="auto", command=self.on_format_mode_change).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="自定义规则", variable=self.material_format_mode_var, 
                       value="custom", command=self.on_format_mode_change).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="手动选择", variable=self.material_format_mode_var, 
                       value="manual", command=self.on_format_mode_change).pack(side='left')
        
        # 智能检测说明
        self.auto_info_var = tk.StringVar(value="将自动检测图像Alpha通道并选择最佳压缩格式")
        self.auto_info_label = ttk.Label(format_frame, textvariable=self.auto_info_var, foreground='blue')
        self.auto_info_label.pack(fill='x', padx=5, pady=2)
        
        # 自定义规则选择（默认隐藏）
        self.custom_format_frame = tk.Frame(format_frame)
        
        # 为每种透明度类型创建格式选择
        alpha_types = [("无透明", "no_alpha"), ("黑白透明", "binary_alpha"), ("渐变透明", "gradient_alpha")]
        formats = ["DXT1", "DXT3", "DXT5", "RGBA8888"]
        default_formats = ["DXT1", "DXT3", "DXT5"]  # 为每种类型设置合理的默认值
        
        self.custom_format_vars = {}
        for i, (type_name, type_key) in enumerate(alpha_types):
            type_frame = tk.Frame(self.custom_format_frame)
            type_frame.pack(fill='x', padx=5, pady=2)
            
            ttk.Label(type_frame, text=f"{type_name}:", width=12).pack(side='left')
            
            self.custom_format_vars[type_key] = tk.StringVar(value=default_formats[i])
            format_frame_inner = tk.Frame(type_frame)
            format_frame_inner.pack(side='left', fill='x', expand=True)
            
            for fmt in formats:
                ttk.Radiobutton(format_frame_inner, text=fmt, variable=self.custom_format_vars[type_key], 
                               value=fmt).pack(side='left', padx=5)
        
        # 手动格式选择（默认隐藏）
        self.manual_format_frame = tk.Frame(format_frame)
        
        self.material_format_var = tk.StringVar(value="DXT1")
        formats = ["RGBA8888", "DXT5", "DXT3", "DXT1"]
        for i, fmt in enumerate(formats):
            ttk.Radiobutton(self.manual_format_frame, text=fmt, variable=self.material_format_var, 
                           value=fmt).grid(row=0, column=i, padx=10, pady=5, sticky='w')
        
        # 格式说明
        format_desc = tk.Text(format_frame, height=3, bg='#f8f8f8', fg='#666666', 
                             font=('Microsoft YaHei', 8), wrap='word')
        format_desc.pack(fill='x', padx=5, pady=5)
        format_desc.insert('1.0', "格式说明：\n• DXT1: 无透明或黑白透明，文件最小\n• DXT3: 黑白透明，适中文件大小\n• DXT5: 渐变透明，较大文件\n• RGBA8888: 最高质量，文件最大")
        format_desc.config(state='disabled')
        
        # 处理按钮
        button_frame = tk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="生成材质配置", 
                  command=self.process_material, style='Custom.TButton').pack()
    
    def create_resize_tab(self):
        """创建静态图像调整选项卡"""
        # 创建主框架
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="静态图像调整")
        
        # 创建Canvas和滚动条
        canvas = tk.Canvas(main_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 说明文本
        desc_frame = tk.Frame(scrollable_frame, bg='#2b2b2b')
        desc_frame.pack(fill='x', padx=10, pady=5)
        
        desc_text = tk.Text(desc_frame, height=3, bg='#2b2b2b', fg='#ffffff', 
                           font=('Microsoft YaHei', 9), wrap='word')
        desc_text.pack(fill='x', padx=5, pady=5)
        desc_text.insert('1.0', "功能说明：将图像文件调整尺寸到指定大小，然后转换为VTF格式。\n适用于需要调整贴图尺寸的场景，支持多种图像格式。")
        desc_text.config(state='disabled')
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(scrollable_frame, text="文件选择")
        file_frame.pack(fill='x', padx=10, pady=5)
        
        # 图像文件选择
        img_frame = tk.Frame(file_frame)
        img_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(img_frame, text="图像文件:").pack(side='left')
        self.resize_img_var = tk.StringVar()
        img_entry = ttk.Entry(img_frame, textvariable=self.resize_img_var, width=40)
        img_entry.pack(side='left', padx=(10, 5), fill='x', expand=True)
        ttk.Button(img_frame, text="选择文件", command=self.browse_resize_image).pack(side='right', padx=(0, 5))
        ttk.Button(img_frame, text="选择文件夹", command=self.browse_resize_folder).pack(side='right')
        
        # 已选择文件列表
        list_frame = tk.Frame(file_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        ttk.Label(list_frame, text="已选择的文件:").pack(anchor='w')
        
        # 文件列表框和滚动条
        listbox_frame = tk.Frame(list_frame)
        listbox_frame.pack(fill='both', expand=True)
        
        self.resize_files_listbox = tk.Listbox(listbox_frame, height=6)
        scrollbar3 = tk.Scrollbar(listbox_frame, orient='vertical', command=self.resize_files_listbox.yview)
        self.resize_files_listbox.configure(yscrollcommand=scrollbar3.set)
        
        self.resize_files_listbox.pack(side='left', fill='both', expand=True)
        scrollbar3.pack(side='right', fill='y')
        
        # 文件管理按钮
        btn_frame3 = tk.Frame(list_frame)
        btn_frame3.pack(fill='x', pady=(5, 0))
        
        ttk.Button(btn_frame3, text="删除选中", command=self.remove_selected_resize_file).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame3, text="清空列表", command=self.clear_resize_file_list).pack(side='left')
        
        # 尺寸设置
        size_frame = ttk.LabelFrame(scrollable_frame, text="尺寸设置")
        size_frame.pack(fill='x', padx=10, pady=5)
        
        size_controls = tk.Frame(size_frame)
        size_controls.pack(padx=5, pady=5)
        
        ttk.Label(size_controls, text="宽度:").grid(row=0, column=0, padx=5, pady=5)
        self.resize_width_var = tk.StringVar(value="1024")
        ttk.Entry(size_controls, textvariable=self.resize_width_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(size_controls, text="高度:").grid(row=0, column=2, padx=5, pady=5)
        self.resize_height_var = tk.StringVar(value="1024")
        ttk.Entry(size_controls, textvariable=self.resize_height_var, width=10).grid(row=0, column=3, padx=5, pady=5)
        
        # 智能压缩格式选择
        format_frame = ttk.LabelFrame(scrollable_frame, text="压缩格式选择")
        format_frame.pack(fill='x', padx=10, pady=5)
        
        # 格式选择模式
        mode_frame = tk.Frame(format_frame)
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        self.resize_format_mode_var = tk.StringVar(value="auto")
        ttk.Radiobutton(mode_frame, text="智能检测（推荐）", variable=self.resize_format_mode_var, 
                       value="auto", command=self.on_format_mode_change).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="自定义规则", variable=self.resize_format_mode_var, 
                       value="custom", command=self.on_format_mode_change).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="手动选择", variable=self.resize_format_mode_var, 
                       value="manual", command=self.on_format_mode_change).pack(side='left')
        
        # 智能检测说明
        self.resize_auto_info_var = tk.StringVar(value="将自动检测图像Alpha通道并选择最佳压缩格式")
        self.resize_auto_info_label = ttk.Label(format_frame, textvariable=self.resize_auto_info_var, foreground='blue')
        self.resize_auto_info_label.pack(fill='x', padx=5, pady=2)
        
        # 自定义规则选择（默认隐藏）
        self.resize_custom_format_frame = tk.Frame(format_frame)
        
        # 为每种透明度类型创建格式选择
        alpha_types = [("无透明", "no_alpha"), ("黑白透明", "binary_alpha"), ("渐变透明", "gradient_alpha")]
        formats = ["DXT1", "DXT3", "DXT5", "RGBA8888"]
        default_formats = ["DXT1", "DXT3", "DXT5"]  # 为每种类型设置合理的默认值
        
        self.resize_custom_format_vars = {}
        for i, (type_name, type_key) in enumerate(alpha_types):
            type_frame = tk.Frame(self.resize_custom_format_frame)
            type_frame.pack(fill='x', padx=5, pady=2)
            
            ttk.Label(type_frame, text=f"{type_name}:", width=12).pack(side='left')
            
            self.resize_custom_format_vars[type_key] = tk.StringVar(value=default_formats[i])
            format_frame_inner = tk.Frame(type_frame)
            format_frame_inner.pack(side='left', fill='x', expand=True)
            
            for fmt in formats:
                ttk.Radiobutton(format_frame_inner, text=fmt, variable=self.resize_custom_format_vars[type_key], 
                               value=fmt).pack(side='left', padx=5)
        
        # 手动格式选择（默认隐藏）
        self.resize_manual_format_frame = tk.Frame(format_frame)
        
        self.resize_format_var = tk.StringVar(value="DXT1")
        formats = ["RGBA8888", "DXT5", "DXT3", "DXT1"]
        for i, fmt in enumerate(formats):
            ttk.Radiobutton(self.resize_manual_format_frame, text=fmt, variable=self.resize_format_var, 
                           value=fmt).grid(row=0, column=i, padx=10, pady=5, sticky='w')
        
        # 格式说明
        resize_format_desc = tk.Text(format_frame, height=3, bg='#f8f8f8', fg='#666666', 
                             font=('Microsoft YaHei', 8), wrap='word')
        resize_format_desc.pack(fill='x', padx=5, pady=5)
        resize_format_desc.insert('1.0', "格式说明：\n• DXT1: 无透明或黑白透明，文件最小\n• DXT3: 黑白透明，适中文件大小\n• DXT5: 渐变透明，较大文件\n• RGBA8888: 最高质量，文件最大")
        resize_format_desc.config(state='disabled')
        
        # 处理按钮
        button_frame = tk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="调整图像尺寸", 
                  command=self.process_resize, style='Custom.TButton').pack()
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_frame = tk.Frame(self.root, bg='#404040', height=30)
        self.status_frame.pack(fill='x', side='bottom')
        self.status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(self.status_frame, text="就绪", 
                                    bg='#404040', fg='#ffffff', 
                                    font=('Microsoft YaHei', 9))
        self.status_label.pack(side='left', padx=10, pady=5)
        
        # 进度条
        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate')
        self.progress.pack(side='right', padx=10, pady=5, fill='x', expand=True)
    
    def update_status(self, message):
        """更新状态栏"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def log_message(self, message):
        """记录消息到状态栏和控制台"""
        self.update_status(message)
        print(message)
    
    def is_file_blacklisted(self, filename):
        """检查文件是否在全局屏蔽词列表中"""
        # 收集所有屏蔽词
        blacklist_words = []
        
        # 添加预设屏蔽词
        for word, var in self.preset_blacklist_vars.items():
            if var.get():
                blacklist_words.append(word)
        
        # 添加自定义屏蔽词
        custom_words = self.custom_blacklist_var.get().strip()
        if custom_words:
            custom_list = [word.strip() for word in custom_words.split(',') if word.strip()]
            blacklist_words.extend(custom_list)
        
        # 检查文件名是否包含任何屏蔽词
        filename_lower = filename.lower()
        for word in blacklist_words:
            if word.lower() in filename_lower:
                return True
        
        return False
    
    def start_progress(self):
        """开始进度条动画"""
        self.progress.start(10)
    
    def stop_progress(self):
        """停止进度条动画"""
        self.progress.stop()
    
    def check_dependencies(self):
        """检查依赖工具"""
        missing_tools = []
        
        # 检查vtfcmd
        try:
            subprocess.run(['vtfcmd', '-help'], capture_output=True, check=False)
        except FileNotFoundError:
            missing_tools.append('vtfcmd.exe')
        
        # 检查ImageMagick
        try:
            subprocess.run(['magick', '-version'], capture_output=True, check=False)
        except FileNotFoundError:
            missing_tools.append('ImageMagick (magick.exe)')
        
        if missing_tools:
            messagebox.showwarning("依赖检查", 
                                 f"未找到以下工具，部分功能可能无法使用：\n" + 
                                 "\n".join(missing_tools))
    
    def browse_nightglow_vtf(self):
        """浏览夜光VTF文件（支持多选）"""
        filenames = filedialog.askopenfilenames(
            title="选择VTF文件（可多选）",
            filetypes=[("VTF文件", "*.vtf"), ("所有文件", "*.*")]
        )
        if filenames:
            for filename in filenames:
                if filename not in self.nightglow_files:
                    self.nightglow_files.append(filename)
                    self.files_listbox.insert(tk.END, os.path.basename(filename))
            
            # 更新输入框显示
            self.nightglow_vtf_var.set(f"已选择 {len(self.nightglow_files)} 个文件")
    
    def browse_nightglow_folder(self):
        """浏览夜光VTF文件夹"""
        folder = filedialog.askdirectory(title="选择包含VTF文件的文件夹")
        if folder:
            # 查找文件夹中的所有VTF文件
            vtf_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.vtf'):
                        vtf_files.append(os.path.join(root, file))
            
            if vtf_files:
                for filename in vtf_files:
                    if filename not in self.nightglow_files:
                        self.nightglow_files.append(filename)
                        self.files_listbox.insert(tk.END, os.path.basename(filename))
                
                # 更新输入框显示
                self.nightglow_vtf_var.set(f"已选择 {len(self.nightglow_files)} 个文件")
                messagebox.showinfo("成功", f"从文件夹中找到并添加了 {len(vtf_files)} 个VTF文件")
            else:
                messagebox.showwarning("警告", "选择的文件夹中没有找到VTF文件")
    
    def remove_selected_file(self):
        """删除选中的文件"""
        selection = self.files_listbox.curselection()
        if selection:
            index = selection[0]
            self.files_listbox.delete(index)
            del self.nightglow_files[index]
            # 更新输入框显示
            if self.nightglow_files:
                self.nightglow_vtf_var.set(f"已选择 {len(self.nightglow_files)} 个文件")
            else:
                self.nightglow_vtf_var.set("")
    
    def clear_file_list(self):
        """清空文件列表"""
        self.files_listbox.delete(0, tk.END)
        self.nightglow_files.clear()
        self.nightglow_vtf_var.set("")
    
    def browse_material_image(self):
        """浏览材质图像文件（支持多选）"""
        filenames = filedialog.askopenfilenames(
            title="选择图像文件（可多选）",
            filetypes=[("图像文件", "*.png *.jpg *.jpeg *.tga *.bmp"), 
                      ("所有文件", "*.*")]
        )
        if filenames:
            for filename in filenames:
                if filename not in self.material_files:
                    self.material_files.append(filename)
                    self.material_files_listbox.insert(tk.END, os.path.basename(filename))
            
            # 更新输入框显示
            self.material_img_var.set(f"已选择 {len(self.material_files)} 个文件")
    
    def browse_material_folder(self):
        """浏览材质图像文件夹"""
        folder = filedialog.askdirectory(title="选择包含图像文件的文件夹")
        if folder:
            # 查找文件夹中的所有图像文件
            image_files = []
            image_extensions = ['.png', '.jpg', '.jpeg', '.tga', '.bmp']
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        image_files.append(os.path.join(root, file))
            
            if image_files:
                for filename in image_files:
                    if filename not in self.material_files:
                        self.material_files.append(filename)
                        self.material_files_listbox.insert(tk.END, os.path.basename(filename))
                
                # 更新输入框显示
                self.material_img_var.set(f"已选择 {len(self.material_files)} 个文件")
                messagebox.showinfo("成功", f"从文件夹中找到并添加了 {len(image_files)} 个图像文件")
            else:
                messagebox.showwarning("警告", "选择的文件夹中没有找到图像文件")
    
    def remove_selected_material_file(self):
        """删除选中的材质文件"""
        selection = self.material_files_listbox.curselection()
        if selection:
            index = selection[0]
            self.material_files_listbox.delete(index)
            del self.material_files[index]
            # 更新输入框显示
            if self.material_files:
                self.material_img_var.set(f"已选择 {len(self.material_files)} 个文件")
            else:
                self.material_img_var.set("")
    
    def clear_material_file_list(self):
        """清空材质文件列表"""
        self.material_files_listbox.delete(0, tk.END)
        self.material_files.clear()
        self.material_img_var.set("")
    
    def browse_material_output(self):
        """浏览材质输出目录"""
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.material_output_var.set(dirname)
    
    def browse_qci_file(self):
        """浏览QCI文件"""
        filename = filedialog.askopenfilename(
            title="选择QCI文件",
            filetypes=[("QCI文件", "*.qci"), ("所有文件", "*.*")]
        )
        if filename:
            self.qci_file_var.set(filename)
    
    def read_cdmaterials_from_qci(self):
        """从QCI文件读取$cdmaterials路径"""
        qci_file = self.qci_file_var.get().strip()
        if not qci_file or not os.path.exists(qci_file):
            messagebox.showerror("错误", "请先选择有效的QCI文件")
            return
        
        try:
            with open(qci_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 查找$cdmaterials行
            import re
            # 支持带引号和不带引号的格式
            pattern1 = r'\$cdmaterials\s+"([^"]+)"'  # 带引号格式
            pattern2 = r'\$cdmaterials\s+([^\s\r\n]+)'  # 不带引号格式
            
            match = re.search(pattern1, content, re.IGNORECASE)
            if not match:
                match = re.search(pattern2, content, re.IGNORECASE)
            
            if match:
                cdmaterials_path = match.group(1)
                # 转换为materials路径格式
                materials_path = f"materials/{cdmaterials_path}"
                self.cdmaterials_var.set(materials_path)
                messagebox.showinfo("成功", f"已读取材质路径：{materials_path}")
            else:
                messagebox.showwarning("警告", "在QCI文件中未找到$cdmaterials定义")
                
        except Exception as e:
            messagebox.showerror("错误", f"读取QCI文件失败：{str(e)}")
    

    
    def browse_lightwarp_file(self):
        """浏览Lightwarp文件"""
        filename = filedialog.askopenfilename(
            title="选择Lightwarp文件",
            filetypes=[("VTF文件", "*.vtf"), ("所有文件", "*.*")]
        )
        if filename:
            self.lightwarp_var.set(filename)
    
    def detect_alpha_channels(self):
        """检测所有选中图像的Alpha通道类型"""
        if not self.material_files:
            messagebox.showerror("错误", "请先选择图像文件")
            return
        
        try:
            alpha_types = set()
            total_files = len(self.material_files)
            
            for i, img_file in enumerate(self.material_files, 1):
                self.update_status(f"检测Alpha通道... ({i}/{total_files})")
                alpha_type = self.analyze_alpha_channel(img_file)
                alpha_types.add(alpha_type)
            
            # 根据检测结果提供建议
            if len(alpha_types) == 1:
                alpha_type = list(alpha_types)[0]
                self.alpha_info_var.set(f"检测结果: {alpha_type}")
                self.suggest_format_and_vmt(alpha_type)
            else:
                self.alpha_info_var.set(f"混合类型: {', '.join(alpha_types)}")
                self.format_suggestion_var.set("建议: 混合类型，请手动选择格式")
            
            self.update_status("Alpha通道检测完成")
            
        except Exception as e:
            messagebox.showerror("错误", f"Alpha通道检测失败: {str(e)}")
            self.update_status("检测失败")
    
    def analyze_alpha_channel(self, img_file):
        """分析单个图像的Alpha通道类型"""
        import subprocess
        
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
            
            # 检查是否主要是0和1值（二值化alpha）
            cmd = ['magick', img_file, '-alpha', 'extract', '-threshold', '50%', '-format', '%[fx:mean]', 'info:']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                threshold_mean = float(result.stdout.strip())
                print(f"阈值化后均值: {threshold_mean:.3f}")
                
                # 如果阈值化后的均值与原始均值相近，且标准差较大，说明主要是黑白值
                if abs(alpha_mean - threshold_mean) < 0.05 and alpha_std > 0.3:
                    return "黑白透明"
            
            return "渐变透明"
            
        except (ValueError, IndexError) as e:
            print(f"Alpha分析异常: {e}")
            return "渐变透明"
    
    def suggest_format_and_vmt(self, alpha_type):
        """根据Alpha通道类型建议格式和VMT配置"""
        if alpha_type == "无透明":
            self.material_format_var.set("DXT1")
            self.format_suggestion_var.set("建议: DXT1 (无透明通道)")
            self.vmt_alpha_config = None
        elif alpha_type == "黑白透明":
            self.material_format_var.set("DXT3")
            self.format_suggestion_var.set("建议: DXT3 + $alphatest (黑白透明)")
            self.vmt_alpha_config = '"$alphatest" "1"'
        elif alpha_type == "渐变透明":
            self.material_format_var.set("DXT5")
            self.format_suggestion_var.set("建议: DXT5 + $translucent (渐变透明)")
            self.vmt_alpha_config = '"$translucent" "1"'
        else:
            self.vmt_alpha_config = None
    
    def on_format_mode_change(self):
        """格式模式切换回调"""
        # 处理材质配置选项卡
        if hasattr(self, 'material_format_mode_var'):
            mode = self.material_format_mode_var.get()
            
            # 隐藏所有框架
            if hasattr(self, 'auto_info_label'):
                self.auto_info_label.pack_forget()
            if hasattr(self, 'custom_format_frame'):
                self.custom_format_frame.pack_forget()
            if hasattr(self, 'manual_format_frame'):
                self.manual_format_frame.pack_forget()
            
            # 根据模式显示相应框架
            if mode == "auto":
                if hasattr(self, 'auto_info_label'):
                    self.auto_info_label.pack(fill='x', padx=5, pady=2)
                    self.auto_info_var.set("将自动检测图像Alpha通道并选择最佳压缩格式")
            elif mode == "custom":
                if hasattr(self, 'custom_format_frame'):
                    self.custom_format_frame.pack(fill='x', padx=5, pady=5)
            elif mode == "manual":
                if hasattr(self, 'manual_format_frame'):
                    self.manual_format_frame.pack(fill='x', padx=5, pady=5)
        
        # 处理静态图像调整选项卡
        if hasattr(self, 'resize_format_mode_var'):
            mode = self.resize_format_mode_var.get()
            
            # 隐藏所有框架
            if hasattr(self, 'resize_auto_info_label'):
                self.resize_auto_info_label.pack_forget()
            if hasattr(self, 'resize_custom_format_frame'):
                self.resize_custom_format_frame.pack_forget()
            if hasattr(self, 'resize_manual_format_frame'):
                self.resize_manual_format_frame.pack_forget()
            
            # 根据模式显示相应框架
            if mode == "auto":
                if hasattr(self, 'resize_auto_info_label'):
                    self.resize_auto_info_label.pack(fill='x', padx=5, pady=2)
                    self.resize_auto_info_var.set("将自动检测图像Alpha通道并选择最佳压缩格式")
            elif mode == "custom":
                if hasattr(self, 'resize_custom_format_frame'):
                    self.resize_custom_format_frame.pack(fill='x', padx=5, pady=5)
            elif mode == "manual":
                if hasattr(self, 'resize_manual_format_frame'):
                    self.resize_manual_format_frame.pack(fill='x', padx=5, pady=5)
    
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
    
    def get_custom_format_and_vmt(self, alpha_type, custom_vars):
        """根据自定义规则获取格式和VMT配置"""
        # 映射alpha类型到变量键
        type_map = {
            "无透明": "no_alpha",
            "黑白透明": "binary_alpha", 
            "渐变透明": "gradient_alpha"
        }
        
        type_key = type_map.get(alpha_type, "no_alpha")
        format_name = custom_vars.get(type_key, tk.StringVar(value="DXT1")).get()
        
        # 根据格式和alpha类型确定VMT配置
        vmt_config = ""
        if alpha_type == "黑白透明" and format_name in ["DXT3", "DXT5"]:
            vmt_config = '"$alphatest" "1"'
        elif alpha_type == "渐变透明" and format_name in ["DXT5", "RGBA8888"]:
            vmt_config = '"$translucent" "1"'
        
        return format_name, vmt_config
    
    def browse_resize_image(self):
        """浏览调整尺寸的图像文件（支持多选）"""
        filenames = filedialog.askopenfilenames(
            title="选择图像文件（可多选）",
            filetypes=[("图像文件", "*.png *.jpg *.jpeg *.tga *.bmp"), 
                      ("所有文件", "*.*")]
        )
        if filenames:
            for filename in filenames:
                if filename not in self.resize_files:
                    self.resize_files.append(filename)
                    self.resize_files_listbox.insert(tk.END, os.path.basename(filename))
            
            # 更新输入框显示
            self.resize_img_var.set(f"已选择 {len(self.resize_files)} 个文件")
    
    def browse_resize_folder(self):
        """浏览调整尺寸的图像文件夹"""
        folder = filedialog.askdirectory(title="选择包含图像文件的文件夹")
        if folder:
            # 查找文件夹中的所有图像文件
            image_files = []
            image_extensions = ['.png', '.jpg', '.jpeg', '.tga', '.bmp']
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        image_files.append(os.path.join(root, file))
            
            if image_files:
                for filename in image_files:
                    if filename not in self.resize_files:
                        self.resize_files.append(filename)
                        self.resize_files_listbox.insert(tk.END, os.path.basename(filename))
                
                # 更新输入框显示
                self.resize_img_var.set(f"已选择 {len(self.resize_files)} 个文件")
                messagebox.showinfo("成功", f"从文件夹中找到并添加了 {len(image_files)} 个图像文件")
            else:
                messagebox.showwarning("警告", "选择的文件夹中没有找到图像文件")
    
    def remove_selected_resize_file(self):
        """删除选中的调整文件"""
        selection = self.resize_files_listbox.curselection()
        if selection:
            index = selection[0]
            self.resize_files_listbox.delete(index)
            del self.resize_files[index]
            # 更新输入框显示
            if self.resize_files:
                self.resize_img_var.set(f"已选择 {len(self.resize_files)} 个文件")
            else:
                self.resize_img_var.set("")
    
    def clear_resize_file_list(self):
        """清空调整文件列表"""
        self.resize_files_listbox.delete(0, tk.END)
        self.resize_files.clear()
        self.resize_img_var.set("")
    
    def get_vtf_format_param(self, format_name):
        """获取VTF格式参数"""
        format_map = {
            "RGBA8888": "rgba8888",
            "DXT5": "dxt5",
            "DXT3": "dxt3",
            "DXT1": "dxt1"
        }
        return format_map.get(format_name, "dxt1")
    
    def get_vtf_command_params(self, format_name):
        """获取VTF命令参数，包括format和alphaformat"""
        format_param = self.get_vtf_format_param(format_name)
        
        # 对于RGBA8888，强制使用rgba8888格式，不使用压缩
        if format_name == "RGBA8888":
            return ['-format', 'rgba8888', '-alphaformat', 'rgba8888']
        # 对于其他格式，使用相同的format和alphaformat
        else:
            return ['-format', format_param, '-alphaformat', format_param]
    
    def process_nightglow(self):
        """处理夜光效果"""
        if not self.nightglow_files:
            messagebox.showerror("错误", "请选择至少一个VTF文件")
            return
        
        # 检查所有文件是否存在
        invalid_files = [f for f in self.nightglow_files if not os.path.exists(f)]
        if invalid_files:
            messagebox.showerror("错误", f"以下文件不存在：\n{chr(10).join(invalid_files)}")
            return
        
        def worker():
            try:
                self.start_progress()
                total_files = len(self.nightglow_files)
                
                for i, vtf_file in enumerate(self.nightglow_files, 1):
                    self.update_status(f"正在处理夜光效果... ({i}/{total_files})")
                    
                    vtf_path = Path(vtf_file)
                    work_dir = vtf_path.parent
                    base_name = vtf_path.stem
                    
                    # 检查全局屏蔽词
                    if self.is_file_blacklisted(base_name):
                        self.log_message(f"跳过全局屏蔽词文件: {base_name}")
                        continue
                    
                    # 创建Selfillum目录
                    selfillum_dir = work_dir / "Selfillum"
                    selfillum_dir.mkdir(exist_ok=True)
                
                    # 1. VTF转TGA
                    self.update_status(f"转换VTF到TGA... ({i}/{total_files})")
                    
                    # 检查VTF文件是否存在
                    if not vtf_path.exists():
                        raise Exception(f"VTF文件不存在: {vtf_file}")
                    
                    # 创建临时目录用于VTF转换
                    import tempfile
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)
                        cmd = [self.vtfcmd_path, '-file', str(vtf_path.absolute()), '-output', str(temp_path), '-exportformat', 'tga']
                        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                        
                        # 详细的错误信息
                        if result.returncode != 0:
                            error_msg = f"VTF转TGA失败\n"
                            error_msg += f"命令: {' '.join(cmd)}\n"
                            error_msg += f"返回码: {result.returncode}\n"
                            error_msg += f"标准输出: {result.stdout}\n"
                            error_msg += f"错误输出: {result.stderr}"
                            raise Exception(error_msg)
                        
                        # 查找临时目录中生成的TGA文件
                        tga_files = list(temp_path.glob(f"{base_name}*.tga"))
                        if not tga_files:
                            # 查找所有TGA文件
                            all_tga_files = list(temp_path.glob("*.tga"))
                            error_msg = f"未找到转换后的TGA文件: {base_name}*.tga\n"
                            error_msg += f"临时目录: {temp_path}\n"
                            error_msg += f"查找模式: {base_name}*.tga\n"
                            error_msg += f"临时目录中的所有TGA文件: {[f.name for f in all_tga_files]}\n"
                            error_msg += f"VTFCmd输出: {result.stdout}"
                            raise Exception(error_msg)
                        
                        # 将TGA文件复制到工作目录
                        temp_tga = tga_files[0]
                        tga_file = work_dir / temp_tga.name
                        import shutil
                        shutil.copy2(temp_tga, tga_file)

                    
                    # 2. 使用ImageMagick调整Alpha通道
                    self.update_status(f"调整Alpha通道... ({i}/{total_files})")
                    temp_file = work_dir / f"{base_name}_full_alpha.tga"
                    final_file = selfillum_dir / f"{base_name}.tga"
                    
                    # 添加全白Alpha通道
                    cmd1 = ['magick', str(tga_file), '-alpha', 'set', '-channel', 'A', 
                           '-evaluate', 'set', '100%', '+channel', str(temp_file)]
                    result = subprocess.run(cmd1, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    if result.returncode != 0:
                        raise Exception(f"设置Alpha通道失败: {result.stderr}")
                    
                    # 降低Alpha到5%
                    cmd2 = ['magick', str(temp_file), '-channel', 'A', '-evaluate', 
                           'multiply', '0.05', '+channel', str(final_file)]
                    result = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    if result.returncode != 0:
                        raise Exception(f"调整Alpha透明度失败: {result.stderr}")
                    
                    # 清理临时文件
                    if temp_file.exists():
                        temp_file.unlink()
                    if tga_file.exists():
                        tga_file.unlink()
                    
                    # 3. TGA转回VTF
                    self.update_status(f"转换TGA到VTF... ({i}/{total_files})")
                    format_params = self.get_vtf_command_params(self.nightglow_format_var.get())
                    cmd3 = [self.vtfcmd_path, '-file', str(final_file), '-output', str(selfillum_dir)] + format_params
                    result = subprocess.run(cmd3, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    if result.returncode != 0:
                        raise Exception(f"TGA转VTF失败: {result.stderr}")
                    
                    # 保留TGA文件供用户查看（可选）
                    # if final_file.exists():
                    #     final_file.unlink()
                    
                    # 如果启用了vmtE发光生成功能
                    if self.vmte_glow_var.get():
                        emissive_processed = self.process_vmte_glow(vtf_path, work_dir, base_name, i, total_files)
                        
                        # 如果成功生成了E发光，则清理Selfillum文件夹中的相关文件
                        if emissive_processed:
                            selfillum_dir = work_dir / "Selfillum"
                            if selfillum_dir.exists():
                                selfillum_vtf = selfillum_dir / f"{base_name}.vtf"
                                selfillum_tga = selfillum_dir / f"{base_name}.tga"
                                if selfillum_vtf.exists():
                                    selfillum_vtf.unlink()
                                    self.log_message(f"已清理Selfillum中的VTF文件: {selfillum_vtf}")
                                if selfillum_tga.exists():
                                    selfillum_tga.unlink()
                                    self.log_message(f"已清理Selfillum中的TGA文件: {selfillum_tga}")
                            
                            # 清理父级文件夹中的TGA文件
                            parent_tga = work_dir / f"{base_name}.tga"
                            if parent_tga.exists():
                                parent_tga.unlink()
                                self.log_message(f"已清理父级文件夹中的TGA: {parent_tga}")
                
                # 如果启用了修改vmt-base功能
                if self.modify_vmtbase_var.get():
                    self.modify_vmt_base()
                
                # 最后清理所有残留的TGA文件
                self.update_status("清理临时文件...")
                for vtf_file in self.nightglow_files:
                    vtf_path = Path(vtf_file)
                    work_dir = vtf_path.parent
                    base_name = vtf_path.stem
                    
                    # 清理父级文件夹中的TGA文件
                    parent_tga = work_dir / f"{base_name}.tga"
                    if parent_tga.exists():
                        parent_tga.unlink()
                        self.log_message(f"已清理残留TGA文件: {parent_tga}")
                    
                    # 清理Selfillum文件夹中的TGA文件
                    selfillum_dir = work_dir / "Selfillum"
                    if selfillum_dir.exists():
                        selfillum_tga = selfillum_dir / f"{base_name}.tga"
                        if selfillum_tga.exists():
                            selfillum_tga.unlink()
                            self.log_message(f"已清理Selfillum中的TGA文件: {selfillum_tga}")
                
                self.update_status("夜光效果处理完成")
                messagebox.showinfo("成功", f"夜光效果处理完成！\n已处理 {total_files} 个文件")
                
            except Exception as e:
                self.update_status("处理失败")
                messagebox.showerror("错误", f"处理失败: {str(e)}")
            finally:
                self.stop_progress()
        
        threading.Thread(target=worker, daemon=True).start()
    
    def process_vmte_glow(self, vtf_path, work_dir, base_name, current_file, total_files):
        """处理vmtE发光生成功能"""
        try:
            # 检查屏蔽词
            blacklist_text = self.blacklist_var.get().strip()
            if blacklist_text:
                blacklist_words = [word.strip() for word in blacklist_text.split(',') if word.strip()]
                for word in blacklist_words:
                    if word.lower() in base_name.lower():
                        self.log_message(f"跳过屏蔽词文件: {base_name} (包含: {word})")
                        return
            
            self.update_status(f"处理vmtE发光生成... ({current_file}/{total_files})")
            
            # 1. 将VTF转换为TGA以检测Alpha通道（确保保留Alpha信息）
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                # 尝试多种方法确保Alpha通道被正确导出
                # 方法1: 使用标准TGA导出
                cmd = [self.vtfcmd_path, '-file', str(vtf_path.absolute()), '-output', str(temp_path), '-exportformat', 'tga']
                
                # 如果原始VTF是DXT5格式（支持Alpha），尝试添加特殊参数
                # 先检查VTF信息
                cmd_info = [self.vtfcmd_path, '-file', str(vtf_path.absolute())]
                info_result = subprocess.run(cmd_info, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                
                has_alpha = False
                if info_result.returncode == 0 and info_result.stdout:
                    vtf_info = info_result.stdout.lower()
                    # 检查是否是支持Alpha的格式
                    if any(fmt in vtf_info for fmt in ['dxt5', 'dxt3', 'rgba8888', 'bgra8888']):
                        has_alpha = True
                        self.log_message(f"检测到支持Alpha的VTF格式")
                
                if has_alpha:
                    # 对于有Alpha的格式，尝试使用PNG导出以保留Alpha信息
                    cmd_png = [self.vtfcmd_path, '-file', str(vtf_path.absolute()), '-output', str(temp_path), '-exportformat', 'png']
                    result_png = subprocess.run(cmd_png, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    
                    if result_png.returncode == 0:
                        # PNG导出成功，转换为TGA
                        png_files = list(temp_path.glob(f"{base_name}*.png"))
                        if not png_files:
                            png_files = list(temp_path.glob("*.png"))
                        
                        if png_files:
                            png_file = png_files[0]
                            tga_file = temp_path / f"{base_name}.tga"
                            
                            # 使用ImageMagick将PNG转为TGA，保留Alpha
                            cmd_convert = ['magick', str(png_file), str(tga_file)]
                            convert_result = subprocess.run(cmd_convert, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                            
                            if convert_result.returncode == 0:
                                self.log_message(f"通过PNG中转成功保留Alpha通道")
                                # 删除PNG文件
                                png_file.unlink()
                                # 使用转换后的TGA文件
                                cmd = None  # 跳过原始TGA导出
                            else:
                                self.log_message(f"PNG转TGA失败，使用原始方法: {convert_result.stderr}")
                
                if cmd:  # 如果没有通过PNG中转成功，使用原始方法
                    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    
                    self.log_message(f"VTF转TGA命令: {' '.join(cmd)}")
                    if result.stdout:
                        self.log_message(f"VTFCMD输出: {result.stdout}")
                    if result.stderr:
                        self.log_message(f"VTFCMD错误: {result.stderr}")
                    
                    if result.returncode != 0:
                        raise Exception(f"VTF转TGA失败: {result.stderr}")
                
                # 查找生成的TGA文件
                tga_files = list(temp_path.glob(f"{base_name}*.tga"))
                if not tga_files:
                    tga_files = list(temp_path.glob("*.tga"))
                if not tga_files:
                    raise Exception(f"未找到转换后的TGA文件")
                else:
                    self.log_message(f"找到TGA文件: {[str(f) for f in tga_files]}")
                
                temp_tga = tga_files[0]
                
                # 验证TGA文件的Alpha通道信息
                cmd_info = ['magick', 'identify', '-verbose', str(temp_tga)]
                result_info = subprocess.run(cmd_info, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result_info.returncode == 0:
                    # 查找Alpha相关信息
                    info_lines = result_info.stdout.split('\n')
                    for line in info_lines:
                        if 'alpha' in line.lower() or 'matte' in line.lower() or 'channel' in line.lower():
                            self.log_message(f"TGA文件信息: {line.strip()}")
                
                # 额外检查：直接查看TGA文件的通道信息
                cmd_channels = ['magick', 'identify', '-format', '%[channels] %[colorspace] %[type]', str(temp_tga)]
                result_channels = subprocess.run(cmd_channels, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result_channels.returncode == 0:
                    self.log_message(f"TGA通道信息: {result_channels.stdout.strip()}")
                
                # 2. 检测Alpha通道是否为全白（最精确的检测方法）
                try:
                    # 方法1: 检查Alpha通道的统计信息
                    cmd_stats = ['magick', str(temp_tga), '-alpha', 'extract', '-format', '%[mean]\n%[min]\n%[max]\n%[standard-deviation]', 'info:']
                    result_stats = subprocess.run(cmd_stats, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    
                    # 方法2: 检查Alpha通道的直方图
                    cmd_hist = ['magick', str(temp_tga), '-alpha', 'extract', '-format', '%[fx:mean<0.999?0:1]', 'info:']
                    result_hist = subprocess.run(cmd_hist, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    
                    # 方法3: 检查Alpha通道的像素值分布
                    cmd_unique = ['magick', str(temp_tga), '-alpha', 'extract', '-unique-colors', '-format', '%[pixel:p{0,0}]\n', 'info:']
                    result_unique = subprocess.run(cmd_unique, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    
                    if result_stats.returncode != 0:
                        self.log_message(f"ImageMagick统计检测失败: {result_stats.stderr}，默认进行处理")
                        is_pure_white_alpha = False
                    else:
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
                            
                            self.log_message(f"Alpha通道统计 - 平均值: {alpha_mean:.6f}, 最小值: {alpha_min:.6f}, 最大值: {alpha_max:.6f}, 标准差: {alpha_std:.6f}")
                            
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
                                self.log_message(f"检测到全黑Alpha通道，跳过发光处理")
                                is_pure_white_alpha = True  # 跳过处理
                                condition1 = condition2 = condition3 = condition4 = False
                            
                            # 额外检查：直方图方法
                            hist_check = False
                            if result_hist.returncode == 0:
                                hist_result = result_hist.stdout.strip()
                                hist_check = (hist_result == '1')
                                self.log_message(f"Alpha通道直方图检查: {hist_result} (1=纯白, 0=有变化)")
                            
                            # 额外检查：唯一颜色数量
                            unique_check = True
                            if result_unique.returncode == 0:
                                unique_colors = result_unique.stdout.strip().split('\n')
                                unique_count = len([c for c in unique_colors if c.strip()])
                                self.log_message(f"Alpha通道唯一颜色数量: {unique_count}")
                                # 如果唯一颜色超过3个，很可能不是纯白
                                if unique_count > 3:
                                    unique_check = False
                            
                            # 检查标准差是否很小（可能是S发光而不是E发光）
                            is_small_variation = alpha_std < 0.01  # 标准差小于0.01认为是S发光
                            
                            # 综合判断：所有条件都满足才认为是纯白Alpha
                            is_pure_white_alpha = (condition1 and condition2 and condition3 and condition4 and hist_check and unique_check)
                            
                            self.log_message(f"Alpha检测结果 - 条件1(min>0.999): {condition1}, 条件2(max>0.9999): {condition2}, 条件3(std<0.001): {condition3}, 条件4(mean>0.999): {condition4}, 直方图检查: {hist_check}, 唯一色检查: {unique_check}")
                            
                            if is_small_variation and not is_black_alpha:
                                self.log_message(f"检测到标准差很小的Alpha通道(std={alpha_std:.6f})，建议作为S发光处理")
                                # 如果标准差很小且最小值不够高，跳过E发光处理
                                if not condition1:  # 最小值不够高，说明有透明区域
                                    self.log_message(f"Alpha通道最小值过低({alpha_min:.6f})，跳过E发光处理，建议使用S发光")
                                    is_pure_white_alpha = True  # 跳过E发光处理
                            
                            self.log_message(f"最终判断: {'跳过E发光处理' if is_pure_white_alpha else '进行E发光处理'}")
                            
                        else:
                            self.log_message(f"ImageMagick输出格式异常，默认进行处理")
                            is_pure_white_alpha = False
                        
                except Exception as e:
                    self.log_message(f"Alpha通道检测异常: {str(e)}，默认进行处理")
                    is_pure_white_alpha = False
                
                if not is_pure_white_alpha:
                    self.generate_emissive_texture_and_vmt(temp_tga, work_dir, base_name)
                    return True  # 返回处理成功状态
                else:
                    self.log_message(f"跳过E发光处理: {base_name}")
                    return False  # 返回未处理状态
                    
        except Exception as e:
            self.log_message(f"vmtE发光生成处理失败: {str(e)}")
            return False  # 返回处理失败状态
    
    def generate_emissive_texture_and_vmt(self, source_tga, work_dir, base_name):
        """生成发光贴图和VMT文件"""
        try:
            # 创建EmissiveGlow文件夹
            emissive_dir = work_dir / "EmissiveGlow"
            emissive_dir.mkdir(exist_ok=True)
            
            # 1. 生成_E贴图：将Alpha通道正片叠底到RGB通道，保持原始Alpha通道
            e_tga_file = emissive_dir / f"{base_name}_E.tga"
            
            # 使用ImageMagick生成E贴图：将Alpha通道作为蒙版应用到RGB通道
            cmd_process = [
                'magick', str(source_tga),
                '(', '+clone', '-alpha', 'extract', ')',
                '-channel', 'RGB', '-compose', 'multiply', '-composite',
                '+channel', str(source_tga), '-compose', 'copy_opacity', '-composite',
                str(e_tga_file)
            ]
            
            result = subprocess.run(cmd_process, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                raise Exception(f"生成E贴图失败: {result.stderr}")
            
            self.log_message(f"成功生成E贴图: {e_tga_file}")
            
            # 2. 转换_E贴图为VTF，使用用户选择的E贴图格式
            format_params = self.get_vtf_command_params(self.e_texture_format_var.get())
            cmd_vtf = [self.vtfcmd_path, '-file', str(e_tga_file), '-output', str(emissive_dir)] + format_params
            result = subprocess.run(cmd_vtf, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                raise Exception(f"_E贴图转VTF失败: {result.stderr}")
            
            self.log_message(f"成功转换E贴图为VTF格式: {self.e_texture_format_var.get()}")
            
            # 3. 生成VMT文件
            self.generate_emissive_vmt(emissive_dir, base_name, work_dir)
            
            # 清理TGA文件
            if e_tga_file.exists():
                e_tga_file.unlink()
                
        except Exception as e:
            raise Exception(f"生成发光贴图和VMT失败: {str(e)}")
    
    def generate_emissive_vmt(self, emissive_dir, base_name, original_work_dir):
        """生成发光VMT文件"""
        try:
            # 查找原始VTF文件对应的VMT文件
            original_vmt_file = original_work_dir / f"{base_name}.vmt"
            output_vmt_file = emissive_dir / f"{base_name}.vmt"
            
            # 查找材质路径
            materials_path = self.find_materials_path_for_nightglow(original_work_dir)
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
                    self.log_message(f"VMT文件已包含发光配置，跳过: {base_name}")
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
            raise Exception(f"生成发光VMT文件失败: {str(e)}")
    
    def generate_patch_vmt_with_emissive(self, existing_content, output_file, materials_path, base_name):
        """为patch格式的VMT添加发光配置"""
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
                
                # 添加发光配置到insert块中
                emissive_configs = [
                    '\t\t"$EmissiveBlendEnabled"\t\t\t"1"',
                    '\t\t"$EmissiveBlendStrength"\t\t\t"0.05"',
                    '\t\t"$EmissiveBlendTexture"\t\t\t"vgui/white"',
                    f'\t\t"$EmissiveBlendBaseTexture"\t\t"{materials_path}/{base_name}_E"',
                    '\t\t"$EmissiveBlendFlowTexture"\t\t"vgui/white"',
                    '\t\t"$EmissiveBlendTint"\t\t\t\t"[ 1 1 1 ]"',
                    '\t\t"$EmissiveBlendScrollVector"\t\t"[ 0 0 ]"'
                ]
                
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
                        # 添加$selfillum配置
                        new_lines.append('\t\t"$selfillum"\t\t\t\t\t"0"')
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
        
        self.log_message(f"已生成patch格式VMT文件: {output_file}")
    
    def generate_standard_vmt_with_emissive(self, existing_content, output_file, materials_path, base_name):
        """为标准格式的VMT添加发光配置"""
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
            
            # 在指定位置插入配置
            for i, config_line in enumerate(emissive_config):
                lines.insert(insert_index + i, config_line)
            
            # 写回文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            self.log_message(f"已生成标准格式VMT文件: {output_file}")
    
    def create_new_patch_vmt(self, output_file, materials_path, base_name):
        """创建新的patch格式VMT文件"""
        # 构建include路径
        include_path = f"materials/{materials_path}/shader/vmt-base.vmt"
        
        vmt_content = f'''patch
{{
\tinclude\t\t"{include_path}"
\tinsert
\t{{
\t\t"$EmissiveBlendEnabled"\t\t\t"1"
\t\t"$EmissiveBlendStrength"\t\t\t"0.05"
\t\t"$EmissiveBlendTexture"\t\t\t"vgui/white"
\t\t"$EmissiveBlendBaseTexture"\t\t"{materials_path}/{base_name}_E"
\t\t"$EmissiveBlendFlowTexture"\t\t"vgui/white"
\t\t"$EmissiveBlendTint"\t\t\t\t"[ 1 1 1 ]"
\t\t"$EmissiveBlendScrollVector"\t\t"[ 0 0 ]"
\t}}
\treplace
\t{{
\t\t"$basetexture" "{materials_path}/{base_name}"
\t\t"$selfillum"\t\t\t\t\t"0"
\t}}
}}
'''
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(vmt_content)
        
        self.log_message(f"已创建新的patch格式VMT文件: {output_file}")
    
    def find_shader_vmt_base(self, work_dir):
        """查找shader目录中的vmt-base.vmt文件"""
        try:
            current_path = Path(work_dir)
            while current_path.parent != current_path:
                shader_dir = current_path / "shader"
                vmt_base = shader_dir / "vmt-base.vmt"
                if vmt_base.exists():
                    return str(vmt_base).replace('\\', '/')
                current_path = current_path.parent
            return None
        except Exception:
            return None
    
    def find_materials_path_for_nightglow(self, work_dir):
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
    
    def modify_vmt_base(self):
        """修改vmt-base.vmt文件"""
        try:
            # 查找第一个VTF文件的目录作为基准
            if not self.nightglow_files:
                return
            
            first_vtf = Path(self.nightglow_files[0])
            work_dir = first_vtf.parent
            
            # 查找父级文件夹的shader子文件夹
            parent_dir = work_dir.parent
            shader_dir = parent_dir / "shader"
            vmt_base_file = shader_dir / "vmt-base.vmt"
            
            if not vmt_base_file.exists():
                print(f"未找到vmt-base.vmt文件: {vmt_base_file}")
                return
            
            # 读取文件内容
            with open(vmt_base_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找并替换注释的$selfillum行
            import re
            # 更灵活的正则表达式，匹配各种格式的注释$selfillum行
            pattern = r'//\s*"\$selfillum"\s+"1"\s+//\s*开启自发光。亮度区分取决于颜色贴图的\s*A\s*通道，越白则越亮。不做自发光必须关掉。'
            replacement = '\t"$selfillum"\t\t\t\t\t"1"\t\t\t\t// 开启自发光。亮度区分取决于颜色贴图的 A 通道，越白则越亮。不做自发光必须关掉。'
            
            if re.search(pattern, content):
                new_content = re.sub(pattern, replacement, content)
                
                # 写回文件
                with open(vmt_base_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"已修改vmt-base.vmt文件: {vmt_base_file}")
            else:
                # 如果第一个模式没匹配到，尝试更宽松的模式
                pattern2 = r'//\s*"\$selfillum"[^\n]*开启自发光[^\n]*不做自发光必须关掉[^\n]*'
                if re.search(pattern2, content):
                    new_content = re.sub(pattern2, replacement, content)
                    
                    # 写回文件
                    with open(vmt_base_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    print(f"已修改vmt-base.vmt文件: {vmt_base_file}")
                else:
                    print(f"在vmt-base.vmt中未找到需要修改的$selfillum行")
                    print(f"文件内容预览: {content[:500]}...")
                
        except Exception as e:
            print(f"修改vmt-base.vmt失败: {str(e)}")
    
    def process_material(self):
        """处理材质配置"""
        if not self.material_files:
            messagebox.showerror("错误", "请选择至少一个图像文件")
            return
        
        output_dir = self.material_output_var.get().strip()
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return
        
        # 检查所有文件是否存在
        invalid_files = [f for f in self.material_files if not os.path.exists(f)]
        if invalid_files:
            messagebox.showerror("错误", f"以下文件不存在：\n{chr(10).join(invalid_files)}")
            return
        
        def worker():
            try:
                self.start_progress()
                total_files = len(self.material_files)
                output_path = Path(output_dir)
                
                # 确保输出目录存在
                output_path.mkdir(parents=True, exist_ok=True)
                
                # 获取材质路径并构建完整的输出路径
                materials_path = self.cdmaterials_var.get().strip()
                if not materials_path:
                    raise Exception("请输入材质路径或从QCI文件读取")
                
                # 移除开头的materials/前缀（如果存在）
                if materials_path.startswith('materials/'):
                    materials_path = materials_path[10:]
                
                # 构建完整的materials路径结构
                full_materials_path = output_path / "materials" / materials_path
                full_materials_path.mkdir(parents=True, exist_ok=True)
                
                # 收集屏蔽词：预设屏蔽词 + 自定义屏蔽词
                blocked_keywords = []
                
                # 添加选中的预设屏蔽词
                for word, var in self.material_preset_blacklist_vars.items():
                    if var.get():
                        blocked_keywords.append(word)
                
                # 添加自定义屏蔽词
                custom_words = self.material_custom_blacklist_var.get().strip()
                if custom_words:
                    custom_list = [word.strip() for word in custom_words.split(',') if word.strip()]
                    blocked_keywords.extend(custom_list)
                processed_count = 0
                
                for i, img_file in enumerate(self.material_files, 1):
                    self.update_status(f"正在生成材质配置... ({i}/{total_files})")
                    
                    img_path = Path(img_file)
                    base_name = img_path.stem
                    
                    # 检查屏蔽词
                    is_blocked = any(keyword.lower() in base_name.lower() for keyword in blocked_keywords)
                    if is_blocked:
                        print(f"跳过文件 {base_name}：包含屏蔽词")
                        continue
                    
                    processed_count += 1
                    
                    # 根据模式选择格式
                    mode = self.material_format_mode_var.get()
                    if mode == "auto":
                        # 智能检测alpha通道
                        self.update_status(f"检测Alpha通道... ({i}/{total_files})")
                        alpha_type = self.analyze_alpha_channel(str(img_file))
                        format_name, vmt_config = self.get_optimal_format_and_vmt(alpha_type)
                        self.vmt_alpha_config = vmt_config
                        format_params = self.get_vtf_command_params(format_name)
                        print(f"智能检测: {os.path.basename(img_file)} -> {alpha_type} -> {format_name}")
                    elif mode == "custom":
                        # 自定义规则模式
                        self.update_status(f"检测Alpha通道... ({i}/{total_files})")
                        alpha_type = self.analyze_alpha_channel(str(img_file))
                        format_name, vmt_config = self.get_custom_format_and_vmt(alpha_type, self.custom_format_vars)
                        self.vmt_alpha_config = vmt_config
                        format_params = self.get_vtf_command_params(format_name)
                        print(f"自定义规则: {os.path.basename(img_file)} -> {alpha_type} -> {format_name}")
                    else:
                        # 手动模式，使用用户选择的格式
                        format_params = self.get_vtf_command_params(self.material_format_var.get())
                        self.vmt_alpha_config = ""
                        print(f"手动模式: {os.path.basename(img_file)} -> {self.material_format_var.get()}")
                    
                    # 1. 图像转VTF - 直接输出到materials路径
                    self.update_status(f"转换图像到VTF... ({i}/{total_files})")
                    cmd = [self.vtfcmd_path, '-file', str(img_file), '-output', str(full_materials_path)] + format_params
                    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    if result.returncode != 0:
                        raise Exception(f"图像转VTF失败 ({base_name}): {result.stderr}")
                    
                    # 2. 生成VMT文件
                    self.update_status(f"生成VMT文件... ({i}/{total_files})")
                    self.generate_vmt_files(full_materials_path, base_name, materials_path)
                
                self.update_status("材质配置生成完成")
                skipped_count = total_files - processed_count
                if skipped_count > 0:
                    messagebox.showinfo("成功", f"材质配置生成完成！\n已处理 {processed_count} 个文件\n跳过 {skipped_count} 个文件（包含屏蔽词）\n输出目录: {output_path}")
                else:
                    messagebox.showinfo("成功", f"材质配置生成完成！\n已处理 {processed_count} 个文件\n输出目录: {output_path}")
                
            except Exception as e:
                self.update_status("生成失败")
                messagebox.showerror("错误", f"生成失败: {str(e)}")
            finally:
                self.stop_progress()
        
        threading.Thread(target=worker, daemon=True).start()
    
    def generate_vmt_files(self, output_path, base_name, materials_path=None):
        """生成VMT文件"""
        # 获取材质路径
        if materials_path is None:
            materials_path = self.cdmaterials_var.get().strip()
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
        lightwarp_file = self.lightwarp_var.get().strip()
        if lightwarp_file and os.path.exists(lightwarp_file):
            # 复制lightwarp文件到shader目录
            import shutil
            lightwarp_filename = os.path.basename(lightwarp_file)
            lightwarp_dest = shader_dir / lightwarp_filename
            shutil.copy2(lightwarp_file, lightwarp_dest)
            lightwarp_path = f"{materials_path}/shader/{os.path.splitext(lightwarp_filename)[0]}"
        else:
            lightwarp_path = f"{materials_path}/shader/toon_light"
        
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
            self.generate_normal_vmt_file(output_path, base_name, materials_path)
    
    def generate_normal_vmt_file(self, output_path, base_name, materials_path):
        """生成普通材质VMT文件"""
        # 获取alpha配置
        alpha_config = getattr(self, 'vmt_alpha_config', None)
        insert_content = "\t" + alpha_config if alpha_config else ""
        
        vmt_content = f'''patch
{{
	include	"materials/{materials_path}/shader/vmt-base.vmt"
	insert
	{{
{insert_content}
	}}
	replace
	{{
	"$basetexture" "{materials_path}/{base_name}"
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
        path_str = str(output_path).replace('\\', '/')
        if 'materials' in path_str.lower():
            # 提取materials之后的路径
            match = re.search(r'materials[/\\](.+)', path_str, re.IGNORECASE)
            if match:
                return match.group(1).replace('\\', '/')
        return None
    
    def process_resize(self):
        """处理静态图像调整"""
        if not self.resize_files:
            messagebox.showerror("错误", "请选择至少一个图像文件")
            return
        
        # 检查所有文件是否存在
        invalid_files = [f for f in self.resize_files if not os.path.exists(f)]
        if invalid_files:
            messagebox.showerror("错误", f"以下文件不存在：\n{chr(10).join(invalid_files)}")
            return
        
        width = self.resize_width_var.get()
        height = self.resize_height_var.get()
        
        if not width or not height:
            messagebox.showerror("错误", "请输入有效的宽度和高度")
            return
        
        try:
            width = int(width)
            height = int(height)
        except ValueError:
            messagebox.showerror("错误", "宽度和高度必须是数字")
            return
        
        def worker():
            try:
                self.start_progress()
                total_files = len(self.resize_files)
                processed_files = 0
                output_dirs = []
                
                for img_file in self.resize_files:
                    processed_files += 1
                    self.update_status(f"正在处理静态图像调整... ({processed_files}/{total_files})")
                    
                    img_path = Path(img_file)
                    output_dir = img_path.parent / "resized"
                    output_dir.mkdir(exist_ok=True)
                    
                    if output_dir not in output_dirs:
                        output_dirs.append(output_dir)
                    
                    base_name = img_path.stem
                    
                    # 1. 使用ImageMagick调整图像尺寸
                    self.update_status(f"调整图像尺寸... ({processed_files}/{total_files})")
                    resized_img = output_dir / f"{base_name}_resized.tga"
                    
                    cmd1 = ['magick', str(img_path), '-resize', f'{width}x{height}!', str(resized_img)]
                    result = subprocess.run(cmd1, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    if result.returncode != 0:
                        raise Exception(f"调整图像尺寸失败 ({img_path.name}): {result.stderr}")
                    
                    # 2. 转换为VTF
                    self.update_status(f"转换为VTF格式... ({processed_files}/{total_files})")
                    
                    # 根据模式选择格式
                    mode = self.resize_format_mode_var.get()
                    if mode == "auto":
                        # 智能检测alpha通道
                        alpha_type = self.analyze_alpha_channel(str(img_file))
                        format_name, _ = self.get_optimal_format_and_vmt(alpha_type)
                        format_params = self.get_vtf_command_params(format_name)
                        print(f"智能检测: {os.path.basename(img_file)} -> {alpha_type} -> {format_name}")
                    elif mode == "custom":
                        # 自定义规则模式
                        alpha_type = self.analyze_alpha_channel(str(img_file))
                        format_name, _ = self.get_custom_format_and_vmt(alpha_type, self.resize_custom_format_vars)
                        format_params = self.get_vtf_command_params(format_name)
                        print(f"自定义规则: {os.path.basename(img_file)} -> {alpha_type} -> {format_name}")
                    else:
                        # 手动模式，使用用户选择的格式
                        format_params = self.get_vtf_command_params(self.resize_format_var.get())
                        print(f"手动模式: {os.path.basename(img_file)} -> {self.resize_format_var.get()}")
                    
                    cmd2 = [self.vtfcmd_path, '-file', str(resized_img), '-output', str(output_dir)] + format_params
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
                    
                    # 清理临时文件
                    if resized_img.exists():
                        resized_img.unlink()
                
                self.update_status("静态图像调整完成")
                output_info = "\n".join([f"- {dir}" for dir in output_dirs])
                messagebox.showinfo("成功", f"静态图像调整完成！\n处理了 {total_files} 个文件\n输出目录:\n{output_info}")
                
            except Exception as e:
                self.update_status("处理失败")
                messagebox.showerror("错误", f"处理失败: {str(e)}")
            finally:
                self.stop_progress()
        
        threading.Thread(target=worker, daemon=True).start()
    

    
    def update_status(self, message):
        """更新状态栏"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
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
    
    def check_dependencies(self):
        """检查依赖工具"""
        missing_tools = []
        
        # 检查vtfcmd
        self.vtfcmd_path = self.get_vtfcmd_path()
        if not self.vtfcmd_path:
            missing_tools.append("VTFCmd (请确保VTFCmd.exe可访问或添加到PATH)")
        
        # 检查ImageMagick
        try:
            subprocess.run(["magick", "-version"], capture_output=True, check=True, encoding='utf-8', errors='ignore')
        except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
            missing_tools.append("ImageMagick (magick)")
        
        if missing_tools:
            messagebox.showwarning(
                "依赖工具缺失", 
                f"以下工具未找到：\n" + "\n".join(missing_tools) + 
                "\n\n请确保工具已安装并可访问。\n对于VTFCmd，您可以：\n1. 将VTFCmd.exe所在目录添加到PATH环境变量\n2. 或者将VTFCmd.exe复制到当前目录"
            )
            return False
        return True

def main():
    """主函数"""
    root = tk.Tk()
    app = VTFMaterialTool(root)
    
    # 检查依赖工具
    if not app.check_dependencies():
        print("警告: 某些依赖工具未找到，部分功能可能无法正常使用")
    
    root.mainloop()

if __name__ == "__main__":
    main()