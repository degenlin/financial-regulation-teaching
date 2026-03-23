
"""
专项实验模拟数据
每个实验包含：场景描述、数据集、评分逻辑
"""

# ============================================================
# 实验1：2008金融危机银行压力测试
# ============================================================
CRISIS_BANKS = [
    {"name": "雷曼兄弟银行（模拟）", "assets": 6390, "tier1_capital": 128,
     "tier1_ratio": 11.7, "leverage": 30.7, "mortgage_exposure": 850,
     "cdos": 320, "trading_book": 1200, "description": "高杠杆投行，大量MBS持仓"},
    {"name": "美林银行（模拟）",    "assets": 9410, "tier1_capital": 214,
     "tier1_ratio": 8.3,  "leverage": 27.9, "mortgage_exposure": 1100,
     "cdos": 480, "trading_book": 1900, "description": "CDO持仓巨大，流动性脆弱"},
    {"name": "花旗集团（模拟）",    "assets": 21870,"tier1_capital": 890,
     "tier1_ratio": 7.1,  "leverage": 19.4, "mortgage_exposure": 980,
     "cdos": 530, "trading_book": 2300, "description": "系统重要性银行，表外资产隐患"},
    {"name": "贝尔斯登（模拟）",    "assets": 3950, "tier1_capital": 71,
     "tier1_ratio": 10.2, "leverage": 34.0, "mortgage_exposure": 420,
     "cdos": 180, "trading_book": 890, "description": "回购融资占比极高，流动性最弱"},
    {"name": "安全储备商业银行（模拟）","assets": 880, "tier1_capital": 95,
     "tier1_ratio": 14.8, "leverage": 9.3,  "mortgage_exposure": 120,
     "cdos": 10,  "trading_book": 80, "description": "传统商业银行，较为稳健"},
]

CRISIS_SCENARIOS = {
    "S1_轻度": {
        "label": "轻度压力（S1）",
        "gdp_shock": -1.0,
        "house_price_fall": -10,
        "default_rate_rise": 1.5,
        "market_haircut": 0.15,
        "liquidity_shock": 0.10,
        "color": "warning",
        "description": "经济轻度放缓，房价小幅下跌，类似2001年网络泡沫破裂"
    },
    "S2_中度": {
        "label": "中度压力（S2）",
        "gdp_shock": -3.5,
        "house_price_fall": -25,
        "default_rate_rise": 4.0,
        "market_haircut": 0.35,
        "liquidity_shock": 0.25,
        "color": "orange",
        "description": "显著衰退，类似2008年金融危机初期（2008Q3水平）"
    },
    "S3_严重": {
        "label": "严重压力（S3）",
        "gdp_shock": -6.0,
        "house_price_fall": -40,
        "default_rate_rise": 8.0,
        "market_haircut": 0.55,
        "liquidity_shock": 0.50,
        "color": "danger",
        "description": "极端情景，类似2008年10月最严峻时刻，系统性崩溃边缘"
    },
}

# 巴塞尔III最低要求
BASEL3_MIN_CET1    = 4.5
BASEL3_MIN_TIER1   = 6.0
BASEL3_MIN_TOTAL   = 8.0
BASEL3_BUFFER      = 2.5   # 留存缓冲
SIFI_SURCHARGE     = 2.5   # G-SIFI附加资本

def calc_stress_capital(bank, scenario):
    """计算压力后资本充足率"""
    s = CRISIS_SCENARIOS[scenario]
    # 信用损失：违约率上升 × 贷款资产
    credit_loss = bank["assets"] * 0.3 * (s["default_rate_rise"] / 100)
    # 市场损失：交易账簿 × haircut + CDO × haircut × 1.5
    market_loss = (bank["trading_book"] * s["market_haircut"] +
                   bank["cdos"] * s["market_haircut"] * 1.5 +
                   bank["mortgage_exposure"] * s["market_haircut"] * 0.8)
    # 流动性成本（融资收紧）
    liquidity_cost = bank["assets"] * s["liquidity_shock"] * 0.02
    total_loss = credit_loss + market_loss + liquidity_cost
    new_capital = bank["tier1_capital"] - total_loss
    # RWA 在压力下上升（约10-25%）
    rwa_increase = 1 + abs(s["gdp_shock"]) * 0.03
    new_rwa = (bank["assets"] * 0.65) * rwa_increase
    new_ratio = max(new_capital / new_rwa * 100, -20)
    return {
        "credit_loss": round(credit_loss, 1),
        "market_loss": round(market_loss, 1),
        "liquidity_cost": round(liquidity_cost, 1),
        "total_loss": round(total_loss, 1),
        "new_capital": round(new_capital, 1),
        "new_ratio": round(new_ratio, 2),
        "capital_gap": round(max(BASEL3_MIN_TIER1 * new_rwa / 100 - new_capital, 0), 1),
        "pass": new_ratio >= BASEL3_MIN_TIER1,
        "rwa": round(new_rwa, 1),
    }

