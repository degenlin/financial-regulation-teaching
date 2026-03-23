import sys, os

# 将 教学系统/ 加入模块搜索路径，并切换工作目录（确保 DB、模板路径正确）
_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "教学系统")
sys.path.insert(0, _base)
os.chdir(_base)

from app import app, create_app

create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
