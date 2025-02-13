import pandas as pd
import plotly.express as px
import streamlit as st


def set_css_image(image_url):
    # 自定义CSS样式
    st.markdown(f"""
    <style>
        .stApp {{
            background-image: url("{image_url}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        /* 主内容区样式 */
        .main-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}
    
        /* 时间线样式 */
        .timeline {{
            border-left: 3px solid #2ecc71;
            padding-left: 2rem;
            margin: 2rem 0;
        }}
    
        .timeline-item {{
            background: rgba(46, 204, 113, 0.1);
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            position: relative;
        }}
    
        .timeline-item::before {{
            content: "";
            position: absolute;
            left: -2.45rem;
            top: 0;
            width: 15px;
            height: 15px;
            background: #2ecc71;
            border-radius: 50%;
        }}
    
        /* 技能雷达图容器 */
        .skill-chart {{
            background: white;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
    
        /* 响应式布局 */
        @media (max-width: 768px) {{
            .main-container {{
                padding: 1rem;
            }}
            .timeline {{
                padding-left: 1rem;
            }}
        }}
    </style>
    """, unsafe_allow_html=True)


# 简历内容数据
resume_data = {
    "personal_info": {
        "name": "颜立全",
        "title": "后端开发工程师",
        "contact": {
            "📧": "yanlq6@yanlq6@mail2.sysu.edu.cn",
            "📱": "+86 178-8035-6481",
            "📍": "福建厦门"
        },
        "social": {
            "GitHub": "https://github.com/ylitchan",
            "LinkedIn": "https://linkedin.com/in/ylitchan",
            "技术博客": "https://blog.ylitchan.tech"
        }
    },
    "skills": {
        "编程语言": 90,
        "问题处理": 85,
        "数据分析": 75,
        "服务部署": 80,
        "架构设计": 70
    },
    "experience": [
        {
            "period": "2021.07 - 至今",
            "company": "厦门渊亭信息科技有限公司",
            "position": "后端开发工程师",
            "details": [
                "开源数据的采集和数据的清洗，对采集系统状态的预警，数据的监测和推送",
                "第三方项目的开发和支持，主要是军工方面的系统开发，涉及数据的转换、生成",
            ]
        },
        {
            "period": "2020.07 - 2021.07",
            "company": "福建福晶科技股份有限公司",
            "position": "器件研发工程师",
            "details": [
                "负责激光器件的研发及生产线技术的优化升级",
            ]
        }
    ],
    "education": [
        {
            "period": "2018.09 - 2020.06",
            "school": "中山大学",
            "degree": "材料工程 硕士",
            "honors": ['两篇计算机领域发明专利']
        }
    ],
    "projects": [
        {
            "name": "智能海战前沿技术预见系统",
            "tech": ["Python", "LLM", "Neo4j"],
            "description": """基于大模型的军事智能平台""",
            "highlight": """
            \n使用 scrapy 搭建高效数据采集体系，将数据解析为结构化数据存入 es，通过优化请求队列管理以及数据解析流程，针对不同网站的结构异同，成功构建了高度自动化且稳定的数据采集流程，同时监测数据并在特定条件进行系统的通知。
\n 运用fastapi开发后端接口，设计并实现了一套简洁且高效的API体系。通过合理的路由规划、数据验证机制以及异步编程技术的运用，确保了系统能够稳定、快速地与前端进行数据交互，满足了大规模并发请求的需求。
\n 利用pymupdf和pandas等文件处理库，成功开发出一套通用的文件读取和内容解析模块。该模块能够准确识别并读取PDF、Word、Excel等多种格式的文件，针对不同文件格式的特点，编写了定制化的解析逻辑，精准提取文本内容、表格数据等关键信息。
\n 采用textsplitter对提取的文件内容进行合理切分，利用大模型和textrank4zh提取关键词，并将其抽取为图谱实体和关系，不仅提升了信息检索的准确性，还为切片元数据添加了更多的描述信息，确保切分后的文本片段既能保留语义完整性，使系统能够更好地理解数据的语义，有效提升了系统的信息检索能力。
\n 借助langchain框架，编写了智能检索与问答逻辑。通过图谱和向量的融合检索以及设计合理的提示词模板，实现了智能文档检索和问答功能"""
        },
    ]
}


# 简历页面内容
def show_resume():
    # 设置背景图（使用在线图片或本地文件）
    BACKGROUND_IMAGE = r"C:\Users\颜立全\Pictures\微信图片_20250126132618.jpg"  # 示例图片
    set_css_image(BACKGROUND_IMAGE)
    # 页眉部分
    with st.container():
        col1, col2 = st.columns([1, 3])

        with col1:
            st.image(r"C:\Users\颜立全\Pictures\微信图片_20250126130845.jpg",
                     width=200, caption="个人照片")

        with col2:
            st.title(resume_data["personal_info"]["name"])
            st.markdown(f"### {resume_data['personal_info']['title']}")

            # 联系方式
            contact_cols = st.columns(3)
            for i, (icon, info) in enumerate(resume_data["personal_info"]["contact"].items()):
                with contact_cols[i % 3]:
                    st.markdown(f"**{icon} {info}**")

            # 社交链接
            social_links = " | ".join(
                [f"[{platform}]({url})" for platform, url in resume_data["personal_info"]["social"].items()]
            )
            st.markdown(social_links)

    # 核心内容布局
    main_col, side_col = st.columns([3, 1])

    with main_col:
        # 工作经历时间线
        st.subheader("💼 工作经历")
        st.markdown('<div class="timeline">', unsafe_allow_html=True)
        for exp in resume_data["experience"]:
            st.markdown(f"""
            <div class="timeline-item">
                <h4>{exp['company']}</h4>
                <p><strong>{exp['position']}</strong> | {exp['period']}</p>
                <ul>
                    {"".join([f'<li>{detail}</li>' for detail in exp['details']])}
                </ul>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 项目经历
        st.subheader("🚀 项目经历")
        for project in resume_data["projects"]:
            with st.expander(f"{project['name']} - {project['description']}"):
                st.markdown(f"""
                - **技术栈**: {', '.join(project['tech'])}
                - **项目亮点**:  
                  {project['highlight']}
                """)

    with side_col:
        # 技能雷达图
        st.subheader("🛠️ 技术能力")
        df_skills = pd.DataFrame({
            "skill": list(resume_data["skills"].keys()),
            "level": list(resume_data["skills"].values())
        })
        fig = px.line_polar(
            df_skills,
            r='level',
            theta='skill',
            line_close=True,
            range_r=[0, 100],
            color_discrete_sequence=['#2ecc71']
        )
        fig.update_traces(fill='toself')
        st.plotly_chart(fig, use_container_width=True)

        # 教育背景
        st.subheader("🎓 教育经历/成果")
        for edu in resume_data["education"]:
            st.markdown(f"""
            **{edu['school']}**  
            {edu['degree']}  
            *{edu['period']}*  
            {', '.join(edu['honors'])}
            """)

        # 下载按钮
        st.download_button(
            label="📄 下载PDF简历",
            data=open(r"d:\Users\颜立全\Desktop\颜立全-中山大学-硕士-python开发-嘉庚创新实验室.pdf", "rb").read(),
            file_name="颜立全-中山大学-硕士-python开发-嘉庚创新实验室.pdf",
            mime="application/pdf"
        )