# ============================================================
# 实验2：监管沙盒申请评审
# ============================================================
SANDBOX_APPLICATIONS = [
    {
        "id": 1,
        "company": "智信科技（模拟）",
        "product": "AI信贷评分系统 — 基于1200个变量的机器学习模型，为无信用记录人群提供小额贷款授信",
        "innovation_score": 9,
        "risk_level": "中等",
        "target_users": "无银行账户的农村居民，测试规模1000人",
        "customer_protection": "利率上限24%，强制冷静期3天，退出机制完整",
        "existing_license": "无金融牌照",
        "data_source": "电商行为数据、通话记录、缴费记录",
        "regulatory_concern": ["算法黑箱与可解释性", "数据隐私合规", "超限利率风险"],
        "fca_criteria": {"genuine_innovation": 8, "consumer_benefit": 9,
                          "consumer_protection": 6, "regulatory_compliance": 5,
                          "readiness": 7},
    },
    {
        "id": 2,
        "company": "链金保险科技（模拟）",
        "product": "区块链参数保险 — 基于链上气象数据自动赔付的农业参数保险，无需理赔申请",
        "innovation_score": 10,
        "risk_level": "低",
        "target_users": "河南省小麦种植农户，测试规模500户",
        "customer_protection": "智能合约代码已审计，赔付标准公开透明",
        "existing_license": "已持互联网保险经纪牌照",
        "data_source": "国家气象局API数据（公开）",
        "regulatory_concern": ["智能合约法律效力", "赔付触发条件争议处理"],
        "fca_criteria": {"genuine_innovation": 10, "consumer_benefit": 9,
                          "consumer_protection": 8, "regulatory_compliance": 7,
                          "readiness": 8},
    },
    {
        "id": 3,
        "company": "数字支付网络（模拟）",
        "product": "企业间稳定币结算系统 — 以美元锚定的私人稳定币，用于跨境贸易即时结算",
        "innovation_score": 8,
        "risk_level": "高",
        "target_users": "中小外贸企业，测试规模50家",
        "customer_protection": "1:1美元储备，每日披露，第三方托管",
        "existing_license": "已持支付业务许可证",
        "data_source": "内部交易数据",
        "regulatory_concern": ["货币发行权边界", "AML/CFT合规", "储备资产安全性", "系统性风险传染"],
        "fca_criteria": {"genuine_innovation": 7, "consumer_benefit": 7,
                          "consumer_protection": 5, "regulatory_compliance": 4,
                          "readiness": 6},
    },
    {
        "id": 4,
        "company": "惠民理财（模拟）",
        "product": "智能投顾 — 基于GPT的个性化基金组合推荐，管理费0.3%，最低投资100元",
        "innovation_score": 7,
        "risk_level": "中等",
        "target_users": "18-30岁首次理财用户，测试规模2000人",
        "customer_protection": "风险测评强制完成，亏损预警，一键赎回",
        "existing_license": "已持基金销售牌照",
        "data_source": "用户问卷数据",
        "regulatory_concern": ["投资建议的投顾资质", "AI推荐算法的责任认定"],
        "fca_criteria": {"genuine_innovation": 7, "consumer_benefit": 8,
                          "consumer_protection": 7, "regulatory_compliance": 7,
                          "readiness": 8},
    },
]

