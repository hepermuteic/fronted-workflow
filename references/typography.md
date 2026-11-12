# 字体选型与正文检查

正文与必要说明禁用微软雅黑，包括 Microsoft YaHei、Microsoft YaHei UI、中文别名及其实际回退。把正文、标题、品牌、数字、表单控件与第三方组件的字体职责写入 design.md，核对各自真实加载与显示。

## 按内容和场景选择

| 字体 | 可考虑的用途 | 项目检查 |
| --- | --- | --- |
| 思源黑体 / Source Han Sans | 中文正文、表单与信息型界面，可按字重用于标题 | 简体中文字形、实际字重、字体文件与加载体积 |
| Arial | 拉丁正文、数字与通用界面 | 小字号和密集内容的阅读表现，配套中文字体 |
| Tahoma | 紧凑的拉丁界面、短标签 | 字腔与间距，中文搭配，实际系统可用性 |
| Georgia | 拉丁文章正文、编辑式内容与引言 | 与中文衬线字体协调，行高与长文阅读 |
| 霞鹜文楷 / LXGW WenKai | 文艺、教育、阅读场景与有书写感的标题 | 实际字形、屏幕表现和所用发行版的真实字重 |
| 霞鹜文楷 Medium | 需要更强书写感的标题或强调内容 | 使用真实 Medium 资源并登记对应字重 |
| Noto Serif SC | 文化感标题、引文和适合衬线阅读的中文内容 | 字重、字号、屏幕阅读和中英文协调 |
| Mantou Sans / 饅頭黑體 | 儿童、休闲品牌、醒目标题和品牌字 | 项目以台湾繁体中文补充为特点，使用实际简体文案检查字形覆盖 |

以上为候选。按选定 StyleKit 方向、页面内容和用户定位比较实际文字，确定本项目字体。Arial、Tahoma、Georgia 的中文混排需要独立选择支持中文的字体。记录目标设备上的真实可用性，明确所用文件和授权来源。

思源黑体的发行与授权从 Adobe 官方仓库核对。[Source Han Sans](https://github.com/adobe-fonts/source-han-sans)

霞鹜文楷按所用发行版核对实际字重、中文字形和字体资源，嵌入与分发按随附许可处理。[LXGW WenKai](https://github.com/lxgw/LxgwWenKai)

Noto Serif SC 的字体元数据包含简体中文、拉丁字符和字重轴信息。[Noto Serif SC](https://github.com/google/fonts/blob/main/ofl/notoserifsc/METADATA.pb)

Mantou Sans 按实际文案核对简繁体和标点覆盖，参考原项目的定位及授权资料。[Mantou Sans](https://github.com/mant0u0/MantouSans)

## 设计与实现

字体决定包含 family、角色、实际字重、字号、行高、加载方法、语言覆盖、备用字体、资源出处和许可。将选择同步到 tokens、控件与组件主题，使用本页的中文、英文、数字和标点试排。

检查换行、行长、对比度、放大表现、占位提示、错误信息和动态状态。通过删重复文案、合并提示与调整间距维持信息密度。对冷启动、字体加载失败和实际备用字体做必要检查，确认正文和控件显示符合要求。

按页面使用的字重与字形加载字体，评估资源体积、子集、格式和缓存。字体资源和组件依赖按实际项目登记，保留真实来源和字重信息。

需要绑定项目字体文件时，在 task.assets 中按真实来源登记 existing 或 user_provided、role 为 font，并记录 path 与 usage。源码 files 登记代码和配置，二进制字体以资源登记。固定浏览器保存实际字体响应哈希，结合实际字形、声明文件与加载结果核对。

## 实际浏览器验收

固定采集器记录可见正文文本、计算字体与字号，并通过 Chromium/Edge 的平台字体接口取得实际字形使用的 familyName、postScriptName 和 glyphCount。检查声明字体栈、实际回退和字体别名，包括第三方组件、表单与 CSS 生成文字。

实际采用微软雅黑的正文记为 FAIL。缺少实际字形信息、字体加载未完成或无法检查的边界记为未验证，按范围补齐证据。计算样式、字体文件存在和加载请求均与实际渲染结果一起判断。字体样本保存于浏览器快照的 body_typography。

标题与品牌字单独按设计要求判断，正文检查覆盖正文及必要控件文案。原生 APP 使用相应平台字体调试与真实设备证据，记录字体文件、实际字重、字形回退与显示结果。

平台字体检查依据 Chrome DevTools Protocol 的 CSS 字体接口。[CSS.getPlatformFontsForNode](https://chromedevtools.github.io/devtools-protocol/tot/CSS/#method-getPlatformFontsForNode)
