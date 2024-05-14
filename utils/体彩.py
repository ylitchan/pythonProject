# 返奖率=1/(1/胜+1/平+1/负)
# 原始赔率=100/(返奖率/欧赔)
# 保本胜率=1/原始赔率
sheng=float(input("胜欧赔:"))
ping=float(input("平欧赔:"))
fu=float(input("负欧赔:"))
fjl=1/(1/sheng+1/ping+1/fu)
ssl=(fjl/sheng)/100
psl=(fjl/ping)/100
fsl=(fjl/fu)/100
print(f"胜胜率:{ssl}\n平胜率{psl}\n负胜率{fsl}")