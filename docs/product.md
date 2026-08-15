# Ritmo — contexto de producto

Lo que hay que saber para diseñar esto sin romperlo. Corto a propósito: el
detalle completo está en `docs/fases/` y en los ADR.

---

## Qué es

Un **entrenador de running que habla**. Planifica y adapta entrenamientos de 5K
a maratón, recuerda al corredor entre sesiones, le enseña técnica de carrera y
le escribe por Telegram sin que abra la aplicación.

La voz no es un adorno ni un modo alternativo: es la interfaz principal.

## Para quién

Corredores hispanohablantes, de México, de todos los niveles — desde quien nunca
ha corrido hasta quien prepara su tercer maratón. Dos perfiles marcan el diseño:

**El principiante que se apunta a un maratón.** Es quien más se lesiona y quien
más necesita que le digan que no. No sabe qué no sabe. Si la interfaz le pide
datos que no tiene, se va.

**El corredor experimentado.** Ya lleva su reloj, su hoja de cálculo y sus
manías. No va a abandonar nada de eso, y no hay que pedírselo. Entra si le
aportamos algo que su reloj no le da — que es técnica de carrera y criterio.

## Dónde se usa

**Esto importa más que cualquier otra cosa para el diseño.**

- En la calle, de pie, antes de salir a correr. A las 6 de la mañana o a las 8
  de la noche.
- Con **una mano**. La otra lleva llaves, agua o nada porque está en el bolsillo.
- Con **sol de frente**, en una pantalla al 40 % de brillo.
- A veces **con el teléfono en el bolsillo** y sólo los auriculares puestos: la
  pantalla no existe y la voz es todo.
- Con prisa. Nadie contempla una interfaz antes de entrenar.

Una pantalla que se ve preciosa en un monitor de escritorio y que exige leer
texto de 14 px al sol es un fallo de producto, no un detalle.

## La tesis, en un párrafo

Los generadores de planes con IA ya existen y están lesionando gente: el *Wall
Street Journal* reportó fisioterapeutas atendiendo casos relacionados con Runna
cada semana. La causa citada es que **el algoritmo toma al corredor por su
palabra, y el corredor novato rara vez se conoce tan bien como cree**. Un
formulario captura lo que el corredor *afirma*; una conversación captura lo que
*revela*. Por eso la voz. Y por eso el modelo de lenguaje nunca calcula un plan:
la aritmética vive en un motor determinista y verificable, y el modelo sólo
escucha, consulta y explica.

En una frase: **la experiencia de ChatGPT como coach, con la responsabilidad que
ChatGPT no puede dar.**

---

## Las cuatro reglas que no se negocian

Parecen decisiones de interfaz. Son reglas de negocio. Si el diseño las mejora
con buen criterio visual, rompe el producto.

### 1 · En rojo, la pantalla no prescribe

La puerta de seguridad tiene tres estados: verde, ámbar y rojo. **En rojo no
aparece ni un kilómetro, ni un ritmo, ni una sesión, ni «algo suavecito».** La
pantalla muestra la tarjeta de derivación médica y nada más.

No se puede descartar con un toque ni con un «entendido» al vuelo. El corredor
tiene que poder salir de ahí, pero no por accidente y no en el mismo gesto con
el que llegó.

Es la diferencia entre un producto de salud defendible y uno irresponsable.

### 2 · Toda cifra viene del motor, y se nota

Los números que se muestran los calcula un motor determinista, nunca el modelo
de lenguaje. Donde eso sea relevante para el usuario, **la interfaz lo dice**.

El caso concreto: cuando alguien sube una captura de su reloj, se le enseña lo
que se leyó en campos **editables** — y el ritmo aparece **no editable y
etiquetado como calculado**. No es pedantería: si el usuario corrige el ritmo a
mano, la bitácora deja de cuadrar con la distancia y el tiempo, y la progresión
se contamina.

### 3 · Nada se guarda sin que lo vea

Lo que un modelo de visión leyó de una imagen **no entra a la bitácora solo**.
Se muestra, se confirma o se corrige, y entonces se guarda. Una cifra mal leída
contamina la progresión, y la progresión es el producto.

### 4 · La voz da hoy; la pantalla da la estructura

Nadie puede memorizar un plan de 16 semanas escuchándolo. **Leer el plan
completo en voz alta es el error de diseño número uno en coaches de voz.**

- La **voz** entrega una sola cosa: la sesión de hoy y por qué.
- La **pantalla** entrega la estructura: la semana, la fase, el histórico, el
  plan completo si lo quiere ver.

---

## Cómo habla el coach

Se llama **Ritmo**. Es mexicano, habla de tú, cercano y directo. Frases cortas:
una o dos por turno. Nunca enumera opciones en voz alta, porque nadie puede
seguir una lista escuchando.

No diagnostica: dice «eso merece que lo revise alguien», nunca «tienes X».

Y **pregunta antes de prescribir**. Si le piden un plan de maratón sin saber
cuánto corre la persona, se detiene y pregunta — incluso si el corredor insiste
en que no le pregunten. Ese momento es la característica que nos distingue, y la
interfaz debería dejar que se luzca en vez de esconderlo.

## Qué queda fuera, y por qué

- **No hay GPS ni cronómetro en vivo.** No competimos con el reloj del corredor;
  nos conectamos a él. «No compitas con tu reloj» es postura, no carencia.
- **No hay red social, ni ranking, ni feed.** Eso ya lo hace Strava.
- **No hay recomendaciones de tenis ni de equipo.** El corredor entrevistado lo
  llamó «frikadas de tercer nivel que no son lo que te va a dar mayor
  resultado», y le hicimos caso.

## Pantallas que existen

1. **Onboarding** — un carrusel corto que captura el perfil duro (meta, días,
   edad, peso, tiempo de referencia). Sólo la meta es obligatoria; todo lo demás
   se salta. Menos de un minuto o la gente lo abandona.
2. **Principal** — contexto de semana, tarjeta de la sesión de hoy con su
   «por qué», transcripción en vivo y el orbe de voz anclado abajo.
3. **Subir captura** — foto del reloj, revisión de lo extraído, confirmar.
4. **Subir técnica** — miniclip corriendo, diagnóstico cualitativo *(puede
   quedar fuera por tiempo)*.
5. **Modo texto** — respaldo si la voz falla o el micrófono está denegado.

## Contexto de entrega

Es un reto técnico para una vacante, con fecha límite. Se entrega con un video
de 3 minutos. **Lo que no se ve en el video, no existe** para quien evalúa — pero
lo que se ve tiene que ser real, no una maqueta.
