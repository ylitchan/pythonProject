import datetime
import random
import time
import requests
from threading import Thread

diane = requests.Session()
diane.headers = {
    "Authorization": "OTk5MjM3ODQ0MDc1ODA2NzMz.GanE1v.6j-jGmofMgMIhPVciWgKC289vUoiPZOYZjecL4"}
baddester = requests.Session()
baddester.headers = {
    "Authorization": "MTAxNzAzNjA0MjU4NDQ2OTUyNg.GZ_Hab.Aempmn-n0RI-3Dn6GfyN-MmOq7tx4e4nf2rNXo"}
apo = requests.Session()
apo.headers = {
    "Authorization": "OTgyODc1NjcwODI2ODQ0MjAw.Glbm4s.eGngrZibq7xOIyCBPL4vVauIQwygRjiZ2AyMAg"}
Diane = requests.Session()
Diane.headers = {
    "Authorization": "OTk5NjM1MDAzMDEwOTc3Nzky.Gw0kmY.vpn8sSgF0CFJC7OZijfM5DdYuDMMpZn0J8xMGc"}


def task(d: dict):
    index = 0
    while True:
        for s, p in d.items():
            nonce = "962932744101429308"[:4] + "".join(random.choice("0123456789") for _ in range(14))
            try:
                a = p.post('https://discord.com/api/v9/interactions',
                           json={"type": 2, "application_id": "159985415099514880", "guild_id": "898153438217633862",
                                 "channel_id": "962932744101429308", "session_id": s,
                                 "data": {"version": "1036965985858617437", "id": "940112581509644326",

                                          "guild_id": "898153438217633862", "name": "work", "type": 1, "options": [],
                                          "application_command": {"id": "940112581509644326",
                                                                  "application_id": "159985415099514880",
                                                                  "version": "1036965985858617437",
                                                                  "default_member_permissions": "2147483648", "type": 1,
                                                                  "nsfw": False, "name": "work",
                                                                  "description": "Work for one hour and come back to claim your paycheck",
                                                                  "guild_id": "898153438217633862", "options": [
                                                  {"type": 3, "name": "action",
                                                   "description": "Optional action like claim"}]},
                                          "attachments": []}, "nonce": nonce},
                           proxies={"https": "http://192.168.6.42:10502"})
                print(datetime.datetime.now(),d)
                if index == 0:
                    nonce = "962932744101429308"[:4] + "".join(random.choice("0123456789") for _ in range(14))
                    b = p.post('https://discord.com/api/v9/interactions',
                               json={"type": 2, "application_id": "159985415099514880",
                                     "guild_id": "898153438217633862",
                                     "channel_id": "962932744101429308", "session_id": s,
                                     "data": {"version": "1032161805201580072", "id": "940112581190910004",
                                              "guild_id": "898153438217633862", "name": "daily", "type": 1,
                                              "options": [],
                                              "application_command": {"id": "940112581190910004",
                                                                      "application_id": "159985415099514880",
                                                                      "version": "1032161805201580072",
                                                                      "default_member_permissions": "2147483648",
                                                                      "type": 1,
                                                                      "nsfw": False, "name": "daily",
                                                                      "description": "Claim your daily coins",
                                                                      "guild_id": "898153438217633862"},
                                              "attachments": []},
                                     "nonce": nonce}, proxies={"https": "http://192.168.6.42:10502"})
                index += 1
                if index == 13:
                    index = 0
                time.sleep(7200 + random.randint(15, 30))
            except:
                continue


threads = []
for url in [{"7eff55d7c447882e121b582691b47778": diane}, {"f90929ec66580f9d828bbbe6db5d7a86": baddester},
            {"4874de25e3e6afb21627bf351daca118": apo}, {"05526f4e58c6e5df6e668eb0f03a797f": Diane}]:
    t = Thread(target=task, args=(url,))
    t.start()
    threads.append(t)
    time.sleep(random.randint(15, 60))
for t in threads:
    t.join()
print('6')
