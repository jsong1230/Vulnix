"""
테스트용 취약 코드 샘플 (Python)
- SQL Injection, XSS, Hardcoded Credentials, Sensitive Data Logging 취약점 포함
"""

from flask import Flask, request, render_template_string
from sqlalchemy import create_engine

app = Flask(__name__)

# CWE-259: 하드코딩된 비밀번호 (Hardcoded Credentials)
DB_PASSWORD = "admin123"
DB_HOST = "localhost"
DB_URL = f"postgresql://admin:{DB_PASSWORD}@{DB_HOST}/mydb"

engine = create_engine(DB_URL)


@app.route("/users/<int:user_id>")
def get_user(user_id):
    """CWE-89: SQL Injection 취약점"""
    # 취약점: 사용자 입력이 SQL 쿼리에 직접 삽입됨
    with engine.connect() as db:
        # start_line: 24, end_line: 24
        result = db.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return {"user": result.fetchone()}


@app.route("/search")
def search():
    """CWE-79: XSS 취약점"""
    query = request.args.get("q", "")
    # 취약점: 사용자 입력이 HTML 이스케이프 없이 템플릿에 삽입됨
    # start_line: 35, end_line: 35
    return render_template_string(f"<h1>검색 결과: {query}</h1>")


@app.route("/login", methods=["POST"])
def login():
    """CWE-532: 민감 정보 로깅 취약점"""
    import logging

    username = request.form.get("username")
    password = request.form.get("password")

    # 취약점: 비밀번호가 로그에 기록됨
    # start_line: 48, end_line: 48
    logging.info(f"로그인 시도: username={username}, password={password}")

    if username == "admin" and password == DB_PASSWORD:
        return {"status": "success"}
    return {"status": "failed"}, 401


@app.route("/profile")
def profile():
    """안전한 코드 (취약점 없음)"""
    user_id = request.args.get("id", "")
    # 파라미터 바인딩 방식으로 SQL Injection 방지
    with engine.connect() as db:
        from sqlalchemy import text
        result = db.execute(
            text("SELECT * FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
    return {"user": result.fetchone()}
