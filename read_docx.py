from docx import Document

# 读取 DOCX 文件
doc = Document("新建 DOCX 文档.docx")

# 提取所有段落的文本
full_text = []
for para in doc.paragraphs:
    if para.text.strip():  # 只添加非空段落
        full_text.append(para.text)

# 打印内容
print("\n".join(full_text))
