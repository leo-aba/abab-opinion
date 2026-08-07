"""
处理机器组.docx: 删除模板文字 + 去AI味 + 格式整理
"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import copy

SRC = r"D:\Desktop\学习\大三下\aaa实训\刘心宇-202308170205\机器组.docx"
DST = r"D:\Desktop\学习\大三下\aaa实训\刘心宇-202308170205\机器组_润色版.docx"

doc = Document(SRC)

# ============================================================
# 1. 删除模板占位段落（标记删除，后面统一处理）
# ============================================================
# 收集所有段落文本和索引
paragraphs = list(doc.paragraphs)

# 需要删除的段落索引（从0开始）
to_delete = set()

for i, p in enumerate(paragraphs):
    text = p.text.strip()

    # 模板提示文字
    if '摘要字数按照毕设要求' in text:
        to_delete.add(i)
    # 模板关键词（量子力学那行）
    if '量子力学' in text and '关键词' in text:
        to_delete.add(i)
    # "写你自己负责的部分"
    if '写你自己负责的' in text:
        to_delete.add(i)
    # "从用户的角度对系统进行可行性分析"
    if '从用户的角度对系统进行可行性分析' in text:
        to_delete.add(i)
    # "总体设计要站在设计者的角度"
    if '总体设计要站在设计者的角度' in text:
        to_delete.add(i)
    # "该写法仅供参考"
    if '该写法仅供参考' in text:
        to_delete.add(i)

# ============================================================
# 2. 定义需要重写的段落（索引 -> 新文本）
# ============================================================
rewrites = {}

# --- 标题页: "XXXX 系统设计与实现" ---
for i, p in enumerate(paragraphs):
    if 'XXXX 系统设计与实现' in p.text:
        rewrites[i] = 'AI驱动视频评论分析平台设计与实现'

# --- 摘要 (P39) ---
rewrites[39] = (
    "本系统是一个基于B/S架构的视频评论分析平台，前后端分离。后端用FastAPI搭建RESTful API，"
    "数据库用MySQL 8.0配合SQLAlchemy 2.0异步ORM，认证采用JWT，按admin/analyst/viewer三级角色做权限控制。"
    "前端用Vue.js 3 + Composition API做单页面应用，图表部分集成了Chart.js，"
    "包括趋势折线图、情感环形图、话题柱状图、属性旭日图和雷达图六种可视化图表。"
    "平台支持从B站和抖音采集评论，分析进度通过SSE实时推送到前端，"
    "分析完成后通过阿里云DirectMail自动发送HTML邮件报告。"
    "本文重点介绍前后端开发与数据可视化部分的设计和实现。"
)

# --- 背景介绍 (P40) ---
rewrites[40] = (
    "短视频这几年增长很快，B站、抖音上积累了海量的用户评论。"
    "这些评论里有用户对视频内容的直接反馈，也有他们的情感倾向和观点，"
    "对内容创作者和市场研究来说，能快速从大量评论中提取有用信息是很有价值的。"
    "但人工一条条看评论效率太低，而且很难从整体上把握舆论走向。"
    "我们这个平台就是想把数据采集、智能分析和可视化展示整个流程自动化，"
    "让用户能直观地看到评论里到底在讨论什么、情绪倾向怎么样。"
)

# --- 项目背景与意义 (P73) ---
rewrites[73] = (
    "B站和抖音每天产生大量用户评论，这些评论不只是对视频内容的简单反馈，"
    "里面包含了用户的情感倾向、关注焦点和对产品的看法。"
    "对做内容创作的人、品牌方或者做市场调研的来说，"
    "搞清楚大家都在讨论什么、情绪是正面还是负面，对内容方向和产品决策都有参考价值。"
)

# --- P74 ---
rewrites[74] = (
    "但传统的分析方法有几个明显的问题：人工看评论太慢，几千条评论根本看不完；"
    "简单的关键词统计又抓不住评论里真正的意思和情绪；而且评论是不断在增加的，"
    "需要持续跟踪才能及时发现变化。所以做一个能自动采集、智能分析、直观展示评论数据的平台是有实际意义的。"
)

# --- P75 ---
rewrites[75] = (
    "我们这个项目就是做这样一个平台——Opinion AI。它能自动从B站和抖音采集视频评论，"
    "用大语言模型（DeepSeek）做话题分类和情感分析，也可以用Qwen3-Embedding把评论向量化之后，"
    "通过UMAP降维再加HDBSCAN聚类来发现话题，最后用图表和AI生成的综述把结果呈现出来。"
    "我在项目里负责的是前后端框架搭建、数据库设计、API开发、用户认证、前端页面、"
    "可视化仪表盘还有邮件报告系统这些东西。"
)

# --- 本文主要内容 (P77) - 章节概要 ---
rewrites[77] = (
    "本文主要讲Opinion AI平台前后端开发与数据可视化部分的设计和实现，一共六章："
)

# --- P78 - 第一章 ---
rewrites[78] = (
    "第一章 绪论。说明小组成员分工，介绍项目背景和要解决的问题，"
    "概述本文的主要内容，以及开发用的硬件、软件环境。"
)

# --- P79 - 第二章 ---
rewrites[79] = (
    "第二章 主要技术。梳理前后端开发用到的主要技术框架——FastAPI、Vue.js 3、Chart.js、"
    "MySQL、JWT、SSE和阿里云DirectMail，说明每项技术在项目里具体干什么用。"
)

# --- P80 - 第三章 ---
rewrites[80] = (
    "第三章 需求分析。从功能和非功能两个角度分析前后端和数据可视化部分的需求，"
    "明确系统要做哪些事、达到什么标准。"
)

# --- P81 - 第四章 ---
rewrites[81] = (
    "第四章 总体设计。讲系统的四层B/S架构设计，以及九个功能模块各自负责什么。"
)

# --- P82 - 第五章 ---
rewrites[82] = (
    "第五章 详细设计与实现。深入讲数据库设计、用户认证、仪表盘可视化、"
    "分析任务管理、结果展示、实时追踪和邮件报告这些核心模块具体怎么实现的。"
)

# --- P83 - 第六章 ---
rewrites[83] = (
    "第六章 总结与展望。回顾整个项目做了哪些工作，"
    "开发中遇到的问题和解决思路，分析系统目前的特点和不足，以及后续可以怎么改进。"
)

# --- 设计平台-硬件 (P85-86 area) ---
# P85 is "（1）硬件设备" title - keep
# P86 is the hardware description - very AI-ish
rewrites[86] = (
    "开发用的是联想Y9000P笔记本，i7-13700H处理器（14核20线程），"
    "16GB DDR5内存，1TB固态硬盘。显卡是RTX 4060（8GB显存），"
    "跑本地的Qwen3-Embedding-0.6B模型够用。"
)

# --- P88 - 操作系统 ---
rewrites[88] = (
    "系统环境是Windows 11家庭中文版（24H2），开了WSL2，"
    "方便在Windows和Linux环境之间切换。"
)

# --- P90 - 开发平台（非常AI味）---
rewrites[90] = (
    "后端用PyCharm Professional开发，Python 3.10，FastAPI 0.110.1框架，"
    "Uvicorn做ASGI服务器。前端用VS Code + Volar插件，Vite做构建工具。"
    "数据库用MySQL 8.0，InnoDB引擎，支持事务和全文索引。"
    "图表用Chart.js 4.4。代码管理用Git，开发过程中也用了Claude Code辅助。"
)

# --- P92 - 编程语言 ---
rewrites[92] = (
    "后端全部用Python 3.10，加了类型提示（Type Hints），关键业务逻辑用async/await写异步。"
    "数据库操作用SQLAlchemy 2.0异步ORM + asyncmy驱动。"
    "前端用ES6+ JavaScript，HTML5 + CSS3（CSS Variables管理主题色），"
    "用Fetch API调后端RESTful接口。前后端接口按OpenAPI 3.0规范来，"
    "Swagger UI自动生成接口文档方便调试。"
)

# --- 需求分析部分: P91/P113 (在docx里相同的索引) ---
# 在我读到的数据中，P113 是 "写你自己负责的部分的需求分析" - 已加入删除列表
# P114 是 "从用户的角度..." - 已加入删除列表

# --- 总体设计部分 ---
# P140 "写你自己负责的模块的总体设计" - 已在删除列表
# P141 "总体设计要站在设计者的角度逐一实现..." - 已在删除列表

# --- 项目总体架构 (P143) ---
rewrites[143] = (
    "Opinion AI用的是前后端分离的B/S四层架构：表示层、接口层、业务逻辑层、数据访问层。"
    "每层之间有明确的接口，层内部高内聚，层之间低耦合。"
)

# --- P144 表示层 ---
rewrites[144] = (
    "（1）表示层（Presentation Layer）\n"
    "前端是Vue.js 3做的单页面应用，用Composition API（<script setup>）做组件化开发。"
    "数据绑定用ref/reactive，派生状态用computed，数据变化用watch自动更新视图。"
    "静态资源由FastAPI托管，图表用Chart.js渲染（折线图、环形图、柱状图、旭日图、雷达图），"
    "分析进度通过EventSource（SSE）从后端推过来。"
)

# --- P145 接口层 ---
rewrites[145] = (
    "（2）接口层（API Layer）\n"
    "FastAPI写的RESTful API，总共10个路由模块（auth、user、videos、analysis、"
    "settings、dashboard、results、history、stats、tracking），40多个端点。"
    "这层负责路由分发、参数校验（Pydantic Schema）、JWT鉴权、"
    "统一响应格式（{code, message, data}），还有SSE进度推送。"
)

# --- P146 业务逻辑层 ---
rewrites[146] = (
    "（3）业务逻辑层（Service Layer）\n"
    "13个服务模块。我负责的有：auth_service（密码哈希和验证）、history_service（历史记录）、"
    "report_service（HTML邮件报告生成）、email_service（阿里云邮件API）。"
    "组员负责的有：analysis_service（分析流水线）、llm_service（DeepSeek API）、"
    "embed_cluster_service（向量化和聚类）、tracking_service（实时追踪）、"
    "video_service（视频采集）、comment_cleaner（评论清洗）、comment_service（评论入库）、"
    "dashboard_service（仪表盘数据）、results_service（结果查询）。"
    "各服务通过FastAPI的Depends拿数据库会话，模块之间松耦合。"
)

# --- P147 数据访问层 ---
rewrites[147] = (
    "（4）数据访问层（Data Access Layer）\n"
    "用SQLAlchemy 2.0异步ORM操作MySQL 8.0。async_sessionmaker管理连接池，"
    "ORM模型映射7张核心表，用声明式语法定义列类型、约束和索引。"
    "每个HTTP请求通过依赖注入拿到独立的数据库会话，请求结束自动commit或rollback。\n\n"
    "另外还有外部服务层：DeepSeek API做话题分析和情感判断，"
    "阿里云DirectMail发邮件，B站和抖音API采集外部数据。"
)

# --- 总结 (P235) ---
rewrites[235] = (
    "这份报告围绕Opinion AI平台的前后端开发与数据可视化部分，"
    "从需求分析一路做到架构设计再到具体实现。主要做了这些事："
)

# --- P236 ---
rewrites[236] = (
    "（1）后端服务搭建：用FastAPI搭了一套异步Web服务，10个路由模块共40多个API端点。"
    "实现了统一的异常处理、请求日志和JSON响应格式。用FastAPI的依赖注入做了JWT鉴权"
    "和数据库会话自动管理，代码结构比较清晰，后续好维护。"
)

# --- P237 ---
rewrites[237] = (
    "（2）数据库设计：MySQL 8.0，10张表，覆盖用户、视频、评论、话题、分析任务、"
    "追踪任务、积分、设置等业务。用SQLAlchemy 2.0异步ORM做了连接池管理、懒加载引擎和事务管理。"
    "高频字段（用户名、邮箱、视频ID、任务ID）都加了索引，评论用了MySQL ngram全文索引支持中文搜索。"
)

# --- P238 ---
rewrites[238] = (
    "（3）用户认证：bcrypt + JWT做登录认证，支持注册、登录、密码重置和记住登录。"
    "三级角色（admin/analyst/viewer）权限控制，前端路由守卫加API拦截器处理登录态和令牌过期。"
)

# --- P239 ---
rewrites[239] = (
    "（4）前端页面：Vue.js 3写了10个页面（登录、找回密码、仪表盘、创建分析、实时分析、"
    "实时追踪、分析结果、视频管理、历史记录、系统设置），组件化开发，客户端路由。"
    "深色主题（黑底橙青），适配PC和移动端。api.js统一封装HTTP请求和JWT，"
    "charts.js管所有图表实例的创建和销毁，common.js管全局状态和UI工具函数。"
)

# --- P240 ---
rewrites[240] = (
    "（5）数据可视化：Chart.js做了六种图表——趋势折线图（支持天/小时切换）、"
    "情感环形图、话题柱状图、属性旭日图、情感雷达图、时间趋势多线图。"
    "仪表盘用Promise.all并行加载数据，图表实例在重新渲染前先销毁旧的避免内存问题。"
    "配色全部用平台主题色，跟深色主题搭。"
)

# --- P241 ---
rewrites[241] = (
    "（6）实时功能：SSE推送分析进度（比轮询省请求），异步轮询（asyncio.create_task）做评论追踪，"
    "支持增量分析和积分计费。阿里云DirectMail自动发HTML邮件报告。"
)

# --- P242 ---
rewrites[242] = (
    "开发过程中遇到的主要问题和解决办法：\n"
    "（1）SSE超时：向量化和聚类阶段要跑好几分钟，SSE连接容易被代理或浏览器超时断开。"
    "解决方法是每30秒发一个心跳帧保活，客户端在onerror里做自动重连，带上Last-Event-ID支持断点续传。\n"
    "（2）图表加载慢：仪表盘三个图表串行加载要3-5秒，改成Promise.all并行请求后降到1-1.5秒。"
    "每个请求独立try-catch，一个失败不影响其他图表。\n"
    "（3）JWT过期：用户操作到一半令牌过期导致API报错。在api.js的request()里统一拦截401，"
    "自动清除过期令牌跳登录页，提示'登录已过期'，体验好了不少。\n"
    "（4）移动端适配：一开始只做了PC端，手机上侧边栏挡内容、图表太小、按钮点不到。"
    "加了@media max-width: 768px的响应式，侧边栏默认折叠、汉堡菜单呼出，内容单列布局，"
    "图表responsive: true自适应，按钮最小44×44px。"
)

# --- 设计成果亮点 (P244) ---
rewrites[244] = (
    "1、全栈整合：从Vue.js前端到MySQL数据库，完整的数据处理和分析展示链路跑通了。\n"
    "2、可视化比较丰富：六种图表覆盖趋势、分布、对比多个维度，配色跟主题统一，交互也比较流畅。\n"
    "3、体验细节花了些心思：SSE实时推送进度，响应式布局适配多端，空状态和加载态都有提示，"
    "侧边栏追踪红点这些小细节让产品用起来更顺手。\n"
    "4、模块化做得还行：后端三层分离（路由-业务-数据），前端三个模块（api/charts/common）解耦，"
    "后面改需求或加功能不会太痛苦。\n"
    "5、Swagger文档自动生成：FastAPI自带OpenAPI，Swagger UI在线就能看文档和调接口，"
    "前后端联调的时候省了不少沟通成本。"
)

# --- 项目局限性 (P246) ---
rewrites[246] = (
    "（1）大数据量下前端性能：单次分析上万条评论时，话题列表和搜索结果渲染会卡。"
    "后面可以上虚拟滚动（Virtual Scroll）和数据采样，控制DOM节点数量。\n"
    "（2）没写测试：目前全靠人工测和代码审查，没有正式的单元测试和集成测试。"
    "后续应该补pytest后端测试和Vitest前端组件测试，搭CI/CD自动跑。\n"
    "（3）移动端还能更好：基础适配做了，但图表交互（缩放拖拽）和表单填写在手机上体验还是不如PC。"
    "后续可以加触摸手势和移动端专属布局。\n"
    "（4）邮件模板不够灵活：现在是固定的HTML模板，用户不能自定义报告内容。"
    "以后可以提供模板配置，让用户选要包含哪些数据维度。\n"
    "（5）没有国际化：目前只有中文界面。后面可以加i18n支持多语言。"
)

# ============================================================
# 3. 应用重写和删除
# ============================================================

# 首先处理删除（从后往前删，避免索引变化）
# 但python-docx删除段落比较麻烦，我们采用清空方式处理要删除的段落
# 然后合并处理

# 实际做法：创建一个新的paragraph列表
# docx中删除段落需要用XML操作

# 对于要删除的段落，我们将其文本清空
for i in to_delete:
    if i < len(doc.paragraphs):
        p = doc.paragraphs[i]
        # 清空段落内容
        for run in p.runs:
            run.text = ''
        # 如果段落只剩空run，清空整个paragraph的text
        p.text = ''

# 应用重写
for idx, new_text in rewrites.items():
    if idx < len(doc.paragraphs):
        p = doc.paragraphs[idx]
        # 保留第一个run的格式，替换文本
        if p.runs:
            # 保留格式，替换内容
            for j, run in enumerate(p.runs):
                if j == 0:
                    run.text = new_text
                else:
                    run.text = ''
        else:
            # 没有run，添加一个
            p.add_run(new_text)

# ============================================================
# 4. 保存
# ============================================================
doc.save(DST)
print(f"Saved to: {DST}")
print(f"Deleted {len(to_delete)} template paragraphs")
print(f"Rewrote {len(rewrites)} paragraphs")
