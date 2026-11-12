# 本地受保护视觉批准

## 账户与信任边界

使用两个独立 Windows 账户。Codex 在标准账户下运行，审批账户保管签名私钥并人工查看材料。管理员将审核过的签名工具安装到 `C:/ProgramData/CodexFrontendApproval/runtime/`，将公钥登记为 `C:/ProgramData/CodexFrontendApproval/trust.json`。运行账户对此目录仅有读取权限。

私钥保存在审批账户自己的目录中，使用密码加密并限制文件权限。代理不得生成生产私钥、读取密码、代签批准或自行登记公钥。仓库中的 PASS、模型复查、同账户按钮和口头确认均不能满足签名校验。

审批端的 Python 与 cryptography 依赖也必须位于代理不可修改的安装目录。使用 Python 的 `-I` 隔离模式启动受保护的签发脚本。管理员配置完整运行环境后再生成生产密钥，避免通过可修改的解释器、依赖或 PYTHONPATH 暴露私钥密码。

本机若由可修改信任目录的管理员账户运行 Codex，验证器会阻断。账户隔离、私钥和受保护公钥全部配置后再使用批准结果。当前安装提供签发与验签工具，账户和信任登记的实际状态需要检查。

## 首次配置

管理员审核 `frontend-policy/approval_signer.py`、`visual_approval.py` 与 `install-approval-trust.ps1`。将签名工具放到代理不可修改的安装目录。审批账户在自己的交互式终端生成密钥，输入密码，保留私钥，将生成的公钥 JSON 交给管理员。

```powershell
& '受保护Python的绝对路径' -I '受保护approval_signer.py的绝对路径' keygen --private-key "$env:USERPROFILE/.frontend-approval/private.pem" --output "$env:USERPROFILE/frontend-review-public.json" --reviewer "审批账户名"
```

管理员执行安装脚本。AgentIdentity 和 ReviewerIdentity 使用真实 Windows 账户。脚本输出的 key fingerprint 应由用户核对。

```powershell
./install-approval-trust.ps1 -TrustSource '审批公钥JSON路径' -AgentIdentity '计算机名\Codex运行账户' -ReviewerIdentity '计算机名\审批账户'
```

## 每次批准

视觉实现先按 critic.md 完成当前截图的独立美学评审及必要改进。当前 Critic 报告、原始回复和执行记录与最终复核共同进入冻结材料及签名，缺失或未达主工作流的评分条件时先解决对应缺口。

1. 完成真实测试和独立复查，修复已知问题，登记 task.independent_review。运行 finalize 同步清单、执行完整检查并绑定交付前复核，确认最终复核子阶段达到 READY。总体结果在缺少有效批准时保留 BLOCKED。
2. 运行导出命令，得到申请与冻结的截图、源码、原需求、复查报告和交付前复核记录。浏览器原始快照包含实际正文字体采样，最终复核全文绑定签名。导出会拒绝尚有实现检查缺口的任务。
3. 签发工具先将材料复制到审批账户的私有目录并校验哈希。审批者查看工具打印的私有副本，尤其检查文案必要性、组件定制、布局、素材与动态状态。以 request hash 确认这次审批的版本，输入私钥密码，签发批准或拒绝。
4. 将申请和签名回执复制回项目，登记 `task.visual_approval`，重新运行 `check`。

```powershell
python visual_approval.py --root '项目路径' --output '新的审批包目录'
# 审批账户运行受保护的签发工具
& '受保护Python的绝对路径' -I '受保护approval_signer.py的绝对路径' sign --request '审批包/request.json' --private-key '审批私钥路径' --output 'receipt.json' --reviewer '审批账户名' --decision approve
```

task 中登记项目内的实际路径。

```json
{"visual_approval":{"request":"work/approval/request.json","receipt":"work/approval/receipt.json"}}
```

签名采用 Ed25519，绑定任务、策略哈希、执行范围、当前源码、测试记录、截图、独立报告和冻结材料。有效期最长 24 小时。任何绑定内容变化后重新导出并批准。回执拒绝产生 FAIL，缺失、过期、伪造或信任目录可写产生 BLOCKED。有效批准仍须同时满足其余实现检查。

## 检查结果的使用

批准证据是可验证的签名回执。用户可在受保护的审批工具中核验申请及其版本。Codex 所在账户能改写的本地代码和聊天输出仍须与回执核对。完整的最终门禁应由受保护的执行账户运行经过审核的验证器。不要把普通用户目录里的脚本安装声称为已经建立了操作系统隔离。
