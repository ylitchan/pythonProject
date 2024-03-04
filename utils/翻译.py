from pygtrans import Translate

client_translate = Translate()
text = client_translate.translate('Google Translate')
print(text.translatedText)  # 谷歌翻译
