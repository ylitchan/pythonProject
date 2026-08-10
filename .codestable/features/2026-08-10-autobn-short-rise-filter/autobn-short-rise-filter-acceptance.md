# AUTOBN 做空涨幅过滤验收报告

> 阶段：阶段3（验收闭环）
> 验收日期：2026-08-10
> 关联方案：`.codestable/features/2026-08-10-autobn-short-rise-filter/autobn-short-rise-filter-design.md`

## 1. 接口契约核对

- [x] 新增`SHORT_RISE_THRESHOLD=0.2`常量。
- [x] 涨幅计算为最高量基准日开盘价到该日以来最高价。
- [x] 过滤在SHORT开仓分支生效。

## 2. 行为与决策核对

- [x] 涨幅达到20%允许进入现有做空信号流程。
- [x] 涨幅低于20%跳过做空，不清除观察状态。
- [x] LONG、BD入池、OI回撤和平仓逻辑未改。
- [x] 未新增数据源或跨模块结构。

## 3. 验收场景核对

- [x] 最高量日开盘110、以来最高140时涨幅为27.27%，通过20%门槛。
- [x] 最高量日开盘110、以来最高130时涨幅为18.18%，拒绝做空。
- [x] 相关AUTOBN 62 tests / OK。
- [x] 全量126 tests / OK。
- [x] Ruff通过。
- [x] YAML校验通过。

## 4. 术语一致性

- [x] `SHORT_RISE_THRESHOLD`与“最高量基准日/高位涨幅”语义一致。

## 5. 领域影响盘点

- [x] 不新增领域实体、结构决策或流程协议，无需cs-domain。

## 6. requirement回写

- [x] 已backfill `autobn-short-rise-filter.md`为current并更新VISION。

## 7. roadmap回写

- [x] 非roadmap起头。

## 8. attention.md候选盘点

- [x] 无通用环境或工具候选。

## 9. 遗留

- 涨幅过滤是风险门槛，不保证后续必然下跌；回测样本量较小，后续可继续积累实盘样本。
