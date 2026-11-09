#!/bin/bash
# Produktionsstart des Backends. Kein "sleep" wie in run_backend_local.sh:
# docker-compose.yml startet diesen Dienst erst, wenn db und redis ihre
# Healthchecks bestanden haben (condition: service_healthy).
#
# set -e: Schlägt migrate fehl, soll der Container mit Fehler enden (und von
# restart: unless-stopped neu versucht werden), statt mit altem Schema zu
# laufen.
set -euo pipefail

# Deploy-Checks (Resend-Key, Telegram-Webhook-Secret, Security-Settings)
# sind fatal: Jeder Error – Tag security, bot.E001 (leeres Webhook-Secret),
# accounts.E001/E002 (ohne Resend geht keine Aktivierungs-/Reset-Mail raus) –
# bricht den Start per set -e ab. Der Container hängt dann sichtbar im
# Restart-Loop (docker compose ps/logs backend) – besser als eine unsichere
# oder stumm kaputte Konfiguration, die live geht und niemandem auffällt.
#
# Toleriert werden nur Warnings (z. B. bot.W001–W004, security.W*): Sie stehen
# im Log, beenden check aber nicht mit Exit-Code != 0 (Default --fail-level
# ERROR). Wer einen Punkt bewusst hinnimmt, stuft ihn im Check als Warning
# ein oder setzt SILENCED_SYSTEM_CHECKS – nicht hier im Skript.
echo "Running deploy checks (manage.py check --deploy)"
python ./manage.py check --deploy

echo "Applying database migrations"
python ./manage.py migrate --noinput

# Nach migrate (braucht das aktuelle Schema), vor daphne: Avatar-Altlasten mit
# erratbaren Namen und alten EXIF-Daten dürfen nicht live gehen. Idempotent,
# bei aufgeräumtem Bestand ein reiner Verzeichnis-Scan.
echo "Cleaning up legacy avatar files"
python ./manage.py cleanup_legacy_avatars

# Füllt STATIC_ROOT (Volume static), aus dem WhiteNoise ausliefert.
echo "Collecting static files"
python ./manage.py collectstatic --noinput

# ASGI statt runserver: Die Views sind adrf-async. Bewusst ohne
# --proxy-headers – die Client-IP fürs Throttling liest DRF über NUM_PROXIES
# selbst aus X-Forwarded-For; daphne würde sonst einen vom Client
# mitgeschickten Header-Wert als REMOTE_ADDR übernehmen.
echo "Starting daphne on 0.0.0.0:8000"
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