SANDBOX_CRITERIA = {
    "genuine_innovation": "真实创新性（是否为市场首创或显著改进）",
    "consumer_benefit":   "消费者利益（能否切实改善用户金融可及性）",
    "consumer_protection":"消费者保护（风险披露、退出机制是否完善）",
    "regulatory_compliance": "监管合规基础（是否具备基本合规意识和能力）",
    "readiness":          "测试就绪度（方案是否具体可执行）",
}

# ============================================================
# 实验3：证券监管 — 内幕交易识别 + 信披合规
# ============================================================
INSIDER_CASES = [
    {
        "id": 1,
        "company": "华芯半导体（模拟，A股）",
        "event": "并购重组：2024年3月10日，公司宣布以150亿元收购美国芯片设计公司ArTech，消息公告后股价涨停",
        "insider_info_date": "2024-01-15（董事会秘密讨论日）",
        "public_date": "2024-03-10",
        "suspects": [
            {"name": "张某（董事会秘书）", "buy_date": "2024-01-18", "shares": 200000,
             "avg_price": 32.5, "sell_date": "2024-03-11", "sell_price": 43.2,
             "profit": 214, "relation": "直接知情人，出席了1月15日会议"},
            {"name": "李某（张某配偶）",   "buy_date": "2024-01-20", "shares": 150000,
             "avg_price": 32.8, "sell_date": "2024-03-11", "sell_price": 43.0,
             "profit": 153, "relation": "张某配偶，账户由张某管理"},
            {"name": "王某（投行保荐人）", "buy_date": "2024-02-05", "shares": 80000,
             "avg_price": 34.1, "sell_date": "2024-03-12", "sell_price": 42.8,
             "profit": 55.2, "relation": "参与尽调的投行人员，签署了保密协议"},
            {"name": "赵某（普通股民）",   "buy_date": "2024-03-08", "shares": 50000,
             "avg_price": 38.5, "sell_date": "2024-03-11", "sell_price": 43.5,
             "profit": 25, "relation": "无任何关联，基于技术分析买入"},
        ],
        "correct_insiders": [1, 2, 3],  # id序号
        "key_points": [
            "内幕信息认定：并购方案在公告前属于重大未公开信息",
            "知情人范围：直接参与人（张某、投行人员）及其关联人（配偶）均构成知情人",
            "利用行为：在知悉内幕信息后、公告前买入，且有明显获利",
            "赵某不构成内幕交易：买入时间接近公告日，且无关联关系证据",
            "处罚：没收违法所得+1-5倍罚款，情节严重者追究刑事责任",
        ],
    },
    {
        "id": 2,
        "company": "绿康生物（模拟，创业板）",
        "event": "业绩预警：2024年Q3净利润同比下降85%，主力产品被纳入医保集中采购降价70%",
        "insider_info_date": "2024-09-01（管理层已知晓集采结果）",
        "public_date": "2024-10-15",
        "suspects": [
            {"name": "陈某（CFO）",         "buy_date": "N/A", "shares": -500000,
             "avg_price": 28.3, "sell_date": "2024-09-05", "sell_price": 28.0,
             "profit": 14000, "relation": "公司CFO，直接知情人，减持自有股份"},
            {"name": "刘某（基金经理）",    "buy_date": "N/A", "shares": -1000000,
             "avg_price": 27.5, "sell_date": "2024-09-20", "sell_price": 27.1,
             "profit": 400000, "relation": "通过公司IR获取到非公开数据后减持基金持仓"},
            {"name": "周某（散户）",        "buy_date": "2024-09-10", "shares": 20000,
             "avg_price": 27.0, "sell_date": "2024-10-16", "sell_price": 15.2,
             "profit": -236000, "relation": "普通投资者，看好公司基本面买入，遭受损失"},
        ],
        "correct_insiders": [1, 2],
        "key_points": [
            "卖空型内幕交易：知悉利空信息后提前减持同样构成内幕交易",
            "CFO减持：违反窗口期规定，同时构成内幕交易",
            "基金经理：通过IR渠道获取非公开重大信息后操作基金，构成内幕交易",
            "周某系受害者：因信息不对称遭受损失，属于被保护对象",
            "民事赔偿：内幕交易受害者有权提起民事诉讼索赔",
        ],
    },
]

