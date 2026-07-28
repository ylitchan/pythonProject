---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 17
nature: bug
severity: P2
confidence: high
suggested_action: cs-refactor
summary: get_symbols_info 的 exchange_info 兜底分支不可达且缺 _unwrap_api_response，一旦走到必炸
tags: [autotrade-pm, dead-code, latent-bug]
---

# get_symbols_info 的 exchange_info 兜底分支不可达且缺 _unwrap_api_response，一旦走到必炸

## 位置

`tokenDemo/autoTrade_pm.py:2197-2198`

## 证据

```python
def get_symbols_info(self, exchange_info=None):
    # 获取交易所信息（公开合约元信息使用 USDS-M Futures 新 SDK）
    if exchange_info is None:
        exchange_info = self.market_client.rest_api.exchange_information()
    ...
    sp = {
        i["symbol"]: ...
        for i in exchange_info["symbols"]          # :2205
    }
    self.symbols_info = {
        ...
        for symbol in exchange_info["symbols"]      # :2215
    }
```

全项目唯一调用点始终传参（`rzq_market`，`:2343-2344`）：

```python
exchange_info = await self.get_exchange_info()
self.get_symbols_info(exchange_info)
```

同文件内有一处**写对了的同类兜底**可作对照（`_normalize_account_info`，`:531-534`）：

```python
if account_info is None:
    account_info = self._unwrap_api_response(
        self.papi_client.rest_api.account_information()
    )
```

而 `_unwrap_api_response`（`:525-528`）正是把 SDK 的 `ApiResponse` 拆成 dict 的那一层：

```python
def _unwrap_api_response(cls, data):
    if hasattr(data, "data") and callable(data.data):
        return cls._model_to_dict(data.data())
    return cls._model_to_dict(data)
```

## 为什么是问题

两个缺陷叠在一起：

1. **分支不可达**——唯一调用点 `:2344` 永远传 `exchange_info`，`if exchange_info is None` 从未成立过。`get_symbols_info` 是实例方法，本文件外无引用方，测试也不单独用 `None` 调它。
2. **一旦走到必炸**——SDK 的 `exchange_information` 是同步方法（证据：`_call_api:692` 用 `asyncio.to_thread(method, *args, **kwargs)` 提交它，只有同步 callable 才这么用），返回的是 `ApiResponse` 包装对象而不是裸 dict。`:2198` 直接拿返回值不经 `_unwrap_api_response`，紧接着 `:2205` / `:2215` 的 `exchange_info["symbols"]` 就会在包装对象上下标——抛 `TypeError`。同文件 `:531-534` 的正确写法证明了这层拆包是必需的，不是可选的。

顺带两处一致性问题：这条兜底还绕过了 `_call_api` 提供的 `_api_semaphore` 限流与 `API_TIMEOUT_SECONDS` 超时——本文件所有其它 SDK 调用都走 `_call_api` 或至少走 `_unwrap_api_response`，只有这一处两样都没有。

所以它属于"看着是防御，实际是陷阱"：谁将来图省事写一句 `self.get_symbols_info()`（签名明确允许），拿到的不是元数据而是一个 `TypeError`。

## 影响面

不修：当前零运行时影响（分支不可达），但签名对外承诺了一个不能用的调用方式。风险窗口是将来新增调用点时——`get_symbols_info()` 无参调用看起来完全合法，实际必失败，且失败点在两行之后的字典推导里，报错信息（`'ApiResponse' object is not subscriptable`）不会指向真正的原因。

修了会碰到：`tokenDemo/autoTrade_pm.py:2195-2198`。唯一调用点 `:2344` 不需要改动。

## 建议改法

二选一：

- **删兜底**（推荐）：`exchange_info` 改为必填位置参数，`get_symbols_info(self, exchange_info)`。唯一调用点已经在传，改完签名与实际用法一致，`None` 这条路彻底不存在。
- **补对**：若确实想保留无参调用能力，按 `:531-534` 的写法补上 `self._unwrap_api_response(...)`；但由于该方法是同步的而 `get_exchange_info`（`:2180`）已经带 6 小时 TTL 缓存，无参路径会绕过缓存重复打接口，收益可疑——倾向选第一条。

## 对抗验证记录

本条不是工作流产出，是我在做旧审计交叉核查时撞见的，工作局各区域 finder 与 lens finder 均未报出（属本轮覆盖缺口）。证据由我完整复核：

- Grep `get_symbols_info(` 全项目，仅 `:2195`（定义）与 `:2344`（调用，传参）两处命中；测试文件无引用。
- 读 `_call_api:688-695` 确认 `asyncio.to_thread(method, ...)`，据此判定 `exchange_information` 为同步 callable——**这一步纠正了我先前"没 await 会拿到协程对象"的判断，机制是缺拆包而非缺 await**，结论（走到必炸）不变但原因不同。
- 读 `_unwrap_api_response:525-528` 确认拆包逻辑，读 `_normalize_account_info:531-534` 确认同文件内同类兜底的正确写法，构成直接对照。
- 定级取 P2 而非 P1：今天不可达，无任何现网影响；性质标 `bug` 而非 `maintainability`，因为它不只是冗余，是一条写错了的代码路径。这也是本轮唯一一条性质为 `bug` 的发现。
