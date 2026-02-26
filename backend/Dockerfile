# 멀티스테이지 빌드 — 최종 이미지 크기 최소화
FROM python:3.11-slim AS builder

WORKDIR /app

# 시스템 패키지 설치 (빌드 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사 및 설치
COPY pyproject.toml .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# ---- 런타임 이미지 ----
FROM python:3.11-slim AS runtime

# 보안: non-root 사용자 생성
RUN groupadd -r vulnix && useradd -r -g vulnix vulnix

WORKDIR /app

# Semgrep 설치 (정적 분석 도구)
RUN pip install --no-cache-dir semgrep

# 빌더 스테이지에서 설치된 패키지 복사
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 소스 코드 복사
COPY pyproject.toml .
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# 소유권 변경
RUN chown -R vulnix:vulnix /app

# non-root 사용자로 전환
USER vulnix

EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
