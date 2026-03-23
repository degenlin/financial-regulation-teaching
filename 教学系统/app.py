
import os, json, csv, hashlib, io, math
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_from_directory)
import sqlite3
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_data import (
    CRISIS_BANKS, CRISIS_SCENARIOS, BASEL3_MIN_TIER1, SIFI_SURCHARGE,
    calc_stress_capital,
    SANDBOX_APPLICATIONS, SANDBOX_CRITERIA,
    INSIDER_CASES, INFO_DISCLOSURE_ITEMS,
    INSURANCE_COMPANIES, calc_insurance_solvency,
    MARKET_DATA,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "fsreg.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fsreg-2024-secret")

@app.template_filter('from_json')
def from_json_filter(s):
    try:
        return json.loads(s or '{}')
    except Exception:
        return {}

# ── DB helpers ────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name     TEXT NOT NULL,
        role     TEXT NOT NULL DEFAULT 'student',  -- student | teacher
        class_id TEXT DEFAULT '',
        student_id TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS chapters (
        id      INTEGER PRIMARY KEY,
        title   TEXT NOT NULL,
        num     TEXT NOT NULL,
        summary TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS quizzes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        chapter_id INTEGER,
        question   TEXT NOT NULL,
        option_a   TEXT,
        option_b   TEXT,
        option_c   TEXT,
        option_d   TEXT,
        answer     TEXT NOT NULL,
        explanation TEXT DEFAULT '',
        qtype      TEXT DEFAULT 'single',  -- single | multi | judge
        UNIQUE(chapter_id, question),
        FOREIGN KEY(chapter_id) REFERENCES chapters(id)
    );

    CREATE TABLE IF NOT EXISTS quiz_results (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        chapter_id INTEGER,
        score      INTEGER,
        total      INTEGER,
        answers    TEXT,
        taken_at   TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS experiments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        chapter_id  INTEGER,
        description TEXT,
        exp_type    TEXT DEFAULT 'simulation',
        config      TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS exp_submissions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        exp_id      INTEGER,
        user_id     INTEGER,
        result      TEXT,
        score       INTEGER DEFAULT 0,
        feedback    TEXT DEFAULT '',
        submitted_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS discussion_posts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        chapter_id INTEGER,
        user_id    INTEGER,
        content    TEXT NOT NULL,
        posted_at  TEXT DEFAULT (datetime('now','localtime'))
    );
    """)

    # seed chapters
    chapters_data = [
        (1, "金融监管概论", "一",
         "金融监管的定义、目标与必要性。核心议题：市场失灵（信息不对称、外部性、系统性风险）是政府干预的根本依据。监管目标包括维护金融稳定、保护消费者权益和促进市场效率。中国现行监管体制：一行一局一会（人民银行、金融监管总局、证监会）。"),
        (2, "金融监管理论基础", "二",
         "金融监管的理论支撑：公共利益理论（纠正市场失灵）、管制俘获理论（监管者被监管对象影响）和激励监管理论。重点掌握信息不对称（逆向选择与道德风险）对金融监管的理论意义，以及成本收益分析框架。"),
        (3, "银行监管", "三",
         "核心监管框架：巴塞尔协议I/II/III三代演进。巴塞尔III三大支柱：最低资本要求（CET1≥4.5%，含留存缓冲7%）、监督检查（ICAAP）、市场纪律（信息披露）。新增流动性指标：LCR≥100%（30日压力期）、NSFR≥100%（长期稳定性）；杠杆率≥3%。中国存款保险制度（50万元上限）。"),
        (4, "证券监管", "四",
         "证券监管核心：信息披露制度（及时性、完整性、准确性、公平性）；内幕交易认定三要素（内幕信息、知情人身份、利用行为）；市场操纵行为类型；投资者保护。中国证监会的监管职责与《证券法》2019年修订重点。"),
        (5, "保险监管", "五",
         "中国偿二代（C-ROSS）三支柱框架：支柱一定量资本要求（最低资本=风险模块聚合）、支柱二定性监管要求（风险管理）、支柱三市场约束（信息披露）。偿付能力充足率：综合≥100%、核心≥50%为达标。风险类型：保险风险、市场风险、信用风险、操作风险。"),
        (6, "金融控股公司监管", "六",
         "金融控股公司的界定（两类及以上金融牌照）与监管挑战：传染风险（集团内部风险蔓延）、资本重复计算、关联交易利益输送。监管框架：合并监管、并表资本充足率、风险隔离机制。2020年《金融控股公司监督管理试行办法》要点。"),
        (7, "影子银行监管", "七",
         "影子银行的定义与类型：信托、理财、货币基金、资产证券化。主要风险：期限错配、杠杆放大、流动性风险、监管套利。2018年资管新规（统一监管标准，打破刚性兑付，净值化转型）。FSB全球影子银行监测框架。"),
        (8, "金融科技监管", "八",
         "金融科技五大领域：支付（第三方支付监管）、借贷（P2P清理整顿）、保险科技、智能投顾、区块链/加密货币。监管沙盒制度（FCA创立，五大评审标准）：允许在有限环境中测试创新产品。中国监管科技（RegTech）发展与'监管包容期'政策。"),
        (9, "国际金融监管协调", "九",
         "国际监管协调机构：巴塞尔银行监管委员会（BCBS）、国际证监会组织（IOSCO）、国际保险监督官协会（IAIS）、金融稳定理事会（FSB）。G20框架下的监管改革（2008年后）。跨境监管合作机制：信息共享、监管等值认定。���国参与国际监管合作的进展。"),
        (10, "宏观审慎监管与系统性风险", "十",
         "系统性风险的两个维度：时间维度（顺周期性，用CCyB应对）和跨机构维度（系统重要性，用SIFI附加资本应对）。核心工具：逆周期资本缓冲（CCyB，基于信贷/GDP缺口，最高2.5%）、系统重要性银行附加资本（G-SIB/D-SIB，0.5%~3.5%）、贷款价值比（LTV）、存贷比。CoVaR测量系统性风险贡献。"),
    ]
    for cid, ctitle, cnum, csummary in chapters_data:
        db.execute(
            "INSERT OR IGNORE INTO chapters(id,title,num,summary) VALUES(?,?,?,?)",
            (cid, ctitle, cnum, csummary))
        db.execute(
            "UPDATE chapters SET summary=? WHERE id=? AND (summary='' OR summary IS NULL)",
            (csummary, cid))

    # seed default teacher
    pw = hashlib.sha256("teacher123".encode()).hexdigest()
    db.execute(
        "INSERT OR IGNORE INTO users(username,password,name,role) "
        "VALUES('teacher','%s','授课教师','teacher')" % pw)

    # seed sample quizzes for ch1
    q1 = [
        (1, "金融监管存在的核心经济学理由是？",
         "政府偏好干预", "市场失灵（信息不对称与外部性）",
         "企业自律不足", "国际压力要求",
         "B", "市场失灵是监管存在的根本原因", "single"),
        (1, "下列哪项不属于金融监管的主要目标？",
         "维护金融稳定", "保护消费者", "促进市场效率",
         "提高银行利润", "D", "提高银行利润属于商业目标而非监管目标", "single"),
        (1, "巴塞尔协议III引入了哪些新的监管要求？",
         "仅资本充足率", "资本+流动性+杠杆率三维框架",
         "仅流动性监管", "仅杠杆率限制",
         "B", "巴塞尔III在资本基础上增加了LCR、NSFR和杠杆率要求", "single"),
        (1, "中国目前的金融监管体制格局是？",
         "一行一局", "一行两会", "一行一局一会", "三会一行",
         "C", "2023年机构改革后形成一行（人民银行）一局（金融监管总局）一会（证监会）格局", "single"),
        (1, "单一监管模式的代表国家是？",
         "美国", "中国", "英国", "日本",
         "C", "英国采用FCA/PRA双峰模式，属于单一监管体系", "single"),
    ]
    for q in q1:
        db.execute(
            "INSERT OR IGNORE INTO quizzes"
            "(chapter_id,question,option_a,option_b,option_c,option_d,answer,explanation,qtype)"
            " VALUES(?,?,?,?,?,?,?,?,?)", q)

    # seed sample quizzes for ch3
    q3 = [
        (3, "巴塞尔协议III要求核心一级资本（CET1）充足率不低于？",
         "2%", "4.5%", "6%", "8%", "B",
         "CET1最低要求为4.5%，加上留存缓冲2.5%则达7%", "single"),
        (3, "流动性覆盖率（LCR）的监管要求是？",
         "不低于50%", "不低于80%", "不低于100%", "不低于120%",
         "C", "LCR不低于100%，确保银行在30天压力期内有足够高质量流动资产", "single"),
        (3, "存款保险制度在中国的个人存款保障限额为？",
         "10万元", "25万元", "50万元", "100万元",
         "C", "中国存款保险条例规定最高偿付限额为50万元人民币", "single"),
    ]
    for q in q3:
        db.execute(
            "INSERT OR IGNORE INTO quizzes"
            "(chapter_id,question,option_a,option_b,option_c,option_d,answer,explanation,qtype)"
            " VALUES(?,?,?,?,?,?,?,?,?)", q)

    # seed quizzes for ch4 证券监管
    q4 = [
        (4, "构成内幕交易的三个核心要素不包括？",
         "掌握内幕信息", "属于内幕信息知情人",
         "利用内幕信息交易", "交易金额超过100万元",
         "D", "内幕交易认定与金额无关，核心是信息+身份+利用", "single"),
        (4, "上市公司发生重大事项后，应在多少个交易日内进行信息披露？",
         "1个交易日", "2个交易日", "5个交易日", "10个交易日",
         "B", "《上市公司信息披露管理办法》规定应在2个交易日内披露重大事项", "single"),
        (4, "下列哪项行为不构成内幕交易？",
         "董事在知悉重组消息后买入公司股票",
         "基金经理通过非公开渠道获取财报数据后减仓",
         "普通投资者根据技术分析买入股票",
         "CFO在业绩预亏公告前减持自有股份",
         "C", "不知情的普通投资者基于公开信息分析不构成内幕交易", "single"),
    ]
    for q in q4:
        db.execute(
            "INSERT OR IGNORE INTO quizzes"
            "(chapter_id,question,option_a,option_b,option_c,option_d,answer,explanation,qtype)"
            " VALUES(?,?,?,?,?,?,?,?,?)", q)

    # seed quizzes for ch5 保险监管
    q5 = [
        (5, "C-ROSS（偿二代）中，综合偿付能力充足率达标标准为？",
         "≥50%", "≥75%", "≥100%", "≥150%",
         "C", "综合偿付能力充足率须≥100%，核心偿付能力充足率须≥50%", "single"),
        (5, "C-ROSS最低资本的聚合公式（简化）是？",
         "各风险模块直接相加",
         "保险+市场+信用风险的平方根之和，再加操作和利率风险",
         "取最大单项风险",
         "各模块最低资本的加权平均",
         "B", "最低资本=√(保险²+市场²+信用²)+操作风险+利率风险，体现风险分散效应", "single"),
        (5, "保险公司综合偿付能力充足率低于75%时，监管分类为？",
         "A类（正常）", "B类（关注）", "C类（不足）", "D类（严重不足）",
         "C", "低于75%属于C类，监管将采取限制新业务、要求增资等措施", "single"),
    ]
    for q in q5:
        db.execute(
            "INSERT OR IGNORE INTO quizzes"
            "(chapter_id,question,option_a,option_b,option_c,option_d,answer,explanation,qtype)"
            " VALUES(?,?,?,?,?,?,?,?,?)", q)

    # seed quizzes for ch8 金融科技监管
    q8 = [
        (8, "监管沙盒制度最初由哪个机构创立？",
         "美国SEC", "英国FCA", "中国人民银行", "巴塞尔委员会",
         "B", "英国金融行为监管局（FCA）于2016年建立全球首个监管沙盒制度", "single"),
        (8, "下列不属于P2P网络借贷平台监管要求的是？",
         "信息中介定位，不得吸收公众存款",
         "每个借款人在同一平台借款上限20万元",
         "平台自身可以提供担保或增信",
         "资金由银行托管",
         "C", "平台不得自身提供担保，禁止资金池操作，属于信息中介", "single"),
        (8, "金融科技监管中'包容审慎'的核心含义是？",
         "完全放开，不加监管",
         "先禁止，等成熟后再开放",
         "在一定范围内允许创新测试，同时设置消费者保护机制",
         "所有科技公司均需持牌经营",
         "C", "包容审慎即监管沙盒理念：允许创新，但有规模限制和退出机制", "single"),
    ]
    for q in q8:
        db.execute(
            "INSERT OR IGNORE INTO quizzes"
            "(chapter_id,question,option_a,option_b,option_c,option_d,answer,explanation,qtype)"
            " VALUES(?,?,?,?,?,?,?,?,?)", q)

    # seed quizzes for ch10 宏观审慎
    q10 = [
        (10, "逆周期资本缓冲（CCyB）的触发指标主要是？",
         "银行股价指数", "信贷/GDP缺口", "CPI通货膨胀率", "失业率",
         "B", "CCyB由信贷/GDP缺口触发：缺口>10%时缓冲率可达2.5%上限", "single"),
        (10, "ΔCoVaR指标衡量的是？",
         "单个银行自身的市场风险",
         "某机构陷入困境时对金融系统的边际风险贡献",
         "系统全部银行的平均VaR",
         "某机构相对于基准的超额收益波动",
         "B", "ΔCoVaR=系统危机时VaR-正常时VaR，越大说明该机构对系统性风险贡献越大", "single"),
        (10, "全球系统重要性银行（G-SIB）需要额外缴纳的附加资本范围为？",
         "0~1%", "0.5%~3.5%", "1%~5%", "2%~8%",
         "B", "G-SIB附加资本根据系统重要性评分分为1~5档，范围0.5%~3.5%", "single"),
    ]
    for q in q10:
        db.execute(
            "INSERT OR IGNORE INTO quizzes"
            "(chapter_id,question,option_a,option_b,option_c,option_d,answer,explanation,qtype)"
            " VALUES(?,?,?,?,?,?,?,?,?)", q)

    # seed experiments
    exps = [
        (1, "银行资本充足率压力测试模拟", 3,
         "模拟不同宏观经济情景下，商业银行资本充足率的变化。学生需要根据压力情景参数，计算资本缺口并提出补充方案。",
         "calculator", '{"scenarios":["基准","温和压力","严重压力"],"capital_ratio":12.5}'),
        (2, "资管新规合规性判断练习", 7,
         "给出若干资产管理产品的结构描述，判断其是否符合资管新规要求，并指出违规点。",
         "quiz", '{"items":5}'),
        (3, "内幕交易案例模拟裁判", 4,
         "根据给定的证券交易案例，判断是否构成内幕交易，给出法律定性和处罚意见。",
         "judge", '{"cases":3}'),
        (4, "宏观审慎工具组合设计", 10,
         "面对给定的金融系统性风险情景，学生需要从LTV、CCyB、SIFI附加资本等工具中选择合适的政策组合并说明理由。",
         "design", '{"risk_level":"中等"}'),
        (10, "2008金融危机银行压力测试（仿真）", 3,
         "基于2008年金融危机情景数据，计算五大银行在不同压力情景下的资本充足率变化，并提出监管处置建议。",
         "simulation", '{}'),
        (11, "监管沙盒评审模拟", 8,
         "扮演监管沙盒评审官，根据FCA五准则评审四项金融科技产品申请，决定批准或拒绝并说明理由。",
         "simulation", '{}'),
        (12, "证券监管：内幕交易识别+信披合规判断", 4,
         "识别内幕交易嫌疑人，并判断五项信息披露行为是否违规。",
         "simulation", '{}'),
        (13, "保险偿付能力计算（C-ROSS偿二代）", 5,
         "根据C-ROSS三支柱框架，计算保险公司最低资本需求与偿付能力充足率，给出监管诊断意见。",
         "simulation", '{}'),
        (14, "量化监管：VaR/CoVaR/CCyB", 10,
         "运用系统性风险测量工具，分析银行风险敞口，给出逆周期资本缓冲建议。",
         "simulation", '{}'),
        (15, "银行风险控制综合实验", 3,
         "模拟银行风控官，处置信用、市场、操作、流动性四类风险事件，并进行监管指标合规判断。",
         "simulation", '{}'),
    ]
    for e in exps:
        db.execute(
            "INSERT OR IGNORE INTO experiments(id,title,chapter_id,description,exp_type,config)"
            " VALUES(?,?,?,?,?,?)", e)

    db.commit()
    db.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return u

# ── Auth ─────────────────────────────────────────────────────

@app.route("/")
def index():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    if u["role"] == "teacher":
        return redirect(url_for("teacher_dashboard"))
    return redirect(url_for("student_dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pw    = request.form.get("password", "").strip()
        db = get_db()
        u = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (uname, hash_pw(pw))).fetchone()
        db.close()
        if u:
            session["user_id"] = u["id"]
            session["role"]    = u["role"]
            flash(f"欢迎回来，{u['name']}！", "success")
            return redirect(url_for("index"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pw    = request.form.get("password", "").strip()
        name  = request.form.get("name", "").strip()
        sid   = request.form.get("student_id", "").strip()
        cls   = request.form.get("class_id", "").strip()
        if not (uname and pw and name):
            flash("请填写完整信息", "warning")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users(username,password,name,role,student_id,class_id)"
                " VALUES(?,?,?,'student',?,?)",
                (uname, hash_pw(pw), name, sid, cls))
            db.commit()
            flash("注册成功，请登录", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("用户名已存在", "danger")
        finally:
            db.close()
    return render_template("register.html")

# ── Student ───────────────────────────────────────────────────

@app.route("/student")
def student_dashboard():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    db = get_db()
    chapters = db.execute("SELECT * FROM chapters ORDER BY id").fetchall()
    # recent quiz results
    results = db.execute(
        "SELECT qr.*, c.title as ch_title FROM quiz_results qr "
        "JOIN chapters c ON qr.chapter_id=c.id "
        "WHERE qr.user_id=? ORDER BY qr.taken_at DESC LIMIT 5",
        (u["id"],)).fetchall()
    # experiment count
    exp_done = db.execute(
        "SELECT COUNT(*) as n FROM exp_submissions WHERE user_id=?",
        (u["id"],)).fetchone()["n"]
    db.close()
    return render_template("student_dashboard.html",
                           user=u, chapters=chapters,
                           results=results, exp_done=exp_done)

@app.route("/student/chapter/<int:cid>")
def chapter_detail(cid):
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    db = get_db()
    ch = db.execute("SELECT * FROM chapters WHERE id=?", (cid,)).fetchone()
    quizzes = db.execute(
        "SELECT COUNT(*) as n FROM quizzes WHERE chapter_id=?", (cid,)
    ).fetchone()["n"]
    exps = db.execute(
        "SELECT * FROM experiments WHERE chapter_id=?", (cid,)).fetchall()
    posts = db.execute(
        "SELECT dp.*, u.name as uname FROM discussion_posts dp "
        "JOIN users u ON dp.user_id=u.id "
        "WHERE dp.chapter_id=? ORDER BY dp.posted_at DESC LIMIT 20",
        (cid,)).fetchall()
    db.close()
    return render_template("chapter_detail.html",
                           user=u, ch=ch, quiz_count=quizzes,
                           experiments=exps, posts=posts)

@app.route("/student/quiz/<int:cid>", methods=["GET", "POST"])
def quiz(cid):
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    db = get_db()
    ch = db.execute("SELECT * FROM chapters WHERE id=?", (cid,)).fetchone()
    qs = db.execute(
        "SELECT * FROM quizzes WHERE chapter_id=? ORDER BY id", (cid,)
    ).fetchall()
    if request.method == "POST":
        answers = {}
        score = 0
        for q in qs:
            ans = request.form.get(f"q{q['id']}", "").upper()
            answers[str(q["id"])] = ans
            if ans == q["answer"].upper():
                score += 1
        db.execute(
            "INSERT INTO quiz_results(user_id,chapter_id,score,total,answers)"
            " VALUES(?,?,?,?,?)",
            (u["id"], cid, score, len(qs), json.dumps(answers)))
        db.commit()
        db.close()
        return render_template("quiz_result.html",
                               user=u, ch=ch, score=score,
                               total=len(qs), questions=qs,
                               answers=answers)
    db.close()
    return render_template("quiz.html", user=u, ch=ch, questions=qs)

@app.route("/student/experiment/<int:eid>", methods=["GET", "POST"])
def experiment(eid):
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    db = get_db()
    exp = db.execute("SELECT * FROM experiments WHERE id=?", (eid,)).fetchone()
    if not exp:
        db.close()
        return "实验不存在", 404
    cfg = json.loads(exp["config"] or "{}")
    # Simulation experiments have dedicated lab pages — redirect there
    if cfg.get("lab_url"):
        db.close()
        return redirect(cfg["lab_url"])
    ch  = db.execute("SELECT * FROM chapters WHERE id=?",
                     (exp["chapter_id"],)).fetchone()
    prev = db.execute(
        "SELECT * FROM exp_submissions WHERE exp_id=? AND user_id=?"
        " ORDER BY submitted_at DESC LIMIT 1",
        (eid, u["id"])).fetchone()
    if request.method == "POST":
        result = request.form.get("result", "")
        score = _auto_score(exp["exp_type"], result, cfg)
        db.execute(
            "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
            " VALUES(?,?,?,?)",
            (eid, u["id"], result, score))
        db.commit()
        flash(f"提交成功！本次得分：{score} 分", "success")
        return redirect(url_for("experiment", eid=eid))
    db.close()
    return render_template("experiment.html",
                           user=u, exp=exp, ch=ch,
                           config=cfg, prev=prev)

def _auto_score(exp_type, result, cfg):
    if not result:
        return 0
    base = min(60 + len(result) // 5, 95)
    return base

@app.route("/student/discuss/<int:cid>", methods=["POST"])
def post_discussion(cid):
    u = current_user()
    if not u:
        return jsonify({"error": "未登录"}), 401
    content = request.json.get("content", "").strip()
    if not content:
        return jsonify({"error": "内容不能为空"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO discussion_posts(chapter_id,user_id,content) VALUES(?,?,?)",
        (cid, u["id"], content))
    db.commit()
    db.close()
    return jsonify({"ok": True, "name": u["name"],
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")})

# ── Teacher ───────────────────────────────────────────────────

def require_teacher(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u or u["role"] != "teacher":
            flash("需要教师权限", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/teacher")
@require_teacher
def teacher_dashboard():
    u = current_user()
    db = get_db()
    student_count = db.execute(
        "SELECT COUNT(*) as n FROM users WHERE role='student'").fetchone()["n"]
    quiz_count = db.execute(
        "SELECT COUNT(*) as n FROM quiz_results").fetchone()["n"]
    exp_count = db.execute(
        "SELECT COUNT(*) as n FROM exp_submissions").fetchone()["n"]
    chapters = db.execute("SELECT * FROM chapters ORDER BY id").fetchall()
    # avg scores per chapter
    scores = db.execute(
        "SELECT chapter_id, AVG(score*100.0/total) as avg_score, COUNT(*) as cnt "
        "FROM quiz_results GROUP BY chapter_id").fetchall()
    scores_dict = {r["chapter_id"]: r for r in scores}
    db.close()
    return render_template("teacher_dashboard.html",
                           user=u, student_count=student_count,
                           quiz_count=quiz_count, exp_count=exp_count,
                           chapters=chapters, scores=scores_dict)

@app.route("/teacher/students")
@require_teacher
def manage_students():
    u = current_user()
    db = get_db()
    q = request.args.get("q", "")
    if q:
        students = db.execute(
            "SELECT * FROM users WHERE role='student' AND "
            "(name LIKE ? OR username LIKE ? OR student_id LIKE ?)"
            " ORDER BY class_id, name",
            (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    else:
        students = db.execute(
            "SELECT * FROM users WHERE role='student' ORDER BY class_id, name"
        ).fetchall()
    db.close()
    return render_template("manage_students.html",
                           user=u, students=students, q=q)

@app.route("/teacher/import_students", methods=["GET", "POST"])
@require_teacher
def import_students():
    u = current_user()
    if request.method == "POST":
        f = request.files.get("csvfile")
        if not f:
            flash("请选择CSV文件", "warning")
            return redirect(request.url)
        try:
            stream = io.StringIO(f.read().decode("utf-8-sig"))
            reader = csv.DictReader(stream)
            db = get_db()
            ok = err = 0
            errors = []
            for row in reader:
                uname = (row.get("username") or row.get("用户名", "")).strip()
                pw    = (row.get("password") or row.get("密码", "student123")).strip() or "student123"
                name  = (row.get("name") or row.get("姓名", "")).strip()
                sid   = (row.get("student_id") or row.get("学号", "")).strip()
                cls   = (row.get("class_id") or row.get("班级", "")).strip()
                if not uname or not name:
                    err += 1
                    errors.append(f"行缺少必要字段: {dict(row)}")
                    continue
                try:
                    db.execute(
                        "INSERT INTO users(username,password,name,role,student_id,class_id)"
                        " VALUES(?,?,?,'student',?,?)",
                        (uname, hash_pw(pw), name, sid, cls))
                    ok += 1
                except sqlite3.IntegrityError:
                    err += 1
                    errors.append(f"用户名已存在: {uname}")
            db.commit()
            db.close()
            flash(f"导入完成：成功 {ok} 条，失败 {err} 条", "success" if ok else "warning")
            if errors:
                flash("错误详情：" + "；".join(errors[:5]), "warning")
        except Exception as e:
            flash(f"导入失败：{e}", "danger")
        return redirect(url_for("manage_students"))
    return render_template("import_students.html", user=u)

@app.route("/teacher/quiz_stats")
@require_teacher
def quiz_stats():
    u = current_user()
    db = get_db()
    chapters = db.execute("SELECT * FROM chapters ORDER BY id").fetchall()
    cid = request.args.get("cid", type=int)
    results = []
    if cid:
        results = db.execute(
            "SELECT qr.*, u.name as uname, u.student_id, u.class_id "
            "FROM quiz_results qr JOIN users u ON qr.user_id=u.id "
            "WHERE qr.chapter_id=? ORDER BY qr.taken_at DESC",
            (cid,)).fetchall()
    db.close()
    return render_template("quiz_stats.html",
                           user=u, chapters=chapters,
                           results=results, sel_cid=cid)

@app.route("/teacher/add_quiz", methods=["GET", "POST"])
@require_teacher
def add_quiz():
    u = current_user()
    db = get_db()
    chapters = db.execute("SELECT * FROM chapters ORDER BY id").fetchall()
    if request.method == "POST":
        cid  = request.form.get("chapter_id", type=int)
        q    = request.form.get("question", "").strip()
        oa   = request.form.get("option_a", "").strip()
        ob   = request.form.get("option_b", "").strip()
        oc   = request.form.get("option_c", "").strip()
        od   = request.form.get("option_d", "").strip()
        ans  = request.form.get("answer", "").upper().strip()
        exp  = request.form.get("explanation", "").strip()
        if q and ans:
            db.execute(
                "INSERT INTO quizzes(chapter_id,question,option_a,option_b,"
                "option_c,option_d,answer,explanation) VALUES(?,?,?,?,?,?,?,?)",
                (cid, q, oa, ob, oc, od, ans, exp))
            db.commit()
            flash("题目添加成功", "success")
        else:
            flash("请填写题目和正确答案", "warning")
        db.close()
        return redirect(url_for("add_quiz"))
    db.close()
    return render_template("add_quiz.html", user=u, chapters=chapters)

@app.route("/teacher/exp_submissions")
@require_teacher
def exp_submissions():
    u = current_user()
    db = get_db()
    subs = db.execute(
        "SELECT es.*, u.name as uname, u.student_id, e.title as exp_title "
        "FROM exp_submissions es "
        "JOIN users u ON es.user_id=u.id "
        "JOIN experiments e ON es.exp_id=e.id "
        "ORDER BY es.submitted_at DESC LIMIT 100").fetchall()
    db.close()
    return render_template("exp_submissions.html", user=u, subs=subs)

@app.route("/teacher/grade_exp/<int:sid>", methods=["POST"])
@require_teacher
def grade_exp(sid):
    score    = request.form.get("score", type=int, default=0)
    feedback = request.form.get("feedback", "").strip()
    db = get_db()
    db.execute(
        "UPDATE exp_submissions SET score=?, feedback=? WHERE id=?",
        (score, feedback, sid))
    db.commit()
    db.close()
    flash("评分已保存", "success")
    return redirect(url_for("exp_submissions"))

@app.route("/teacher/export_scores")
@require_teacher
def export_scores():
    db = get_db()
    rows = db.execute(
        "SELECT u.name, u.student_id, u.class_id, c.title, "
        "qr.score, qr.total, "
        "ROUND(qr.score*100.0/qr.total,1) as pct, qr.taken_at "
        "FROM quiz_results qr "
        "JOIN users u ON qr.user_id=u.id "
        "JOIN chapters c ON qr.chapter_id=c.id "
        "ORDER BY u.class_id, u.name, c.id").fetchall()
    db.close()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["姓名","学号","班级","章节","得分","总题数","百分比","测验时间"])
    for r in rows:
        w.writerow(list(r))
    from flask import Response
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 "attachment;filename=成绩汇总.csv"})

@app.route("/teacher/delete_student/<int:uid>", methods=["POST"])
@require_teacher
def delete_student(uid):
    db = get_db()
    db.execute("DELETE FROM users WHERE id=? AND role='student'", (uid,))
    db.commit()
    db.close()
    flash("学生账号已删除", "success")
    return redirect(url_for("manage_students"))

@app.route("/teacher/reset_password/<int:uid>", methods=["POST"])
@require_teacher
def reset_password(uid):
    new_pw = request.form.get("new_pw", "student123")
    db = get_db()
    db.execute("UPDATE users SET password=? WHERE id=?",
               (hash_pw(new_pw), uid))
    db.commit()
    db.close()
    flash(f"密码已重置", "success")
    return redirect(url_for("manage_students"))

# ── API ───────────────────────────────────────────────────────

@app.route("/api/stats/class")
@require_teacher
def api_class_stats():
    db = get_db()
    rows = db.execute(
        "SELECT u.class_id, "
        "COUNT(DISTINCT u.id) as student_cnt, "
        "ROUND(AVG(qr.score*100.0/qr.total),1) as avg_score "
        "FROM users u LEFT JOIN quiz_results qr ON u.id=qr.user_id "
        "WHERE u.role='student' GROUP BY u.class_id").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/chapter_progress/<int:uid>")
def api_chapter_progress(uid):
    db = get_db()
    rows = db.execute(
        "SELECT chapter_id, MAX(score*100.0/total) as best "
        "FROM quiz_results WHERE user_id=? GROUP BY chapter_id",
        (uid,)).fetchall()
    db.close()
    return jsonify({r["chapter_id"]: r["best"] for r in rows})

# ── Static download of PPTs ───────────────────────────────────

@app.route("/ppt/<path:filename>")
def download_ppt(filename):
    ppt_dir = os.path.join(BASE_DIR, "..", "PPT课件")
    return send_from_directory(ppt_dir, filename, as_attachment=True)

# ══════════════════════════════════════════════════════════════
# 专项实验路由
# ══════════════════════════════════════════════════════════════

def require_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# ── 实验1：2008金融危机压力测试 ──────────────────────────────

@app.route("/lab/crisis")
@require_login
def lab_crisis():
    u = current_user()
    return render_template("lab_crisis.html", u=u,
                           banks=CRISIS_BANKS,
                           scenarios=CRISIS_SCENARIOS,
                           min_tier1=BASEL3_MIN_TIER1,
                           sifi=SIFI_SURCHARGE)

@app.route("/lab/crisis/run", methods=["POST"])
@require_login
def lab_crisis_run():
    u = current_user()
    scenario = request.form.get("scenario", "S2_中度")
    if scenario not in CRISIS_SCENARIOS:
        scenario = "S2_中度"
    results = []
    for b in CRISIS_BANKS:
        r = calc_stress_capital(b, scenario)
        r["bank"] = b
        results.append(r)
    # save attempt
    db = get_db()
    passed = sum(1 for r in results if r["pass"])
    db.execute(
        "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
        " VALUES(10,?,?,?)",
        (u["id"],
         json.dumps({"scenario": scenario, "passed": passed, "total": len(results)}),
         min(60 + passed * 8, 100)))
    db.commit()
    db.close()
    # compute answers for display
    student_answers = {}
    for b in CRISIS_BANKS:
        key = "action_" + b["name"][:4]
        student_answers[b["name"]] = request.form.get(key, "")
    return render_template("lab_crisis_result.html", u=u,
                           scenario=CRISIS_SCENARIOS[scenario],
                           scenario_key=scenario,
                           results=results,
                           min_tier1=BASEL3_MIN_TIER1,
                           student_answers=student_answers)

# ── 实验2：监管沙盒评审 ──────────────────────────────────────

@app.route("/lab/sandbox")
@require_login
def lab_sandbox():
    u = current_user()
    return render_template("lab_sandbox.html", u=u,
                           apps=SANDBOX_APPLICATIONS,
                           criteria=SANDBOX_CRITERIA)

@app.route("/lab/sandbox/submit", methods=["POST"])
@require_login
def lab_sandbox_submit():
    u = current_user()
    decisions = {}
    score = 0
    feedback = []
    # 参考答案：1=批准, 2=批准, 3=拒绝(高风险), 4=批准
    ref = {"1": "approve", "2": "approve", "3": "reject", "4": "approve"}
    for app_item in SANDBOX_APPLICATIONS:
        aid = str(app_item["id"])
        decision = request.form.get(f"decision_{aid}", "")
        reasoning = request.form.get(f"reason_{aid}", "")
        correct = (decision == ref[aid])
        if correct:
            score += 20
            feedback.append({"app": app_item, "correct": True,
                             "decision": decision, "reasoning": reasoning})
        else:
            feedback.append({"app": app_item, "correct": False,
                             "decision": decision, "reasoning": reasoning,
                             "expected": ref[aid]})
    db = get_db()
    db.execute(
        "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
        " VALUES(11,?,?,?)",
        (u["id"], json.dumps(decisions), score))
    db.commit()
    db.close()
    return render_template("lab_sandbox_result.html", u=u,
                           feedback=feedback, score=score,
                           ref=ref, criteria=SANDBOX_CRITERIA,
                           apps=SANDBOX_APPLICATIONS)

# ── 实验3：证券监管 ──────────────────────────────────────────

@app.route("/lab/securities")
@require_login
def lab_securities():
    u = current_user()
    return render_template("lab_securities.html", u=u,
                           insider_cases=INSIDER_CASES,
                           disclosure_items=INFO_DISCLOSURE_ITEMS)

@app.route("/lab/securities/submit", methods=["POST"])
@require_login
def lab_securities_submit():
    u = current_user()
    score = 0
    ic_results = []
    for case in INSIDER_CASES:
        selected = request.form.getlist(f"insider_{case['id']}")
        selected_ids = set(int(x) for x in selected if x.isdigit())
        correct_ids  = set(range(1, len(case["suspects"]) + 1))
        correct_ids  = set(i+1 for i, s in enumerate(case["suspects"])
                          if i+1 in set(case["correct_insiders"]))
        # simpler: correct_insiders are 1-indexed positions
        correct_ids = set(case["correct_insiders"])
        tp = len(selected_ids & correct_ids)
        fp = len(selected_ids - correct_ids)
        fn = len(correct_ids - selected_ids)
        case_score = max(0, tp * 15 - fp * 10)
        score += case_score
        ic_results.append({
            "case": case,
            "selected": selected_ids,
            "correct": correct_ids,
            "tp": tp, "fp": fp, "fn": fn,
            "case_score": case_score,
        })
    # disclosure
    disc_results = []
    disc_score = 0
    for item in INFO_DISCLOSURE_ITEMS:
        ans = request.form.get(f"disc_{item['id']}", "")
        correct_ans = "yes" if item["violation"] else "no"
        correct = (ans == correct_ans)
        if correct:
            disc_score += 8
        disc_results.append({"item": item, "correct": correct, "answer": ans})
    score += disc_score
    score = min(score, 100)
    db = get_db()
    db.execute(
        "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
        " VALUES(12,?,?,?)",
        (u["id"], json.dumps({"ic_score": score-disc_score, "disc_score": disc_score}), score))
    db.commit()
    db.close()
    return render_template("lab_securities_result.html", u=u,
                           ic_results=ic_results,
                           disc_results=disc_results,
                           score=score)

# ── 实验4：保险偿付能力 ──────────────────────────────────────

@app.route("/lab/insurance")
@require_login
def lab_insurance():
    u = current_user()
    return render_template("lab_insurance.html", u=u,
                           companies=INSURANCE_COMPANIES)

@app.route("/lab/insurance/calc", methods=["POST"])
@require_login
def lab_insurance_calc():
    u = current_user()
    cid = request.form.get("company_id", "0", type=str)
    try:
        company = INSURANCE_COMPANIES[int(cid)]
    except Exception:
        company = INSURANCE_COMPANIES[0]
    result = calc_insurance_solvency(company)
    # grade student's answers
    student_comp = request.form.get("student_comprehensive", "").strip()
    student_core = request.form.get("student_core", "").strip()
    score = 0
    comp_correct = core_correct = False
    try:
        sc = float(student_comp)
        if abs(sc - result["comprehensive_ratio"]) <= 5:
            score += 40
            comp_correct = True
    except Exception:
        pass
    try:
        sc2 = float(student_core)
        if abs(sc2 - result["core_ratio"]) <= 5:
            score += 30
            core_correct = True
    except Exception:
        pass
    # diagnosis question
    diagnosis = request.form.get("diagnosis", "")
    if diagnosis and len(diagnosis) > 20:
        score += 30
    db = get_db()
    db.execute(
        "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
        " VALUES(13,?,?,?)",
        (u["id"],
         json.dumps({"company": company["name"], "comp_ratio": result["comprehensive_ratio"]}),
         score))
    db.commit()
    db.close()
    return render_template("lab_insurance_result.html", u=u,
                           company=company,
                           result=result,
                           student_comp=student_comp,
                           student_core=student_core,
                           comp_correct=comp_correct,
                           core_correct=core_correct,
                           diagnosis=diagnosis,
                           score=score)

# ── 实验5：量化监管（VaR / CoVaR / CCyB） ────────────────────

@app.route("/lab/quant")
@require_login
def lab_quant():
    u = current_user()
    return render_template("lab_quant.html", u=u,
                           banks=MARKET_DATA["banks"],
                           portfolio=MARKET_DATA["portfolio"],
                           macro=MARKET_DATA["macro_vars"],
                           ccyb_rule=MARKET_DATA["ccyb_rule"])

@app.route("/lab/quant/submit", methods=["POST"])
@require_login
def lab_quant_submit():
    u = current_user()
    score = 0
    feedback = {}

    # Q1: 哪家银行系统性风险贡献最大（CoVaR最高）
    ans1 = request.form.get("q1_bank", "")
    best_covar = max(MARKET_DATA["banks"], key=lambda b: b["covar_contribution"])
    if ans1 == best_covar["name"]:
        score += 25
        feedback["q1"] = {"correct": True, "answer": ans1,
                           "correct_ans": best_covar["name"]}
    else:
        feedback["q1"] = {"correct": False, "answer": ans1,
                           "correct_ans": best_covar["name"]}

    # Q2: VaR最高的银行（个体风险最大）
    ans2 = request.form.get("q2_bank", "")
    highest_var = max(MARKET_DATA["banks"], key=lambda b: b["var_99"])
    if ans2 == highest_var["name"]:
        score += 20
        feedback["q2"] = {"correct": True, "answer": ans2,
                           "correct_ans": highest_var["name"]}
    else:
        feedback["q2"] = {"correct": False, "answer": ans2,
                           "correct_ans": highest_var["name"]}

    # Q3: CCyB 推荐值（根据信贷/GDP缺口）
    gap = MARKET_DATA["macro_vars"]["credit_gdp_gap"]
    if gap < 2:
        ccyb_ans = "0"
    elif gap < 5:
        ccyb_ans = "0.5"
    elif gap < 10:
        ccyb_ans = "1.5"
    else:
        ccyb_ans = "2.5"
    ans3 = request.form.get("q3_ccyb", "")
    if ans3 == ccyb_ans:
        score += 25
        feedback["q3"] = {"correct": True, "answer": ans3, "correct_ans": ccyb_ans}
    else:
        feedback["q3"] = {"correct": False, "answer": ans3, "correct_ans": ccyb_ans}

    # Q4: 最大单周损失（历史模拟法，取最小单周收益率）
    rets = [w["return"] for w in MARKET_DATA["portfolio"]]
    min_weekly = min(rets)   # 最大单周亏损（最负的值，如 -12.5）
    ans4 = request.form.get("q4_mdd", "").strip()
    try:
        v4 = float(ans4)
        if abs(v4 - min_weekly) <= 1.0:
            score += 30
            feedback["q4"] = {"correct": True, "answer": ans4,
                               "correct_ans": min_weekly}
        else:
            feedback["q4"] = {"correct": False, "answer": ans4,
                               "correct_ans": min_weekly}
    except Exception:
        feedback["q4"] = {"correct": False, "answer": ans4,
                           "correct_ans": min_weekly}

    db = get_db()
    db.execute(
        "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
        " VALUES(14,?,?,?)",
        (u["id"], json.dumps(feedback), score))
    db.commit()
    db.close()
    return render_template("lab_quant_result.html", u=u,
                           feedback=feedback, score=score,
                           banks=MARKET_DATA["banks"],
                           macro=MARKET_DATA["macro_vars"],
                           portfolio=MARKET_DATA["portfolio"],
                           max_dd=min_weekly,
                           ccyb_correct=ccyb_ans,
                           gap=gap)

# ── 实验6：银行风险控制综合实验 ─────────────────────────────

BANK_RISK_SCENARIO = {
    "bank_name": "兴华商业银行（模拟）",
    "total_assets": 2800,   # 亿元
    "loan_book": 1680,
    "tier1_capital": 196,
    "rwa": 2100,
    "deposits": 2100,
    "interbank_funding": 420,
    "loan_classification": {
        "正常":  {"amount": 1512, "provision_rate": 0.01},
        "关注":  {"amount": 126,  "provision_rate": 0.02},
        "次级":  {"amount": 25.2, "provision_rate": 0.25},
        "可疑":  {"amount": 12.6, "provision_rate": 0.50},
        "损失":  {"amount": 4.2,  "provision_rate": 1.00},
    },
    "market_positions": {
        "债券持仓": {"amount": 420, "duration": 5.2, "yield_shift": 1.0},
        "股票持仓": {"amount": 84,  "beta": 1.15,    "market_drop": 20},
        "外汇敞口": {"amount": 56,  "exchange_move": 5},
    },
    "liquidity": {
        "hqla": 280,            # 高质量流动资产
        "30d_outflow": 245,     # 30日净流出
        "stable_funding": 1890, # 可用稳定资金
        "required_funding": 1680,# 所需稳定资金
    },
    "risk_events": [
        {"id": 1, "type": "信用风险",
         "desc": "最大单一客户—恒大地产（模拟）贷款50亿元，已出现偿还困难迹象，逾期90天",
         "exposure": 50, "current_class": "正常",
         "correct_action": "下调至次级/可疑，计提专项拨备，上报大额风险暴露"},
        {"id": 2, "type": "市场风险",
         "desc": "持有5年期国债200亿元，若市场利率上升100bp，债券价格变动如何？",
         "bond_amount": 200, "duration": 5.2, "rate_shift": 1.0,
         "correct_loss": round(200 * 5.2 * 0.01, 1),
         "correct_action": "损失约10.4亿元；建议缩短久期或使用利率互换对冲"},
        {"id": 3, "type": "操作风险",
         "desc": "发现某支行行长与客户勾结，通过虚假贷款挪用资金1.2亿元，已立案侦查",
         "exposure": 1.2,
         "correct_action": "启动应急预案，全额计提损失拨备，向监管报告重大事件，内部审计全面排查"},
        {"id": 4, "type": "流动性风险",
         "desc": "市场传言该行资产质量恶化，同业拆借市场出现融资困难，当日到期同业负债80亿元无法续作",
         "exposure": 80,
         "correct_action": "动用HQLA（质押回购融资），启动流动性应急预案，向央行申请紧急流动性援助"},
    ]
}

@app.route("/lab/bankrisk")
@require_login
def lab_bankrisk():
    u = current_user()
    s = BANK_RISK_SCENARIO
    # 计算指标
    npl_amount = sum(
        v["amount"] for k, v in s["loan_classification"].items()
        if k in ("次级", "可疑", "损失"))
    npl_ratio = npl_amount / s["loan_book"] * 100
    provision = sum(
        v["amount"] * v["provision_rate"]
        for v in s["loan_classification"].values())
    tier1_ratio = s["tier1_capital"] / s["rwa"] * 100
    lcr = s["liquidity"]["hqla"] / s["liquidity"]["30d_outflow"] * 100
    nsfr = s["liquidity"]["stable_funding"] / s["liquidity"]["required_funding"] * 100
    metrics = {
        "tier1_ratio": round(tier1_ratio, 2),
        "npl_ratio": round(npl_ratio, 2),
        "provision": round(provision, 1),
        "lcr": round(lcr, 1),
        "nsfr": round(nsfr, 1),
    }
    return render_template("lab_bankrisk.html", u=u,
                           s=s, metrics=metrics)

@app.route("/lab/bankrisk/submit", methods=["POST"])
@require_login
def lab_bankrisk_submit():
    u = current_user()
    score = 0
    results = []
    s = BANK_RISK_SCENARIO

    for event in s["risk_events"]:
        ans = request.form.get(f"event_{event['id']}", "").strip()
        # 简单评分：答案包含关键词
        keywords_map = {
            1: ["次级", "可疑", "拨备", "下调"],
            2: ["10", "久期", "对冲", "利率互换"],
            3: ["应急", "拨备", "报告", "审计"],
            4: ["HQLA", "质押", "应急", "央行"],
        }
        kws = keywords_map.get(event["id"], [])
        matched = sum(1 for kw in kws if kw in ans)
        event_score = min(matched * 6, 20)
        score += event_score
        results.append({
            "event": event,
            "answer": ans,
            "event_score": event_score,
            "max_score": 20,
            "keywords": kws,
            "matched_keywords": [kw for kw in kws if kw in ans],
        })

    # 指标判断题
    ind_correct = {"q_lcr": "pass", "q_npl": "warning", "q_tier1": "pass"}
    ind_answers = {}
    for q_id, correct in ind_correct.items():
        ans = request.form.get(q_id, "")
        ind_answers[q_id] = {"answer": ans, "correct": ans == correct, "expected": correct}
        if ans == correct:
            score += 5

    db = get_db()
    db.execute(
        "INSERT INTO exp_submissions(exp_id,user_id,result,score)"
        " VALUES(15,?,?,?)",
        (u["id"], json.dumps({"events_answered": len(results)}), score))
    db.commit()
    db.close()

    s2 = BANK_RISK_SCENARIO
    npl_amount = sum(
        v["amount"] for k, v in s2["loan_classification"].items()
        if k in ("次级", "可疑", "损失"))
    npl_ratio = npl_amount / s2["loan_book"] * 100
    provision = sum(
        v["amount"] * v["provision_rate"]
        for v in s2["loan_classification"].values())
    tier1_ratio = s2["tier1_capital"] / s2["rwa"] * 100
    lcr = s2["liquidity"]["hqla"] / s2["liquidity"]["30d_outflow"] * 100
    nsfr = s2["liquidity"]["stable_funding"] / s2["liquidity"]["required_funding"] * 100
    metrics = {
        "tier1_ratio": round(tier1_ratio, 2),
        "npl_ratio": round(npl_ratio, 2),
        "provision": round(provision, 1),
        "lcr": round(lcr, 1),
        "nsfr": round(nsfr, 1),
    }
    ind_labels = {
        "pass": "达标，无需干预",
        "warning": "警告，需关注",
        "fail": "不达标，需整改",
        "normal": "正常范围",
        "adequate": "达标但空间有限",
        "insufficient": "不足，需补充资本",
        "critical": "严重，资产质量恶化",
        "": "（未作答）",
    }
    return render_template("lab_bankrisk_result.html", u=u,
                           s=s2, metrics=metrics,
                           results=results, score=score,
                           ind_answers=ind_answers,
                           ind_labels=ind_labels)

def create_app():
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    init_db()
    return app

create_app()

if __name__ == "__main__":
    print("=" * 50)
    print("  金融监管教学实验系统  启动中...")
    print("  访问地址: http://127.0.0.1:5000")
    print("  教师账号: teacher / teacher123")
    print("=" * 50)
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
