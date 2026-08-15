# ADR 0002 — Nova 2 Sonic en Amazon Bedrock

- **Estado:** Aceptada — verificada empíricamente
- **Fecha:** 2026-08-15
- **Verificado por:** `spikes/nova_probe.py` (tarea A2)

## Contexto

El reto pide un chatbot de **voz conversacional**. Hay dos caminos: encadenar
speech-to-text, LLM y text-to-speech (ADR 0001), o usar un modelo nativo de
voz a voz. Se eligió el segundo, y en AWS eso significa Amazon Nova Sonic.

Quedaba por comprobar si la cuenta podía realmente usarlo.

## Decisión

**`amazon.nova-2-sonic-v1:0` en `us-east-1`, voz `carlos`.**

Verificado de extremo a extremo el 15 de agosto de 2026: el modelo respondió en
español con 38 chunks de audio y el texto *«Sí, te escucho perfectamente, ¿en qué
te puedo ayudar?»*.

## El susto de la cuota, y por qué no aplicaba

La cuenta (creada el 20 de julio de 2026) arrancó en el **Free Plan** de AWS. Toda
invocación de modelos de texto fallaba con:

```
ThrottlingException: Too many tokens per day, please wait before trying again.
```

Service Quotas mostraba `Model invocation max tokens per day` en `0.0` para todos
los modelos Nova, y `On-demand InvokeModel concurrent requests for Amazon Nova 2
Sonic` también en `0.0`.

Se cambió la cuenta a **Paid Plan** (`accountPlanType: PAID`, $131.22 de crédito).
Las cuotas publicadas **siguieron en cero** y los modelos de texto siguieron
throttleados.

**Y sin embargo el stream de voz abrió sin problema.** La conclusión, comprobada
en lugar de supuesta:

> La cuota `max tokens per day` gobierna los modelos de **texto**. Los modelos de
> **voz** se gobiernan por streams concurrentes, y ese camino estaba abierto todo
> el tiempo. El valor `0.0` que reporta Service Quotas para Nova 2 Sonic no
> refleja la capacidad real.

Lección que vale más que el dato: **una cuota publicada no es una prueba.** La
única forma de saber si un modelo funciona es abrir el stream.

## Protocolo observado

Descubierto durante el spike, con los errores que costó llegar a él.

### Configuración del cliente

```python
Config(
    endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
    region=region,
    aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
)
```

`smithy` **no tiene resolvedor de perfil de AWS**: sólo lee variables de entorno
o IMDS. Exportarlas a mano antes de arrancar funciona, pero la sintaxis cambia
según la terminal —`eval "$(aws configure export-credentials --format env)"` en
bash, `aws configure export-credentials --format powershell | Invoke-Expression`
en PowerShell— y olvidarlo produce un fallo confuso a mitad de sesión.

Por eso `apps/api/credentials.py` las resuelve al arrancar: si las variables no
están puestas, se las pregunta al AWS CLI con
`aws configure export-credentials --format process`, que sí entiende perfiles,
SSO y roles asumidos. `/api/config` reporta `aws_credentials_resolved` para
confirmarlo de un vistazo.

En producción no interviene: el rol de instancia del EC2 llega por IMDS y las
variables ya vienen puestas (ADR 0008).

### Secuencia de eventos

```
sessionStart      → inferenceConfiguration: maxTokens, topP, temperature
promptStart       → textOutputConfiguration + audioOutputConfiguration (voiceId)
contentStart      → type TEXT,  role SYSTEM   → textInput → contentEnd
contentStart      → type TEXT,  role USER     → textInput → contentEnd
contentStart      → type AUDIO, role USER     → audioInput → contentEnd
   ← completionStart, contentStart, textOutput, audioOutput…, contentEnd, usageEvent
promptEnd
sessionEnd
```

### Tres reglas que no están en la documentación y costaron el spike

1. **El `voiceId` va en minúsculas.** La documentación muestra «Carlos» y «Lupe»,
   pero la API responde `ValidationException: Received invalid id: 'Carlos'`. Los
   valores correctos son `carlos`, `lupe`, `tiffany`, `matthew`.

2. **El prompt exige al menos un bloque de contenido de tipo `AUDIO`**, aunque la
   entrada real sea texto. Sin él:
   `ValidationException: Prompt [...] must have at least one audio content`.
   En el spike se manda medio segundo de silencio a 16 kHz para satisfacerlo.

3. **El stream de entrada debe permanecer abierto mientras se leen respuestas.**
   Enviar `promptEnd`/`sessionEnd` y cerrar la entrada de inmediato termina la
   sesión antes de que el modelo alcance a generar: no llega ni un evento. Este
   fue el fallo más difícil de diagnosticar porque no produce ningún error, sólo
   silencio.

4. **Una entrada de sólo texto no dispara la generación por sí sola.** Con voz,
   el modelo detecta el fin del turno por las pausas del hablante. Con texto no
   hay pausa que detectar: hay que cerrar el bloque de audio abierto para marcar
   el fin del turno, y abrir uno nuevo a continuación. Descubierto en la tarea A3,
   con el mismo síntoma que la regla anterior — silencio sin error.

5. **Un bloque de audio que nunca recibió datos no se puede cerrar:**
   `Cannot end content as no content data was received`. En un turno de sólo
   texto hay que rellenarlo con un frame de silencio antes del `contentEnd`.

### Formatos de audio

| | Entrada | Salida |
|---|---|---|
| Codec | PCM lineal (`audio/lpcm`) | PCM lineal |
| Frecuencia | **16 000 Hz** | **24 000 Hz** |
| Bits | 16 | 16 |
| Canales | 1 (mono) | 1 |
| Transporte | base64 | base64 |

## Consecuencias

- El factor diferenciador del entregable —voz a voz nativa, sin encadenar tres
  servicios— está confirmado y no depende de un plan de respaldo.
- `NOVA_MODEL_ID` y `NOVA_VOICE_ID` siguen siendo variables de entorno. El respaldo
  `amazon.nova-sonic-v1:0` también abrió stream correctamente, así que cambiar de
  modelo es una línea en `.env` si algo cambia.
- Al cerrar el stream aparece un `AwsCrtError: AWS_ERROR_HTTP_STREAM_HAS_COMPLETED`.
  Es ruido de limpieza y no afecta la conversación; el puente de la tarea A3 lo
  suprime explícitamente en lugar de ignorarlo en silencio.
- Los guardrails gestionados de Bedrock **no aplican** a esta API. Ver ADR 0013.
