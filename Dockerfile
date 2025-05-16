FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /code

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock /code/
RUN uv sync --frozen

ENV PATH="/code/.venv/bin:$PATH"

COPY . /code/
