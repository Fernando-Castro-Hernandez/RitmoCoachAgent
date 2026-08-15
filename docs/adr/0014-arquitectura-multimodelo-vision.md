# ADR 0014 — Arquitectura multi-nube: voz en Bedrock, visión en Anthropic

- **Estado:** Aceptada
- **Fecha:** 2026-08-14 · **revisada** 2026-08-15 (pivote multi-nube)
- **Relacionada:** [ADR 0002](0002-nova-2-sonic-en-bedrock.md),
  [ADR 0010](0010-fuera-de-alcance-gps-y-tracking.md),
  [ADR 0011](0011-modulo-de-tecnica-de-carrera.md),
  [ADR 0013](0013-guardrails-fuera-de-la-ruta-de-voz.md)

## Contexto

El ADR 0010 cerró el rastreo GPS: Ritmo no compite con el reloj del corredor. Pero
esa decisión dejó un hueco real que la entrevista de la Fase 2 hizo evidente: el
corredor **ya tiene los datos** —ritmo, distancia, zonas de frecuencia cardíaca—
sólo que viven en la pantalla de su reloj o de Strava, y dictarlos por voz es
tedioso y propenso a error.

La salida obvia era integrarse con Garmin Connect o Strava. La salida obvia tiene
un costo que no cabe en esta ventana:

| Costo de la integración OAuth | Detalle |
|---|---|
| Alta como desarrollador | Strava exige aplicación registrada y aprobación; Garmin, solicitud a su programa |
| Flujo OAuth 2 completo | Pantalla de consentimiento, callback con HTTPS, almacenamiento y rotación de refresh tokens |
| Secretos nuevos | `client_id` y `client_secret` por proveedor, con toda la superficie de fuga que implica |
| Modelos de datos distintos | Cada API tiene su esquema; dos integraciones son dos mapeadores |
| Y aun así, cobertura parcial | Quien usa Polar, Coros, Suunto o Nike Run Club se queda fuera |

Nada de eso enseña técnica de carrera ni evita una lesión. Es plomería.

Al mismo tiempo, hay una constatación técnica dura: **Nova 2 Sonic sólo acepta la
modalidad `SPEECH`.** Verificado contra el catálogo real de la cuenta:

```console
$ aws bedrock list-foundation-models --region us-east-1 \
    --query "modelSummaries[?modelId=='amazon.nova-2-sonic-v1:0'].inputModalities"
[["SPEECH"]]
```

No hay forma de pasarle una imagen. El modelo de voz no puede ser también el
modelo de visión, no por diseño de producto sino por capacidad del modelo.

## Decisión

**Dos rutas, dos modelos, dos protocolos. La captura de pantalla sustituye a la
integración OAuth.**

```
RUTA DE VOZ (streaming, sincrónica, presupuesto de latencia ~800 ms)
  navegador ─WebSocket─► FastAPI ─InvokeModelWithBidirectionalStream─►
                                    amazon.nova-2-sonic-v1:0   [SPEECH]

RUTA DE VISIÓN (REST, asincrónica, presupuesto de latencia ~3 s)
  navegador ─POST multipart─► FastAPI ─Converse─►
                                    amazon.nova-2-lite-v1:0    [TEXT·IMAGE·VIDEO]
                                    fallback: anthropic.claude-haiku-4-5  [TEXT·IMAGE]
                             │
                             └─► extracción validada ─► LogRepo ─► motor de dominio
```

Las dos rutas nunca se cruzan. La de visión escribe en la base; la de voz lee de
la base a través de sus herramientas. El coach se entera de la carrera subida
porque `get_week_context` la ve, no porque el modelo de voz haya visto la imagen.

### Modelo elegido y por qué

`amazon.nova-2-lite-v1:0`, con `anthropic.claude-haiku-4-5-20251001-v1:0` como
respaldo. Ambos verificados disponibles en `us-east-1` en la cuenta `602440904865`.

