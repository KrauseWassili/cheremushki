# Basis-Image per Digest gepinnt: Ein Tag wie 3.13-slim-bookworm wird bei
# jedem Python-/Debian-Patch neu vergeben, der Build wäre damit nicht
# reproduzierbar. Tag zur Lesbarkeit: python:3.13-slim-bookworm. Update:
#   docker pull python:3.13-slim-bookworm
#   docker inspect --format '{{index .RepoDigests 0}}' python:3.13-slim-bookworm
# und den Digest in BEIDEN Stages ersetzen.

# --- Build-Stage: Compiler und Header nur hier ------------------------------ #
FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72 AS builder

# gcc/Header für den Fall, dass eine Abhängigkeit ohne passendes Wheel aus dem
# sdist gebaut werden muss. Bleiben in dieser Stage, das finale Image enthält
# keinen Compiler.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# Eigene venv außerhalb von /src: Die Dev-Override-Datei bind-mountet ./backend
# nach /src, eine venv dort würde überdeckt.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /src

# --frozen: exakt die Versionen aus uv.lock, ein veraltetes Lockfile bricht den
# Build ab, statt still neu aufzulösen. --no-dev: black & Co. gehören nicht
# ins Image.
#
# uv-Version bewusst gepinnt: uv.lock trägt eine Format-Revision (aktuell
# "revision = 2"), die die schreibende uv-Version festlegt. Ein älteres uv
# kann ein neueres Lockfile nicht lesen und bricht ab; ein neueres uv liest
# das alte, schreibt beim nächsten `uv lock` lokal aber evtl. eine höhere
# Revision. Wer uv lokal aktualisiert und das Lockfile neu schreibt, hebt
# diese Version mit an (und umgekehrt).
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.7.19 \
 && uv sync --frozen --no-dev --no-install-project --no-cache

# --- Laufzeit-Image ------------------------------------------------------- #
FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72

# Nur Laufzeitbibliotheken: libpq5 für psycopg, libjpeg/zlib für Pillow,
# curl für den Healthcheck in docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    curl \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src

# Feste UID/GID 1000: Im Dev-Setup schreibt der Container über den Bind-Mount
# nach backend/media – mit derselben UID wie der übliche Host-Nutzer gehören
# die Dateien danach nicht root.
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --home-dir /src --shell /usr/sbin/nologin app

# venv und Code gehören root und sind für app nur lesbar: Eine Lücke im
# Webprozess soll weder Code noch installierte Pakete überschreiben können.
COPY --from=builder /opt/venv /opt/venv
COPY . /src/

COPY ./scripts/migrations.sh /bin/migrations.sh
RUN chmod +x /bin/migrations.sh

# Schreibbar für app nur, was zur Laufzeit beschrieben wird: media/ (Avatare)
# und staticfiles/ (collectstatic im Startskript). Die Mountpunkte der
# benannten Volumes vorab als app anlegen: Docker befüllt ein neues, leeres
# Volume beim ersten Start mit Inhalt UND Eigentümer des Image-Verzeichnisses
# – ohne das gehörten sie root, und collectstatic bzw. Avatar-Uploads
# schlügen mit PermissionError fehl. celery beat schreibt nach /tmp.
RUN mkdir -p /src/media /src/staticfiles \
 && chown app:app /src/media /src/staticfiles \
 && touch ./.env

# PYTHONUNBUFFERED=1: Logs sofort auf stdout statt gepuffert.
# PYTHONDONTWRITEBYTECODE=1: Keine __pycache__-Dateien (/src ist für app
# ohnehin nicht schreibbar).
# COLUMNS=80: Breite für die Celery-Ausgabe.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COLUMNS=80

USER app

# Kein HEALTHCHECK hier: worker, celery_beat und celery_flower laufen aus
# demselben Image und lauschen nicht auf 8000. Der Healthcheck des Webdienstes
# steht deshalb in docker-compose.yml beim backend.
EXPOSE 8000
CMD ["bash", "./scripts/run_backend_prod.sh"]
