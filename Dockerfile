FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install project along with its dependencies.
COPY pyproject.toml /app/
COPY core /app/core
COPY practice /app/practice
COPY tournament /app/tournament
COPY sample_bot.py /app/sample_bot.py
COPY scripts /app/scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

# Default to the practice server; Fly launch can override this command if needed.
CMD ["python", "-m", "practice.server", "--host", "0.0.0.0", "--port", "8080"]