| Criterio | Por qué manda aquí |
|---|---|
| Es extracción, no razonamiento | Leer «8.42 km · 5:37 /km · 47:18» de una captura es OCR con estructura. Un modelo frontera es desperdicio. |
| Latencia | El usuario espera mirando una barra de progreso. Segundos, no decenas de segundos. |
| Costo por imagen | Es la operación que más se repite (una por entrenamiento). Va al tier más barato que resuelva. |
| Salida estructurada | `Converse` con `toolConfig` obliga al modelo a devolver el JSON del esquema, en vez de prosa que hay que parsear. |
| Vídeo nativo | Nova 2 Lite acepta `VIDEO` — deja abierta la puerta a subir el clip entero si la extracción por fotogramas se queda corta. |

**Nota sobre el enunciado original.** El pivote pedía documentar «Claude 3.5 Sonnet
/ Nova Pro». Se descartaron los dos: Sonnet 3.5 es una generación anterior y más
cara para una tarea que no lo necesita, y Nova Pro es el tier de razonamiento, no
el de extracción. Para leer números de una captura, el tier ligero es la respuesta
correcta y la barata al mismo tiempo. Si la exactitud de extracción medida cae por
debajo del umbral, se sube de tier — pero se sube con una métrica en la mano, no
por precaución.

### El motor sigue siendo el dueño de los números

El modelo de visión **no calcula nada.** Devuelve lo que ve, y punto:

```json
{
  "distance_km": 8.42,
  "duration_sec": 2838,
  "avg_pace_sec_per_km": 337,
  "avg_hr": 152,
  "confidence": "high",
  "unreadable_fields": []
}
```

Y el backend, antes de escribir en la bitácora:

1. **Recalcula** el ritmo con `coach_domain.paces.pace_from_run`. Si difiere del
   que leyó el modelo en más de 3 s/km, el ritmo del motor gana y la discrepancia
   se registra.
2. **Rechaza lo imposible** — distancia negativa, ritmo de 1:30/km, duración de
   cero. El motor decide qué es plausible, no el LLM.
3. **Confirma por voz cuando no está seguro.** `confidence: "low"` no escribe en la
   bitácora: encola una pregunta para que el coach la haga en la siguiente
   conversación. «Leí ocho cuarenta y dos, ¿va?»

Esto extiende, no rompe, la regla del ADR 0003: *si es un número, viene del motor.*
La visión es una **fuente de entrada** más, al mismo nivel que la voz del usuario, y
pasa por la misma validación.

### Análisis biomecánico: fotogramas, no vídeo

El corredor sube un miniclip de 5–10 segundos. El **navegador** extrae ~10
fotogramas clave con `<video>` + `canvas.toBlob()` y sube JPEG.

Se eligió así, y no subir el vídeo entero, por cuatro razones:

- Un clip de 10 s en 1080p pesa entre 10 y 25 MB; diez JPEG a 720p pesan menos de
  1 MB en total. En una EC2 `t4g.small` con 2 GB de RAM esa diferencia es real.
- El backend no necesita `ffmpeg` ni códecs. Cero dependencias binarias nuevas.
- Funciona igual con el modelo de respaldo, que no acepta `VIDEO`.
- El vídeo nunca sale del teléfono. Sólo diez cuadros. Es la opción que menos datos
  mueve, y para material que es literalmente el cuerpo de una persona eso importa.

El diagnóstico que produce es **cualitativo y acotado** — aterrizaje respecto al
centro de masa, caída de cadera, cruce de brazos, inclinación del tronco— y se
guarda en el perfil para que el módulo de técnica (ADR 0011) **priorice qué señal
enseñar**. No mide ángulos ni pretende hacerlo: eso requiere calibración,
seguimiento de articulaciones y un plano de cámara controlado. Un modelo de visión
generalista mirando diez cuadros de un teléfono en horizontal no da para eso, y
decir lo contrario sería el mismo error que criticamos en el ADR 0010.

Y sigue sin diagnosticar: si algo en el vídeo sugiere lesión, el resultado no es un
nombre clínico, es *«esto merece que lo revise alguien»*.

## Lo que apareció al conectarlo de verdad

Tres cosas que la documentación no dice y que sólo salieron ejecutando contra la
cuenta. Van aquí por la misma razón que las cinco reglas no documentadas del ADR
0002: son las que le cuestan una tarde a quien venga después.

