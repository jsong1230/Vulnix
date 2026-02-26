# Vulnix Backend — Railway 배포용
# 모노레포 루트에서 backend/ 서브디렉토리를 빌드 컨텍스트로 사용

FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# ---- 런타임 이미지 ----
FROM python:3.11-slim AS runtime

RUN groupadd -r vulnix && useradd -r -g vulnix vulnix

WORKDIR /app

RUN pip install --no-cache-dir semgrep

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY backend/pyproject.toml .
COPY backend/src/ ./src/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini .

RUN chown -R vulnix:vulnix /app

USER vulnix

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
