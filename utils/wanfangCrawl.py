# @Date: 2025/3/3
# @Author: ylitchan
import asyncio
import decimal
import io
import json
import os
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, datetime

import requests
from google.protobuf.json_format import MessageToJson, ParseDict
from pymongo import MongoClient
from redisbloom.client import Client

import payload_pb2
from patent_pb2 import Root
from protobuf_inspector.types import StandardParser

os.environ["http_proxy"] = 'http://192.168.8.205:10502'
os.environ["https_proxy"] = 'http://192.168.8.205:10502'
MINIO_HOST = "192.168.6.147"
MINIO_PORT = "9010"
MINIO_HOST_PORT = MINIO_HOST + ":" + MINIO_PORT
MINIO_USER = 'dataexa'
MINIO_PASSWORD = 'DataExa@2020'
MINIO_SECURE = False


def decode_proto_binary(binary_data):
    fh = io.BytesIO(binary_data)
    parser = StandardParser()
    decoded_dict = parser.parse_message(fh, "message")
    try:
        # 创建空对象
        root = Root()
        # root=payload_pb2.Root2()
        # 二进制解码
        root.ParseFromString(binary_data)

        # 转换为 Python 字典格式
        decoded_dict = json.loads(MessageToJson(
            root,
            # including_default_value_fields=True,
            preserving_proto_field_name=False
        ))
        print("解码成功，数据结构验证:", decoded_dict)
        return decoded_dict

    except Exception as e:
        print(f"解码失败: {str(e)}")
        return None


def get_payload(p, start_date, kw):
    # 加 10 天
    end_date = min(start_date + timedelta(days=30), datetime.now())
    end_date_str = end_date.strftime('%Y-%m-%d')
    start_date_str = start_date.strftime('%Y-%m-%d')
    payload = {
        "1": {
            "1": "patent",
            "2": f"(全部:({kw})) and 公开日:[{start_date_str} TO {end_date_str}]",
            "4": {
                "1": "Type",
                "2": "\"Patent\""
            },
            "5": p,
            "6": 50,
            "8": "\u0000",
            "9": 1
        },
        "2": 2
    }
    redis_client.set('32suo_wanfang_mark', json.dumps(payload, ensure_ascii=False))
    hex_data = ParseDict(payload, payload_pb2.Root2()).SerializeToString().hex()
    t = list(bytearray.fromhex(hex_data))
    o = len(t)  # 固定 o 为 106（假设 t 的长度）
    p = [0, 0, 0, 0]
    a = bytearray(5 + o)  # 长度 111

    # 循环
    for s in range(3, -1, -1):
        p[s] = o % 256
        o = o // 256

    # 后续操作（对应 a.set）
    a[1:5] = p  # 将 p 放入 a 的第 1-4 位
    a[5:] = t  # 将 t 放入 a 的第 5 位起
    hex_data = ' '.join(f'{byte:02x}' for byte in a).replace(' ', '')
    return bytes.fromhex(hex_data.upper())


def job(i):
    ii = i.get('119')
    if not redis_client.bfAdd('32suo_patent_bloom', ii.get('4')):
        return
    a = i.get('3')
    item = {
        "original_title": ii.get('2').replace("<span class='highlight'>", "").replace("</span>",
                                                                                      ""),
        "announcement_number": ii.get('4'), "announcement_time": ii.get('16'),
        "announcement_year": ii.get('16').split('-')[0],
        "article_type": ii.get('13', '专利'),
        "article_url": f'https://d.wanfangdata.com.cn/patent/{a}',
        'google_url': f'https://patents.google.com/patent/{ii.get("4")}',
        'create_time': datetime.now()
    }
    item_list.append(item)


