# Scrapy settings for alphaPlan project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = 'alphaPlan'

SPIDER_MODULES = ['alphaPlan.spiders']
NEWSPIDER_MODULE = 'alphaPlan.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = 'alphaPlan (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
# CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 60
# The download delay setting will honor only one of:
# CONCURRENT_REQUESTS_PER_DOMAIN = 16
# CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {'authorization':'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA','x-twitter-auth-type':'OAuth2Session','x-csrf-token':'c6c670f526f6513757d6cb8d75fc544c708c025a01f39dc5fe85a09c7c9d7345abfb369a0b54e832c713619d9ac612e632e10d85615db8b7bc12b7e9f858b0c3b1e4827725918f18d30041ce60b99639','user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.54'}
# DEFAULT_REQUEST_HEADERS = {'authorization':'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA','x-twitter-auth-type':'OAuth2Session','x-csrf-token':'07e7120541046fff57dac4d71488037d9005f838efcb058e31cc3148157323836afbc8dd8e6929a310a26809cc13e87b93405b524af8552f33ebcbabd53e5a456ecefc7aea71c8b31b5490e0a288e5f9','user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.54'},


# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    'alphaPlan.middlewares.AlphaplanSpiderMiddleware': 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    'alphaPlan.middlewares.AlphaplanDownloaderMiddleware': 80,
    'alphaPlan.middlewares.RandomDelayMiddleware': 100,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
# EXTENSIONS = {
#    'scrapy.extensions.telnet.TelnetConsole': None,
# }

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    'alphaPlan.pipelines.AlphaplanPipeline': 300,
    # 'alphaPlan.pipelines.TweetPipeline': 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
# AUTOTHROTTLE_ENABLED = True
# The initial download delay
# AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = 'httpcache'
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'
HTTPERROR_ALLOW_ALL = True
# DOWNLOAD_TIMEOUT = 600
RETRY_ENABLED = True
RETRY_TIMES = 1
RETRY_ALL_HTTP_CODES = True
PROJECT_URL = 'http://localhost:6800/'
CLOSESPIDER_TIMEOUT = 900
LOG_LEVEL = 'ERROR'
ACCOUNT_LIST = [('dao_ust', '1639838455760035840', {
    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; kdt=YY5epcm5ePgzHpX3oXabVshhh27g18lEHMuYH7v4; _gid=GA1.2.1842052750.1687350267; dnt=1; auth_multi="1577862800952930305:1bedb7ef5487e0ca4faa75e233f94abf2b7e59eb|1573326306661793792:b8da11bc85168214fe4b0b6957cc318478a3a6e2"; auth_token=5503c671b8069c470766fdea2d66ba5fb9a86538; guest_id=v1%3A168735332699056847; ct0=e19897d7753735caf08114c7dddf607957a28df444b776c21a2b74b16100bd05790d7cdf5b6c32478aa17ed0eb87520b121e6c39235f656d71973706e3c270b64f7c888caee8ebd78b5d003f9ab97ae8; lang=zh-cn; twid=u%3D1568898000654680064; guest_id_marketing=v1%3A168735332699056847; guest_id_ads=v1%3A168735332699056847; personalization_id="v1_quUYBDnAEMLTiqebrNCQJQ=="',
    'X-Csrf-Token': 'e19897d7753735caf08114c7dddf607957a28df444b776c21a2b74b16100bd05790d7cdf5b6c32478aa17ed0eb87520b121e6c39235f656d71973706e3c270b64f7c888caee8ebd78b5d003f9ab97ae8'}),
                ('dao_ust2', '1667054883219083264', {
                    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                    'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; _gid=GA1.2.294164188.1687613031; gt=1672929356564557831; kdt=NM3A3BOWMx37GmPm0Z4Lhye1iVVcztVSlceYK2X6; lang=zh-cn; dnt=1; auth_multi="1121014957422907392:fb739a04e9f024dfa6860b837b9c437aaa93f0fa"; auth_token=450444b721eb21cfa581e4195ac7384545dd89cc; guest_id=v1%3A168769252221011498; ct0=1a3a1a3f3f3497d56d958b4363e1514dbfd5f90dd3cec4455a20d0223c656bfd9786b307c96508e2f85501c6c137ae9dab5cddf5f6b3655c6d3b11f72d39041376df5f2b01920c2b148c3389e8fc1bca; twid=u%3D1666748651618865153; guest_id_marketing=v1%3A168769252221011498; guest_id_ads=v1%3A168769252221011498; personalization_id="v1_BLq9lVhxG6JsQL5ss6yM5g=="',
                    'X-Csrf-Token': '1a3a1a3f3f3497d56d958b4363e1514dbfd5f90dd3cec4455a20d0223c656bfd9786b307c96508e2f85501c6c137ae9dab5cddf5f6b3655c6d3b11f72d39041376df5f2b01920c2b148c3389e8fc1bca'}),
                ('dao_ust3', '1646838020363153408', {
                    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                    'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; kdt=YY5epcm5ePgzHpX3oXabVshhh27g18lEHMuYH7v4; _gid=GA1.2.1842052750.1687350267; dnt=1; lang=zh-cn; auth_multi="1568898000654680064:5503c671b8069c470766fdea2d66ba5fb9a86538|1577862800952930305:1bedb7ef5487e0ca4faa75e233f94abf2b7e59eb|1573326306661793792:b8da11bc85168214fe4b0b6957cc318478a3a6e2"; auth_token=bc4e0b0e13059d5f73217d2e512963ab84d2b03c; guest_id=v1%3A168735792361821059; ct0=5f9cd12434705cc3270ebe333b8b3cfa6f4df1fbd15306751b4c853d4cfb650082da2b70ebecb3d60552549c151c4fa4d17a8ef20969692024ec5aeabc572bfc2e7a2634167d48c2347572bf87a20c54; twid=u%3D1121014957422907392; guest_id_marketing=v1%3A168735792361821059; guest_id_ads=v1%3A168735792361821059; personalization_id="v1_dhsI3gVYY2Bo9x07dcPgzg=="',
                    'X-Csrf-Token': '5f9cd12434705cc3270ebe333b8b3cfa6f4df1fbd15306751b4c853d4cfb650082da2b70ebecb3d60552549c151c4fa4d17a8ef20969692024ec5aeabc572bfc2e7a2634167d48c2347572bf87a20c54'}),
                # ('ISHTARider', '1644339127071162369', {
                #     'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                #     'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; _gid=GA1.2.294164188.1687613031; guest_id_marketing=v1%3A168829689465553665; guest_id_ads=v1%3A168829689465553665; guest_id=v1%3A168829689465553665; gt=1675464730205642752; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCJ1GVhaJAToMY3NyZl9p%250AZCIlYzBhZmI3MjQ3NTJmZDY3OWE0NTYyMjA1YTgxZmU1NTI6B2lkIiUzMjFk%250AMjhjZDY0NmM0ZDI3NzI2ZjgzMTllZDU0ZjNlMg%253D%253D--4ac0b57fcd27b2ca1cc8ad9d825d4d48b59027c9; kdt=zBtD6Bktgq2aIvUZf7xzrq6xlhuST6YV9ox6s3r7; auth_token=357750d608a5b780006fc29bfc81e82d78dc1331; ct0=5b71b50e51eb85faa15703e0b2e9764f99c8fe0a135380a23e63e21ddf414a16af6cc5bcf0cd1ef9b09c614d4436f5b3d96b4335491f86422178eb712ab0ce89063a22cf19272a0563f41b1444fc14c3; lang=en; twid=u%3D1577862800952930305; personalization_id="v1_PAeDOjqQBC3f1kFkSj6QkQ=="',
                #     'X-Csrf-Token': '5b71b50e51eb85faa15703e0b2e9764f99c8fe0a135380a23e63e21ddf414a16af6cc5bcf0cd1ef9b09c614d4436f5b3d96b4335491f86422178eb712ab0ce89063a22cf19272a0563f41b1444fc14c3'}),

                ]
LIST_LIST = [('ISHTARider', '1644339127071162369', {
    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'Cookie': '_ga=GA1.2.1016685455.1694920460; g_state={"i_l":4,"i_p":1702214923150}; guest_id_marketing=v1%3A170541168146988141; guest_id_ads=v1%3A170541168146988141; guest_id=v1%3A170541168146988141; gt=1747249347803365440; _gid=GA1.2.629680583.1705411688; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCCEzdRKNAToMY3NyZl9p%250AZCIlMzc3M2VmMTI5Y2ZiNTFmYjQwN2JmOGY1YWU5ODYzYzE6B2lkIiVhNDk3%250AYzdjNGE4M2FiMjUxNDRlZWU3OTcwODJmMzc2NQ%253D%253D--4c8207d531addd1e78f1056c5605ac209e1aa21c; kdt=nT1cgKmu0jucoL9driKQIPHteNGIeugPmUaiEVwV; auth_token=d4228ac610f21e056a4bfeb3542bdb2396b36793; ct0=013199d972058cf035602a15bf4216e7a4985776c135e62c3c813206102ddb3f21e608d202a4df6165c4701fd030d31398740ef8f0558298de97ddafcab88183c8bad3789ec4fb7adc6df2158dc8ebad; att=1-LQNPwf0p04a3sHBIFB3KGLVN6o8190PitLqdZT4M; lang=en; personalization_id="v1_Lw4sezdRBAs+MJPFsVoYpA=="; twid=u%3D1577862800952930305',
    'X-Csrf-Token': '013199d972058cf035602a15bf4216e7a4985776c135e62c3c813206102ddb3f21e608d202a4df6165c4701fd030d31398740ef8f0558298de97ddafcab88183c8bad3789ec4fb7adc6df2158dc8ebad'})]
