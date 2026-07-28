---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 07
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: 个人微信(wx=True)发送分支及 wx_key/user_name 配置在生产路径上不可达
tags: [autotrade-pm, dead-code, config-residue]
---

# 个人微信(wx=True)发送分支及 wx_key/user_name 配置在生产路径上不可达

## 位置

`tokenDemo/autoTrade_pm.py:429-434`（配置注入）与 `:628-642`（发送分支）

## 证据

`from_cfg` 注入两个只服务于该分支的字段：

```python
obj.wx_key = kwargs.get(
    "wx_key", os.getenv("WX_KEY", "fe197940-30c1-4cea-a41a-17b461423f83")
)
obj.user_name = kwargs.get(
    "user_name", os.getenv("USER_NAME", "49124710049@chatroom")
)
```

`send_msg` 的 `wx` 形参默认 `False`，`if wx:` 分支是这两个字段的唯一读取方：

```python
async def send_msg(
    self, msg: str, wx: bool = False, qy_key: Optional[str] = None
) -> None:
    ...
    if wx:
        json_msg = {
            "MsgItem": [
                {
                    "AtWxIDList": ["string"],
                    "ImageContent": "",
                    "MsgType": 0,
                    "TextContent": msg,
                    "ToUserName": self.user_name,
                }
            ]
        }
        url = (
            f"http://wechatpadpro:1238/message/SendTextMessage?key={self.wx_key}"
        )
    else:
        json_msg = {"msgtype": "text", "text": {"content": msg}}
        url = (...)
```

全文件 `send_msg(` 共 24 个 AUTOBN 侧调用点（`:760`、`:764`、`:770`、`:774`、`:777`、`:784`、`:843`、`:888`、`:892`、`:909`、`:939`、`:959`、`:987`、`:990`、`:996`、`:1598`、`:1717`、`:2005`、`:2009`、`:2047`、`:2051`、`:2323`、`:2328`、`:2356`），**没有一处传 `wx=True`**；测试文件 `test_autoTrade_pm.py` 也没有任何 `wx=True` / `wx_key` / `user_name` 的引用。

`:396` 还留着一行注释掉的形参签名 `#        wx_key, user_name,`，是同一次迁移的残留痕迹。

## 为什么是问题

`if wx:` 分支、两个配置字段、两个环境变量（`WX_KEY` / `USER_NAME`）以及那个硬编码的 `wechatpadpro:1238` 内网地址构成一整条**从未被执行过的通知链路**。通知早已切到企业微信 webhook + PushPlus（`:620-625`），个人微信这条只剩壳。

危害不在运行时（它不执行），而在两处误导：

1. **运维会以为它是可用开关**——看到 `WX_KEY` / `USER_NAME` 两个环境变量和 `wx` 形参，会以为配上就能走个人微信通知，实际没有任何调用点会触发它，配了也不生效。
2. **`send_msg` 的签名比实际需要宽一档**——`wx` 形参让每个读代码的人都要先确认"到底有没有人传 True"才能理解这个函数的行为。

顺带一处：`:430` 的默认值是一个形如真实 webhook key 的硬编码 UUID，`:433` 是一个真实形态的群聊 ID。因为分支不可达，实际不构成凭证泄露风险，但删除时应当一并清掉，别把它留在仓库里。

## 影响面

不修：`send_msg` 保留一个永假的分支和两个死配置，`from_cfg` 的配置面看起来比实际能力大。

修了会碰到：`tokenDemo/autoTrade_pm.py:429-434`（删两个字段）、`:601-603`（`send_msg` 签名去 `wx` 形参）、`:611`（docstring 去 `wx` 说明）、`:628-648`（`if wx:` / `else:` 合并成单一企业微信分支）、`:396`（清掉注释残留）。24 个调用点全部用默认值调用，**无需改动任何调用点**。

`AUTOA.send_msg`（`:2666`）是独立实现（`classmethod`，签名 `(cls, msg, pushplus_notification=None)`），不受影响。

## 建议改法

删 `wx` 形参和 `if wx:` 整段，`send_msg` 只留企业微信 webhook 分支；同步删 `from_cfg` 的 `wx_key` / `user_name` 与 `:396` 注释残留。如果个人微信通道以后还要用，应当在真正接线的那次改动里重新加，而不是提前留壳。

## 对抗验证记录

本条的自动验证 agent 在网关 524 中断，证据由我手工复核：

- Grep `wx=True\|wx_key\|user_name\|send_msg(` 覆盖 `autoTrade_pm.py` 与 `test_autoTrade_pm.py`：`wx_key` / `user_name` 只出现在 `:396`（注释）、`:429-433`（赋值）、`:636`、`:641`（`if wx:` 内读取）四处；24 个 `send_msg(` 调用点无一传 `wx=True`。
- 读 `:601-648` 确认 `if wx:` 是这两个字段的唯一读取路径，且 `wx` 只能由调用方显式传 True 才为真（没有从配置/环境变量间接置真的路径）。
- 结论：分支不可达属实，非"暂时没用但可能被外部调用"——`send_msg` 是实例方法，本文件外无引用方（`autoTrade.py` / `autoTrade_papi.py` 各有自己的副本）。
- 定级取 P2：纯清理，不影响任何现有行为，收益是配置面与函数签名的诚实度。