async def download_pdf(p, semaphore, start_date, kw):
    """
    异步下载PDF文件
    参数:
    url: PDF文件的URL地址
    filename: 保存的文件名（可选），默认使用URL中的文件名
    """
    while 1:
        try:

            # 2016-01-11
            async with semaphore:
                # 创建aiohttp会话
                stime = time.time()
                binary_data = get_payload(p, start_date, kw)
                response = requests.post(url="https://s.wanfangdata.com.cn/SearchService.SearchService/search",
                                         headers=headers,  # http_version=1,impersonate='chrome110',
                                         data=binary_data,
                                         proxies={'https': 'http://192.168.8.205:10502'})
                decoded_dict = decode_proto_binary(response.content[5:])
                if decoded_dict and '检索结果为空' not in decoded_dict.get('2', '检索结果为空'):
                    global total
                    global pg
                    total2 = int(
                        decimal.Decimal(str(decoded_dict.get('3', 0) / 50)).quantize(1, rounding=decimal.ROUND_UP))
                    if pg == total:
                        pg = total2
                    total = total2
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        # 提交所有任务并获取结果
                        results = executor.map(job, decoded_dict.get("4", []))
                    # for i in decoded_dict.get("4", []):
                    #     ii = i.get('119')
                    #     if not redis_client.bfAdd('32suo_patent_bloom', ii.get('4')):
                    #         continue
                    #     a = i.get('3')
                    #     item = {
                    #         "original_title": ii.get('2').replace("<span class='highlight'>", "").replace("</span>",
                    #                                                                                       ""),
                    #         "announcement_number": ii.get('4'), "announcement_time": ii.get('16'),
                    #         "announcement_year": ii.get('16').split('-')[0],
                    #         "article_type": ii.get('13', '专利'),
                    #         "article_url": f'https://d.wanfangdata.com.cn/patent/{a}',
                    #         'google_url': f'https://patents.google.com/patent/{ii.get("4")}',
                    #         'create_time': datetime.now()
                    #     }
                    #     item_list.append(item)
                    print(p, kw, '成功', '耗时', time.time() - stime)
                    time.sleep(random.uniform(2, 5))
                    break
                elif '检索结果为空' in decoded_dict.get('2', '检索结果为空'):
                    print(p, kw, '检索结果为空')
                    return
                else:
                    print(p, kw, '失败')
                    time.sleep(30)
        except Exception as e:
            traceback.print_exc()
            print(f"下载过程中出现错误: {p}")
            time.sleep(300)


# 示例用法
async def main():
    global pg
    global total
    semaphore = asyncio.Semaphore(1)
    target_date = datetime(2016, 1, 1)
    page = 1
    for kw in query_key_dict[::-1]:
        while target_date <= datetime.now():
            while page <= total:
                print(target_date, kw, '总数', total * 50)
                # 查询最多返回6000条
                step = min(100, pg)
                st = time.time()
                await asyncio.gather(*[download_pdf(i, semaphore, target_date, kw) for i in range(page, page + step)])
                print(datetime.now(), '本次采集', len(item_list))
                if item_list:
                    data_collection.insert_many(item_list, ordered=False)
                item_list.clear()
                page += step
                pg = pg - step
                print(time.time() - st)
                if pg == 0:
                    break
            target_date = target_date + timedelta(days=30)
            total = 1
            page = 1
            pg = total
        target_date = datetime(2016, 1, 1)


