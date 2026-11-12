# StyleKit 发现与复用

## 选定后的完整同语种文档

固定选定 slug，后续需求继续采用它。已连接 MCP 时调用 stylekit_get_style，include 包含 brief，读取实际 structuredContent.brief.designDocument。其默认 content 为英文。需要页面对应语言时读取实际文档链接，并将 locale 设为该页语言。

未连接 MCP 时使用已安装的 CLI 获取 brief，再通过以下命令取得官方完整 Markdown。zh-CN 映射到 zh，英文为 en。若当前语言版本不可取得，记录受阻，不能声称英文摘要是完整的本页语言文档。

```powershell
python '<skill>/scripts/stylekit.py' --output work/stylekit/editorial/design.zh.md document editorial --locale zh
```

完整来源含 Implementation Contract，保留源 URL、slug、locale、内容 SHA256 和获取时间。已有来源变化时保存版本化副本，保留历史资料。把完整来源原样纳入项目 design.md，再追加项目适配与验收章节。按 Implementation Contract 逐条落实，适配的实际修改与冲突处理明确记录。

## 调用时机

新视觉方向的四张参考图生成前执行目录查询，再查询候选风格详情与 brief，按场景形成 A/B/C/D。用户选定后获取该方向 tokens 和具体组件 recipe，浏览可用的动画/模板资产，再写 design.md。局部续作沿用已存的真实选型与素材，来源变化时刷新受影响资料。本任务同 slug、语言与版本的真实响应复用已保存内容；brief 已含所需 tokens 或资源时直接使用，缺字段时再补查。完整返回保存一次，读取时只提取当前需要的 data 字段，避免将同一 stdout 与解析后的 data 重复载入上下文。MCP、CLI、HTTP 作为实际可用的调用与回退路径，一次成功后无需并行重复查询同一内容。

已安装的只读适配器调用固定的官方 stylekit-cli 0.3.1。已连接官方 MCP 时优先调用，未连接或实际受阻时使用此 CLI／HTTP 接口。保存命令、实际返回和线上/内置数据来源。CLI 与 MCP 的可用情况分别报告。

```powershell
python '<skill>/scripts/stylekit.py' --output work/stylekit-catalog.json list --limit 16 --json
python '<skill>/scripts/stylekit.py' --output work/editorial-brief.json brief editorial --json
python '<skill>/scripts/stylekit.py' --output work/editorial-button.json recipe editorial button --json
python '<skill>/scripts/stylekit.py' --output work/pointer-assets.json assets --query pointer --limit 10 --json
```

具体 kind/id 从真实资产列表读取。资产返回 source/remote 且含实际 files 时才可复用源码。metadata、restricted、external 按返回信息处理，不能凭元数据声明已取得组件。遇到网络故障保留真实错误，尝试官方 HTTP API 或网页，明确内置快照的时效。

StyleKit registry 安装的是主题变量，运行组件按 recipe 或资产中的实际代码实现。核对依赖、许可、归属和接口，按原规则改写禁色、默认色板、布局和缓动，优先用于主要组件，缺少合适资源时再组合补充 UI 库。不要把打印出的 add 安装命令当作安装成功。

## 场景覆盖

采用开放目录，先取得实际 total 与分页信息，再按场景筛选、按需翻页；找到满足差异要求的四个候选后停止展开其他风格。保持来源、查询时间与实际使用的分页，不为选型加载整个目录的全部详情。覆盖企业/B2B、后台/数据、作品集、内容/杂志、知识库、电商、品牌营销、创意表达等常见场景。教育、医疗、金融、无障碍优先或其他业务按任务映射内容、数据与交互要求，再找适合的风格。覆盖数量随线上与快照变化，记录实际 total，保留分页，避免用网页标题数字推断可取得的资产数量。

## 四套方案记录

选型阶段只保存一份轻量 work/style-discovery.json，记录 scene、source、queried_at、catalog_total、mode=new、options。每项有 id、style_name、style_slug、source、layout、typography、components、material、imagery、motion。style_name 和 style_slug 来自实际查询。A/B/C/D 每对至少三个非配色字段具体不同。直接展示四张图片，图注附实际风格名称、slug 和动态意向，保持参考阶段轻量。

正式任务设置 task.style_discovery 指向该文件并登记实际选定编号。已有选型可用 mode=existing，用户指定方向可用 mode=user_custom，都附真实 evidence 文件并解释沿用范围。文件进入计划与执行指纹。自动检查只检查记录与明显重复，风格差异仍需查看实际图像。

## 官方依据

CLI、MCP、HTTP 与 registry 的用途及数据级别按官方说明核对。[开发者入口](https://www.stylekit.top/zh/developers) · [CLI](https://github.com/AnxForever/stylekit/blob/main/packages/cli/README.md) · [HTTP API](https://github.com/AnxForever/stylekit/blob/main/docs/API.md)
