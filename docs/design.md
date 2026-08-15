# Ritmo — brief de diseño

Deliberadamente abierto. Aquí no hay paleta ni tipografía elegidas: hay un
encargo, unas restricciones físicas y una lista de cosas que ya vimos y no
queremos. El criterio visual es tuyo.

Lo que **no** es negociable está en [`product.md`](product.md), y son cuatro
reglas de negocio, no de estilo.

---

## El encargo en una frase

Un entrenador de running que habla, usado **de pie en la calle, con una mano,
con sol de frente y a veces con el teléfono en el bolsillo**.

## La restricción que manda sobre todas

**Esto no se contempla, se usa mientras pasa otra cosa.** Nadie mira esta
pantalla sentado y con calma; la mira treinta segundos antes de salir a correr,
o entre semáforos, o no la mira porque va con auriculares.

De ahí salen cuatro consecuencias que sí son duras:

| | Por qué |
|---|---|
| **Contraste alto de verdad** | Pantalla al 40 % de brillo y sol de frente. El gris sobre gris elegante desaparece. |
| **Objetivos táctiles grandes** | Se toca con el pulgar, con una mano, a veces en movimiento. |
| **Todo estado tiene señal visual *y* textual** | El teléfono puede estar en el bolsillo, o el usuario puede no distinguir el azul del verde. Un color solo nunca comunica un estado. |
| **`prefers-reduced-motion` respetado** | El orbe se mueve mucho. Para quien lo pide, tiene que quedarse quieto sin perder información. |

Si hay que elegir entre que se vea sofisticado y que se lea al sol, se lee al sol.

## El orbe de voz

Es el foco de la interfaz y donde vale la pena gastar el presupuesto de diseño.
Tiene doce estados, y el requisito es que **cada uno se distinga sin leer**:

```
IDLE             quieto                      Toca para hablar
REQUESTING_MIC   pulso lento                 Permite el micrófono
CONNECTING       anillo girando              Conectando…
LISTENING        amplitud reactiva al volumen real del micrófono
USER_SPEAKING    ondas expandiéndose         transcripción parcial
THINKING         contracción                 …
TOOL_RUNNING     punto en órbita             Revisando tu plan…
SPEAKING         pulso sincronizado al audio transcripción del coach
INTERRUPTIBLE    borde punteado              Toca para interrumpir
RENEWING         SIN CAMBIO PERCEPTIBLE      — invisible a propósito
ERROR            rojo                        mensaje + «cambiar a texto»
SAFETY_STOP      rojo fijo, detenido         tarjeta de derivación médica
```

Dos notas sobre esa lista:

**`RENEWING` no se ve.** La sesión de voz se renueva cada ocho minutos por una
limitación del modelo. Si el usuario percibe algo, fallamos: un «reconectando…»
cada ocho minutos hace que el producto se sienta frágil aunque funcione.

**`LISTENING` reacciona al volumen real del micrófono**, no a una animación en
bucle. Es la señal de que el sistema *está oyendo* y no sólo *pretendiendo* oír.
Ese detalle es la mitad de la confianza en un producto de voz.

Cómo se ve todo eso es tuyo. Puede no ser un círculo.

## Layout de referencia, no de obligado cumplimiento

Es lo que salió de la Fase 1. Si encuentras algo mejor, adelante — respetando
las cuatro reglas de `product.md`.

```
┌──────────────────────────────────────┐
│  ● Ritmo                    ⚙   ES   │  estado de conexión · ajustes
├──────────────────────────────────────┤
│   SEMANA 7 / 16      · fase: build   │  contexto siempre visible
│   Maratón CDMX       · faltan 63 d   │
│                                      │
│   ╭────────────────────────────────╮ │
│   │  HOY · Tirada larga            │ │  la tarjeta de sesión
│   │  18 km   6:15–6:40 /km         │ │  es la unidad de decisión
│   │  Zona 2  ·  ~1 h 55 min        │ │
│   │  ⓘ por qué esta sesión         │ │  ← abre la justificación
│   ╰────────────────────────────────╯ │
│                                      │
│   ── transcripción en vivo ───────── │
│   Tú     me molestó algo la rodilla  │
│   Coach  ¿en qué parte exactamente?  │
├──────────────────────────────────────┤
│            ((( ◉ )))                 │  el orbe
│             Escuchando…              │
│   [⌨ escribir]          [⏹ terminar] │
└──────────────────────────────────────┘
```

Móvil primero. En escritorio se abre a dos columnas: plan e histórico a la
izquierda, conversación con el orbe anclado a la derecha. Mismo componente,
distinta densidad.

**La tarjeta de sesión es la unidad de decisión del producto.** Es lo que el
corredor mira y lo que le dice qué hacer hoy. El «por qué esta sesión» no es un
extra: es lo que separa un entrenador de una hoja de cálculo.

## Tono

Mexicano, de tú, cercano y directo. Como un entrenador que ya te conoce, no como
una app que te motiva.

- Sin gamificación. Ni rachas, ni medallas, ni confeti.
- Sin frases de póster. «¡Tú puedes!» no está en el producto.
- Celebrar sí, exagerar no.
- Los errores dicen qué pasó y qué hacer, sin disculparse dos veces.

## Lo que ya vimos y no queremos

No por prohibición estética, sino porque es lo que sale por defecto y ya lo
tienen todos:

- El degradado morado-a-azul de las apps de IA.
- Fondo crema con serif de display y acento terracota.
- Negro casi puro con un único acento verde ácido.
- Emojis como marcadores de sección.
- Todo centrado, todo con esquinas muy redondeadas, tarjetas con barra de acento
  a la izquierda.
- La estética «fitness app»: naranja agresivo, números gigantes, gráficas de
  anillos.

Lo último merece una nota: **este producto no es Strava y no debería parecerlo.**
Strava mide y compara. Nosotros enseñamos y frenamos. Si el diseño grita
rendimiento, contradice el mensaje central, que es que a veces la respuesta
correcta es no correr.

## De dónde sacar identidad, si sirve

El mundo del que sale esto: el asfalto a las seis de la mañana, la cadencia, la
respiración, la repetición semana tras semana, el kilometraje que sube poco a
poco. Un plan de entrenamiento tiene ritmo — literalmente: días duros, días
suaves, semanas de descarga. Hay algo ahí.

Y algo que quizá dé más: **este producto se distingue por lo que se niega a
hacer.** Pregunta antes de prescribir, y frena cuando duele. Un lenguaje visual
que transmita criterio y calma en vez de energía y urgencia estaría diciendo la
verdad sobre el producto.

## Detalles técnicos que condicionan

- **React 19 + TypeScript + Vite + Tailwind v4.** Zustand para estado.
- **iOS Safari necesita un gesto del usuario** para abrir el `AudioContext`. El
  primer toque tiene que existir y tiene que ser evidente.
- **El micrófono se silencia mientras el coach habla** (si no, se interrumpe a sí
  mismo con el altavoz). El estado `INTERRUPTIBLE` es lo que le dice al usuario
  que aun así puede cortarlo.
- Debe funcionar **sin voz**: si deniegan el micrófono o la red falla, la
  aplicación degrada a chat de texto y sigue siendo usable.
