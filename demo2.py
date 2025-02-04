from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from binance.spot import Spot


# 获取币安所有交易对信息（带智能缓存）
@st.cache_data(ttl=300)
def get_all_symbols():
    try:
        client = Spot()
        info = client.exchange_info()
        return pd.DataFrame([s for s in info['symbols'] if s['status'] == 'TRADING'])
    except Exception as e:
        st.error(f"获取交易对失败: {str(e)}")
        return pd.DataFrame()


# 获取市场数据（带重试机制）
@st.cache_data(ttl=60)
def get_market_data():
    try:
        client = Spot()
        tickers = client.ticker_24hr()
        return pd.DataFrame(tickers).rename(columns={
            'symbol': 'Symbol',
            'lastPrice': '最新价',
            'priceChangePercent': '24H涨跌',
            'volume': '成交量',
            'quoteVolume': '成交额',
            'highPrice': '最高价',
            'lowPrice': '最低价'
        })
    except Exception as e:
        st.error(f"获取市场数据失败: {str(e)}")
        return pd.DataFrame()


# 页面：币种筛选器
def show_screener():
    st.title("🔍 智能币种筛选器")

    # 获取基础数据
    symbols_df = get_all_symbols()
    market_df = get_market_data()

    if symbols_df.empty or market_df.empty:
        st.warning("数据加载中，请稍候...")
        return

    # 合并数据集
    full_df = pd.merge(
        symbols_df[['symbol', 'baseAsset', 'quoteAsset', 'filters']],
        market_df,
        left_on='symbol',
        right_on='Symbol'
    )

    # 数据预处理
    numeric_cols = ['最新价', '24H涨跌', '成交量', '成交额', '最高价', '最低价']
    full_df[numeric_cols] = full_df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    # 筛选条件面板
    with st.expander("⚙️ 筛选条件", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            min_volume = st.number_input("最小成交量 (USDT)",
                                         value=1e6,
                                         format="%.0f",
                                         help="24小时成交量阈值")
            quote_asset = st.multiselect(
                "计价货币",
                options=full_df['quoteAsset'].unique(),
                default=['USDT']
            )

        with col2:
            price_change_range = st.slider(
                "24H涨跌幅 (%)",
                min_value=-50.0,
                max_value=500.0,
                value=(-10.0, 100.0)
            )
            min_price = st.number_input("最低价格 (USDT)", value=0.0)

        with col3:
            volatility_threshold = st.slider(
                "波动率阈值 (%)",
                min_value=0.0,
                max_value=100.0,
                value=5.0
            )
            price_filter = st.checkbox("仅显示可交易价格范围", True)

    # 动态筛选逻辑
    filtered_df = full_df[
        (full_df['成交额'] >= min_volume) &
        (full_df['quoteAsset'].isin(quote_asset)) &
        (full_df['24H涨跌'] >= price_change_range[0]) &
        (full_df['24H涨跌'] <= price_change_range[1]) &
        (full_df['最新价'] >= min_price)
        ]

    # 计算波动率
    filtered_df['波动率'] = (
            (filtered_df['最高价'] - filtered_df['最低价']) /
            filtered_df['最低价'] * 100
    ).round(2)

    filtered_df = filtered_df[filtered_df['波动率'] >= volatility_threshold]

    # 解析价格过滤器
    if price_filter:
        def parse_price_filter(filters):
            for f in filters:
                if f['filterType'] == 'PRICE_FILTER':
                    return float(f['minPrice']), float(f['maxPrice'])
            return 0, float('inf')

        filtered_df['价格范围'] = filtered_df['filters'].apply(parse_price_filter)
        filtered_df[['最低限价', '最高限价']] = pd.DataFrame(
            filtered_df['价格范围'].tolist(), index=filtered_df.index
        )
        filtered_df = filtered_df[
            (filtered_df['最新价'] >= filtered_df['最低限价']) &
            (filtered_df['最新价'] <= filtered_df['最高限价'])
            ]

    # 展示结果
    st.subheader(f"筛选结果：{len(filtered_df)} 个币种符合条件")

    # 交互式数据表格
    with st.container():
        st.dataframe(
            filtered_df.sort_values('成交额', ascending=False)
            .head(500)
            .style.format({
                '最新价': "{:.4f}",
                '24H涨跌': "{:.2f}%",
                '成交量': "{:,.2f}",
                '成交额': "${:,.2f}",
                '波动率': "{:.2f}%"
            }),
            use_container_width=True,
            height=600,
            column_config={
                "symbol": "交易对",
                "baseAsset": "基础货币",
                "quoteAsset": "计价货币",
                "最新价": st.column_config.NumberColumn(format="$%.4f"),
                "24H涨跌": st.column_config.ProgressColumn(
                    format="%.2f%%",
                    min_value=-50,
                    max_value=500
                ),
                "波动率": st.column_config.NumberColumn(format="%.2f%%")
            }
        )

    # 数据可视化
    with st.expander("📊 可视化分析", expanded=True):
        tab1, tab2 = st.tabs(["分布分析", "关联分析"])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.histogram(
                    filtered_df,
                    x='24H涨跌',
                    nbins=50,
                    title="涨跌幅分布",
                    labels={'24H涨跌': '24小时涨跌 (%)'}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.scatter(
                    filtered_df,
                    x='成交额',
                    y='波动率',
                    color='quoteAsset',
                    log_x=True,
                    title="成交额 vs 波动率"
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig = px.imshow(
                filtered_df[numeric_cols].corr(),
                text_auto=True,
                title="指标相关性分析"
            )
            st.plotly_chart(fig, use_container_width=True)

    # 数据导出
    st.download_button(
        label="📥 导出筛选结果",
        data=filtered_df.to_csv(index=False).encode('utf-8'),
        file_name=f"crypto_screener_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )
