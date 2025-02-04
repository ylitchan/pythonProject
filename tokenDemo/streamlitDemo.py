import streamlit as st

from mainPage import show_main
from resumePage import show_resume
from screenerPage import show_screener
from settingsPage import show_settings

# 全局设置
st.set_page_config(
    page_title="ylitchan主页",
    layout="wide",
    page_icon="📊"
)
# 自定义CSS美化
st.markdown("""
<style>
    .stSelectbox label {font-weight: bold;}
    .stSlider span {color: #2c3e50;}
    .stDateInput>div>div>input {background-color: #f0f2f6;}
        /* 主内容区样式 */
    .main-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem;
    }

    /* 时间线样式 */
    .timeline {
        border-left: 3px solid #2ecc71;
        padding-left: 2rem;
        margin: 2rem 0;
    }

    .timeline-item {
        background: rgba(46, 204, 113, 0.1);
        padding: 1rem;
        margin-bottom: 1rem;
        border-radius: 8px;
        position: relative;
    }

    .timeline-item::before {
        content: "";
        position: absolute;
        left: -2.45rem;
        top: 0;
        width: 15px;
        height: 15px;
        background: #2ecc71;
        border-radius: 50%;
    }

    /* 技能雷达图容器 */
    .skill-chart {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    /* 响应式布局 */
    @media (max-width: 768px) {
        .main-container {
            padding: 1rem;
        }
        .timeline {
            padding-left: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)
# 多页面导航
PAGES = {
    "📈 实时行情": "main",
    "🔍 币种预警": "screener",
    "📄 我的简历": "resume",  # 新增简历页面
    "⚙️ 系统设置": "settings"
}
# 路由控制
selected_page = st.sidebar.selectbox("导航菜单", list(PAGES.keys()), index=0)

if PAGES[selected_page] == "screener":
    show_screener()
elif PAGES[selected_page] == "main":
    show_main()
elif PAGES[selected_page] == "resume":
    show_resume()
else:
    # 嵌入网页
    show_settings()
