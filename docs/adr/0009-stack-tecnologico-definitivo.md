# ADR 0009 — Stack tecnológico definitivo

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Depende de:** [ADR 0008](0008-plataforma-de-despliegue.md)

## Contexto

El ADR 0008 fija un contenedor de larga vida en EC2 `us-east-1` con Docker Compose.
Eso deja libre la elección de lenguajes y frameworks, sujeta a tres presiones:
el camino más corto y menos riesgoso al streaming bidireccional de Nova Sonic,
la testabilidad del motor de dominio, y 4 días de calendario.

## Decisión

| Capa | Elección | Razón determinante |
|---|---|---|
| **Frontend** | React 19 + TypeScript + Vite | Sin SSR que justifique Next.js — no usamos Vercel. Vite compila rápido y produce estáticos que Caddy sirve directo. |
| **Captura de audio** | `AudioWorkletNode` nativo | `ScriptProcessorNode` está deprecado y corre en el hilo principal. El worklet resamplea 48 kHz Float32 → 16 kHz PCM16 fuera del hilo de UI. |
| **Reproducción** | `AudioContext` + ring buffer | Evita huecos entre chunks. Sin esto la voz suena entrecortada. |
| **Estado de UI** | Zustand | La máquina de estados del orbe de voz tiene 12 estados; Zustand la modela sin ceremonia. |
| **Estilos** | Tailwind v4 | Velocidad de iteración. El diseño vive en tokens, no en CSS disperso. |
| **Backend** | **Python 3.13 + FastAPI + uvicorn** | Ver justificación abajo. WebSockets nativos y `async` que encaja con el modelo de streaming. |
| **Cliente Bedrock** | `aws-sdk-bedrock-runtime` (cliente experimental de streaming bidireccional) | Es la ruta documentada por AWS. Partimos del ejemplo oficial de `aws-samples`, no de cero. |
| **Motor de dominio** | Paquete Python puro, sin I/O | Cero dependencias de red o LLM. Testeable con `pytest` + `hypothesis`. |
| **Base de datos** | PostgreSQL 17 + SQLAlchemy 2 + Alembic | Migraciones versionadas. `pgvector` disponible para memoria semántica. n8n lee la misma instancia. |
| **Automatización** | n8n self-hosted (mismo compose) | Alineación con Adivor (ADR 0005). Workflows exportados a JSON y versionados. |
| **Reverse proxy** | Caddy 2 | HTTPS automático y proxy de WebSocket sin configuración. |
| **Observabilidad** | Langfuse + métricas propias | Ver [ADR 0012](0012-observabilidad-y-metricas.md). |
| **CI** | GitHub Actions | Lint, tipos, pruebas del motor y suite de evals en cada push. |

## Por qué Python y no Node en el backend

Es la única elección del stack que estuvo genuinamente reñida, así que se documenta
el criterio completo.

**A favor de Node:** un solo lenguaje en todo el repo, tipos compartidos entre
frontend y backend, y un único `package.json`.

**A favor de Python, que es lo que decide:**

1. **Los ejemplos oficiales de Nova Sonic son Python primero.** El repositorio
   `aws-samples/amazon-nova-samples/speech-to-speech/amazon-nova-2-sonic` trae la
   implementación de consola en Python, incluido **el patrón de renovación de sesión
   a los 8 minutos** — que es justo la parte más delicada y menos documentada del
   sistema. Copiar un patrón probado en el punto de mayor riesgo vale más que la
   comodidad de un lenguaje único.
2. **El motor de dominio se prueba mejor.** Las reglas R1–R8 son invariantes
   numéricos, y `hypothesis` permite pruebas basadas en propiedades: *generar miles
   de planes aleatorios y afirmar que ninguno viola R1 ni R3*. Eso es evidencia
   mucho más fuerte que una decena de casos escritos a mano, y es exactamente el
   tipo de rigor que hace concreta la frase «resultados verificables».
3. **El riesgo del lenguaje dual es bajo.** La frontera entre frontend y backend son
   frames de audio y un puñado de mensajes JSON, no un modelo de dominio compartido.
   Se define una vez con Pydantic del lado servidor y tipos TypeScript del lado
   cliente; el costo de mantenerlos sincronizados es marginal en un proyecto de este
   tamaño.

## Consecuencias

- El repositorio es políglota. Se mitiga con un `Makefile` que unifica los comandos
  (`make dev`, `make test`, `make evals`) para que nadie tenga que recordar dos
  gestores de paquetes.
- `packages/coach-domain` no importa nada de FastAPI, boto3 ni la base de datos.
  Esa restricción se verifica en CI: si alguien introduce una dependencia de red en
  el motor, el pipeline falla.
- Los tipos entre frontend y backend pueden desincronizarse. Aceptado: la superficie
  es pequeña y está cubierta por pruebas de integración del WebSocket.