INFO_DISCLOSURE_ITEMS = [
    {"id": 1, "category": "及时性",
     "scenario": "公司于2024年4月2日（周二）与战略投资者签署了投资协议，于4月8日（周一）才发布公告",
     "violation": True, "violation_type": "未能在两个交易日内披露重大事项",
     "rule": "《上市公司信息披露管理办法》第22条：应在签署协议后两个交易日内披露"},
    {"id": 2, "category": "完整性",
     "scenario": "年报中列示了主要关联方交易，但未披露一笔金额2.3亿元的向控股股东关联方的无息借款",
     "violation": True, "violation_type": "重大关联交易漏报",
     "rule": "《企业会计准则》第36号及《上市规则》：金额超过净资产5%的关联交易须充分披露"},
    {"id": 3, "category": "准确性",
     "scenario": "公告称'已获得某省重大项目批复'，实际仅完成了意向签约，正式批复尚未取得",
     "violation": True, "violation_type": "信息表述存在实质性误导",
     "rule": "《证券法》第78条：信息披露须真实、准确，不得有虚假记载或误导性陈述"},
    {"id": 4, "category": "格式规范",
     "scenario": "临时公告采用了证监会标准格式，所有必要条款均已包含，内容清晰完整",
     "violation": False, "violation_type": None,
     "rule": "符合《上市公司信息披露管理办法》的格式要求"},
    {"id": 5, "category": "公平披露",
     "scenario": "CEO在非公开路演中向部分机构投资者透露了尚未公告的季报数据",
     "violation": True, "violation_type": "选择性披露（Regulation FD违反）",
     "rule": "《上市公司投资者关系管理工作指引》：重大信息须同步向全体投资者披露"},
]

# ============================================================
# 实验4：保险偿付能力计算（C-ROSS偿二代）
# ============================================================
INSURANCE_COMPANIES = [
    {
        "name": "华泰人寿（模拟）",
        "type": "人身险",
        "actual_capital": 85.0,       # 实际资本（亿元）
        "core_capital": 72.0,          # 核心资本
        "min_capital_base": 60.0,      # 最低资本（基础）
        "products": {
            "长期寿险": {"reserves": 320, "risk_factor": 0.045},
            "健康险":   {"reserves": 80,  "risk_factor": 0.055},
            "万能险":   {"reserves": 150, "risk_factor": 0.070},
            "年金险":   {"reserves": 200, "risk_factor": 0.040},
        },
        "investment_assets": {
            "国债":    {"amount": 180, "risk_factor": 0.005},
            "企业债":  {"amount": 120, "risk_factor": 0.025},
            "股票":    {"amount": 80,  "risk_factor": 0.320},
            "不动产":  {"amount": 60,  "risk_factor": 0.150},
            "银行存款":{"amount": 220, "risk_factor": 0.005},
        },
        "operational_risk_factor": 0.08,
        "interest_rate_risk_add": 12.0,
        "description": "中型寿险公司，万能险占比偏高"
    },
    {
        "name": "安盛财险（模拟）",
        "type": "财产险",
        "actual_capital": 45.0,
        "core_capital": 40.0,
        "min_capital_base": 28.0,
        "products": {
            "车险":    {"reserves": 60,  "risk_factor": 0.180},
            "企业财险":{"reserves": 30,  "risk_factor": 0.220},
            "责任险":  {"reserves": 15,  "risk_factor": 0.250},
            "农业险":  {"reserves": 8,   "risk_factor": 0.300},
        },
        "investment_assets": {
            "国债":    {"amount": 55,  "risk_factor": 0.005},
            "企业债":  {"amount": 30,  "risk_factor": 0.025},
            "股票":    {"amount": 15,  "risk_factor": 0.320},
            "银行存款":{"amount": 65,  "risk_factor": 0.005},
        },
        "operational_risk_factor": 0.10,
        "interest_rate_risk_add": 3.0,
        "description": "中型财险公司，车险为主要业务"
    },
]