### 1 · Nova 2 Lite no se invoca por su identificador

```console
$ # con modelId = amazon.nova-2-lite-v1:0
ValidationException: Invocation of model ID amazon.nova-2-lite-v1:0 with
on-demand throughput isn't supported. Retry your request with the ID or ARN
of an inference profile that contains this model.
```

Hay que usar un **perfil de inferencia entre regiones**, y el prefijo no es
opcional:

```console
$ aws bedrock list-inference-profiles --region us-east-1
us.amazon.nova-2-lite-v1:0                      ACTIVE
global.amazon.nova-2-lite-v1:0                  ACTIVE
us.anthropic.claude-haiku-4-5-20251001-v1:0     ACTIVE
```

`VISION_MODEL_ID` es ahora `us.amazon.nova-2-lite-v1:0`. Detalle con
consecuencias de arquitectura: el perfil `us.` enruta la petición a cualquier
región de Estados Unidos, así que **la co-ubicación con la instancia EC2 del ADR
0008 no está garantizada para la ruta de visión**. Se acepta: esta ruta tiene un
presupuesto de latencia de segundos, no de milisegundos, y el usuario está
mirando una barra de progreso. Para la voz, que sí es sensible, Nova Sonic se
sigue invocando directamente contra `us-east-1`.

### 2 · La cuota que no afectaba a la voz sí afecta a la visión

```console
ThrottlingException: Too many tokens per day, please wait before trying again.
```

El ADR 0002 documentó que las cuotas de esta cuenta figuraban en `0.0` y que aun
así el stream de voz abría sin problema, y de ahí salió la lección de que *«una
cuota publicada no es una prueba»*. Ahora se ve la otra mitad: **ese mismo cero
sí gobierna a los modelos de texto y visión.**

```console
$ aws service-quotas list-service-quotas --service-code bedrock --region us-east-1
Model invocation max tokens per day for Amazon Nova 2 Lite    0.0
```

La lección se afina: la cuota no es una prueba **en ninguna dirección**. Un cero
no demuestra que algo esté bloqueado ni que esté abierto. Sólo la llamada real
lo dice, y hay que hacerla por cada ruta.

### 3 · Los modelos de Anthropic exigen un formulario previo

```console
ResourceNotFoundException: Model use case details have not been submitted for
this account. Fill out the Anthropic use case details form before using the
model.
```

Es un trámite único en la consola de Bedrock, no un problema de permisos ni de
cuota. Queda anotado como paso manual de despliegue.

### 4 · El bloqueo no era del modelo, era de la cuenta

Al intentar cambiar el modelo principal a Claude Haiku 4.5 apareció lo que
convierte los tres hallazgos anteriores en uno solo:

```console
$ aws service-quotas list-service-quotas --service-code bedrock \
    --region us-east-1 --query "Quotas[?contains(QuotaName,'tokens per day')]"
Nova 2 Lite ........... 0.0
Nova Pro .............. 0.0
Nova Premier .......... 0.0
Claude Haiku 4.5 ...... 0.0
Claude Sonnet 4.5 ..... 0.0
Claude Opus 4.5 ....... 0.0
```

**Todos** los modelos con visión de la cuenta están en cero, y se comprobó
ejecutando: los seis devuelven `ThrottlingException`. Y por separado:

```console
$ aws bedrock get-foundation-model-availability \
    --model-id anthropic.claude-haiku-4-5-20251001-v1:0
{ "agreementAvailability": { "status": "NOT_AVAILABLE" },
  "authorizationStatus": "AUTHORIZED",
  "entitlementAvailability": "AVAILABLE" }
```

Todos los modelos de Anthropic salen `NOT_AVAILABLE`; todos los de Amazon,
`AVAILABLE`. El acuerdo es **por proveedor**, no por modelo.

La conclusión cambia el diseño: **elegir bien el modelo no resuelve nada.** La
cuenta es nueva y las cuotas se levantan solas en su ciclo diario; hasta
entonces ningún modelo con visión responde. Cualquier decisión de la forma «el
modelo principal será X» es una apuesta sobre qué se desbloquea primero.

