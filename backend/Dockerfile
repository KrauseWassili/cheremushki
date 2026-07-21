FROM python:3.13-slim-bookworm

# Install system dependencies for Postrgres and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY pyproject.toml uv.lock ./
# Install uv and project dependencies
RUN pip install -U pip uv && uv pip install --system .
COPY . /src/

COPY ./scripts/migrations.sh /bin/migrations.sh
RUN chmod +x /bin/migrations.sh

# Create empty env-file to avoid warnings
RUN touch ./.env

# PYTHONUNBUFFERED=1: Prevents buffering of outputs → better logs.
# PYTHONDONTWRITEBYTECODE=1: Does not write __pycache__ files in the container.
# Set variable for celery
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COLUMNS=80

EXPOSE 8000
CMD ["./scripts/run_backend_local.sh"]