def calc_insurance_solvency(company):
    """计算C-ROSS偿付能力充足率"""
    # 保险风险最低资本
    insurance_risk = sum(
        p["reserves"] * p["risk_factor"]
        for p in company["products"].values()
    )
    # 市场风险最低资本
    market_risk = sum(
        a["amount"] * a["risk_factor"]
        for a in company["investment_assets"].values()
    )
    # 信用风险（简化）
    credit_risk = sum(
        a["amount"] * a["risk_factor"] * 0.5
        for a in company["investment_assets"].values()
        if a["risk_factor"] > 0.01
    )
    # 操作风险
    total_premiums = sum(p["reserves"] * 0.15 for p in company["products"].values())
    op_risk = total_premiums * company["operational_risk_factor"]
    # 利率风险附加
    ir_risk = company["interest_rate_risk_add"]
    # 汇总（简化：开方求和）
    import math
    min_capital = math.sqrt(insurance_risk**2 + market_risk**2 + credit_risk**2) + op_risk + ir_risk
    # 综合偿付能力充足率
    comprehensive_ratio = company["actual_capital"] / min_capital * 100
    core_ratio = company["core_capital"] / min_capital * 100
    return {
        "insurance_risk": round(insurance_risk, 2),
        "market_risk": round(market_risk, 2),
        "credit_risk": round(credit_risk, 2),
        "op_risk": round(op_risk, 2),
        "ir_risk": ir_risk,
        "min_capital": round(min_capital, 2),
        "comprehensive_ratio": round(comprehensive_ratio, 1),
        "core_ratio": round(core_ratio, 1),
        "pass_comprehensive": comprehensive_ratio >= 100,
        "pass_core": core_ratio >= 50,
        "status": "达标" if comprehensive_ratio >= 100 and core_ratio >= 50
                  else ("核心不达标" if core_ratio < 50 else "综合不达标"),
        "risk_rating": "A" if comprehensive_ratio >= 150 else
                        "B" if comprehensive_ratio >= 100 else
                        "C" if comprehensive_ratio >= 75 else "D",
    }

# ============================================================
# 实验5：量化监管 — VaR计算与系统性风险（CoVaR）
# ============================================================
MARKET_DATA = {
    "banks": [
        {"name": "工商银行（模拟）",  "beta": 0.85, "vol": 0.18, "corr_sys": 0.72,
         "assets": 37000, "leverage": 12.5, "var_99": 2.8, "covar_contribution": 3.2},
        {"name": "招商银行（模拟）",  "beta": 1.10, "vol": 0.22, "corr_sys": 0.68,
         "assets": 9800,  "leverage": 14.2, "var_99": 4.1, "covar_contribution": 4.8},
        {"name": "平安银行（模拟）",  "beta": 1.25, "vol": 0.26, "corr_sys": 0.61,
         "assets": 5200,  "leverage": 15.8, "var_99": 5.3, "covar_contribution": 5.7},
        {"name": "宁波银行（模拟）",  "beta": 1.35, "vol": 0.29, "corr_sys": 0.55,
         "assets": 2800,  "leverage": 13.1, "var_99": 6.2, "covar_contribution": 5.1},
        {"name": "中小农商行（模拟）","beta": 0.65, "vol": 0.32, "corr_sys": 0.42,
         "assets": 450,   "leverage": 11.3, "var_99": 7.8, "covar_contribution": 2.1},
    ],
    "portfolio": [
        {"week": "W1",  "return": 0.8},
        {"week": "W2",  "return": -1.2},
        {"week": "W3",  "return": 2.1},
        {"week": "W4",  "return": -0.5},
        {"week": "W5",  "return": -3.8},
        {"week": "W6",  "return": -7.2},
        {"week": "W7",  "return": -12.5},
        {"week": "W8",  "return": -4.1},
        {"week": "W9",  "return": -1.8},
        {"week": "W10", "return": 1.5},
        {"week": "W11", "return": 3.2},
        {"week": "W12", "return": 0.9},
    ],
    "macro_vars": {
        "credit_gdp_gap": 8.5,   # 信贷/GDP缺口（%）
        "house_price_growth": 6.2,
        "interbank_rate_spread": 0.85,
        "vix_equivalent": 28.5,
        "leverage_ratio_system": 312,  # 全社会杠杆率
    },
    "ccyb_rule": {
        "0-2":   {"ccyb": 0,   "signal": "正常"},
        "2-5":   {"ccyb": 0.5, "signal": "预警"},
        "5-10":  {"ccyb": 1.5, "signal": "偏热"},
        "10+":   {"ccyb": 2.5, "signal": "过热"},
    }
}
