#!/usr/bin/env bash
#
# Despliegue de Ritmo en la instancia EC2. Se ejecuta EN LA MÁQUINA, no aquí:
# lo lanza `aws ssm send-command`, así que no hay SSH abierto ni llave privada
# que custodiar. El puerto 22 del grupo de seguridad está cerrado a propósito.
#
# Es idempotente: se puede volver a correr para desplegar un commit nuevo.
#
#   sudo /opt/ritmo/infra/deploy.sh
#
# Espera encontrar `/opt/ritmo/.env` ya escrito. Ese archivo NO viaja en el
# user-data ni en el repositorio: lo deposita `scripts/deploy_remote.py` por
# SSM. El user-data se lee desde dentro de la instancia por IMDS, así que
# cualquier proceso de la caja podría leer lo que se ponga ahí.

set -euo pipefail

RAIZ=/opt/ritmo
cd "$RAIZ"

echo "── traer el código ──────────────────────────────────────"
git fetch --all --prune
git reset --hard origin/main
git log --oneline -1

# El archivo de local no puede existir aquí: monta ~/.aws como volumen y en el
# servidor las credenciales las da el rol de instancia. Ver su cabecera.
rm -f docker-compose.override.yml

echo "── construir el frontend ────────────────────────────────"
# Se compila en la máquina para que lo que sirve Caddy salga del mismo commit
# que la API. Subir un `dist` construido en otro sitio es cómo acaban
# desincronizados sin que nadie lo note.
npm --prefix apps/web ci
npm --prefix apps/web run build

echo "── levantar ─────────────────────────────────────────────"
# `migrate` corre y sale antes de que la API acepte tráfico; está declarado
# como dependencia con `service_completed_successfully`.
docker compose pull --quiet --ignore-buildable || true
docker compose up -d --build --remove-orphans

echo "── esperar a que la API responda ────────────────────────"
for i in $(seq 1 60); do
  if docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" 2>/dev/null; then
    echo "la API responde"
    break
  fi
  sleep 5
done

echo "── estado ───────────────────────────────────────────────"
docker compose ps
echo
echo "configuración efectiva:"
docker compose exec -T api python -c "
import json, urllib.request
d = json.loads(urllib.request.urlopen('http://localhost:8000/api/config').read())
for k, v in d.items():
    print('  {:32} {}'.format(k, v))
"
