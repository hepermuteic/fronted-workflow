# 动态组件与鼠标交互的优先选择

编码前先检查现有兼容动效引擎。再查询选定 StyleKit 风格的组件配方、动态资产与 Cursor Lab，优先复用符合场景、源码可用的模式。优先采用 StyleKit 自带动态资源，实际缺口再评估 Magic UI、Aceternity UI 等补充组件。

React 的布局、列表、拖拽、弹簧和手势优先评估 Motion，接口使用 motion/react。多框架的指针跟随、复杂时间线和滚动编排优先评估 GSAP。已有合适引擎直接复用，简单局部过渡可用 CSS 并记录选择理由，避免为了展示多套依赖而叠加引擎。引入引擎前通过 Context7 核实版本/API，记录实际安装与调用。

在 task.design_plan.motion_plan 记录 engine、reason、docs_evidence，以及 pointer 对象。pointer 包含 decision=used/omitted、reason、touch_fallback、keyboard_fallback、reduced_motion、cleanup。每个新页面都作适配判断，根据场景采用磁吸、局部倾斜、聚光、拖拽或其他交互。表单、密集工具和触屏场景可用清晰状态反馈解释省略重指针效果的原因。

精细指针效果按 hover:hover/pointer:fine 启用，保留系统光标与焦点，避免遮住文字。触屏提供等价操作，键盘完成主要任务，减少动态模式缩短或关闭位移并保留状态结果。卸载时清理监听、动画和定时器。

实际验证 hover、指针移动、前后样式、点击结果、触屏回退、键盘、reduced-motion 和卸载清理。仅导入库、背景常动或截图无法覆盖这些行为。记录引擎 import、实际组件及对应浏览器步骤。

已核实 Motion 的 useMotionValue/useSpring/useReducedMotion，以及 GSAP 的 quickTo/matchMedia/revert。具体项目按其版本再次核实，持续动画不得默认使用 linear 或 ease-in-out。[Motion](https://motion.dev/docs/react) · [GSAP](https://gsap.com/docs/v3/)
