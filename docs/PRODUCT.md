# Product

<!-- impeccable:product-schema 1 -->

Ritmo — un entrenador de running que habla. El detalle completo vive en
`docs/fases/` y en los ADR; esto es lo que hay que saber para diseñar sin
romperlo.

## Platform

web

## Stack

Ya resuelto por el código existente: **React 19 · TypeScript 5.7 · Vite 6 ·
Zustand 5 · Vitest**, en `apps/web/`.

Un dato que corregir antes de construir: **Tailwind no está instalado.** El
ADR 0009 lo documenta como parte del stack, pero `apps/web/package.json` no lo
incluye. Hoy el frontend es React sin sistema de estilos. Instalarlo o no es
decisión de la fase de diseño.

Backend: FastAPI + PostgreSQL, ya construido y en verde (381 pruebas). Expone
`/ws/voice/{user_id}` (WebSocket de voz), `/api/profile/{user_id}`,
`/api/vision/workout` y `/api/plan/{user_id}/export.csv`.

## Users

Corredores hispanohablantes, de México, de todos los niveles — desde quien nunca
ha corrido hasta quien prepara su tercer maratón. Dos perfiles marcan el diseño:

**El principiante que se apunta a un maratón.** Es quien más se lesiona y quien
más necesita que le digan que no. No sabe qué no sabe. Si la interfaz le pide
datos que no tiene, se va.

**El corredor experimentado.** Ya lleva su reloj, su hoja de cálculo y sus
manías. No va a abandonar nada de eso, y no hay que pedírselo. Entra si le
aportamos algo que su reloj no le da: técnica de carrera y criterio.

## Product Purpose

Planificar y adaptar entrenamientos de 5K a maratón, recordar al corredor entre
sesiones, enseñarle técnica de carrera y escribirle por Telegram sin que abra la
aplicación.

**La voz no es un adorno ni un modo alternativo: es la interfaz principal.**

Éxito es que un corredor salga a entrenar sabiendo qué le toca hoy y por qué — y
que cuando le duela algo, el sistema le diga que pare en vez de darle
kilómetros.

## Positioning

Los generadores de planes con IA ya existen y están lesionando gente: el *Wall
Street Journal* reportó fisioterapeutas atendiendo casos relacionados con Runna
cada semana. La causa citada es que **el algoritmo toma al corredor por su
palabra, y el corredor novato rara vez se conoce tan bien como cree**.

Un formulario captura lo que el corredor *afirma*; una conversación captura lo
que *revela*. Por eso la voz. Y el modelo de lenguaje **nunca calcula un plan**:
la aritmética vive en un motor determinista y verificable, y el modelo sólo
escucha, consulta y explica.

En una frase: **la experiencia de ChatGPT como coach, con la responsabilidad que
ChatGPT no puede dar.**

Lo que un competidor no podría copiar sin rehacerse entero: que la seguridad y
la progresión son código determinista y auditable, no una instrucción de prompt.

## Operating Context

**Esto pesa más que cualquier otra cosa para el diseño.**

- En la calle, de pie, antes de salir a correr. A las 6 de la mañana o a las 8
  de la noche.
- Con **una mano**. La otra lleva llaves, agua, o está en el bolsillo.
- Con **sol de frente**, en una pantalla al 40 % de brillo.
- A veces **con el teléfono en el bolsillo** y sólo los auriculares puestos: la
  pantalla no existe y la voz es todo.
- Con prisa. Nadie contempla una interfaz antes de entrenar.

Una pantalla que se ve preciosa en un monitor de escritorio y exige leer texto
de 14 px al sol es un fallo de producto, no un detalle.

**Contexto de evaluación (confirmado):** el entregable se defiende de dos formas
a la vez — un video de 3 minutos **y** una URL pública que un evaluador abrirá
en frío desde su propio teléfono. Eso hace que el primer arranque, los estados
vacíos, el permiso de micrófono y los errores tengan que aguantar a un
desconocido sin contexto. No hay camino feliz ensayado que valga.

## Capabilities and Constraints

Pantallas que existen:

1. **Onboarding** — carrusel corto para el perfil duro (meta, días, edad, peso,
   tiempo de referencia). Sólo la meta es obligatoria; todo lo demás se salta.
   Menos de un minuto o la gente lo abandona.
2. **Principal** — contexto de semana, tarjeta de la sesión de hoy con su
   «por qué», transcripción en vivo, orbe de voz anclado abajo.
3. **Subir captura del reloj** — foto, revisión de lo extraído, confirmar.
4. **Subir técnica** — miniclip corriendo, diagnóstico cualitativo. *Puede
   quedar fuera por tiempo.*
5. **Modo texto** — respaldo si la voz falla o deniegan el micrófono.

Restricciones técnicas:

