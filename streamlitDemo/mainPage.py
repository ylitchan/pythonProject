from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from binance.spot import Spot
from plotly.subplots import make_subplots


# 主页面（保持原有K线图代码）
def show_main():
    # 这里保留之前的K线图实现代码
    # 侧边栏控件
    with st.sidebar:
        st.header("⚙️ 参数配置")
        client = Spot()
        # 获取所有交易对信息
        exchange_info = client.exchange_info()
        # 提取所有交易对
        default_symbols = [symbol['symbol'] for symbol in exchange_info['symbols'] if
                           'USDT' in symbol['quoteAsset'] and 'TRADING' in symbol['status']]
        # 创建组合选择框
        symbol = st.selectbox(
            label="选择或输入交易对",
            options=default_symbols,
            index=0,
            format_func=lambda x: "🟢 " + x if x in default_symbols else "🔵 自定义: " + x,
            help="支持输入任意币安交易对，如 XRPUSDT",
            key="symbol_selector"
        )
        interval = st.selectbox("时间周期", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)
        days_back = st.slider("回溯天数", 1, 365, 30)

    # 时间范围计算
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days_back)

    # 自定义自动刷新组件
    def auto_refresh_component():
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 立即刷新"):
                st.cache_data.clear()
        with col2:
            refresh_flag = st.empty()
            refresh_flag.markdown(
                f"<div style='color:green'>⏳ 下次自动刷新: <span id='countdown'>60</span>秒</div>",
                unsafe_allow_html=True
            )

    # 获取币安数据
    @st.cache_data(ttl=300)  # 5分钟缓存
    def get_binance_data(symbol, interval, start_time, end_time):
        try:
            client = Spot()
            # 转换为毫秒时间戳
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)

            # 获取K线数据
            klines = client.klines(
                symbol=symbol,
                interval=interval,
                startTime=start_ts,
                endTime=end_ts,
                limit=1000
            )

            # 转换为DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_asset_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])

            # 数据类型转换
            numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

            # 时间戳处理
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)

            return df[['Open', 'High', 'Low', 'Close', 'Volume']]

        except Exception as e:
            st.error(f"数据获取失败: {str(e)}")
            return None

    data = get_binance_data(symbol, interval, start_time, end_time)

    if data is not None and not data.empty:
        # 主界面布局
        col1, col2 = st.columns([3, 1])

        with col1:
            # 创建带成交量的子图
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3]
            )
            # K线图
            fig.add_trace(
                go.Candlestick(
                    x=data.index,
                    open=data['Open'],
                    high=data['High'],
                    low=data['Low'],
                    close=data['Close'],
                    increasing_line_color='#00C853',  # 阳线颜色
                    decreasing_line_color='#FF1744',  # 阴线颜色
                    name='价格'
                ),
                row=1, col=1
            )
            # 添加技术指标（示例：20周期均线）
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['Close'].rolling(20).mean(),
                line=dict(color='#0984e3', width=2),
                name='20周期均线'
            ))
            # 成交量柱状图
            fig.add_trace(
                go.Bar(
                    x=data.index,
                    y=data['Volume'],
                    marker_color=np.where(
                        data['Close'] > data['Open'],
                        '#00C853',  # 阳线成交量颜色
                        '#FF1744'  # 阴线成交量颜色
                    ),
                    name='成交量'
                ),
                row=2, col=1
            )
            # 图表布局配置
            fig.update_layout(
                title=f'{symbol} {interval} K线图',
                xaxis=dict(
                    type='date',
                    rangeslider=dict(visible=False),
                    rangeselector=dict(
                        buttons=list([
                            dict(count=1, label="1天", step="day", stepmode="backward"),
                            dict(count=7, label="1周", step="day", stepmode="backward"),
                            dict(step="all")
                        ])
                    )
                ),
                yaxis_title="价格 (USDT)",
                template="plotly_white",
                height=600,
                margin=dict(l=20, r=20, t=60, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # 实时数据面板
            st.subheader("实时信息")
            latest = data.iloc[-1]
            st.metric("当前价格", f"{latest['Close']:.4f}")
            st.metric("24小时涨跌幅",
                      f"{(latest['Close'] / data.iloc[-24]['Close'] - 1) * 100:.2f}%",
                      delta_color="off")

            st.markdown("---")
            st.markdown(f"**开盘价**: {latest['Open']:.4f}")
            st.markdown(f"**最高价**: {latest['High']:.4f}")
            st.markdown(f"**最低价**: {latest['Low']:.4f}")
            st.markdown(f"**成交量**: {latest['Volume']:.2f}")

        # 数据表格展示
        with st.expander("查看完整数据"):
            st.dataframe(
                data.sort_index(ascending=False),
                column_config={
                    "Open": st.column_config.NumberColumn(format="%.4f"),
                    "High": st.column_config.NumberColumn(format="%.4f"),
                    "Low": st.column_config.NumberColumn(format="%.4f"),
                    "Close": st.column_config.NumberColumn(format="%.4f"),
                    "Volume": st.column_config.NumberColumn(format="%.2f")
                }
            )

    else:
        st.warning("未获取到有效数据，请调整参数后重试")

    # 页脚信息
    st.markdown("---")
    st.caption("数据来源：Binance API | 数据延迟：实时")
