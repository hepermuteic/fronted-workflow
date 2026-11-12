# 实际页面与当前源码的对应

浏览器能执行断言，只能证明打开的页面有该行为。测试 URL 指向旧页面时，不能把本地新文件的哈希贴上去，就声称新代码已经测过。

## 静态页面

在 `task.files` 列出实际页面及同源 JS/CSS 输入。固定 runner 捕获实际 HTML、脚本和样式响应；实际 HTML 必须匹配声明文件，同源运行代码也必须匹配当前输入。点击和 SPA hash 变化不会伪造一个新的文档来源。

任务范围只影响需要检查的页面/区域，不代表可以漏记实际运行的代码。外部 CDN 资源仍捕获并纳入运行证据；外部库来源和版本另按组件规范核实。

## React、Vue 等构建项目

Vue/Vite 项目在 task.files 登记实际 .vue、.ts 或 .js 入口、样式、Vite 配置、package.json 及项目锁文件等相关输入。使用项目已有命令执行生产构建，再启动 vite preview，登记本次实际生成的 HTML、JS、CSS 文件名。开发服务的 HMR 注入与源码变换会影响字节对应，正式验收按构建产物采集。

Vue 的 TypeScript 组件按项目配置运行 vue-tsc 等类型检查，纯 TypeScript 项目运行现有 tsc 检查，结果作为独立命令证据。Vite 构建只转译 TypeScript，类型检查需实际执行。JavaScript 项目使用适用的现有检查与构建命令。参考 Vue 官方的 TypeScript 工程说明。[Vue TypeScript](https://vuejs.org/guide/typescript/overview)

使用实际项目命令构建并运行产物预览。计划中指定构建检查及本次真实输出文件，示例结构：

```json
{
  "deployment": {"mode": "build", "check_id": "build"},
  "checks": [
    {"id": "build", "type": "command", "required": true,
     "outputs": ["dist/index.html", "dist/assets/app.js", "dist/assets/app.css"]}
  ]
}
```

上面只示意相关字段；保留任务已有检查。真实文件名按构建配置填写，包括带哈希的实际文件名；不要照搬示例或临时换成别的页面。第一次可先用项目命令了解输出，再把确切文件列入检查并通过 `run --check-id build -- <真实命令参数>` 正式运行。

构建凭证绑定实际输入、命令执行和输出字节。`browser-run` 校验构建凭证及当前输出，再校验服务器真正返回的 HTML 和同源 JS/CSS。构建后的源代码变化、产物篡改或旧服务器内容都使对应证据不合格。

命令检查的输入哈希和浏览器运行资源分别记录；采集新增运行资源不要求无故重跑同一构建。修改真实输入或输出后才重跑相应检查。编译产物不要同时列为会被构建修改的源输入。

SSR、服务端实时注入、运行时变换等不能与声明字节对应时，当前通用 runner 会阻断来源认定。需要该项目可验证的服务版本/构建对应机制后才能认证此范围；不能给它自动豁免或声称已经测过当前源码。其他页面行为仍可诊断，但不能据此报总体 PASS。
