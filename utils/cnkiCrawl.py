import json
import os
import random
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from jsonpath_ng import parse
from scrapy import Selector

thread_pool = ThreadPoolExecutor(max_workers=1)
# 创建一个会话
session = requests.Session()

# 设置最大重定向次数为 1
session.max_redirects = 1
headers2 = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'sec-ch-ua': "\"Chromium\";v=\"121\", \"Not A(Brand\";v=\"99\"",
    'sec-ch-ua-mobile': "?0",
    'sec-ch-ua-platform': "\"Windows\"",
    'DNT': "1",
    'Upgrade-Insecure-Requests': "1",
    'Sec-Fetch-Site': "same-site",
    'Sec-Fetch-Mode': "navigate",
    'Sec-Fetch-User': "?1",
    'Sec-Fetch-Dest': "document",
    'Referer': "https://kns.cnki.net/",
    'Accept-Language': "zh-CN,zh;q=0.9",
    'Cookie': """zkUserIp=39d66212-5b57-4d90-bc7e-5f6bd5464ad3; Ecp_ClientId=h241023104800363446; Ecp_loginuserjf=17880356481; Ecp_loginuserbk=sh0266; Ecp_ClientIp=117.30.59.151; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22194690a4932765-0ebde91a9e4e3d8-4c657b58-1327104-194690a493314e7%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22%24device_id%22%3A%22194690a4932765-0ebde91a9e4e3d8-4c657b58-1327104-194690a493314e7%22%7D; _c_WBKFRo=HpA2B1ir3pILZdltbCCPR1pMsuuBzVNqbIrAfCGx; Hm_lvt_dcec09ba2227fd02c55623c1bb82776a=1738723907,1738726158,1738735754; tfstk=gdNmE6_PU-kb2gEpDulfdp8E5QW8GEGscldtXfnNU0oSMAnY7c2g0oDZBZiTqGqaqI3ZgtMZ7oEs6-hVhAmaRPQbMcFgFC4Q5SQj6ZGblfGNvMCKsraj1x7LhyFia4usW1d2_xljazEMNmfd9ra49U2g06Fx-16imclZ3C5ra0g9gqrwgU7o7VK2QIrazamSWhJw3Voyz20pQflabz7oR0oZQyWqc5PzagAlemBYrK_ipxmUu0AHP70VTD1I4CP8NqkDhznlSNVooxmnF2j_GSr87SFjFT9-1ze3jRrF2Kn4K2qop-jHikqj7ucYTN6jFAPgs4w5jdm3QreQQYbVgzcmmAP84epSiRrbsxwD5warguwIAxW5V4VY9AmIE3S4yzmqKRqAVCoYKzrop7KJ9XyQq5DETg5pUpoX9CgPW7J6CxuSrDhKHCIIiUI06abkLNMqPqidrav6CxuSrDQlrp5s34gjv; SID_kns_new=kns2618109; ASP.NET_SessionId=pcjh2idv2x01aalvmnbfdceq; SID_kxreader_new=27019032; aams-security={"UserIp":"10.21.0.50","Version":"1.0.0.1","AppId":"KNS_BASIC_READ","DebugMode":false,"CreateTime":"20250207175205"}; SID_nzkhtml=019214; SID_restapi=018109; knsadv-searchtype=%7B%22BLZOG7CK%22%3A%22gradeSearch%2CmajorSearch%22%2C%22MPMFIG1A%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22T2VC03OH%22%3A%22gradeSearch%2CmajorSearch%22%2C%22JQIRZIYA%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22S81HNSV3%22%3A%22gradeSearch%22%2C%22YSTT4HG0%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22ML4DRIDX%22%3A%22gradeSearch%2CmajorSearch%22%2C%22WQ0UVIAA%22%3A%22gradeSearch%2CmajorSearch%22%2C%22VUDIXAIY%22%3A%22gradeSearch%2CmajorSearch%22%2C%22NN3FJMUV%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22LSTPFY1C%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22HHCPM1F8%22%3A%22gradeSearch%2CmajorSearch%22%2C%22OORPU5FE%22%3A%22gradeSearch%2CmajorSearch%22%2C%22WD0FTY92%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22BPBAFJ5S%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22EMRPGLPA%22%3A%22gradeSearch%2CmajorSearch%22%2C%22PWFIRAGL%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22U8J8LYLV%22%3A%22gradeSearch%2CmajorSearch%22%2C%22R79MZMCB%22%3A%22gradeSearch%22%2C%22J708GVCE%22%3A%22gradeSearch%2CmajorSearch%22%2C%22HR1YT1Z9%22%3A%22gradeSearch%2CmajorSearch%22%2C%22JUP3MUPD%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22NLBO1Z6R%22%3A%22gradeSearch%2CmajorSearch%22%2C%22RMJLXHZ3%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%221UR4K4HZ%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22NB3BWEHK%22%3A%22gradeSearch%2CmajorSearch%22%2C%22XVLO76FD%22%3A%22gradeSearch%2CmajorSearch%22%7D; SID_sug=018110; LID=WEEvREcwSlJHSldSdmVpZ0doOFdUdGJvK1RweWtoTGtzK3FvQkZIS2w3UT0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!; Ecp_LoginStuts={"IsAutoLogin":false,"UserName":"sh0266","ShowName":"%E5%8E%A6%E9%97%A8%E5%A4%A7%E5%AD%A6","UserType":"bk","BShowName":"","r":"qwkNYT","Members":[]}; Ecp_session=1; dblang=both; c_m_LinID=LinID=WEEvREcwSlJHSldSdmVpZ0doOFdUdGJvK1RweWtoTGtzK3FvQkZIS2w3UT0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!&ot=03%2F09%2F2025%2017%3A54%3A45; c_m_expire=2025-03-09%2017%3A54%3A45"""
}
headers1 = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'sec-ch-ua': "\"Chromium\";v=\"121\", \"Not A(Brand\";v=\"99\"",
    'sec-ch-ua-mobile': "?0",
    'sec-ch-ua-platform': "\"Windows\"",
    'DNT': "1",
    'Upgrade-Insecure-Requests': "1",
    'Sec-Fetch-Site': "same-site",
    'Sec-Fetch-Mode': "navigate",
    'Sec-Fetch-User': "?1",
    'Sec-Fetch-Dest': "document",
    'Referer': "https://kns.cnki.net/",
    'Accept-Language': "zh-CN,zh;q=0.9",
    'Cookie': """zkUserIp=41dc8551-0049-4230-b75b-eddd811dd8af; Ecp_ClientId=c241230160600943557; LID=WEEvREcwSlJHSldSdmVpbisvY2UzTUo1S0NpWGVTUG83K1VSVjB2VldjST0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!; Ecp_loginuserbk=sh0266; Ecp_ClientIp=27.154.88.131; cnkiUserKey=7ff07d27-5836-4437-8b43-903e8ff55724; _c_WBKFRo=AefjVIHlHLatJHL9qMwhTHXraz0sCXTFaEQf6sey; Ecp_loginuserjf=17880356481; Ecp_LoginStuts={"IsAutoLogin":true,"UserName":"sh0266","ShowName":"%E5%8E%A6%E9%97%A8%E5%A4%A7%E5%AD%A6","UserType":"bk","BUserName":"","BShowName":"","BUserType":"","r":"S7sBTF","Members":[]}; SID_nzkhtml=019214; SID_nzkpic=019164; ASP.NET_SessionId=ibcmowceosnbrfb4t4wfycv2; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219467fe2f74327-0f8e26e8c0b84a8-3e3b7b03-1327104-19467fe2f75f02%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219467fe2f74327-0f8e26e8c0b84a8-3e3b7b03-1327104-19467fe2f75f02%22%7D; Ecp_session=1; SID_sug=018109; SID_kns_new=kns2618132; knsadv-searchtype=%7B%22BLZOG7CK%22%3A%22gradeSearch%2CmajorSearch%22%2C%22MPMFIG1A%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22T2VC03OH%22%3A%22gradeSearch%2CmajorSearch%22%2C%22JQIRZIYA%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22S81HNSV3%22%3A%22gradeSearch%22%2C%22YSTT4HG0%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22ML4DRIDX%22%3A%22gradeSearch%2CmajorSearch%22%2C%22WQ0UVIAA%22%3A%22gradeSearch%2CmajorSearch%22%2C%22VUDIXAIY%22%3A%22gradeSearch%2CmajorSearch%22%2C%22NN3FJMUV%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22LSTPFY1C%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22HHCPM1F8%22%3A%22gradeSearch%2CmajorSearch%22%2C%22OORPU5FE%22%3A%22gradeSearch%2CmajorSearch%22%2C%22WD0FTY92%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22BPBAFJ5S%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22EMRPGLPA%22%3A%22gradeSearch%2CmajorSearch%22%2C%22PWFIRAGL%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22U8J8LYLV%22%3A%22gradeSearch%2CmajorSearch%22%2C%22R79MZMCB%22%3A%22gradeSearch%22%2C%22J708GVCE%22%3A%22gradeSearch%2CmajorSearch%22%2C%22HR1YT1Z9%22%3A%22gradeSearch%2CmajorSearch%22%2C%22JUP3MUPD%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22NLBO1Z6R%22%3A%22gradeSearch%2CmajorSearch%22%2C%22RMJLXHZ3%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%221UR4K4HZ%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22NB3BWEHK%22%3A%22gradeSearch%2CmajorSearch%22%2C%22XVLO76FD%22%3A%22gradeSearch%2CmajorSearch%22%7D; dblang=both; Hm_lvt_dcec09ba2227fd02c55623c1bb82776a=1736911280,1738835855; Hm_lpvt_dcec09ba2227fd02c55623c1bb82776a=1738835855; HMACCOUNT=FF4678F7964BAE91; SID_restapi=018133; c_m_LinID=LinID=WEEvREcwSlJHSldSdmVpbisvY2UzTUo1S0NpWGVTUG83K1VSVjB2VldjST0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!&ot=02%2F14%2F2025%2011%3A52%3A13; c_m_expire=2025-02-14%2011%3A52%3A13; SID_kxreader_new=27017040; aams-security={"UserIp":"10.21.0.50","Version":"1.0.0.1","AppId":"KNS_BASIC_READ","DebugMode":false,"CreateTime":"20250206175741"}; tfstk=gnMiH8teTfP6yv3RW2y6N1EerGOLCGwb5qBYk-U2TyzQBSUt0rcm7VV4Mhax-E0q-OE4QCN40V3bHfew1S4qVmKsBrHmOtmScAK_Hhwsf-w2yUp8nci_hzw-L6YKYnrbnlR91ygsf-w2JIN667nszUuhxfy2xJr_coy4gP7exuqY3OPVQ67URoy43PrqY9ruqs5N3O-nYyZ43ru43bR2_PMqLv8hhQfZ0cgSKlVgzcA53tDhe54rbyX2zvqMnzoa-tW0WAME9Dm9STiLCY3u2VpFI4mqVjPnnw8ulvmEQjoCSErIgVeUW8RNxRHsbbPqUE1qrR00aAPh0Tosbyw3YY-ANyH3WqkgT3BuMJk8aRlpOFFYIu0qCVjc34oK2ANInUbUlfE7LoDX4s40gg8VT_zZutZeDv5fG5rQxze50s6VPa9U6HxhanNaAlaJxHffG5rQxzKHx_Jb_kZ_y"""
}

