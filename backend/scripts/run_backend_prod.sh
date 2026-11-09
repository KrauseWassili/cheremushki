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
# sind fatal: Jeder Error – Tag security, config.E001 (SECRET_KEY Platzhalter
# oder < 50 Zeichen), bot.E001/E002 (Webhook-Secret leer bzw. Platzhalter oder
# < 32 Zeichen), accounts.E001/E002 (ohne Resend geht keine Aktivierungs-/
# Reset-Mail raus), accounts.E003 (Resend-Key ohne "re_" oder Platzhalter) –
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
# erratbaren Namen und alten EXIF-Daten sollen nicht live bleiben. Idempotent;
# bei aufgeräumtem Bestand prüft jeder Lauf trotzdem, ob die referenzierten
# Dateien existieren (ein exists() pro Avatar) und listet das Verzeichnis.
#
# Bewusst OHNE --clear-missing: Ein falsch gemountetes Media-Volume ließe
# sonst alle Avatare "fehlen", und der Start würde sie aus der DB löschen.
# Tote Verweise stehen nur im Log; leeren manuell mit
#   docker compose exec backend python manage.py cleanup_legacy_avatars --clear-missing
#
# Nicht fatal (anders als check --deploy oben): Ein Abbruch (leeres
# Avatar-Verzeichnis bei vorhandenen Verweisen) oder ein Fehler beim Aufräumen
# ist ein Fall fürs Log, kein Grund, das Backend nicht zu starten –
# public_media sperrt die alten Namen ohnehin.
echo "Cleaning up legacy avatar files"
if ! python ./manage.py cleanup_legacy_avatars; then
    echo "WARNUNG: cleanup_legacy_avatars fehlgeschlagen oder abgebrochen (siehe oben) – Start geht weiter." >&2
fi

# Füllt STATIC_ROOT (Volume static), aus dem WhiteNoise ausliefert.
echo "Collecting static files"
python ./manage.py collectstatic --noinput

# ASGI statt runserver: Die Views sind adrf-async. Bewusst ohne
# --proxy-headers – die Client-IP fürs Throttling liest DRF über NUM_PROXIES
# selbst aus X-Forwarded-For; daphne würde sonst einen vom Client
# mitgeschickten Header-Wert als REMOTE_ADDR übernehmen.
echo "Starting daphne on 0.0.0.0:8000"
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
