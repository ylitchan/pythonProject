import re

from DrissionPage import SessionPage

# page = SessionPage()
# page.get('http://g1879.gitee.io/drissionpage')
# print(5)

# 导入 ChromiumOptions
from DrissionPage import ChromiumPage, ChromiumOptions
from openpyxl import Workbook, load_workbook

# 打开 Excel 文件
workbook = load_workbook('D:\pythonProject\drissionDemo\https___www.google.com.hk_maps (8).xlsx')

# 获取第一个工作表
sheet1 = workbook.active

# 获取第一列的数据
column_data = [cell.value for cell in sheet1['A']]
# 创建一个新的工作簿
sheet = workbook.create_sheet(title='Sheet2')
sheet.append(['类型', '图片', '地址', 'plus code', '所在', '电话', '简体名称', '繁体名称', '网站', '邮编', '经纬度'])
item = {}
# 创建浏览器配置对象，指定浏览器路径
co = ChromiumOptions().set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
# 用该配置创建页面对象
page = ChromiumPage(addr_or_opts=co)
# column_data = [
#     'https://www.google.com.hk/maps/place/%E9%BB%8E%E6%98%8E%E4%BD%93%E8%83%BD%E8%BF%90%E5%8A%A8%E4%B8%AD%E5%BF%83/data=!4m7!3m6!1s0x34693de87a0fa7b3:0x1d678c97d9205ff2!8m2!3d24.1547268!4d120.6319111!16s%2Fg%2F11g8bvtxxg!19sChIJs6cPeug9aTQR8l8g2ZeMZx0?authuser=0&hl=zh-CN&rclk=1',
#     'https://www.google.com.hk/maps/place/%E7%BB%BC%E5%90%88%E4%BD%93%E8%82%B2%E9%A6%86%E6%9A%A8%E5%AD%A6%E7%94%9F%E6%B4%BB%E5%8A%A8%E4%B8%AD%E5%BF%83/data=!4m7!3m6!1s0x34681bfa06fa77e5:0x521ad352b223e858!8m2!3d24.9401357!4d121.3658833!16s%2Fg%2F11gbzcdspp!19sChIJ5Xf6BvobaDQRWOgjslLTGlI?authuser=0&hl=zh-CN&rclk=1',
#     'https://www.google.com.hk/maps/place/%E5%BC%B9%E8%B7%B3%E8%BF%90%E5%8A%A8%E4%B8%AD%E5%BF%83/data=!4m7!3m6!1s0x34693ddbfd077de9:0x4d2420fbd8a855bf!8m2!3d24.1480988!4d120.6258591!16s%2Fg%2F11c7p4w8w_!19sChIJ6X0H_ds9aTQRv1Wo2PsgJE0?authuser=0&hl=zh-CN&rclk=1']
for url in column_data:
    try:
        page.get(url)
        item["title"] = page.ele('.DUwDvf lfPIob').text
        title2 = page.ele('.bwoZTb ')
        item["title2"] = title2.text if title2 else ''
        item["img"] = page.ele('.RZ66Rb FgCUCc').ele('tag:img').attrs.get('src')
        cate = page.ele('.DkEaL ')
        item["cate"] = cate.text if cate else ''
        # if '机场' not in item['cate']:
        #     continue
        for i in page.eles('.AeaXub'):
            if '' in i.text:
                loc = ' ' + i.ele('.Io6YTe fontBodyMedium kR99db ').text
                yb = re.search(r'\s\d{3,}', loc)
                item['yb'] = yb.group().strip() if yb else ''
                item["loc"] = loc.replace(item['yb'], '').strip()
            elif '' in i.text:
                item["web"] = i.ele('.Io6YTe fontBodyMedium kR99db ').text
            elif '' in i.text:
                item["tele"] = i.ele('.Io6YTe fontBodyMedium kR99db ').text
            elif '' in i.text:
                site = i.ele('.Io6YTe fontBodyMedium kR99db ').text.split(' ', 1)
                item['plus_code'] = site[0]
                item["site"] = site[-1]
        item['zb'] = ','.join(re.search('@.*?/', page.url).group()[1:].split(',')[:-1])
        print(item)
        # 定义要写入的列表数据
        # data = [[] for i in sorted(item.keys())]

        sheet.append([item.get(i, '') for i in
                      sorted(['title', 'title2', 'img', 'cate', 'yb', 'loc', 'web', 'tele', 'plus_code', 'site'])])
    except:
        print('失败', url)
        continue
# # 逐行写入数据
# for row in data:
#     sheet.append(row)
# 保存工作簿
workbook.save('供油.xlsx')
