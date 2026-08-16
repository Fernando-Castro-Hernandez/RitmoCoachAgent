# Los cinco flujos proactivos

Un flujo que sólo vive en una instancia no es un entregable. Estos cinco están
exportados y versionados aquí.

## La decisión que explica por qué los cinco son idénticos

Un nodo de horario de n8n tiene **una** zona horaria. Ritmo tiene una por
corredor. Programar «todos los días a las 6:00» significa elegir la mañana de
alguien y mandársela a todos los demás — que es el punto ciego 7 de la Fase 1.

Así que la responsabilidad se partió por donde debe:

| | responsabilidad |
|---|---|
| **n8n** | corre cada hora en punto, en UTC, y pregunta |
| **la API** | responde quién tiene las 6:00 **en su hora** ahora mismo |

Por eso los cinco flujos llevan el mismo cron (`5 * * * *`, en UTC) aunque uno
sea de la mañana, otro de la tarde y otro sólo del domingo: **la hora local no
la decide el flujo**. Añadir un corredor en Tokio no toca ningún JSON.

Y como la decisión quedó en Python, está probada: `test_automation.py` pone un
corredor en Ciudad de México y otro en Toronto y verifica que cada uno sale en
un instante UTC distinto.

Por lo mismo, los flujos no redactan nada. La API devuelve el `chat_id` y el
**texto ya hecho**. Eso mantiene dos reglas del producto donde hay pruebas que
las cubren, en vez de repartidas entre cinco JSON: que toda cifra venga del
motor, y que en rojo no se prescriba.

## Los cinco

| archivo | flujo | cuándo (hora del corredor) |
|---|---|---|
| `01-recordatorio-matutino.json` | `morning` | 6:00, si hoy toca entrenar |
| `02-checkin-post-sesion.json` | `checkin` | 20:00, si tenía sesión y no registró nada |
| `03-racha-en-riesgo.json` | `streak` | 18:00, tras 3 días sin correr |
| `04-resumen-semanal.json` | `weekly` | domingo 19:00 |
| `05-escalamiento-ambar-a-rojo.json` | `escalation` | a cualquier hora, en cuanto hay rojo |

Los cuatro primeros **callan cuando la puerta de seguridad está en rojo**. La
puerta no puede tener una puerta trasera por Telegram.

El quinto es el único que habla en rojo, y no prescribe: entrega el mensaje de
derivación que redactó el dominio, el mismo que el corredor oiría hablando. Y
ojo con de quién es la decisión: el escalamiento lo hace `assess()`, que
convierte una molestia de 3 o más que lleva tres días en rojo. El flujo sólo
reparte.

## El aviso perdido: dos políticas, a propósito

Los cuatro rutinarios se marcan como enviados **al entregarlos**. Si Telegram
falla, ese recordatorio se pierde y no se reintenta.

El escalamiento tiene un nodo más: confirma la entrega con `POST /api/automation/ack`
**después** de que Telegram aceptó. Si falla, vuelve a salir a la hora siguiente.

Un «buenos días» perdido no le cuesta nada a nadie. Un «para de entrenar y que
te vea alguien» perdido, sí.

## Importar

1. En n8n: **Workflows → Import from File**, uno por uno.
2. En **Settings → Variables** (o en el entorno de la instancia):

   ```
   RITMO_API_URL         https://<host-de-la-api>
   RITMO_AUTOMATION_KEY  el mismo valor de AUTOMATION_API_KEY en el .env de la API
   ```

   El acceso a `$env` desde los nodos requiere `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`
   en la instancia.

3. **Volver a elegir la credencial de Telegram** en el nodo «Mandar por
   Telegram» de cada flujo. Los identificadores de credencial son de cada
   instancia, y el token del bot no se versiona — por eso el JSON trae
   `REEMPLAZAR_AL_IMPORTAR`.

4. Activar. El primer barrido cae al minuto 5 de la hora siguiente.

## Probarlos sin esperar a las seis de la mañana

El endpoint acepta un instante fijo, así que la demostración por zona horaria no
depende del reloj:

```bash
# 12:00 UTC = 06:00 en Ciudad de México
curl -H "X-Ritmo-Automation-Key: $AUTOMATION_API_KEY" \
  "$RITMO_API_URL/api/automation/due/morning?at=2026-08-18T12:00:00Z"

# 10:00 UTC = 06:00 en Toronto
curl -H "X-Ritmo-Automation-Key: $AUTOMATION_API_KEY" \
  "$RITMO_API_URL/api/automation/due/morning?at=2026-08-18T10:00:00Z"
```

Ojo: los cuatro flujos rutinarios **marcan como enviado lo que devuelven**, así
que llamar al endpoint a mano gasta el aviso del día para ese corredor.

## Lo que todavía no está verificado

Estos JSON están escritos contra el formato de exportación de n8n, pero **no se
han importado a una instancia viva**: no hay una corriendo en este entorno. Lo
que sí está probado es todo lo que decide el comportamiento —a quién, cuándo,
con qué texto y cuándo callarse— porque eso vive en la API, con 37 pruebas.

Lo que queda por confirmar al importarlos es de plomería: que las versiones de
nodo coincidan con las de la instancia, que la credencial de Telegram quede
enganchada, y que `$env` esté accesible.
