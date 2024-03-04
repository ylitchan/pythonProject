import re
import time
import os
import openai
from jsonpath_ng import parse
# {"role": "assistant", "content":"sale:unknown,\nlaunch:unknown,\nlisting:unknown,\nliquidity providing:unknown,\nairdrop:unknown"}
openai.api_key = os.getenv("openai")
res = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    # messages=[{"role": "assistant", "content":"sale:unknown,launch:unknown,listing:unknown,liquidity providing:unknown,airdrop:unknown"},{"role": "user","content": 'We will be having a community AMA to update everyone on:Apr 5, Wed, 9PM UTC+85' + '\n按照之前的格式提取以上内容中代币sale时间/代币launch时间/代币listing时间/代币liquidity providing时间/代币airdrop时间,若时间为现在则为now,若为其他情况则为unknown'}]
    messages=[
              {"role": "user",
               "content": 'I just DUMPED 40 eth worth of my $PSYOP air drop to buy more $WAGMI提取以上内容中推荐的所有代币token名称(格式为$token)'}]
)
# print(res)
print(u"%s" % parse('$..content').find(res)[0].value)
# alpha = re.findall(
#     r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+ \w+|\$[A-Za-z0-9_]+|#[A-Za-z0-9_]+|0x[A-Za-z0-9_]+',
#     '代币sale时间：2023-04-28 00:00:00 CST Saturday 代币launch时间：暂无信息 代币token：$arbistream 代币发射chain：发射chain名称: #Arbitrum 合约contract地址：0xecbee2fae67709f718426ddc3bf770b26b95ed20',
#     re.I)
# print(alpha)
# print(re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+',u"%s" % res['choices'][0]['message']['content']).group())
# @BearrInu swap is now live!    Stealth Launch Sept 2022    Date of $CAI launch: 30.03.2023 $SECT launch is LIVE!
# WL Mint: 3/30  12:00 (UTC+8)   Public launch of $SECT on @CamelotDEX begins in three hours!    $DOF is now listed on http://mute.io 🚀
# We will be having a community AMA to update everyone on:Apr 5, Wed, 9PM UTC+85    Only 2 days left for the $PEG sale for @PepesGame on https://t.co/fL3LzhAIgn
# $LEX liquidity will be seeded 18th Apr, exclusively on Camelot. Sale token claims go live at the same time.         Contract is live on mainnet: 0xecbee2fae67709f718426ddc3bf770b26b95ed20
# Binance will list $PEPE and $FLOKI
