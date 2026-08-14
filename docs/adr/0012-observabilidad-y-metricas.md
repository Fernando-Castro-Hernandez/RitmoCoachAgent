# ADR 0012 — Observabilidad, métricas y DevOps

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Depende de:** [ADR 0008](0008-plataforma-de-despliegue.md), [ADR 0009](0009-stack-tecnologico-definitivo.md)

## Contexto

Adivor define su misión como **«consultoría de IA con resultados verificables»** y
sus valores como **«confianza, claridad y responsabilidad en cada entregable»**. Es
el vocabulario de una empresa que evalúa evidencia, no demos.

Además hay una necesidad puramente técnica: un sistema de voz en streaming es
prácticamente imposible de depurar sin trazas. Cuando una respuesta llega tarde o el
coach dice algo raro, sin instrumentación no hay forma de saber si el problema fue la
red, el modelo, una herramienta lenta o el prompt.

## Decisión

Tres capas, cada una con un propósito distinto y ninguna opcional.

### 1 · Trazas de conversación — Langfuse Cloud

Cada sesión de voz produce una traza con turnos, transcripciones, llamadas a
herramientas, latencias por tramo y la decisión final del motor.

Se usa **el plan gratuito de Langfuse Cloud**, no autoalojado. Langfuse v3 requiere
Postgres, ClickHouse, Redis y almacenamiento compatible con S3: es una decisión
correcta en producción y desproporcionada para una instancia `t4g.small` con 4 días
de calendario. El autoalojado queda documentado como ruta de producción.

### 2 · Métricas de sistema — endpoint propio

Un endpoint `/metrics` en formato Prometheus, alimentado por instrumentación
explícita en el puente de audio. Prometheus y Grafana **no** se despliegan en el
MVP; el endpoint existe para que puedan conectarse después, y los números se
publican en el README.

### 3 · Reproducción de sesión — `/debug/sessions/{id}`

Una vista que reconstruye una conversación completa: qué se dijo, qué herramientas
se invocaron con qué argumentos, cuánto tardó cada tramo y qué decidió el motor.
Resuelve el punto ciego que Fase 1 identificó como el número 10.

## Métricas clave

### Latencia de voz

| Métrica | Definición | Objetivo |
|---|---|---|
| `ttfa_ms` | **Time To First Audio.** Fin del habla del usuario → primer byte de audio del coach. | p50 < 800 ms · p95 < 1500 ms |
| `barge_in_stop_ms` | Usuario empieza a hablar → el audio del coach se detiene. | < 200 ms |
| `tool_call_ms` | Duración por herramienta invocada. | p95 < 300 ms |
| `renewal_gap_ms` | Hueco perceptible durante la renovación de conexión a los 8 min. | < 50 ms |

`ttfa_ms` es **la métrica titular del proyecto**. Es la que determina si la
conversación se siente humana, y es el número que va en el README.

### Calidad del dominio — las que hacen literal «resultados verificables»

| Métrica | Definición | Objetivo |
|---|---|---|
| `invariant_violations_total` | Planes emitidos que violan R1–R8. Se valida cada plan antes de entregarlo. | **0, siempre** |
| `red_flag_recall` | Escenarios de bandera roja del suite de evals correctamente escalados a rojo. | **100 %** |
| `numbers_from_engine_pct` | Porcentaje de cifras pronunciadas por el coach que son rastreables a un resultado de herramienta. | **100 %** |
| `safety_gate_triggers{nivel}` | Conteo de activaciones por verde, ámbar y rojo. | — (observación) |

`numbers_from_engine_pct` merece explicación porque es poco común: mide
directamente la regla del ADR 0003 —*si es un número, viene del motor*— comparando
los numerales del texto emitido contra los valores devueltos por herramientas en esa
misma traza. Es una **medida cuantitativa de alucinación numérica**, no una promesa
de prompt. Cualquier valor por debajo de 100 % es un fallo reportable.

### Producto

| Métrica | Para qué sirve |
|---|---|
| `checkin_completion_rate` | ¿El usuario termina el check-in o lo abandona? |
| `session_duration_s` | Debe rondar 90–180 s. Si sube mucho, el coach está hablando de más. |
| `proactive_response_rate` | Porcentaje de recordatorios de Telegram que producen respuesta. Mide si lo proactivo aporta o molesta. |

## DevOps

Alcance calibrado a 4 días: se automatiza lo que protege la calidad, se deja manual
lo que sólo ahorraría minutos.

### CI — GitHub Actions en cada push

```
ruff + mypy            → estilo y tipos
pytest packages/       → motor de dominio, cobertura mínima 95 %
hypothesis             → propiedades: ningún plan generado viola R1–R8
pytest apps/api        → integración del WebSocket
python evals/run.py    → suite de escenarios golden
  └─ falla el build si red_flag_recall < 100 %
docker build           → verifica que las imágenes compilan
check-domain-purity    → falla si coach-domain importa red, boto3 o la BD
```

Los dos últimos controles son los interesantes: **el pipeline falla si el motor de
dominio se contamina con I/O, y falla si el sistema deja de detectar una bandera
roja.** La arquitectura queda protegida por CI, no por disciplina.

### Entorno y despliegue

- `docker-compose.yml` idéntico en local y producción: paridad dev/prod real.
- `make dev` · `make test` · `make evals` · `make deploy`.
- Despliegue por SSH con `docker compose pull && up -d`. **Deliberadamente manual**:
  un pipeline de entrega continua completo no aporta a un entregable de 4 días y sí
  consume horas. Declarado como tal en el README.
- Pre-commit con ruff. Commits convencionales.

### Secretos

- **AWS: ninguno.** Rol IAM de instancia (ADR 0008).
- Token de Telegram y claves de Langfuse en `.env` del servidor, con `.env.example`
  versionado y `.env` en `.gitignore`.

## Consecuencias

- El README puede publicar números medidos en lugar de adjetivos. Es la diferencia
  entre «baja latencia» y «p50 de 640 ms medido en 50 turnos desde Guadalajara».
- Langfuse Cloud implica enviar transcripciones a un tercero. Para una demo con datos
  sintéticos es aceptable; **queda anotado como decisión a revisar** si el sistema
  manejara datos reales de salud de usuarios.
- La instrumentación añade trabajo a cada tramo del puente de audio. Se acepta:
  sin ella el sistema no es depurable.
