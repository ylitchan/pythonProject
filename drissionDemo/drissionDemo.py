from DrissionPage import SessionPage

# page = SessionPage()
# page.get('http://g1879.gitee.io/drissionpage')
# print(5)
from DrissionPage import WebPage,ChromiumOptions



# 指定s模式创建对象
page = WebPage(chromium_options=ChromiumOptions().set_local_port(9222).use_system_user_path())
page.get('http://g1879.gitee.io/drissionpage')
