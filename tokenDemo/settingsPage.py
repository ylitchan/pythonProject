import streamlit as st


# 自定义CSS（设置背景图）
def set_background_image(image_url):
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("{image_url}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        /* 内容区域半透明背景 */
        .st-emotion-cache-1y4p8pa,
        .st-emotion-cache-1v0mbdj {{
            background-color: rgba(255, 255, 255, 0.9) !important;
            border-radius: 10px;
            padding: 20px;
        }}

        /* 侧边栏样式 */
        .st-emotion-cache-6qob1r {{
            background-color: rgba(0, 0, 0, 0.8) !important;
        }}

        /* 按钮样式 */
        .stButton>button {{
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
            padding: 10px 20px;
            border: none;
            font-size: 16px;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


def show_settings():
    # 设置背景图（使用在线图片或本地文件）
    BACKGROUND_IMAGE = "https://images.unsplash.com/photo-1519681393784-d120267933ba"  # 示例图片
    set_background_image(BACKGROUND_IMAGE)

    # 页面内容
    st.title("⚙️ 系统设置")
    st.write("欢迎来到系统设置页面，请根据需要调整参数。")

    # 设置项
    with st.container():
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🔐 安全设置")
            st.checkbox("启用双重认证", value=True)
            st.checkbox("自动注销（30分钟无操作）", value=True)
            st.button("更改密码")

        with col2:
            st.subheader("🎨 外观设置")
            theme = st.selectbox("主题模式", ["浅色", "深色", "自动"])
            font_size = st.slider("字体大小", 12, 24, 16)
            st.color_picker("主色调", "#4CAF50")

    # 保存设置
    if st.button("💾 保存设置"):
        st.success("设置已保存！")
        st.balloons()
