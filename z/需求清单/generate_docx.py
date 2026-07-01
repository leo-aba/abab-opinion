#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 AI Opinion Analytics 需求清单文档"""

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

# ============================================================
# Helper functions
# ============================================================

def set_cell_shading(cell, color):
    """Set cell background color"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    shading.set(qn('w:val'), 'clear')
    tcPr.append(shading)

def add_table_row(table, cells_data, header=False, color=None):
    """Add a row to table with style"""
    row = table.add_row()
    for i, text in enumerate(cells_data):
        cell = row.cells[i]
        cell.text = str(text)
        for p in cell.paragraphs:
            p.space_before = Pt(4)
            p.space_after = Pt(4)
            for run in p.runs:
                run.font.size = Pt(10)
                if header:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
        if header and color:
            set_cell_shading(cell, color)
    return row

def set_heading(doc, text, level=1):
    """Add a styled heading"""
    h = doc.add_heading(text, level=level)
    return h

def add_para(doc, text, bold=False, size=11, indent=False):
    """Add a paragraph with styling"""
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.left_indent = Cm(0.8)
    run = p.add_run(text)
    run.font.size = Pt(size)
    if bold:
        run.font.bold = True
    return p

def add_bullet(doc, text, level=0):
    """Add a bullet point"""
    p = doc.add_paragraph(text, style='List Bullet')
    p.paragraph_format.left_indent = Cm(1.2 + level * 0.8)
    for run in p.runs:
        run.font.size = Pt(10)
    return p

def add_numbered(doc, text, level=0):
    """Add a numbered item"""
    p = doc.add_paragraph(text, style='List Number')
    for run in p.runs:
        run.font.size = Pt(10)
    return p

def create_styled_table(doc, headers, rows, col_widths=None):
    """Create a styled table with header"""
    table = doc.add_table(rows=1, cols=len(headers), style='Table Grid')
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    header_cells = table.rows[0].cells
    for i, text in enumerate(headers):
        header_cells[i].text = text
        for p in header_cells[i].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255)
        set_cell_shading(header_cells[i], 'FF7A22')

    # Data rows
    for row_data in rows:
        add_table_row(table, row_data)

    # Set column widths if provided
    if col_widths:
        for row in table.rows:
            for i, width in enumerate(col_widths):
                row.cells[i].width = Cm(width)

    doc.add_paragraph()  # spacer
    return table

# ============================================================
# Main Document Generation
# ============================================================

doc = Document()

# Page setup
for section in doc.sections:
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

# ============================================================
# COVER PAGE
# ============================================================
doc.add_paragraph()
doc.add_paragraph()
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('AI Opinion Analytics')
run.font.size = Pt(36)
run.font.bold = True
run.font.color.rgb = RGBColor(255, 122, 34)

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run('AI 驱动的视频评论分析平台')
run.font.size = Pt(18)
run.font.color.rgb = RGBColor(0, 0, 0)

doc.add_paragraph()
info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = info.add_run('需求清单文档\n\n页面清单 · 交互逻辑 · 数据需求 · API 接口')
run.font.size = Pt(14)
run.font.color.rgb = RGBColor(102, 102, 102)

doc.add_paragraph()
date_p = doc.add_paragraph()
date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = date_p.add_run('2026年6月29日')
run.font.size = Pt(12)
run.font.color.rgb = RGBColor(153, 153, 153)

doc.add_page_break()

# ============================================================
# TABLE OF CONTENTS (manual)
# ============================================================
set_heading(doc, '目录', 1)
toc_items = [
    '一、项目概述',
    '二、页面清单',
    '    2.1 登录/注册页',
    '    2.2 Dashboard 仪表盘',
    '    2.3 创建分析向导',
    '    2.4 实时分析页（Pipeline）',
    '    2.5 实时追踪页',
    '    2.6 分析结果页',
    '    2.7 视频管理页',
    '    2.8 历史记录页',
    '    2.9 系统设置页',
    '    2.10 全局组件（侧边栏 / 顶栏）',
    '三、交互逻辑',
    '    3.1 登录 / 注册流程',
    '    3.2 侧边栏导航',
    '    3.3 创建分析向导流程',
    '    3.4 实时分析流程',
    '    3.5 实时追踪流程',
    '    3.6 结果浏览流程',
    '    3.7 视频管理流程',
    '    3.8 历史记录流程',
    '    3.9 设置管理流程',
    '    3.10 键盘快捷键',
    '    3.11 响应式适配',
    '四、数据需求',
    '    4.1 用户 (User)',
    '    4.2 视频 (Video)',
    '    4.3 评论 (Comment)',
    '    4.4 分析任务 (AnalysisTask)',
    '    4.5 话题 / Topic (Topic)',
    '    4.6 情感数据 (Sentiment)',
    '    4.7 追踪任务 (TrackingTask)',
    '    4.8 积分 / 配额 (Credit)',
    '    4.9 系统设置 (Settings)',
    '    4.10 分析日志 (AnalysisLog)',
    '五、API 接口清单',
    '    5.1 认证接口',
    '    5.2 仪表盘接口',
    '    5.3 视频接口',
    '    5.4 评论接口',
    '    5.5 分析任务接口',
    '    5.6 话题接口',
    '    5.7 追踪任务接口',
    '    5.8 结果接口',
    '    5.9 设置接口',
    '六、附录：Pipeline 阶段说明',
]
for item in toc_items:
    p = doc.add_paragraph(item)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    for run in p.runs:
        run.font.size = Pt(11)

doc.add_page_break()

# ============================================================
# 一、项目概述
# ============================================================
set_heading(doc, '一、项目概述', 1)
add_para(doc, 'AI Opinion Analytics 是一个 AI 驱动的视频评论分析平台，支持 B站（Bilibili）和抖音 等主流视频平台。'
         '系统通过大模型（LLM）与向量检索技术，对海量用户评论进行聚类分析、Topic 发现和属性级情感分析，'
         '帮助运营和产品团队快速洞察用户观点、识别舆论热点和潜在风险。')
add_para(doc, '核心技术能力：', bold=True)
add_bullet(doc, 'AI 驱动的评论聚类与主题发现')
add_bullet(doc, '细粒度属性级情感分析（正面 / 负面 / 中性）')
add_bullet(doc, 'Embedding 向量化 + 聚类分析 Pipeline')
add_bullet(doc, 'AI 自动生成分析总结报告')
add_bullet(doc, '实时追踪模式：持续监控新增评论并动态更新分析结果')
add_bullet(doc, '智能评论检索与趋势洞察')

doc.add_page_break()

# ============================================================
# 二、页面清单
# ============================================================
set_heading(doc, '二、页面清单', 1)

pages = [
    {
        'id': 'login',
        'name': '登录/注册页 (Login & Register)',
        'route': 'page-login',
        'desc': '用户认证入口，包含左侧品牌宣传区和右侧登录/注册双表单切换。登录与注册在同一卡片区域内切换显示，无需页面跳转。',
        'components': [
            '装饰性几何圆形元素（solid-circle × 4）',
            '左侧品牌标语："AI 驱动的视频评论分析平台"',
            '三个功能亮点（Feature List）：AI评论聚类、属性情感分析、智能检索',
            '—— 登录表单（id="login-card"，默认显示）——',
            '登录表单：用户名输入框、密码输入框、"记住我"复选框、"忘记密码"链接',
            '登录按钮（btn-primary）：登录',
            '注册入口按钮（btn-secondary）：创建新账户 → 切换到注册表单',
            '—— 注册表单（id="register-card"，默认隐藏）——',
            '注册表单：用户名输入框（至少3位）、邮箱输入框、密码输入框（至少6位）、确认密码输入框',
            '注册按钮（btn-primary）：注册',
            '返回登录按钮（btn-secondary）：已有账户？登录 → 切换回登录表单',
        ],
        'states': [
            '默认态 → 显示登录表单',
            '登录中（按钮显示"登录中..."并禁点击）',
            '登录成功 → 跳转 Dashboard',
            '点击"创建新账户" → 隐藏登录表单，显示注册表单',
            '注册表单验证失败 → alert 提示（字段为空/用户名过短/密码过短/两次密码不一致）',
            '注册中（按钮显示"注册中..."并禁点击）',
            '注册成功 → alert 提示 → 自动切回登录表单并预填用户名',
        ],
    },
    {
        'id': 'dashboard',
        'name': 'Dashboard 仪表盘',
        'route': 'content-dashboard',
        'desc': '平台主页面，展示核心数据指标和可视化图表。',
        'components': [
            '4 个统计卡片（评论总数、视频数量、热门 Topic、平均情绪）',
            '实时追踪任务卡片区（dashboard-tracking-section，有追踪任务时显示）',
            '评论增长趋势折线图（Chart.js, 近30天）',
            '情绪占比环形图（正面/负面/中性）',
            'TOP10 热门 Topic 横向柱状图',
        ],
        'states': ['无追踪任务时隐藏 tracking-section', '有追踪任务时显示实时追踪卡片'],
    },
    {
        'id': 'wizard',
        'name': '创建分析向导 (Create Analysis)',
        'route': 'content-wizard',
        'desc': '4 步向导引导用户创建新的评论分析任务。',
        'components': [
            '步骤指示器（4 步：选择平台 → 搜索视频 → 分析参数 → 开始分析）',
            'Step1: 平台选择卡片（Bilibili / 抖音），选中态带橙色边框和✓标记',
            'Step2: 搜索方式Tab切换（URL / BV号 / AV号 / 关键词）',
            '      视频搜索输入框 + 搜索按钮',
            '      搜索结果表格（封面、标题、UP主、发布时间、评论数、选择按钮）',
            'Step3: 评论数量选择器（100/500/1,000/5,000/全部）',
            '      时间范围选择器（最近7天/最近30天/全部）',
            '      语言选择器（中文/英文/全部）',
            '      分析模式卡片：实时追踪 vs 普通分析',
        ],
        'states': [
            '每个步骤有独立显示/隐藏',
            '平台选择：未选中 → 选中（橙色边框+✓）',
            '视频选择按钮：选择 → 已选择✓（高亮）',
            '参数选择器：未选中 → 选中（黑底白字）',
            'Step4: 配置摘要 + 追踪模式积分警告（仅追踪模式显示）',
        ],
    },
    {
        'id': 'pipeline',
        'name': '实时分析页 (Pipeline)',
        'route': 'content-pipeline',
        'desc': '展示分析任务的 Pipeline 执行进度，包含 6 个阶段的实时状态。',
        'components': [
            '进度条（百分比 + 填充动画）',
            '6 阶段 Pipeline 列表：',
            '  1) 评论采集 2) 数据清洗 3) Embedding 向量化',
            '  4) 聚类分析 5) Topic 生成 6) AI 总结生成',
            '每个阶段有状态图标（等待中/运行中/已完成）和连接线',
            '右侧实时日志面板（等宽字体终端风格）',
            '追踪模式扩展区（tracking-extension，仅追踪模式显示）：',
            '  - 新增评论数 / 剩余积分 / 当前 Topic 数',
            '  - 积分消耗进度条',
            '  - 查看实时结果 & 停止追踪按钮',
        ],
        'states': [
            '等待中（waiting）：灰色图标 + 虚线连接器',
            '运行中（running）：橙色脉冲图标 + 渐变连接器',
            '已完成（done）：青色图标 + 实线连接器',
            '普通模式完成后自动跳转 Results 页',
            '追踪模式完成后自动进入追踪监控模式',
        ],
    },
    {
        'id': 'tracking',
        'name': '实时追踪页 (Tracking)',
        'route': 'content-tracking',
        'desc': '管理所有正在运行的实时追踪任务。',
        'components': [
            '空状态提示（无追踪任务时）：图标 + 引导文案 + 创建分析按钮',
            '追踪任务卡片列表（有任务时）：',
            '  - 追踪状态标签（橙色·追踪中）',
            '  - 视频标题、平台、UP主、分析完成时间',
            '  - 4 个数据面板：新增评论 / 总评论数 / 剩余积分 / 运行时间',
            '  - 最新追踪日志（等宽字体）',
            '  - 查看结果 & 停止追踪按钮',
        ],
        'states': ['空状态', '有追踪任务状态', '追踪已停止状态'],
    },
    {
        'id': 'results',
        'name': '分析结果页 (Results)',
        'route': 'content-results',
        'desc': '展示分析结果，包含 6 个子 Tab 页。仅在视频分析完成后有数据。',
        'components': [
            '6 个 Tab 切换按钮：概览 / Topic聚类 / 属性情感 / 时间趋势 / AI总结 / 评论检索',
            '追踪状态栏（仅追踪模式显示）：新增评论、总评论、剩余积分、运行时间、刷新/停止按钮',
            'Tab1-概览：5 个结果统计数字 + 评论增长趋势图 + 情绪分布环形图',
            'Tab2-Topic聚类：左侧 Topic 列表 + 右侧详情面板（代表评论、关键词、AI总结）',
            'Tab3-属性情感：属性×情感旭日图 + 情感雷达图',
            'Tab4-时间趋势：多线趋势图（总评论/正面/负面），支持按天/按小时/按周切换',
            'Tab5-AI总结：AI分析报告卡片（总览描述 + 4个高亮要点）',
            'Tab6-评论检索：关键词搜索框 + 评论列表（高亮匹配词）',
        ],
        'states': [
            'Tab 切换状态',
            'Topic 列表中选中/未选中项',
            '追踪模式下的追踪状态栏',
            '评论搜索过滤前后',
            '时间趋势粒度切换（按天/按小时/按周）',
        ],
    },
    {
        'id': 'videos',
        'name': '视频管理页 (Video Management)',
        'route': 'content-videos',
        'desc': '视频卡片网格视图，展示所有已添加的分析视频。',
        'components': [
            '视频卡片网格（响应式自适应列数）',
            '每张卡片包含：封面区（渐变色占位）+ 平台标签 + 视频标题 + UP主 + 评论数 + 日期 + 状态标签',
            '状态标签：实时追踪中（橙色）/ 已分析（青色）/ 待分析（橙色）',
            '追踪中的卡片在封面右上角显示追踪状态行',
        ],
        'states': ['有视频列表', '空列表（暂无数据）'],
    },
    {
        'id': 'history',
        'name': '历史记录页 (History)',
        'route': 'content-history',
        'desc': '以表格形式展示所有历史分析记录，支持筛选和分页。',
        'components': [
            '筛选栏：平台下拉 / 时间范围下拉 / 标题搜索框 / 筛选按钮',
            '数据表格：视频标题、平台标签、分析模式标签、Topic数、评论数、分析时间、操作按钮',
            '表头支持排序（Topic数、评论数列）',
            '分页控件：上一页 / 页码 / 下一页',
        ],
        'states': [
            '筛选前/筛选后',
            '分页切换',
            '列表数据在不同页之间切换',
            '排序状态',
        ],
    },
    {
        'id': 'settings',
        'name': '系统设置页 (Settings)',
        'route': 'content-settings',
        'desc': '系统配置管理页面。',
        'components': [
            '分析偏好设置区域：',
            '  - 默认评论数量下拉选择器',
            '  - 自动生成AI总结开关',
            '  - 实时分析动画开关',
            '通知设置区域：',
            '  - 分析完成通知开关',
            '  - 异常预警开关',
            '账户信息区域：',
            '  - 用户名（显示+修改按钮）',
            '  - 邮箱（显示+修改按钮）',
            '  - API Key（脱敏显示+重新生成按钮）',
        ],
        'states': ['开关 on/off 切换', '各配置项修改保存'],
    },
]

# Output each page
for page in pages:
    set_heading(doc, f'2.{pages.index(page)+1} {page["name"]}', 2)
    add_para(doc, f'路由标识: {page["route"]}', size=10)
    add_para(doc, f'描述: {page["desc"]}', size=11)
    add_para(doc, 'UI 组件清单:', bold=True, size=10)
    for comp in page['components']:
        add_bullet(doc, comp)
    add_para(doc, '状态说明:', bold=True, size=10)
    for state in page['states']:
        add_bullet(doc, state)
    doc.add_paragraph()

# 2.10 Global Components
set_heading(doc, '2.10 全局组件（侧边栏 / 顶栏）', 2)

add_para(doc, '侧边栏 (Sidebar)', bold=True)
add_para(doc, '固定左侧，黑色背景 (#000000)，240px 宽。包含：')
add_bullet(doc, 'Logo + 应用名："Opinion AI"')
add_bullet(doc, '导航菜单分为两组：')
add_bullet(doc, '主菜单：Dashboard / 创建分析 / 实时分析 / 实时追踪(条件显示) / 分析结果', level=1)
add_bullet(doc, '管理：视频管理 / 历史记录 / 系统设置', level=1)
add_bullet(doc, '每个导航项：图标 + 文字，hover 高亮，active 状态带橙色左边框')
add_bullet(doc, '实时追踪导航项：带橙色脉冲圆点指示器，仅在追踪活跃时显示')
add_bullet(doc, '底部用户区域：头像圆形（首字母）、用户名、角色、退出登录按钮')
add_bullet(doc, '移动端 (≤768px) 侧边栏默认隐藏，通过汉堡菜单按钮滑出，带半透明遮罩层')

add_para(doc, '顶部栏 (Top Header)', bold=True)
add_para(doc, 'Sticky 定位，显示当前页面标题（h2）和 greeting 文案，右侧 4 个统计数字。')
add_bullet(doc, '移动端显示汉堡菜单按钮，隐藏右侧统计数字')
add_bullet(doc, '标题和 greeting 随 navigated 页面动态切换')

doc.add_page_break()

# ============================================================
# 三、交互逻辑
# ============================================================
set_heading(doc, '三、交互逻辑', 1)

# 3.1
set_heading(doc, '3.1 登录 / 注册流程', 2)

add_para(doc, '登录流程：', bold=True)
add_numbered(doc, '用户进入页面 → 显示登录页（#page-login），默认展示登录表单')
add_numbered(doc, '输入用户名/密码（预填 admin / password）')
add_numbered(doc, '可选勾选"记住我"')
add_numbered(doc, '点击"登录"按钮 → 按钮变为"登录中..."并禁用（pointer-events: none）')
add_numbered(doc, '模拟 800ms 延迟 → 登录页 fadeOut 动画 → 隐藏登录页')
add_numbered(doc, '显示 App 页（#page-app），导航到 Dashboard')
add_numbered(doc, '可选：点击"忘记密码"链接跳转密码重置（当前为入口链接，功能待实现）')

add_para(doc, '注册流程：', bold=True)
add_numbered(doc, '在登录表单底部点击"创建新账户"按钮 → showRegister() 触发')
add_numbered(doc, '登录表单卡片隐藏（login-card display:none），注册表单卡片显示（register-card display:block）')
add_numbered(doc, '注册表单包含 4 个字段：用户名（≥3位）、邮箱、密码（≥6位）、确认密码')
add_numbered(doc, '点击"注册"按钮 → doRegister() 执行前端验证：')
add_bullet(doc, '所有字段必填 → 为空时 alert "请填写所有字段"')
add_bullet(doc, '用户名长度 < 3 → alert "用户名至少需要3位"')
add_bullet(doc, '密码长度 < 6 → alert "密码至少需要6位"')
add_bullet(doc, '两次密码不一致 → alert "两次输入的密码不一致"')
add_numbered(doc, '验证通过 → 按钮变为"注册中..."并禁用')
add_numbered(doc, '模拟 800ms 延迟 → alert "注册成功！即将切换到登录页"')
add_numbered(doc, '→ 自动切回登录表单（showLogin()），预填注册用户名到登录用户名框')
add_numbered(doc, '→ 清空注册表单所有字段')
add_numbered(doc, '用户可在注册表单底部点击"已有账户？登录"返回登录表单（showLogin()）')

add_para(doc, '退出登录流程：', bold=True)
add_numbered(doc, '点击侧边栏底部"退出登录"按钮 → 停止所有追踪任务 → App 页 fadeOut')
add_numbered(doc, '→ 显示登录页（fadeIn 动画）→ currentPage 设为 login，默认展示登录表单')

# 3.2
set_heading(doc, '3.2 侧边栏导航', 2)
add_numbered(doc, '点击导航项 → navigate(page) 函数触发')
add_numbered(doc, '隐藏所有 .page-content → 显示对应 content-{page}')
add_numbered(doc, '更新顶部栏标题和 greeting 文案')
add_numbered(doc, '更新导航项 active 状态（橙色左边框 + 加粗）')
add_numbered(doc, '特定页面初始化图表：Dashboard → initDashboardCharts()，Results → initResultsCharts()')
add_numbered(doc, '移动端（≤768px）：点击导航后自动关闭侧边栏')

# 3.3
set_heading(doc, '3.3 创建分析向导流程', 2)
add_para(doc, 'Step 1 — 选择平台：', bold=True)
add_numbered(doc, '点击平台卡片 → selectPlatform() → 切换选中态（橙色边框 + ✓标记显示）')
add_numbered(doc, '点击"下一步" → wizardNext(2) → 更新步骤指示器 → 显示 Step2')

add_para(doc, 'Step 2 — 搜索视频：', bold=True)
add_numbered(doc, '切换搜索 Tab（URL / BV号 / AV号 / 关键词）→ switchSearchTab()')
add_numbered(doc, '输入搜索内容 + 点击"搜索" → searchVideos()（当前展示 Mock 数据）')
add_numbered(doc, '点击视频行的"选择"按钮 → selectVideo() → 按钮变为"已选择 ✓"（高亮态）')
add_numbered(doc, '记录所选视频标题到 selectedVideoTitle 变量')
add_numbered(doc, '点击"下一步/上一步"导航')

add_para(doc, 'Step 3 — 分析参数：', bold=True)
add_numbered(doc, '评论数量：点击切换 selected 态，黑底白字')
add_numbered(doc, '时间范围：最近7天 / 最近30天 / 全部')
add_numbered(doc, '语言：中文 / 英文 / 全部')
add_numbered(doc, '分析模式：点击卡片切换，实时追踪（推荐标签）/ 普通分析')
add_numbered(doc, '模式卡片 hover 上浮效果，选中态橙色边框')

add_para(doc, 'Step 4 — 确认 & 开始：', bold=True)
add_numbered(doc, '页面加载时调用 updateWizardSummary() 汇总所有参数')
add_numbered(doc, '若为追踪模式，显示积分警告（⚠️ 预计运行时间、积分消耗率）')
add_numbered(doc, '点击"Start Analysis"按钮 → startAnalysis()')
add_numbered(doc, '→ 导航到 Pipeline 页 → pipelineReset() → pipelineRun()')

# 3.4
set_heading(doc, '3.4 实时分析流程 (Pipeline)', 2)
add_para(doc, '6 阶段 pipeline 按顺序执行，每阶段有独立延迟（1.0s ~ 1.8s）：', bold=True)
add_numbered(doc, '评论采集 (15%) → 数据清洗 (30%) → Embedding 向量化 (50%)')
add_numbered(doc, '→ 聚类分析 (70%) → Topic 生成 (85%) → AI 总结生成 (100%)')
add_para(doc, '每阶段执行时：', bold=True)
add_bullet(doc, '前一阶段标记为 done（青色✓图标）')
add_bullet(doc, '当前阶段标记为 running（橙色脉冲动画图标）')
add_bullet(doc, '进度条宽度同步更新')
add_bullet(doc, '实时日志面板滚动追加日志行（时间戳 + 消息 + 颜色分类）')
add_para(doc, '全部完成后：', bold=True)
add_bullet(doc, '普通分析模式：2秒后自动跳转 Results 页')
add_bullet(doc, '实时追踪模式：启动追踪扩展区，开始监控新增评论')
add_bullet(doc, '追踪模式下显示侧边栏追踪入口（橙色脉冲圆点）')

# 3.5
set_heading(doc, '3.5 实时追踪流程', 2)
add_numbered(doc, 'Pipeline 完成后 → initTrackingMode() 初始化')
add_numbered(doc, '启动定时器 trackingInterval（每3秒执行一次）')
add_numbered(doc, '每周期模拟：新增 2-9 条评论、消耗积分（100点/小时速率）、5%概率新增Topic')
add_numbered(doc, '更新 Pipeline 扩展区 UI：新增评论数、剩余积分、Topic 数、积分进度条')
add_numbered(doc, '同步更新 Results 页追踪状态栏')
add_numbered(doc, '同步更新 Dashboard 追踪任务卡片')
add_numbered(doc, '积分耗尽 → 自动停止追踪 → 日志记录 "积分已耗尽，追踪自动停止"')
add_numbered(doc, '手动停止：点击"停止追踪"按钮 → stopTracking() → 清除定时器 → UI 更新为停止态')
add_numbered(doc, '退出登录时自动停止所有追踪任务')

# 3.6
set_heading(doc, '3.6 结果浏览流程', 2)
add_para(doc, 'Tab 切换：', bold=True)
add_numbered(doc, '点击 Tab 按钮 → switchResultTab() → 切换 .active 态 → 显示对应 tab-panel')
add_numbered(doc, '切换到情感 Tab 时重新初始化旭日图和雷达图')
add_numbered(doc, '切换到趋势 Tab 时重新初始化趋势详情图')

add_para(doc, 'Topic 详情交互：', bold=True)
add_numbered(doc, '点击左侧 Topic 列表项 → showTopicDetail() → 更新右侧面板')
add_numbered(doc, '面板内容：Topic名称、评论数、占比、代表评论（3条）、关键词标签、AI总结')

add_para(doc, '评论检索：', bold=True)
add_numbered(doc, '输入关键词 → searchComments() 实时过滤 → 匹配词高亮（橙色背景）')
add_numbered(doc, '显示匹配结果计数 "显示 N 条评论"')

add_para(doc, '追踪模式下的结果页：', bold=True)
add_numbered(doc, '顶部显示追踪状态栏（绿色背景）')
add_numbered(doc, '点击"刷新数据"按钮模拟拉取最新数据')
add_numbered(doc, '点击"停止追踪"停止追踪任务')

# 3.7
set_heading(doc, '3.7 视频管理流程', 2)
add_numbered(doc, '网格布局自动填充（repeat(auto-fill, minmax(280px, 1fr))）')
add_numbered(doc, 'hover 卡片上浮 2px + 橙色边框')
add_numbered(doc, '根据分析状态显示不同标签：实时追踪中（橙色·脉冲）/ 已分析（青色）/ 待分析（橙色）')
add_numbered(doc, '点击卡片可导航到对应分析结果（当前为展示态）')

# 3.8
set_heading(doc, '3.8 历史记录流程', 2)
add_numbered(doc, '筛选栏条件变更 → 点击"筛选"按钮 → 过滤表格数据')
add_numbered(doc, '点击表头排序 → 切换排序方向 → 更新表格')
add_numbered(doc, '分页切换 → 更新表格数据 + active 页码高亮')
add_numbered(doc, '点击"查看结果" → 导航到 Results 页')
add_numbered(doc, '第一页时禁用"上一页"按钮，最后一页时禁用"下一页"按钮')

# 3.9
set_heading(doc, '3.9 设置管理流程', 2)
add_numbered(doc, '下拉选择器：修改默认评论数量')
add_numbered(doc, 'Toggle 开关：点击切换 on/off 类 → 橙色背景滑动动画')
add_numbered(doc, '修改按钮：触发用户名/邮箱编辑弹窗（当前为入口）')
add_numbered(doc, '重新生成按钮：触发 API Key 重新生成（当前为入口）')

# 3.10
set_heading(doc, '3.10 键盘快捷键', 2)
create_styled_table(doc,
    ['快捷键', '页面', '功能'],
    [
        ['Enter', '登录页（登录表单可见）', '触发登录'],
        ['Enter', '登录页（注册表单可见）', '触发注册'],
    ],
    col_widths=[3, 5, 6]
)

# 3.11
set_heading(doc, '3.11 响应式适配', 2)
create_styled_table(doc,
    ['断点', '适配规则'],
    [
        ['≤ 1024px', '统计卡片 → 2列；图表行 → 单列；结果统计 → 3列；Topic布局 → 单列；Pipeline布局 → 单列；登录页 → 纵向布局'],
        ['≤ 768px', '侧边栏 → 隐藏（汉堡菜单呼出）；主内容 → 无边距；统计卡片 → 2列；结果统计 → 2列；平台卡片 → 单列'],
        ['≤ 480px', '统计卡片 → 1列；结果统计 → 1列；登录标题 → 28px；登录卡片 → padding 24px'],
    ],
    col_widths=[3, 11]
)

doc.add_page_break()

# ============================================================
# 四、数据需求
# ============================================================
set_heading(doc, '四、数据需求', 1)
add_para(doc, '以下定义系统各数据实体及字段。字段类型简写：S=字符串, N=数字, B=布尔, D=日期时间, J=JSON/对象, E=枚举。')

# 4.1
set_heading(doc, '4.1 用户 (User)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '用户唯一标识'],
        ['username', 'S', '是', '用户名，登录凭证'],
        ['password_hash', 'S', '是', '密码哈希值'],
        ['email', 'S', '否', '邮箱地址'],
        ['avatar_url', 'S', '否', '头像 URL'],
        ['role', 'E', '是', '角色：admin / analyst / viewer'],
        ['api_key', 'S', '否', 'API 访问密钥'],
        ['credits', 'N', '是', '剩余积分余额'],
        ['created_at', 'D', '是', '账户创建时间'],
        ['updated_at', 'D', '是', '最后更新时间'],
        ['last_login_at', 'D', '否', '最后登录时间'],
        ['remember_token', 'S', '否', '"记住我" 持久化 token'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.2
set_heading(doc, '4.2 视频 (Video)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '视频唯一标识'],
        ['platform', 'E', '是', '平台：bilibili / douyin'],
        ['platform_video_id', 'S', '是', '平台侧视频 ID（BV号/AV号/抖音video_id）'],
        ['title', 'S', '是', '视频标题'],
        ['description', 'S', '否', '视频简介'],
        ['cover_url', 'S', '否', '封面图 URL'],
        ['uploader_name', 'S', '否', 'UP主/作者名称'],
        ['uploader_id', 'S', '否', 'UP主/作者平台ID'],
        ['url', 'S', '是', '视频播放页 URL'],
        ['publish_time', 'D', '否', '视频发布时间'],
        ['duration_seconds', 'N', '否', '视频时长（秒）'],
        ['comment_count', 'N', '否', '评论总数（快照）'],
        ['view_count', 'N', '否', '播放量（快照）'],
        ['like_count', 'N', '否', '点赞数（快照）'],
        ['analysis_status', 'E', '是', '分析状态：pending / analyzing / analyzed / tracking'],
        ['last_analysis_at', 'D', '否', '最近分析时间'],
        ['created_at', 'D', '是', '添加时间'],
        ['updated_at', 'D', '是', '最后更新时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.3
set_heading(doc, '4.3 评论 (Comment)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '评论唯一标识'],
        ['video_id', 'S (UUID)', '是', '所属视频 ID（FK → Video）'],
        ['platform_comment_id', 'S', '是', '平台侧评论 ID'],
        ['content', 'S', '是', '评论文本内容'],
        ['author_name', 'S', '否', '评论者用户名'],
        ['author_avatar', 'S', '否', '评论者头像 URL'],
        ['like_count', 'N', '否', '评论点赞数'],
        ['reply_count', 'N', '否', '评论回复数'],
        ['publish_time', 'D', '否', '评论发布时间'],
        ['language', 'S', '否', '评论语言（zh/en/other）'],
        ['embedding', 'J', '否', '文本 Embedding 向量（float[]）'],
        ['sentiment', 'E', '否', '情感标签：positive / negative / neutral'],
        ['sentiment_score', 'N', '否', '情感置信度分数 (0-1)'],
        ['topic_id', 'S (UUID)', '否', '所属 Topic ID（FK → Topic）'],
        ['is_cleaned', 'B', '是', '是否经过数据清洗'],
        ['created_at', 'D', '是', '采集时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.4
set_heading(doc, '4.4 分析任务 (AnalysisTask)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '任务唯一标识'],
        ['user_id', 'S (UUID)', '是', '创建者 ID（FK → User）'],
        ['video_id', 'S (UUID)', '是', '目标视频 ID（FK → Video）'],
        ['platform', 'E', '是', '平台：bilibili / douyin'],
        ['mode', 'E', '是', '分析模式：normal / tracking'],
        ['comment_limit', 'N', '是', '评论抓取数量上限（0=全部）'],
        ['time_range', 'E', '是', '时间范围：7d / 30d / all'],
        ['language_filter', 'E', '是', '语言过滤：zh / en / all'],
        ['status', 'E', '是', '任务状态: queued / collecting / cleaning / embedding / clustering / topic_gen / summarizing / completed / failed'],
        ['progress_pct', 'N', '否', '完成百分比 (0-100)'],
        ['total_comments_processed', 'N', '否', '已处理评论数'],
        ['topic_count', 'N', '否', '发现的 Topic 数量'],
        ['error_message', 'S', '否', '失败时的错误信息'],
        ['started_at', 'D', '否', '开始时间'],
        ['completed_at', 'D', '否', '完成时间'],
        ['duration_ms', 'N', '否', '总耗时（毫秒）'],
        ['created_at', 'D', '是', '创建时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.5
set_heading(doc, '4.5 话题 / Topic (Topic)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', 'Topic 唯一标识'],
        ['task_id', 'S (UUID)', '是', '所属分析任务 ID（FK → AnalysisTask）'],
        ['video_id', 'S (UUID)', '是', '所属视频 ID（FK → Video）'],
        ['name', 'S', '是', 'Topic 名称（如"价格"、"AI功能"）'],
        ['comment_count', 'N', '是', '该 Topic 下的评论数量'],
        ['percentage', 'N', '是', '占比百分比'],
        ['keywords', 'J', '否', '关键词列表（string[]）'],
        ['representative_comments', 'J', '否', '代表评论 ID 列表（string[]）'],
        ['ai_summary', 'S', '否', 'AI 生成的 Topic 总结'],
        ['sentiment_distribution', 'J', '否', '情感分布 {positive:N, negative:N, neutral:N}'],
        ['created_at', 'D', '是', '创建时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.6
set_heading(doc, '4.6 情感数据 (Sentiment)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '记录唯一标识'],
        ['comment_id', 'S (UUID)', '是', '关联评论 ID（FK → Comment）'],
        ['task_id', 'S (UUID)', '是', '所属分析任务 ID（FK → AnalysisTask）'],
        ['aspect', 'S', '是', '属性维度（如"价格"、"性能"、"续航"）'],
        ['sentiment', 'E', '是', '情感：positive / negative / neutral'],
        ['score', 'N', '是', '情感强度分数 (0-5)'],
        ['confidence', 'N', '否', '置信度 (0-1)'],
        ['created_at', 'D', '是', '分析时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.7
set_heading(doc, '4.7 追踪任务 (TrackingTask)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '追踪任务唯一标识'],
        ['analysis_task_id', 'S (UUID)', '是', '关联的分析任务 ID（FK → AnalysisTask）'],
        ['video_id', 'S (UUID)', '是', '监控的视频 ID（FK → Video）'],
        ['status', 'E', '是', '状态：active / paused / stopped / exhausted'],
        ['poll_interval_seconds', 'N', '是', '扫描间隔（秒），默认 60'],
        ['new_comments_since_start', 'N', '是', '启动以来新增评论数'],
        ['credits_consumed', 'N', '是', '已消耗积分'],
        ['credits_rate_per_hour', 'N', '是', '积分消耗速率（点/小时），默认 100'],
        ['started_at', 'D', '是', '追踪启动时间'],
        ['stopped_at', 'D', '否', '追踪停止时间'],
        ['last_poll_at', 'D', '否', '最近一次扫描时间'],
        ['last_comment_id', 'S', '否', '最近一次扫描到的最后一条评论ID（用于增量拉取）'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.8
set_heading(doc, '4.8 积分 / 配额 (Credit)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '记录唯一标识'],
        ['user_id', 'S (UUID)', '是', '所属用户 ID（FK → User）'],
        ['balance', 'N', '是', '当前余额'],
        ['transaction_type', 'E', '是', '交易类型：purchase / consume / refund / gift'],
        ['amount', 'N', '是', '变动金额（+充值/-消费）'],
        ['task_id', 'S (UUID)', '否', '关联任务 ID（消费时关联）'],
        ['description', 'S', '否', '交易描述'],
        ['created_at', 'D', '是', '交易时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.9
set_heading(doc, '4.9 系统设置 (Settings)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '设置唯一标识'],
        ['user_id', 'S (UUID)', '是', '所属用户 ID（FK → User）'],
        ['default_comment_count', 'N', '否', '默认评论抓取量：100/500/1000/5000'],
        ['auto_generate_summary', 'B', '否', '是否自动生成 AI 总结'],
        ['realtime_animation', 'B', '否', '是否展示实时分析动画'],
        ['notify_on_complete', 'B', '否', '分析完成是否通知'],
        ['notify_on_anomaly', 'B', '否', '负面情绪异常是否预警'],
        ['created_at', 'D', '是', '创建时间'],
        ['updated_at', 'D', '是', '最后更新时间'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

# 4.10
set_heading(doc, '4.10 分析日志 (AnalysisLog)', 2)
create_styled_table(doc,
    ['字段名', '类型', '必填', '说明'],
    [
        ['id', 'S (UUID)', '是', '日志唯一标识'],
        ['task_id', 'S (UUID)', '是', '关联分析任务 ID（FK → AnalysisTask）'],
        ['log_level', 'E', '是', '日志级别：info / success / warn / error'],
        ['stage', 'E', '否', 'Pipeline 阶段：collecting / cleaning / embedding / clustering / topic_gen / summarizing'],
        ['message', 'S', '是', '日志消息内容'],
        ['metadata', 'J', '否', '附加元数据'],
        ['created_at', 'D', '是', '日志时间戳'],
    ],
    col_widths=[3.5, 2.5, 1.5, 7]
)

doc.add_page_break()

# ============================================================
# 五、API 接口清单
# ============================================================
set_heading(doc, '五、API 接口清单', 1)
add_para(doc, '以下 API 接口基于前端交互需求推导，包含请求方法、路径、参数和响应说明。')
add_para(doc, 'Base URL: /api/v1', size=10)

# 5.1
set_heading(doc, '5.1 认证接口', 2)

create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['1. 登录', 'POST', '/auth/login', '用户名+密码登录，返回 access_token 和用户信息'],
        ['2. 注册', 'POST', '/auth/register', '创建新账户（用户名+密码+邮箱）'],
        ['3. 登出', 'POST', '/auth/logout', '注销当前会话，失效 token'],
        ['4. 忘记密码', 'POST', '/auth/forgot-password', '发送密码重置邮件'],
        ['5. 刷新 Token', 'POST', '/auth/refresh', '刷新 access_token'],
        ['6. 获取当前用户', 'GET', '/auth/me', '获取当前登录用户的完整信息'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, '接口详情：', bold=True)

add_para(doc, 'POST /auth/login', bold=True, indent=True)
add_para(doc, 'Request: { "username": "admin", "password": "password", "remember": true }', indent=True, size=10)
add_para(doc, 'Response: { "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400, "user": { ... } }', indent=True, size=10)

add_para(doc, 'POST /auth/register', bold=True, indent=True)
add_para(doc, 'Request: { "username": "newuser", "password": "***", "confirm_password": "***", "email": "user@example.com" }', indent=True, size=10)
add_para(doc, 'Response (201): { "id": "uuid", "username": "newuser", "email": "user@example.com", "created_at": "..." }', indent=True, size=10)
add_para(doc, 'Error (409): { "error": "username_exists" | "email_exists" } — 用户名或邮箱已被注册', indent=True, size=10)
add_para(doc, 'Error (422): { "error": "validation_failed", "details": { "username": "至少3位", "password": "至少6位" } }', indent=True, size=10)

# 5.2
set_heading(doc, '5.2 仪表盘接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['7. 获取概览统计', 'GET', '/dashboard/stats', '评论总数、视频数、热门Topic、平均情绪等'],
        ['8. 评论增长趋势', 'GET', '/dashboard/trends', '近30天评论增长数据（用于折线图）'],
        ['9. 情绪占比', 'GET', '/dashboard/sentiment-ratio', '正面/负面/中性评论占比'],
        ['10. TOP10 Topic', 'GET', '/dashboard/top-topics', '按评论数量的 TOP10 话题排名'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'GET /dashboard/stats 响应示例：', bold=True, indent=True)
add_para(doc, '{ "total_comments": 123221, "total_videos": 421, "hot_topic": "AI", "hot_topic_comments": 2341, "avg_sentiment": "positive", "comments_today": 2567, "new_videos_today": 18, "completion_rate": 96 }', indent=True, size=9)

# 5.3
set_heading(doc, '5.3 视频接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['11. 搜索视频', 'GET', '/videos/search', '按 URL/BV号/AV号/关键词搜索平台视频'],
        ['12. 视频列表', 'GET', '/videos', '已添加的分析视频列表（支持分页）'],
        ['13. 视频详情', 'GET', '/videos/{id}', '获取视频详情及最新分析状态'],
        ['14. 添加视频', 'POST', '/videos', '将视频加入分析库'],
        ['15. 删除视频', 'DELETE', '/videos/{id}', '删除视频及关联数据'],
        ['16. 获取视频封面', 'GET', '/videos/{id}/cover', '返回视频封面图片'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'GET /videos/search?platform=bilibili&type=url&q=https://... 响应示例：', bold=True, indent=True)
add_para(doc, '{ "items": [{ "id": "uuid", "platform_video_id": "BV1xx", "title": "...", "uploader_name": "科技美学", "publish_time": "2026-06-15", "comment_count": 12845, "cover_url": "..." }] }', indent=True, size=9)

add_para(doc, 'GET /videos?page=1&page_size=12&status=analyzed 响应示例：', bold=True, indent=True)
add_para(doc, '{ "items": [...], "total": 421, "page": 1, "page_size": 12, "total_pages": 36 }', indent=True, size=9)

# 5.4
set_heading(doc, '5.4 评论接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['17. 评论列表', 'GET', '/comments', '分页获取评论列表（按视频过滤）'],
        ['18. 评论搜索', 'GET', '/comments/search', '全文搜索评论（支持高亮匹配）'],
        ['19. 评论详情', 'GET', '/comments/{id}', '获取单条评论详情'],
        ['20. 评论统计', 'GET', '/comments/stats', '按视频/时间范围统计评论量'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'GET /comments/search?video_id=xxx&q=价格&page=1&page_size=20 响应示例：', bold=True, indent=True)
add_para(doc, '{ "items": [{ "id": "uuid", "content": "这个价格...", "author_name": "...", "like_count": 128, "publish_time": "...", "topic_name": "价格", "sentiment": "negative", "highlight_ranges": [[2,4],[40,42]] }], "total": 2334 }', indent=True, size=9)

# 5.5
set_heading(doc, '5.5 分析任务接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['21. 创建分析任务', 'POST', '/analysis', '创建新的分析任务（含平台/视频/参数）'],
        ['22. 获取任务状态', 'GET', '/analysis/{id}/status', '获取 Pipeline 各阶段进度'],
        ['23. 获取任务日志', 'GET', '/analysis/{id}/logs', '获取分析日志（实时追加）'],
        ['24. 取消任务', 'POST', '/analysis/{id}/cancel', '取消运行中的分析任务'],
        ['25. 任务列表', 'GET', '/analysis', '历史分析任务列表（含筛选和排序）'],
        ['26. 任务详情', 'GET', '/analysis/{id}', '获取分析任务完整信息'],
        ['27. 删除任务', 'DELETE', '/analysis/{id}', '删除分析任务及关联数据'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'POST /analysis 请求示例：', bold=True, indent=True)
add_para(doc, '''{
  "video_id": "uuid",
  "platform": "bilibili",
  "mode": "tracking",
  "comment_limit": 500,
  "time_range": "7d",
  "language_filter": "zh"
}''', indent=True, size=9)
add_para(doc, 'Response: { "task_id": "uuid", "status": "queued", "estimated_duration_s": 45 }', indent=True, size=9)

add_para(doc, 'GET /analysis/{id}/status 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "status": "clustering",
  "progress_pct": 70,
  "stages": [
    { "name": "collecting", "status": "done", "duration_ms": 1200 },
    { "name": "cleaning", "status": "done", "duration_ms": 800 },
    { "name": "embedding", "status": "done", "duration_ms": 1500 },
    { "name": "clustering", "status": "running", "duration_ms": null },
    { "name": "topic_gen", "status": "waiting", "duration_ms": null },
    { "name": "summarizing", "status": "waiting", "duration_ms": null }
  ],
  "total_comments_processed": 350,
  "eta_seconds": 12
}''', indent=True, size=9)

# 5.6
set_heading(doc, '5.6 话题接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['28. Topic 列表', 'GET', '/topics', '获取分析任务的所有 Topic 列表'],
        ['29. Topic 详情', 'GET', '/topics/{id}', 'Topic 详情（含代表评论、关键词、AI总结）'],
        ['30. Topic 评论列表', 'GET', '/topics/{id}/comments', '获取该 Topic 下的评论列表'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'GET /topics?task_id=xxx 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "items": [
    { "id": "uuid", "name": "价格", "comment_count": 2334, "percentage": 12.3, "sentiment_distribution": { "positive": 680, "negative": 890, "neutral": 764 } },
    { "id": "uuid", "name": "AI功能", "comment_count": 1892, "percentage": 9.8, ... }
  ]
}''', indent=True, size=9)

add_para(doc, 'GET /topics/{id} 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "id": "uuid",
  "name": "价格",
  "comment_count": 2334,
  "percentage": 12.3,
  "keywords": ["贵", "性价比", "降价", "值得买", "首发", "国行"],
  "representative_comments": [
    { "id": "uuid", "content": "这个价格真的有点贵了...", "author_name": "...", "like_count": 128, "sentiment": "negative" }
  ],
  "ai_summary": "用户普遍认为产品定价偏高，但对功能价值持认可态度..."
}''', indent=True, size=9)

# 5.7
set_heading(doc, '5.7 追踪任务接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['31. 启动追踪', 'POST', '/tracking/start', '对已完成的分析启动持续追踪'],
        ['32. 停止追踪', 'POST', '/tracking/{id}/stop', '停止指定追踪任务'],
        ['33. 追踪状态', 'GET', '/tracking/{id}/status', '获取追踪运行状态'],
        ['34. 追踪列表', 'GET', '/tracking', '所有活跃追踪任务列表'],
        ['35. 刷新追踪数据', 'POST', '/tracking/{id}/refresh', '手动触发一次增量数据拉取'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'POST /tracking/start 请求示例：', bold=True, indent=True)
add_para(doc, '{ "analysis_task_id": "uuid", "poll_interval_seconds": 60 }', indent=True, size=9)

add_para(doc, 'GET /tracking/{id}/status 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "id": "uuid",
  "status": "active",
  "new_comments_since_start": 326,
  "total_comments": 52667,
  "credits_remaining": 4520,
  "credits_rate_per_hour": 100,
  "estimated_runtime_hours": 45.2,
  "duration_seconds": 17280,
  "total_topics": 18,
  "last_poll_at": "2026-06-29T16:30:00Z"
}''', indent=True, size=9)

# 5.8
set_heading(doc, '5.8 结果接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['36. 结果概览', 'GET', '/results/{task_id}/overview', '总览数据：评论总数、Topic数、情感分布'],
        ['37. 情感分析', 'GET', '/results/{task_id}/sentiment', '属性级情感分析数据（旭日图+雷达图）'],
        ['38. 趋势数据', 'GET', '/results/{task_id}/trends', '时间趋势数据（按天/小时/周）'],
        ['39. AI 总结', 'GET', '/results/{task_id}/summary', 'AI 生成的完整分析报告'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'GET /results/{task_id}/sentiment 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "aspects": [
    { "aspect": "价格", "positive": 680, "negative": 890, "neutral": 764, "score_positive": 4.2, "score_negative": 3.5 },
    { "aspect": "AI功能", "positive": 1200, "negative": 320, "neutral": 372, "score_positive": 4.8, "score_negative": 1.5 }
  ]
}''', indent=True, size=9)

add_para(doc, 'GET /results/{task_id}/trends?granularity=day 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "granularity": "day",
  "series": [
    { "label": "总评论", "data": [["2026-06-01", 823], ["2026-06-02", 845], ...] },
    { "label": "正面", "data": [["2026-06-01", 580], ...] },
    { "label": "负面", "data": [["2026-06-01", 148], ...] }
  ]
}''', indent=True, size=9)

# 5.9
set_heading(doc, '5.9 设置接口', 2)
create_styled_table(doc,
    ['接口', '方法', '路径', '说明'],
    [
        ['40. 获取设置', 'GET', '/settings', '获取当前用户所有系统设置'],
        ['41. 更新设置', 'PUT', '/settings', '批量更新设置项'],
        ['42. 更新用户信息', 'PUT', '/users/{id}', '修改用户名/邮箱'],
        ['43. 重新生成API Key', 'POST', '/users/{id}/regenerate-api-key', '重新生成 API Key'],
    ],
    col_widths=[3, 1.5, 3, 7]
)

add_para(doc, 'GET /settings 响应示例：', bold=True, indent=True)
add_para(doc, '''{
  "default_comment_count": 500,
  "auto_generate_summary": true,
  "realtime_animation": true,
  "notify_on_complete": true,
  "notify_on_anomaly": true
}''', indent=True, size=9)

add_para(doc, 'PUT /settings 请求示例：', bold=True, indent=True)
add_para(doc, '{ "default_comment_count": 1000, "notify_on_complete": false }', indent=True, size=9)

doc.add_page_break()

# ============================================================
# 六、附录
# ============================================================
set_heading(doc, '六、附录：Pipeline 阶段说明', 1)

create_styled_table(doc,
    ['阶段', '名称', '说明', '输入', '输出', '预估耗时'],
    [
        ['1', '评论采集', '通过平台 API 或爬虫抓取视频评论数据', '视频 ID、评论数量限制、时间范围', '原始评论数据列表', '1-5 秒（取决于评论量）'],
        ['2', '数据清洗', '去重、去噪、表情符号处理、无效内容过滤', '原始评论数据', '清洗后的评论数据', '1-2 秒'],
        ['3', 'Embedding 向量化', '使用大模型将评论文本转为向量表示', '清洗后评论文本', '向量数组 (n × 768/1536)', '2-10 秒（取决于评论量）'],
        ['4', '聚类分析', '基于向量相似度对评论进行聚类', '向量数组', '聚类分组结果', '2-5 秒'],
        ['5', 'Topic 生成', 'LLM 对每个聚类生成话题名称、关键词和总结', '聚类结果 + 代表评论文本', 'Topic 列表 + 关键词 + AI 总结', '2-5 秒'],
        ['6', 'AI 总结生成', 'LLM 整合所有 Topic 数据，生成完整分析报告', '所有 Topic 数据', '整体分析报告文本', '1-3 秒'],
    ],
    col_widths=[1, 2.5, 4, 2.5, 2.5, 2]
)

doc.add_paragraph()

add_para(doc, '追踪模式下的额外流程：', bold=True)
add_numbered(doc, '初始分析完成（6阶段）后，系统记录 last_comment_id')
add_numbered(doc, '按 poll_interval_seconds 周期轮询平台 API')
add_numbered(doc, '发现新评论 → 增量清洗 → 增量 Embedding → 分配到已有 Topic 或创建新 Topic')
add_numbered(doc, '更新情感统计数据')
add_numbered(doc, '如积分耗尽 → 自动停止追踪 → 发送通知')

doc.add_paragraph()
doc.add_paragraph()

# Footer
footer = doc.add_paragraph()
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer.add_run('— 文档结束 —')
run.font.size = Pt(10)
run.font.color.rgb = RGBColor(153, 153, 153)
run.font.italic = True

# ============================================================
# Save
# ============================================================
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AI_Opinion_Analytics_需求清单.docx')
doc.save(output_path)
print(f'文档已生成: {output_path}')