url = "https://kns.cnki.net/kns8s/brief/grid"
headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'sec-ch-ua-platform': "\"Windows\"",
    'X-Requested-With': "XMLHttpRequest",
    'sec-ch-ua': "\"Microsoft Edge\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
    'sec-ch-ua-mobile': "?0",
    'Sec-Fetch-Site': "same-origin",
    'Sec-Fetch-Mode': "cors",
    'Sec-Fetch-Dest': "empty",
    'Referer': "https://kns.cnki.net/kcms2/article/abstract?v=Mw9fkKjKljqYeQJU_e7DiCOew6sspHitjX8XExsAcVyuzSnv9qeLvU5w2aa0nXbgCHc1OtgXxYwul9ipBI9mcQqWcdFD2MwpIaY3QPsFDWhOUJnNsP6EijFtgFqI_Rdxy-UvOolWOd_fbTDElmnX3zwU7kZLhLuTn4qblZaPU-1IqEkze8HanBL31-BqxtzH&uniplatform=NZKPT&language=CHS",
    'Accept-Language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    'dnt': "1",
    'sec-gpc': "1",
    'Cookie': "Ecp_notFirstLogin=uxqONI; Ecp_ClientId=h241023104800363446; Ecp_loginuserjf=17880356481; SID_sug=018131; Ecp_loginuserbk=sh0266; SID_kns_new=kns2618133; knsLeftGroupSelectItem=; SID_restapi=018132; Ecp_ClientIp=117.30.59.151; showlists=YSTT4HG0%2CLSTPFY1C%2CJUP3MUPD%2CMPMFIG1A%2CEMRPGLPA%2CWQ0UVIAA%2CBLZOG7CK%2CPWFIRAGL%2CNN3FJMUV%2CNLBO1Z6R%2C1735194583068; dSearchFolds=true; dsorders=FFD; dmaxgroups=100; LID=WEEvREcwSlJHSldSdmVpa3VEcjFad09zbmtKeGo3WWpwdzNDZWJjaDhyYz0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!; Ecp_LoginStuts={\"IsAutoLogin\":false,\"UserName\":\"sh0266\",\"ShowName\":\"%E5%8E%A6%E9%97%A8%E5%A4%A7%E5%AD%A6\",\"UserType\":\"bk\",\"BShowName\":\"\",\"r\":\"uxqONI\",\"Members\":[]}; Ecp_session=1; knsadv-searchtype=%7B%22BLZOG7CK%22%3A%22gradeSearch%2CmajorSearch%22%2C%22MPMFIG1A%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22T2VC03OH%22%3A%22gradeSearch%2CmajorSearch%22%2C%22JQIRZIYA%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22S81HNSV3%22%3A%22gradeSearch%22%2C%22YSTT4HG0%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22ML4DRIDX%22%3A%22gradeSearch%2CmajorSearch%22%2C%22WQ0UVIAA%22%3A%22gradeSearch%2CmajorSearch%22%2C%22VUDIXAIY%22%3A%22gradeSearch%2CmajorSearch%22%2C%22NN3FJMUV%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22LSTPFY1C%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22HHCPM1F8%22%3A%22gradeSearch%2CmajorSearch%22%2C%22OORPU5FE%22%3A%22gradeSearch%2CmajorSearch%22%2C%22WD0FTY92%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22BPBAFJ5S%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22EMRPGLPA%22%3A%22gradeSearch%2CmajorSearch%22%2C%22PWFIRAGL%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%22U8J8LYLV%22%3A%22gradeSearch%2CmajorSearch%22%2C%22R79MZMCB%22%3A%22gradeSearch%22%2C%22J708GVCE%22%3A%22gradeSearch%2CmajorSearch%22%2C%22HR1YT1Z9%22%3A%22gradeSearch%2CmajorSearch%22%2C%22JUP3MUPD%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22NLBO1Z6R%22%3A%22gradeSearch%2CmajorSearch%22%2C%22RMJLXHZ3%22%3A%22gradeSearch%2CmajorSearch%2CsentenceSearch%22%2C%221UR4K4HZ%22%3A%22gradeSearch%2CmajorSearch%2CauthorSearch%2CsentenceSearch%22%2C%22NB3BWEHK%22%3A%22gradeSearch%2CmajorSearch%22%2C%22XVLO76FD%22%3A%22gradeSearch%2CmajorSearch%22%7D; dblang=both; c_m_LinID=LinID=WEEvREcwSlJHSldSdmVpa3VEcjFad09zbmtKeGo3WWpwdzNDZWJjaDhyYz0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!&ot=01%2F26%2F2025%2009%3A36%3A30; c_m_expire=2025-01-26%2009%3A36%3A30; tfstk=g_XZ3oxpfRewcrIPRTvqUsR8lp99hKzWItTXmijDfFYG5iTcTZbBCGsccx-D-NB61FOc8KSVqG61llQe3ZSxhnNTWnmOLakjCPFOmxJXnza7F8sOfKp0PFtNozY9DMY0ACm63U9Hnza7dmpBHjJc5I1YkySHJnumofbDtpxy-fcGoFAn-3-JnKvcoHAHDh-mIhvmt2YpmKYcoKqeKeKqaA8DPv-ysojIvTAz3IOwrGYEUDBejncOjeuZ79kW_UD28xDcLhjBxCHrUSTlwFOWyw2IQKSH0wR5_zkNuijRiBWqSl_lmNBeBLPbXQ5hO_ONTPD2ROt2ZKAEmxjeLeQPdL2o8HChfsXO7mkDXO6WgUdUmxdXKTOlZNoY2MvMmZdRhzH9SijRe_9zQ4KNtgJF4xuvxpGdH1umgCxpYUZUYmqIRw8nyFWEMjdO9H87XlhxMCxpYUZUYjhv6pKePlEO."
}
k = {
    # '无人平台': ['无人机', '无人车', '无人艇', '无人潜航器', '无人船只', 'UAV', 'UGV', 'UUV', 'USV',
    #              'Unmanned Aerial Vehicle', 'Unmanned Ground Vehicle', 'Unmanned Underwater Vehicle',
    #              'Unmanned Surface Vehicle', 'Unmanned vessels'],
    '军事智能': [
        # '军事人工智能', '军事智能网络分析', '军事自主决策', '作战自主导航', '战场大数据分析与云计算',
        #          '网络空间作战技术', '战场仿真与虚拟现实技术', '军事智能指挥控制系统', '战场模拟', '反蜂群',
        #          '反卫星', '反隐形战机', 'Anti-swarm', 'anti-satelliteanti-submarine', 'anti-stealth fighter',
        #          'Military Artificial',
        # 'Military Intelligence',
        # 'Military Autonomous',
        # 'Operational Autonomous Navigation', 'Cyber Warfare Technology',
        # 'Battlefield Modeling'
    ],
    '战场通信': [
        # '军事通信', '作战通信',
        '战场通信', '战场无线电', '战场短波', '战场超短波', '战场微波',
        '战场卫星通信', '战场网络通信', '战场有线通信', '战场水下通信', '电子战', '电子战与干扰',
        'Military Communications', 'Battlefield Communications', 'Battlefield Satellite Communications',
        'Battlefield Network Communications', 'Battlefield Wired Communications',
        'Battlefield Underwater Communications', 'C4ISR', 'Battlefield Networking', 'Electronic Warfare']
    , '探测感知': ['战场探测感知', '水下声学探测', '军事传感器', '战场检测', '雷达', '声纳', '军事红外传感器',
                   '电子干扰', '战场光电探测', '作战卫星侦察', '电子战', 'Battlefield Detection and Sensing',
                   'Military Sensors', 'Battlefield Surveillance', 'Radar  Naval', 'Sonar',
                   'Military Infrared Sensors', 'Electronic Warfare and Jamming',
                   'Battlefield Electro-Optical Detection', 'Operational Satellite Reconnaissance',
                   'Maritime Surveillance', 'Underwater Acoustic Detection']
    , '海上兵力投送': ['海上兵力投送', '海上运输', '航空母舰', '驱逐舰', '巡洋舰', '护卫舰', '潜艇', '两栖作战',
                       '两栖攻击舰', '登陆舰艇', '空中投送', '海军航空力量', '舰载飞机', '直升机', '支援舰艇',
                       '补给舰', 'Aircraft carrier', 'sea cruiser', 'sea frigate', 'Amphibious assault ships',
                       ' landing ships', ' combat helicopters', 'Logistics and support ships', 'Supply ship',
                       'Warships', 'Naval vessels', 'submarine', 'Naval Ship'],
    # '海战武器装备': [
    #     '海战武器系统', '舰炮', '导弹', '鱼雷', '反潜武器', '反潜火箭深弹',
    #     '反潜直升机','反潜无人机','水雷','激光武器','激光炮', '防空激光武器','电磁炮',
    #     '高超声速武器','高超声速导弹', '粒子束武器', '网络武器',
    #     '生物武器', 'Naval gun', 'Missile', 'torpedo Antisubmarine', 'Anti-submarine rocket deep bomb',
    #     'Antisubmarine helicopter', 'Antisubmarine UAV',
    #     'Mine weapon', 'laser weapon', 'Electromagnetic Cannon ', 'EM Cannon',
    #     ' Railgun', 'Hypersonic Weapon', 'Particle Beam Weapon',
    #     'Cyber Weapon', '高超声速导弹',
    #     '高超声速滑翔弹头',
    #     'HGV',
    #     '高超声速巡航导弹', 'HCM', '高超声速战术导弹',
    #     '高超声速反舰导弹', '高超声速战术弹头', 'Hypersonic Glide Vehicle',
    #     'Hypersonic Cruise Missile', 'Hypersonic  Missile', 'Hypersonic Anti-Ship Missile',
    #     'Hypersonic Tactical Warhead', 'hypersonic', ' glide missile；cruise missile',
    #     'hypersonic aircraft',
    #     '新概念武器', '定向能武器',
    #     'Directed Energy Weapons', '激光武器',
    #     '固态激光武器',
    #     'Solid-State Laser Weapons',
    #     '气体激光武器 ', 'Gas Laser Weapons',
    #     '光纤激光武器 ',
    #     'Fiber Laser Weapons',
    #     '自由电子激光 ',
    #     'Free Electron Laser', '便携式激光武器',
    #     'Portable Laser Weapons', '高能激光武器 ', 'High-Energy Laser Weapons', '微波武器',
    #     '电磁武器',
    #     'Electromagnetic Weapons', '电磁炮', '电磁脉冲武器', 'EMP',
    #     '生物武器 ', 'Bioweapons',
    #     '纳米武器', 'Nanoweapons', '量子武器', 'Quantum Weapons', '机载激光武器', '舰载激光武器',
    #     '激光武器', '固态激光武器', 'Solid-State Laser Weapons',
    #     '气体激光武器 ', 'Gas Laser Weapons', '光纤激光武器 ', 'Fiber Laser Weapons',
    #     '化学激光武器 ',
    #     'Chemical Laser Weapons', '自由电子激光 ', 'Free Electron Laser', '便携式激光武器',
    #     'Portable Laser Weapons', '高能激光武器 ', 'High-Energy Laser Weapons', 'Laser Weapons']
}
h = 1
hh = 1
for k, v in k.items():
    for vv in v:
        pageNext = '1'
        while pageNext:
            print('翻页请求头', h)
            if h == 1:
                session.headers = headers1
                h = 2
            else:
                session.headers = headers2
                h = 1
            print('当前页码', k, vv, pageNext)
            payload = {
                'boolSearch': "true",
                'QueryJson': "{\"Platform\":\"\",\"Resource\":\"JOURNAL\",\"Classid\":\"YSTT4HG0\",\"Products\":\"\",\"QNode\":{\"QGroup\":[{\"Key\":\"Subject\",\"Title\":\"\",\"Logic\":0,\"Items\":[],\"ChildItems\":[{\"Key\":\"input[data-tipid=gradetxt-1]\",\"Title\":\"关键词\",\"Logic\":0,\"Items\":[{\"Key\":\"input[data-tipid=gradetxt-1]\",\"Title\":\"关键词\",\"Logic\":0,\"Field\":\"KY\",\"Operator\":\"FUZZY\",\"Value\":\"无人机\",\"Value2\":\"\"}],\"ChildItems\":[]}]},{\"Key\":\"ControlGroup\",\"Title\":\"\",\"Logic\":0,\"Items\":[],\"ChildItems\":[{\"Key\":\".tit-startend-yearbox\",\"Title\":\"\",\"Logic\":0,\"Items\":[{\"Key\":\".tit-startend-yearbox\",\"Title\":\"出版年度\",\"Logic\":0,\"Field\":\"YE\",\"Operator\":7,\"Value\":\"2010\",\"Value2\":\"2025\"}],\"ChildItems\":[]}]}]},\"ExScope\":\"1\",\"SearchType\":1,\"Rlang\":\"CHINESE\",\"KuaKuCode\":\"\",\"View\":\"changeDBCh\",\"SearchFrom\":1}".replace(
                    '无人机', vv),
                'pageNum': pageNext,
                'pageSize': "20",
                'sortField': "FFD",
                'sortType': "DESC",
                'dstyle': "listmode",
                'boolSortSearch': "false",
                'aside': f"（关键词：{vv}(模糊)）",
                'searchFrom': "资源范围：学术期刊;  中英文扩展;  时间范围：出版年度：2010 到 2025,更新时间：不限;  来源类别：全部期刊; ",
                # 'CurPage': "1"
            }
            while 1:
                try:
                    response = session.post(url, data=payload)
                    break
                except:
                    traceback.print_exc()
                    continue
            selector = Selector(text=response.text)
            list_data = selector.xpath('//table[@class="result-table-list"]//tbody//tr')
            for e in list_data:
                print('文章请求头', hh)
                if hh == 1:
                    session.headers = headers1
                    hh = 2
                else:
                    session.headers = headers2
                    hh = 1
                data_dir = f'./军事智能/技术预见/论文/{k}/'
                item = {'ORIGINAL_CITATIONS'.lower(): [], 'original_labels': [k, vv, '论文', '技术预见'],
                        'article_url': e.xpath('.//td[@class="name"]//@href').get()}
                res = session.get(item['article_url'])
                while isinstance(res, str) or '系统检测到您的访问行为异常，请帮助我们完成' in res.text:
                    try:
                        print('系统检测到您的访问行为异常，请帮助我们完成')
                        res = session.get(item['article_url'])
                        v_value = Selector(text=res.text).xpath('//*[@id="v-value"]/@value').get()
                        print(v_value)
                        url_new = session.get(f'https://kns.cnki.net/kcms2/newLink?v={v_value}').text
                        res = session.get(url_new)
                    except:
                        traceback.print_exc()
                        continue
                bar_url = Selector(text=res.text).xpath('//li[@class="btn-html" and not(@style)]//@href').get()
                if not bar_url or Selector(text=res.text).xpath('//span[@class="sign"]').get():
                    # time.sleep(random.randint(5, 10) * 60)
                    continue
                if bar_url:
                    res = session.get(bar_url, allow_redirects=False)
                    if '%E5%AF%B9%E4%B8%8D%E8%B5%B7%EF%BC%8C%E6%9C%AC%E5%88%8A%E5%8F%AA%E6%94%B6%E5%BD%95%E9%A2%98%E5%BD%95%E4%BF%A1%E6%81%AF%EF%BC%8C%E6%9A%82%E4%B8%8D%E6%8F%90%E4%BE%9B%E5%8E%9F%E6%96%87%E4%B8%8B%E8%BD%BD%E3%80%82%E7%BB%99%E6%82%A8%E9%80%A0%E6%88%90%E4%B8%8D%E4%BE%BF%E8%AF%B7%E8%B0%85%E8%A7%A3%EF%BC%81' in dict(
                            res.headers).get('location'):
                        continue
                    while res.status_code == 302:
                        url302 = dict(res.headers).get('location')
                        if 'https://bar.cnki.net/bar/verify/index.html?' in url302 or 'ErrorMsg.html?' in url302 and '%E5%AF%B9%E4%B8%8D%E8%B5%B7%EF%BC%8C%E6%9C%AC%E5%88%8A%E5%8F%AA%E6%94%B6%E5%BD%95%E9%A2%98%E5%BD%95%E4%BF%A1%E6%81%AF%EF%BC%8C%E6%9A%82%E4%B8%8D%E6%8F%90%E4%BE%9B%E5%8E%9F%E6%96%87%E4%B8%8B%E8%BD%BD%E3%80%82%E7%BB%99%E6%82%A8%E9%80%A0%E6%88%90%E4%B8%8D%E4%BE%BF%E8%AF%B7%E8%B0%85%E8%A7%A3%EF%BC%81' not in url302:
                            print('需要验证', k, vv, pageNext, item['article_url'])
                            if hh == 1:
                                session.headers = headers1
                                hh = 2
                            else:
                                session.headers = headers2
                                hh = 1
                            time.sleep(random.randint(3, 6) * 60)
                            res = session.get(bar_url, allow_redirects=False)
                        else:
                            res = session.get(urljoin(res.url, url302), allow_redirects=False)
                    info_url = res.url.replace('https://kns.cnki.net/nzkhtml/xmlRead/trialRead.html?',
                                               'https://kns.cnki.net/nzkhtml/knsread/litNotes/getPaperInfo?')
                    try:
                        response = session.get(info_url)
                        info = response.json()['content']
                        tiluinfo = info['tiluInfo']
                        item['article_type'] = '论文'
                        item['country'] = '中国'
                        item['doi'] = tiluinfo['doi']
                        item['keywords'] = info['keywords']
                        item['original_keywords'] = info['englishKeywords']
                        item['original_authors_name'] = '，'.join(
                            [a['personinfo']['fullName'] or '' for a in info['authors']])
                        catalogInfos = '\n'.join(
                            [f"{c.get('cataTitle', '')}\n{c.get('content', '')}" for c in info.get('catalogInfos', [])])
                        content = info['content'] + catalogInfos
                        selector = Selector(text=content)
                        dbCode = tiluinfo['dbCode']
                        fileCode = tiluinfo['fileCode']
                        image_base = f'https://kns.cnki.net/nzkhtml/resource/{dbCode}/{fileCode}/images/'
                        image_address = set()
                        item['original_title_translate'] = tiluinfo['title']
                        item['original_title'] = info['englishTitle']
                        data_dir = data_dir + re.sub(r'[\\/*?:"<>|]', '', item['original_title_translate'])
                        if not os.path.exists(data_dir):
                            os.makedirs(data_dir)
                        content = content.replace('data-src="', 'src="')
                        for datasrc in selector.xpath('//@data-src').getall():
                            image_url = image_base + datasrc
                            r = requests.get(image_url, stream=True)
                            with open(data_dir + f'/{datasrc}', 'wb') as f:
                                for chunk in r.iter_content(chunk_size=1024):
                                    if chunk:
                                        f.write(chunk)
                            image_url = f'/fs.collection-platform.com/utenet/report/cnki/{(tiluinfo["postTime"] or "").replace("-", "/")}//' + datasrc
                            image_address.add(image_url)
                            content = content.replace(datasrc, image_url)
                        item['image_address'] = list(image_address)
                        # selector = Selector(text=content)
                        # item['image_address'] = [image_base + datasrc for datasrc in selector.xpath('//@data-src').getall()]
                        item['original_content'] = content
                        item['original_content_translate'] = content
                        item['original_institution'] = list(
                            {a['organizationInfos'][0]['organizationName'] for a in info['authors'] if
                             a['organizationInfos']})
                        item['original_journal'] = tiluinfo['source']
                        # item['original_labels'] = ['论文', '技术预见', ] + (info['keywords'] or [])
                        item['original_references'] = [b['title'][3:] for b in info['bibliography']]
                        item['original_summary'] = tiluinfo['summary']
                        item['original_summary_translate'] = tiluinfo['summary']

                        item['report_time'] = tiluinfo["postTime"] or ''
                        item['year'] = item['report_time'][:4]
                        paperid = item['article_url'].split('?', 1)[-1].split('&')[0]
                        api_r = {
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CJFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CDFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CMFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CPFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=IPFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CYFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CCNDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=WWJDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=CBBDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=SCPDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=SCSDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/references?{paperid}&type=NLNKREF&': 0,
                        }
                        api_c = {
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=CDFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=CMFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=CPFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=IPFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=CYFDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=CCNDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=WWJDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=CBBDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=SCPDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=SCSDREF&': 0,
                            f'https://kns.cnki.net/restapi/citation-api/v1/literature/citations?{paperid}&type=NLNKREF&': 0,
                        }
                        us = f'https://kns.cnki.net/restapi/literature-api/v1/articles/relations/similar?{paperid}&uniplatform=NZKPT&'
                        # for ur in api_r:
                        #     while 1:
                        #         try:
                        #             print('rrrrrrrrrrrrrrrrrrrrrrrrrrrrr', ur)
                        #             res = requests.get(ur + 'start=1&size=10', headers=headers)
                        #             print(res.text)
                        #             res_json = res.json()
                        #             print('rrrrrrrrrrrrrrrrrrrrrrrrrrrrr', res_json)
                        #             tr = 0
                        #             if res_json.get('data', {}):  # .get('papers', []):
                        #                 tr = res_json.get('data', {}).get('total', 0)
                        #             api_r[ur] = tr
                        #             break
                        #         except Exception as e:
                        #             traceback.print_exc()
                        for uc in api_c:
                            while 1:
                                try:
                                    # print('cccccccccccccc', uc)
                                    res = requests.get(uc + 'start=1&size=10', headers=headers)
                                    res_json = res.json()
                                    # print('ccccccccccccccc', res_json)
                                    tc = 0
                                    if res_json.get('data', {}):  # .get('papers', []):
                                        tc = res_json.get('data', {}).get('total', 0)
                                    api_r[uc] = tc
                                    break
                                except Exception as e:
                                    traceback.print_exc()
                                # while 1:
                                #     try:
                                #         print('ssssssssss', us)
                                #         res = requests.get(us + 'start=1&size=10', headers=headers)
                                #         res_json = res.json()
                                #         ts = 0
                                #         if res_json.get('data', {}):  # .get('papers', []):
                                #             ts = res_json.get('data', {}).get('total', 1)
                                #         break
                                #     except Exception as e:
                                #         traceback.print_exc()
                                # PROXIES.update({'http://192.168.8.42:10505': {
                                #     "http": 'http://192.168.8.43:10502',
                                #     "https": 'http://192.168.8.43:10502'
                                # }, 'http://192.168.8.43:10502': {
                                #     "http": 'http://192.168.8.42:10505',
                                #     "https": 'http://192.168.8.42:10505'}}.pop(
                                #     response.meta.get('proxy', 'http://192.168.8.42:10505')))
                                pass


                        def chuli(ub, pb):
                            number = 0
                            references = []
                            while number < 5:
                                references.clear()
                                try:
                                    print('bbbbbbbbbbbbbb', item.get('ORIGINAL_TITLE'.lower()), ub)
                                    up = ub + f'&start={pb}&size=10'
                                    res = requests.get(up, headers=headers)
                                    res_json = res.json()
                                    if not (papers_p := res_json.get('data', {}).get('data', [])):
                                        return references
                                    for paper in papers_p:
                                        # print([ii.value for ii in parse('$..relations').find(paper)])
                                        reference = {'ORIGINAL_TITLE'.lower(): ''.join(
                                            [oan.get('value') for oan in parse('$..metadata').find(paper)[0].value if
                                             oan.get('name') == 'TI']),
                                            'ORIGINAL_AUTHORS_NAME'.lower(): '，'.join(
                                                [oan.value for oan in parse('$..authors..title').find(paper) if
                                                 oan.value]),
                                            'ORIGINAL_JOURNAL'.lower(): '，'.join(
                                                [oan.value for oan in parse('$..source..title').find(paper) if
                                                 oan.value]) if parse(
                                                '$..source').find(paper) else ''.join(
                                                [oan.get('value') for oan in parse('$..metadata').find(paper)[0].value
                                                 if
                                                 oan.get('name') == 'LY']),
                                            'ARTICLE_URL'.lower(): ''.join(
                                                [oan.get('url') for oan in parse('$..relations').find(paper)[0].value if
                                                 oan.get('scope') == 'ABSTRACT']) if parse('$..relations').find(
                                                paper) else ''}
                                        if 'literature-api' in up:
                                            reference['REPORT_TIME'.lower()] = ''.join(
                                                [oan.get('value') for oan in parse('$..metadata').find(paper)[0].value
                                                 if
                                                 oan.get('name') == 'PT'])
                                        references.append(reference)
                                    break
                                except:
                                    traceback.print_exc()
                                    # PROXIES.update({'http://192.168.8.42:10505': {
                                    #     "http": 'http://192.168.8.43:10502',
                                    #     "https": 'http://192.168.8.43:10502'
                                    # }, 'http://192.168.8.43:10502': {
                                    #     "http": 'http://192.168.8.42:10505',
                                    #     "https": 'http://192.168.8.42:10505'}}.pop(
                                    #     response.meta.get('proxy', 'http://192.168.8.42:10505')))
                                    pass
                                number += 1
                                # time.sleep(10)
                            return references


                        # if ts:
                        #     futures = [thread_pool.submit(chuli, us, ps) for ps in
                        #                range(1, 2)]
                        #     # 使用as_completed方法来获取已完成的任务
                        #     for future in as_completed(futures):
                        #         item['ORIGINAL_SIMILAR'.lower()].extend(future.result())
                        # for ur, tr in api_r.items():
                        #     if tr:
                        #         futures = [thread_pool.submit(chuli, ur, pr) for pr in
                        #                    range(1, int(tr / 10) + 2 if tr % 10 else int(tr / 10) + 1)]
                        #         # 使用as_completed方法来获取已完成的任务
                        #         for future in as_completed(futures):
                        #             item['ORIGINAL_REFERENCES'.lower()].extend(future.result())
                        for uc, tc in api_c.items():
                            if tc:
                                futures = [thread_pool.submit(chuli, uc, pc) for pc in
                                           range(1, int(tc / 10) + 2 if tc % 10 else int(tc / 10) + 1)]
                                # 使用as_completed方法来获取已完成的任务
                                for future in as_completed(futures):
                                    item['ORIGINAL_CITATIONS'.lower()].extend(future.result())
                        # except Exception as e:
                        #     traceback.print_exc()
                        print('已入库', k, vv, item['original_title_translate'])
                        with open(data_dir + f'/crawl_message.json', 'w', encoding='utf-8') as f:
                            json.dump(item, f, ensure_ascii=False, indent=4)
                            # time.sleep(random.randint(5, 10) * 60)
                    except:
                        traceback.print_exc()
                        print(pageNext, item['article_url'])
                        break
            pageNext = selector.xpath('//*[@id="PageNext"]/@data-curpage').get()