### Consecuencia de diseño: cadena configurable y degradación a manual

Dos cambios, y ninguno es sobreingeniería defensiva — los cuatro modos de fallo
se encontraron ejecutando, no imaginando.

**Una cadena, no un modelo.** `VISION_MODEL_CHAIN` es una lista ordenada por
preferencia. `ChainVisionClient` la recorre hasta que uno responde, saltando los
errores recuperables —cuota, acuerdo pendiente, modelo no listo, perfil de
inferencia— y propagando los que no lo son: un formato de imagen inválido
fallaría igual en todos, y seguir la cadena sólo multiplicaría la espera. Así
**desbloquear cualquiera de los modelos hace funcionar la ruta sin tocar código
ni volver a desplegar**, que es exactamente la flexibilidad que hace falta
cuando no se sabe cuál se levantará primero.

**Y si no responde ninguno, se degrada a captura manual.** El endpoint no
devuelve 502: devuelve `mode: "manual"` con los campos vacíos y editables. El
corredor teclea cuatro números y sigue con su vida. Un entrenamiento sin
registrar contamina la progresión igual que una cifra mal leída, así que la
peor salida posible es una pantalla de error.

Esto reordena la tesis del pivote, y para bien: **la visión es una comodidad,
no un requisito.** Lo que sustituye a la integración con Garmin no es el modelo
de visión — es no exigir OAuth. Escribir cuatro números sigue siendo más rápido
que registrar una aplicación en Strava.

---

## Revisión del 15-ago-2026: la visión sale de AWS

Las cuotas de la cuenta de Bedrock no se levantaron, y no son ajustables a
petición: `Not adjustable` hasta que la cuenta cumpla su ciclo. Esperar a que
AWS desbloquee una cuenta nueva no es un plan de entrega.

**Decisión: arquitectura multi-nube.** Cada ruta va al proveedor que la resuelve
mejor, y ninguna depende de la disponibilidad de la otra.

```
RUTA DE VOZ · AWS Bedrock                     latencia ~800 ms, streaming
  navegador ─WebSocket─► FastAPI ─InvokeModelWithBidirectionalStream─►
                                    amazon.nova-2-sonic-v1:0   [SPEECH]

RUTA DE VISIÓN · API directa de Anthropic     latencia ~3 s, REST
  navegador ─POST multipart─► FastAPI ─messages.create─►
                                    api.anthropic.com
                                    claude-haiku-4-5           [TEXT·IMAGE]
                             │
                             └─► si falla ─► captura manual
```

### Por qué cada uno donde está

| | Voz | Visión |
|---|---|---|
| **Dónde** | AWS Bedrock | API directa de Anthropic |
| **Por qué ahí** | Anthropic no tiene streaming bidireccional de voz. Nova Sonic sí, y es speech-to-speech nativo. | Saldo propio, cuotas propias, sin acuerdos pendientes ni ciclos de cuenta nueva. |
| **Por qué no al revés** | Una API REST no da barge-in ni prosodia; encadenar STT+LLM+TTS multiplica la latencia (ADR 0001). | En Bedrock esta ruta estaba a cero y no se podía desbloquear a petición. |
| **Credenciales** | Rol IAM de instancia, cero claves estáticas | `ANTHROPIC_API_KEY` en el entorno |

El beneficio real no es de latencia ni de coste: es que **un incidente de
disponibilidad en un proveedor ya no tumba las dos rutas.** Con todo en Bedrock,
la cuota diaria en cero dejó la visión inservible sin tocar la voz sólo por
casualidad —porque el streaming bidireccional no la consume—. Repartirlo lo
convierte en una propiedad del diseño y no en una suerte.

### El modelo: Haiku 4.5, no Haiku 3.5

El pivote pedía `claude-3-5-haiku-latest`. **Claude 3.5 Haiku no acepta imágenes
de entrada.** Es texto solamente, y usarlo aquí rompería la ruta entera con un
error poco obvio; es el tropiezo fácil de cometer al buscar «el Haiku barato».

El Haiku con visión es el **4.5** (`claude-haiku-4-5-20251001`), que además es
más nuevo y más capaz. Hay una prueba que falla si alguien vuelve a poner un 3.5
en la cadena, para que el error no se pueda repetir en silencio.

