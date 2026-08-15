# Documentación — Ritmo

Coach de voz conversacional para runners. Reto técnico de Adivor.

## Fases

| # | Documento | Qué contiene |
|---|---|---|
| — | [Reto original](00-reto-original.md) | Transcripción del correo de Adivor y requisitos extraídos |
| 1 | [Alcance y viabilidad](fases/fase-1-alcance-y-viabilidad.html) | Investigación de Adivor y mercado, reglas de dominio, interfaz, dictamen de stack y despliegue |
| 2 | [Investigación de usuario](fases/fase-2-investigacion-usuario.md) | Entrevista a corredor experimentado, la pirámide y reajuste de alcance |
| 3 | [Plan de implementación](fases/fase-3-plan-de-implementacion.md) | Seis fases de ejecución, tarea por tarea, viernes a lunes |
| — | [Prompts del sistema](prompts.md) | Las cuatro capas del prompt, la regla de clarificación autónoma y cómo se verifica |
| — | [Contexto de producto](PRODUCT.md) | Qué es, para quién, dónde se usa y las cuatro reglas que no se negocian |
| — | [Brief de diseño](DESIGN.md) | Encargo, restricciones físicas y estados del orbe. Abierto en lo estético |

La Fase 1 es un documento HTML: ábrelo en el navegador o consulta la
[versión publicada](https://claude.ai/code/artifact/85cb6fa3-e64b-4037-a117-a3202dbc1474).

## Decisiones de arquitectura

| ADR | Decisión | Estado |
|---|---|---|
| 0001 | Speech-to-speech nativo frente a STT + LLM + TTS | Pendiente (tarea F4) |
| 0002 | Nova 2 Sonic en Bedrock | Pendiente (se completa en A2) |
| 0003 | Motor determinista frente a LLM para los planes | Pendiente (tarea F4) |
| 0004 | Telegram sobre WhatsApp | Pendiente (tarea F4) |
| 0005 | n8n para orquestación proactiva | Pendiente (tarea F4) |
| 0006 | Proxy WebSocket para credenciales | Pendiente (tarea F4) |
| 0007 | Renovación de sesión a los 8 minutos | Pendiente (tarea F4) |
| [0008](adr/0008-plataforma-de-despliegue.md) | Plataforma de despliegue: EC2 en us-east-1 | Aceptada |
| [0009](adr/0009-stack-tecnologico-definitivo.md) | Stack tecnológico definitivo | Aceptada |
| [0010](adr/0010-fuera-de-alcance-gps-y-tracking.md) | Sin rastreo GPS | Aceptada |
| [0011](adr/0011-modulo-de-tecnica-de-carrera.md) | Módulo de técnica de carrera | Aceptada |
| [0012](adr/0012-observabilidad-y-metricas.md) | Observabilidad, métricas y DevOps | Aceptada |
| [0013](adr/0013-guardrails-fuera-de-la-ruta-de-voz.md) | Guardrails de Bedrock fuera de la ruta de voz | Aceptada |
| [0014](adr/0014-arquitectura-multimodelo-vision.md) | Arquitectura multi-nube: voz en Bedrock, visión en Anthropic | Aceptada |

## La tesis en un párrafo

Los generadores de planes con IA ya existen y están lesionando gente: el *Wall Street
Journal* reportó fisioterapeutas atendiendo casos relacionados con Runna cada semana.
La causa citada es que **el algoritmo toma al corredor por su palabra, y el corredor
novato rara vez se conoce tan bien como cree**. Un formulario captura lo que el
corredor afirma; una conversación captura lo que revela. Por eso la voz no es adorno.
Y por eso el LLM nunca calcula un plan: la aritmética vive en un motor determinista y
verificable, y el modelo sólo escucha, consulta y explica.

Y por eso el coach **se niega a generar un plan cuando le falta contexto**: pregunta
antes de prescribir, incluso si el corredor insiste en que no le pregunten. Los datos
duros llegan por formulario, los matices por voz, y los entrenamientos por una foto de
la pantalla del reloj —sin OAuth, sin Garmin, sin Strava (ADR 0014).