# 运行异步函数
if __name__ == "__main__":
    headers = {
        # ":authority": "s.wanfangdata.com.cn",
        # ":method": "POST",
        # ":path": "/SearchService.SearchService/search",
        # ":scheme": "https",
        "content-length": "111",
        "sec-ch-ua-platform": "\"Windows\"",
        "x-user-agent": "grpc-web-javascript/0.1",
        "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Microsoft Edge\";v=\"133\", \"Chromium\";v=\"133\"",
        "sec-ch-ua-mobile": "?0",
        "cookies": "CASTGC=;CASTGCSpecial=;",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
        "content-type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "accept": "*/*",
        "origin": "https://s.wanfangdata.com.cn",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://s.wanfangdata.com.cn/advanced-search/patent",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "cookie": "zh_choose=n",
        "dnt": "1",
        "sec-gpc": "1",
        "priority": "u=1, i"
    }
    query_key_dict = [
        # "质量保证",
        # "验证", "校验",
        # "检查",
        "测量",
        "分析", "测试方法", "无损测试", "环境测试", "性能测试",
        "可靠性测试", "耐久性测试", "应力测试", "负载测试", "疲劳测试", "振动测试", "热测试", "声学测试",
        "电磁兼容性", "安全测试",
        "可用性测试", "互操作性测试", "符合性测试", "认证测试", "校准", "计量学", "仪器仪表", "数据采集",
        "信号处理", "误差分析",
        "失效模式分析", "根本原因分析", "测试自动化", "测试设备", "测试夹具", "测试平台", "测试装置", "测试协议",
        "测试标准", "测试规范",
        "测试报告", "测试用例", "测试场景", "测试计划", "测试策略", "测试管理", "测试覆盖率", "测试指标",
        "测试优化", "测试验证",
        "动态测试", "静态测试", "功能测试", "回归测试", "系统测试", "集成测试", "单元测试", "白盒测试", "黑盒测试",
        "灰盒测试",
        "极限测试", "加速测试", "老化测试", "可重复性", "可再现性", "测试数据", "测试环境", "测试模型", "测试流程",
        "测试工具",
        "测试精度", "测试范围", "测试周期", "测试结果", "测试评估",
        "Quality Assurance", "Validation", "Verification", "Inspection", "Measurement", "Analysis",
        "Testing Methods",
        "Non-Destructive Testing", "Environmental Testing", "Performance Testing",
        "Reliability Testing", "Durability Testing", "Stress Testing", "Load Testing", "Fatigue Testing",
        "Vibration Testing", "Thermal Testing", "Acoustic Testing", "Electromagnetic Compatibility",
        "Safety Testing",
        "Usability Testing", "Interoperability Testing", "Conformance Testing", "Certification Testing",
        "Calibration",
        "Metrology", "Instrumentation", "Data Acquisition", "Signal Processing", "Error Analysis",
        "Failure Mode Analysis", "Root Cause Analysis", "Test Automation", "Test Equipment", "Test Fixtures",
        "Test Platforms", "Test Apparatus", "Test Protocols", "Test Standards", "Test Specifications",
        "Test Reports", "Test Cases", "Test Scenarios", "Test Plans", "Test Strategies", "Test Management",
        "Test Coverage", "Test Metrics", "Test Optimization", "Test Verification",
        "Dynamic Testing", "Static Testing", "Functional Testing", "Regression Testing", "System Testing",
        "Integration Testing", "Unit Testing", "White Box Testing", "Black Box Testing", "Gray Box Testing",
        "Stress Limit Testing", "Accelerated Testing", "Aging Testing", "Repeatability", "Reproducibility",
        "Test Data",
        "Test Environment", "Test Model", "Test Process", "Test Tools",
        "Test Accuracy", "Test Scope", "Test Cycle", "Test Results", "Test Evaluation",
        "仿真", "建模", "虚拟测试", "数字孪生", "有限元分析", "计算流体力学", "多物理场仿真", "系统仿真",
        "硬件在环", "软件在环",
        "实时仿真", "蒙特卡洛仿真", "随机建模", "确定性建模", "预测建模", "机器学习", "人工智能", "神经网络",
        "深度学习", "强化学习",
        "监督学习", "无监督学习", "迁移学习", "自然语言处理", "计算机视觉", "图像识别", "模式识别", "数据挖掘",
        "大数据分析", "云计算",
        "边缘计算", "物联网", "信息物理系统", "嵌入式系统", "实时系统", "分布式系统", "网络系统", "无线通信",
        "传感器网络", "执行器网络",
        "控制系统", "反馈控制", "自适应控制", "优化控制", "鲁棒控制", "非线性控制", "智能控制", "自动化",
        "机器人技术", "自主系统",
        "训练模拟器", "飞行模拟器", "驾驶模拟器", "射击模拟器", "虚拟现实", "增强现实", "混合现实", "严肃游戏",
        "游戏化", "电子学习",
        "远程学习", "混合学习", "移动学习", "适应性学习", "个性化学习", "基于能力的学习", "微学习", "即时培训",
        "在职培训", "学徒制",
        "导师指导", "教练辅导", "领导力发展", "团队建设", "协作工具",
        "Simulation", "Modeling", "Virtual Testing", "Digital Twin", "Finite Element Analysis",
        "Computational Fluid Dynamics", "Multi-Physics Simulation", "System Simulation", "Hardware-in-the-Loop",
        "Software-in-the-Loop",
        "Real-Time Simulation", "Monte Carlo Simulation", "Stochastic Modeling", "Deterministic Modeling",
        "Predictive Modeling", "Machine Learning", "Artificial Intelligence", "Neural Networks", "Deep Learning",
        "Reinforcement Learning",
        "Supervised Learning", "Unsupervised Learning", "Transfer Learning", "Natural Language Processing",
        "Computer Vision", "Image Recognition", "Pattern Recognition", "Data Mining", "Big Data Analytics",
        "Cloud Computing",
        "Edge Computing", "Internet of Things", "Cyber-Physical Systems", "Embedded Systems", "Real-Time Systems",
        "Distributed Systems", "Network Systems", "Wireless Communication", "Sensor Networks", "Actuator Networks",
        "Control Systems", "Feedback Control", "Adaptive Control", "Optimal Control", "Robust Control",
        "Nonlinear Control", "Intelligent Control", "Automation", "Robotics", "Autonomous Systems",
        "Training Simulators", "Flight Simulators", "Driving Simulators", "Shooting Simulators", "Virtual Reality",
        "Augmented Reality", "Mixed Reality", "Serious Games", "Gamification", "E-Learning",
        "Distance Learning", "Blended Learning", "Mobile Learning", "Adaptive Learning", "Personalized Learning",
        "Competency-Based Learning", "Microlearning", "Just-In-Time Training", "On-the-Job Training",
        "Apprenticeship",
        "Mentoring", "Coaching", "Leadership Development", "Team Building", "Collaboration Tools",
        "机械工程", "电气工程", "电子工程", "计算机工程", "软件工程", "土木工程", "结构工程", "航空航天工程",
        "汽车工程", "生物医学工程",
        "化学工程", "材料工程", "环境工程", "能源工程", "核工程", "石油工程", "采矿工程", "岩土工程", "交通工程",
        "城市工程",
        "水资源工程", "海岸工程", "海洋工程", "船舶工程", "飞机设计", "航天器设计", "火箭科学", "推进系统",
        "空气动力学", "水动力学",
        "热力学", "传热", "流体力学", "固体力学", "结构力学", "振动分析", "声学", "光学", "电磁学", "量子力学",
        "纳米技术", "微技术", "生物技术", "基因工程", "合成生物学", "生物信息学", "神经科学", "认知科学", "心理学",
        "人因工程",
        "系统工程", "需求工程", "设计工程", "制造工程", "生产工程", "工艺工程", "工业工程", "质量工程",
        "可靠性工程", "安全工程",
        "优化设计", "工程仿真", "工程分析", "工程测试", "工程管理", "工程标准", "工程规范", "工程材料", "工程设备",
        "工程工具",
        "工程流程", "工程创新", "工程项目", "工程验证", "工程优化",
        "Mechanical Engineering", "Electrical Engineering", "Electronic Engineering", "Computer Engineering",
        "Software Engineering", "Civil Engineering", "Structural Engineering", "Aerospace Engineering",
        "Automotive Engineering", "Biomedical Engineering",
        "Chemical Engineering", "Materials Engineering", "Environmental Engineering", "Energy Engineering",
        "Nuclear Engineering", "Petroleum Engineering", "Mining Engineering", "Geotechnical Engineering",
        "Transportation Engineering", "Urban Engineering",
        "Water Resources Engineering", "Coastal Engineering", "Marine Engineering", "Naval Architecture",
        "Aircraft Design", "Spacecraft Design", "Rocket Science", "Propulsion Systems", "Aerodynamics",
        "Hydrodynamics",
        "Thermodynamics", "Heat Transfer", "Fluid Mechanics", "Solid Mechanics", "Structural Mechanics",
        "Vibration Analysis", "Acoustics", "Optics", "Electromagnetism", "Quantum Mechanics",
        "Nanotechnology", "Microtechnology", "Biotechnology", "Genetic Engineering", "Synthetic Biology",
        "Bioinformatics", "Neuroscience", "Cognitive Science", "Psychology", "Human Factors Engineering",
        "Systems Engineering", "Requirements Engineering", "Design Engineering", "Manufacturing Engineering",
        "Production Engineering", "Process Engineering", "Industrial Engineering", "Quality Engineering",
        "Reliability Engineering", "Safety Engineering",
        "Optimization Design", "Engineering Simulation", "Engineering Analysis", "Engineering Testing",
        "Engineering Management", "Engineering Standards", "Engineering Specifications", "Engineering Materials",
        "Engineering Equipment", "Engineering Tools",
        "Engineering Process", "Engineering Innovation", "Engineering Projects", "Engineering Validation",
        "Engineering Optimization"
        "无人机", "无人飞行器", "无人地面车辆", "无人水下航行器", "自主导航", "路径规划", "避障", "定位",
        "地图构建", "同步定位与地图构建",
        "传感器融合", "多传感器集成", "数据融合", "信息融合", "决策支持系统", "专家系统", "知识库系统", "智能代理",
        "多代理系统", "群体智能",
        "进化计算", "遗传算法", "粒子群优化", "蚁群优化", "模拟退火", "禁忌搜索", "启发式方法", "元启发式",
        "优化技术", "线性规划",
        "非线性规划", "整数规划", "动态规划", "随机规划", "约束规划", "多目标优化", "帕累托优化", "博弈论",
        "决策理论", "运筹学",
        "武器系统", "弹药", "军械", "炸药", "推进剂", "烟火技术", "弹道学", "制导系统", "导航系统", "指挥与控制",
        "通信系统", "雷达", "声呐", "激光雷达", "光电系统", "红外系统", "夜视", "伪装", "隐身技术", "装甲",
        "防护装备", "个人防护装备", "防弹保护", "防爆保护", "化学防护", "生物防护", "辐射防护", "核防护",
        "危险品处理", "去污",
        "急救", "医疗撤离", "战斗伤员护理", "远程医疗", "健康监测",
        "Unmanned Aerial Vehicle", "Unmanned Aircraft", "Unmanned Ground Vehicle", "Unmanned Underwater Vehicle",
        "Autonomous Navigation", "Path Planning", "Obstacle Avoidance", "Localization", "Mapping", "SLAM",
        "Sensor Fusion", "Multi-Sensor Integration", "Data Fusion", "Information Fusion",
        "Decision Support Systems",
        "Expert Systems", "Knowledge-Based Systems", "Intelligent Agents", "Multi-Agent Systems",
        "Swarm Intelligence",
        "Evolutionary Computation", "Genetic Algorithms", "Particle Swarm Optimization", "Ant Colony Optimization",
        "Simulated Annealing", "Tabu Search", "Heuristic Methods", "Metaheuristics", "Optimization Techniques",
        "Linear Programming",
        "Nonlinear Programming", "Integer Programming", "Dynamic Programming", "Stochastic Programming",
        "Constraint Programming", "Multi-Objective Optimization", "Pareto Optimization", "Game Theory",
        "Decision Theory", "Operations Research",
        "Weapon Systems", "Ammunition", "Ordnance", "Explosives", "Propellants", "Pyrotechnics", "Ballistics",
        "Guidance Systems", "Navigation Systems", "Command and Control",
        "Communication Systems", "Radar", "Sonar", "LIDAR", "Electro-Optical Systems", "Infrared Systems",
        "Night Vision", "Camouflage", "Stealth Technology", "Armor",
        "Protective Equipment", "Personal Protective Equipment", "Ballistic Protection", "Blast Protection",
        "Chemical Protection", "Biological Protection", "Radiation Protection", "Nuclear Protection",
        "Hazardous Materials Handling", "Decontamination",
        "First Aid", "Medical Evacuation", "Combat Casualty Care", "Telemedicine", "Health Monitoring"
    ]
    item_list = []
    total = 1
    pg = total
    client = MongoClient("mongodb://192.168.6.147:27017/")
    db = client['sjdz_spiders_num']  # 数据库名称
    data_collection = db['wanfang_patent']
    redis_client = Client(host='192.168.6.147')
    asyncio.run(main())