### Coste de esta decisión

- **Dos facturas y dos consolas** en vez de una. Es el precio de no tener un
  único punto de fallo, y a esta escala es un renglón.
- **Una clave estática que gestionar.** La voz no tiene ninguna —rol IAM de
  instancia— así que ahora hay una asimetría real: `ANTHROPIC_API_KEY` vive en
  el entorno del servidor y hay que rotarla a mano. Queda anotado como la deuda
  de seguridad de esta decisión.
- **La imagen sale de AWS.** Antes la captura viajaba dentro de la nube; ahora
  sale a `api.anthropic.com`. Para capturas de reloj es aceptable; si algún día
  entrara material más sensible, habría que revisarlo.

### Lo que NO cambia

`ChainVisionClient`, el esquema, `reconcile`, la validación del motor y la
degradación a captura manual son idénticos. El cliente nuevo implementa el mismo
protocolo `VisionClient`, así que el resto del sistema no se entera de por dónde
salió la imagen — y por eso este pivote fue un archivo nuevo y una variable de
entorno, no un refactor. `BedrockVisionClient` se conserva: volver es cambiar una
línea en `get_vision_client`, y sigue siendo la alternativa si el saldo se agota.

Y sobre todo: **el motor sigue mandando.** El ritmo se recalcula igual, la
discrepancia se marca igual, y nada entra a la bitácora sin que el corredor lo
vea. La regla del ADR 0003 no depende del proveedor.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **OAuth con Strava / Garmin** | Días de trabajo en plomería y aprobaciones externas; cobertura parcial; cero valor para el usuario que no usa esas apps. El costo está arriba en la tabla. |
| **OCR clásico (Tesseract) en el backend** | Las capturas de reloj son la peor entrada posible para OCR clásico: fondo negro, tipografías condensadas, unidades pegadas al número, gráficos superpuestos. Y añade un binario al contenedor. |
| **Nova 2 Sonic también para las imágenes** | Imposible. `inputModalities: [SPEECH]`. |
| **Nova Pro / Claude Sonnet para extraer** | Sobredimensionado para OCR estructurado. Se reserva como escalón si la exactitud medida lo justifica. |
| **Vídeo completo a Bedrock** | Peso, RAM, dependencias y datos personales de más. Ver arriba. |
| **Estimación de pose en el navegador (MoveNet/MediaPipe)** | Más preciso en teoría, pero es un proyecto en sí mismo: calibración, suavizado, definición de umbrales clínicos. Fuera de la ventana, y prometería una precisión que no podríamos defender. |

## Consecuencias

- **Cero OAuth, cero secretos de terceros.** Toda la superficie multimodal usa las
  mismas credenciales de Bedrock que ya resuelve el rol IAM de la instancia.
- **Cobertura universal.** Funciona con cualquier reloj, cualquier app, cualquier
  país. Si tiene pantalla, sirve.
- **El usuario ve lo que se registró antes de que se registre.** La extracción se
  muestra editable. Una cifra mal leída que entra a la bitácora contamina la
  progresión, y la progresión es el producto.
- **Dos modelos que versionar.** `NOVA_MODEL_ID` para voz y `VISION_MODEL_ID` para
  imagen, ambos en configuración, ambos reportados por `GET /api/config`.
- **Nueva métrica:** `vision_extraction_confidence` y `vision_field_correction_rate`
  —cuántos campos corrige el usuario a mano—. Si ese segundo número sube, el modelo
  de visión está fallando y hay que subir de tier. Se añade al ADR 0012.
- **Límite declarado:** el análisis biomecánico es orientativo, se presenta como
  tal en la interfaz, y no sustituye a la valoración de un profesional.
- **Riesgo asumido:** una captura de pantalla puede contener texto que intente
  redirigir al modelo. El prompt de extracción trata la imagen como **datos, nunca
  como instrucciones**, y la salida pasa por el esquema de `toolConfig`, que no
  tiene campo donde alojar una instrucción. Es la misma separación que el ADR 0013
  aplica a la voz.
