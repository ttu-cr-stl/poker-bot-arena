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

# Default to the 4-seat tournament host tuned for ~45-minute events.
CMD ["python", "-m", "tournament", "--host", "0.0.0.0", "--port", "8080", "--seats", "4", "--starting-stack", "8000", "--sb", "100", "--bb", "200"]
