FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY fixtures ./fixtures
RUN uv sync --frozen --no-dev && playwright install --with-deps chromium

COPY config.example.yml ./config.yml

EXPOSE 8501
CMD ["streamlit", "run", "src/ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