- **iOS Safari exige un gesto del usuario** para abrir el `AudioContext`. El
  primer toque tiene que existir y ser evidente.
- **El micrófono se silencia mientras el coach habla**, o se interrumpe a sí
  mismo por el altavoz. El estado `INTERRUPTIBLE` es lo que avisa al usuario de
  que aun así puede cortarlo.
- **La sesión de voz se renueva cada 8 minutos** por límite del modelo. El
  estado `RENEWING` **no debe ser perceptible**: un «reconectando…» cada ocho
  minutos hace que el producto se sienta frágil aunque funcione.
- Debe seguir siendo usable **sin voz**.

Fuera de alcance, y por qué:

- **Sin GPS ni cronómetro en vivo.** No competimos con el reloj del corredor;
  nos conectamos a él. Es postura, no carencia (ADR 0010).
- **Sin red social, ranking ni feed.** Eso ya lo hace Strava.
- **Sin recomendaciones de tenis ni equipo.** El corredor entrevistado lo llamó
  «frikadas de tercer nivel que no son lo que te va a dar mayor resultado».

## Brand Commitments

**Nombre:** Ritmo.

**Voz:** mexicano, de tú, cercano y directo. Frases cortas, una o dos por turno.
Nunca enumera opciones en voz alta, porque nadie puede seguir una lista
escuchando. No diagnostica: dice «eso merece que lo revise alguien», nunca
«tienes X».

**Y pregunta antes de prescribir.** Si le piden un plan de maratón sin saber
cuánto corre la persona, se detiene y pregunta — incluso si el corredor insiste
en que no le pregunten. Ese momento es la característica que nos distingue, y la
interfaz debería dejar que se luzca en vez de esconderlo.

Sin gamificación: ni rachas, ni medallas, ni confeti. Sin frases de póster.
Celebrar sí, exagerar no.

**Idioma (confirmado):** español de México e inglés, **los dos funcionando**,
con selector real. Los textos van centralizados; ninguna cadena vive suelta en
un componente.

## Evidence on Hand

- **Investigación de usuario real:** entrevista a un corredor experimentado
  (`docs/fases/fase-2-investigacion-usuario.md`). De ahí salieron el módulo de
  técnica y la decisión de no hacer GPS. Sus palabras son citables.
- **Backend funcionando:** 381 pruebas en verde, motor de dominio al 98 % de
  cobertura, ruta de voz y ruta de visión verificadas contra los modelos reales.
- **Reportaje del *Wall Street Journal*** sobre lesiones asociadas a Runna: es
  la base de la tesis y es real.
- **No hay:** usuarios reales, testimonios, métricas de uso, ni marca gráfica
  previa. Nada de eso se puede inventar en la interfaz.

## Product Principles

Las cuatro primeras parecen decisiones de interfaz y son reglas de negocio. Si
el diseño las «mejora» con buen criterio visual, rompe el producto.

1. **En rojo, la pantalla no prescribe.** La puerta de seguridad tiene tres
   estados. En rojo no aparece ni un kilómetro, ni un ritmo, ni una sesión, ni
   «algo suavecito»: sólo la tarjeta de derivación. Y no se descarta con un
   toque al vuelo — el corredor tiene que poder salir, pero no por accidente ni
   en el mismo gesto con el que llegó.
2. **Toda cifra viene del motor, y se nota.** En la revisión de una captura, los
   campos leídos son editables y **el ritmo aparece no editable y etiquetado
   como calculado**. Si el usuario lo corrige a mano, la bitácora deja de cuadrar
   con la distancia y el tiempo, y la progresión se contamina.
3. **Nada se guarda sin que lo vea.** Lo que un modelo leyó de una imagen se
   muestra, se confirma o se corrige, y entonces se guarda.
4. **La voz da hoy; la pantalla da la estructura.** Nadie memoriza un plan de 16
   semanas escuchándolo. Leer el plan completo en voz alta es el error de diseño
   número uno en coaches de voz.
5. **Criterio antes que energía.** Este producto se distingue por lo que se
   niega a hacer. Un lenguaje que grite rendimiento contradice el mensaje
   central, que es que a veces la respuesta correcta es no correr.

## Accessibility & Inclusion

- **Ningún estado se comunica sólo con color.** El teléfono puede estar en el
  bolsillo y el usuario puede no distinguir el verde del azul: cada estado
  necesita señal visual **y** textual.
- **Contraste real**, no elegante: pantalla al 40 % de brillo con sol de frente.
- **Objetivos táctiles grandes**, para el pulgar, con una mano y en movimiento.
- **`prefers-reduced-motion` respetado.** El orbe se mueve mucho; para quien lo
  pide tiene que quedarse quieto sin perder información.
- **Sin micrófono la aplicación sigue sirviendo.** Denegar el permiso no puede
  ser un callejón sin salida, sobre todo con un evaluador abriéndola en frío.
