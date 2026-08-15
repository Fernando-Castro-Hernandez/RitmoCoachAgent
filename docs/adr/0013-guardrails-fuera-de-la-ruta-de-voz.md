# ADR 0013 — Guardrails de Bedrock fuera de la ruta de voz

- **Estado:** Aceptada
- **Fecha:** 2026-08-15
- **Relacionada:** [ADR 0002](0002-nova-2-sonic-en-bedrock.md), [ADR 0003](0003-motor-determinista-vs-llm-para-planes.md)

## Contexto

Un coach de running toca territorio sensible: dolor, lesiones, peso, suplementos.
Amazon Bedrock Guardrails es el servicio gestionado para filtrar justamente eso, y
la opción evidente era activarlo sobre el modelo.

Se creó el guardrail `ritmo-coach-safety` (`g4hhzrmtxbbo`) con cuatro temas
denegados —diagnóstico médico, prescripción, trastornos alimenticios y sustancias
de rendimiento—, `PROMPT_ATTACK` en HIGH y enmascarado de datos personales.

Al intentar aplicarlo apareció el obstáculo.

## El hallazgo

**Bedrock Guardrails no soporta `InvokeModelWithBidirectionalStream`**, que es la
única API por la que se invoca Nova Sonic.

Los guardrails inline se adjuntan mediante los encabezados
`X-Amzn-Bedrock-GuardrailIdentifier` y `X-Amzn-Bedrock-GuardrailVersion`, que están
documentados para `InvokeModel`, `InvokeModelWithResponseStream`, `Converse` y
`ConverseStream`. No existe equivalente para la API bidireccional, y Nova Sonic no
está disponible por ninguna de las otras.

## Decisión

**Defensa en profundidad, con el guardrail como segunda capa y no como primera.**

```
Capa 1 · PRIMARIA      packages/coach_domain/safety.py
                       Puerta determinista. Se evalúa ANTES de que el LLM
                       redacte. Veredicto rojo bloquea toda prescripción.
                       Es código puro, testeado, y no depende de ningún
                       servicio externo ni de que un prompt aguante.

Capa 2 · AUDITORÍA     ApplyGuardrail sobre las transcripciones
                       API independiente del modelo. Se llama de forma
                       asíncrona sobre el texto de entrada y de salida,
                       FUERA de la ruta crítica de latencia.
                       Alimenta `safety_gate_triggers` y el reproductor
                       de sesión.
```

`ApplyGuardrail` está disponible en el mismo cliente
(`aws_sdk_bedrock_runtime.client`), así que no añade dependencias.

## Por qué el orden importa

Poner el guardrail primero habría sido lo cómodo y lo equivocado. Un guardrail es
un clasificador probabilístico: puede fallar, y su latencia entra en el
presupuesto de la conversación. La regla que impide que el coach recete
entrenamiento a alguien con dolor de 7/10 **no puede ser probabilística**.

Que el servicio gestionado no aplicara aquí terminó siendo útil: obligó a que la
seguridad viviera donde debía vivir desde el principio.

## Consecuencias

- El guardrail **no bloquea en tiempo real** durante la conversación de voz.
  Detecta y registra; no interrumpe. Queda declarado como tal en el README, sin
  presentarlo como una barrera que no es.
- Si en el futuro el coach expone un modo de sólo texto sobre `Converse`, el mismo
  guardrail sí se puede adjuntar inline sin cambios.
- Queda pendiente publicar una versión del guardrail: hoy apunta a `DRAFT`, que
  sirve para desarrollo pero no es una referencia estable.
- El `inputAction` de las entidades PII está en `BLOCK`. Para un coach de voz
  conviene `ANONYMIZE`: bloquear el turno completo porque alguien mencionó un
  teléfono rompe la conversación en lugar de protegerla.
