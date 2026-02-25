"""Alembic 마이그레이션 환경 설정 — async SQLAlchemy 연동"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# alembic.ini 로거 설정 적용
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 환경변수에서 DATABASE_URL 로드
import os
import sys

# src 경로를 모듈 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import get_settings
from src.models.base import Base

# 모든 모델을 import하여 Base.metadata에 등록
from src.models import user, team, repository, scan_job, vulnerability, patch_pr  # noqa: F401

settings = get_settings()

# DATABASE_URL을 alembic config에 주입 (asyncpg -> psycopg2로 변환)
# Alembic은 동기 드라이버를 사용하므로 변환 필요
sync_database_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql://"
)
config.set_main_option("sqlalchemy.url", sync_database_url)

# 마이그레이션 대상 메타데이터
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """오프라인 모드: SQL 스크립트만 생성 (DB 연결 없음)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """동기 연결로 마이그레이션 실행"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 엔진으로 마이그레이션 실행"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드: 실제 DB에 마이그레이션 적용"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
