# Guion de grabación

Vídeo de 3:00–3:30, dos actos, dos dispositivos. Está escrito para grabarse de
corrido; cada escena trae **qué se ve**, **qué se dice** y **cuánto dura**.

La narrativa es una sola frase, y conviene tenerla en la cabeza al grabar:

> Un coach de voz que **no se inventa los números** y **sabe cuándo callarse**.

Todo lo demás —el calendario, la visión, Telegram— existe para sostener eso.

---

## Antes de grabar

### 1. La cuenta de demostración, recién sembrada

```bash
docker compose exec -T api python scripts/seed_demo.py --reset
```

Deja `demo@adivor.com` / `password123` en semana 7 de 16 de maratón, con 36
sesiones en la bitácora y la puerta en **ámbar** por una molestia de 3.

### 2. El día que grabas importa

El script de siembra lo dice al terminar, y es la trampa número uno:

> **AVISO: hoy es día de DESCANSO en el plan**, así que la hoja NO enseñará la
> sesión recortada en ámbar.

El plan descansa los **lunes**. Si grabas un lunes, el Acto 2 abre con
«Descanso» y se pierde el plano de la sesión recortada. **Graba martes a
domingo.** Si no hay más remedio, la escena 2.2 se sustituye por el calendario,
que sí enseña la carga entera.

### 3. Ventanas

| acto | viewport | cómo |
|---|---|---|
| 1 | 390 × 844 (iPhone 14) | DevTools → Toggle device toolbar |
| 2 | 1440 × 900, pantalla completa | ventana normal, sin DevTools |

Cierra las pestañas de más: en el Acto 2 se ve la barra del navegador.

### 4. Permisos, antes de que ruede la cámara

Entra una vez a `https://54-80-131-31.sslip.io/app`, pulsa el orbe y **acepta el
micrófono**. Si el diálogo de permiso sale en el vídeo, se come diez segundos y
se ve como un tropiezo.

### 5. Los dos archivos que vas a subir

- **Un clip corriendo de lado, ≤ 15 s.** Que se vea el cuerpo entero. El
  navegador saca 10 fotogramas y **sólo esos** salen del teléfono.
- **Una captura de Strava, Garmin o Runna** con distancia y tiempo legibles.

Tenlos en el escritorio, no en una carpeta con veinte cosas más.

### 6. Red de seguridad

La voz es en vivo y puede tardar. Si a los ~4 s no arranca, **pulsa ESCRIBIR y
sigue por texto**: el guion funciona igual y no se nota como fallo, porque el
respaldo de texto es una característica, no un parche. Dilo en voz alta si pasa:
«también funciona escrito, que es lo que uso cuando voy en el metro».

---

## ACTO 1 · El corredor que empieza (móvil) — 0:00 a 1:25

**Lo que hay que dejar claro:** que esto se usa con el teléfono en la mano, y
que el coach **prefiere preguntar antes que inventar**.

### 1.1 · Portada — 0:00 a 0:12 (12 s)

**En pantalla:** `https://54-80-131-31.sslip.io/` en viewport móvil. El isotipo
entra animado, el titular debajo.

**Voz en off:**
> «Ritmo es un entrenador de running por voz. Le hablas como a una persona, pero
> los kilómetros y los ritmos no los dice el modelo: los calcula un motor
> determinista. Esa es toda la idea.»

Pulsa **Crear cuenta**.

### 1.2 · Registro — 0:12 a 0:22 (10 s)

**En pantalla:** correo y contraseña, cuenta nueva de verdad.

**Voz en off:**
> «Cuenta nueva, en vivo. Lo que vais a ver no es una demo sembrada.»

> Usa un correo que no hayas usado: `demo-video-<algo>@adivor.com`.

### 1.3 · Carrusel — 0:22 a 0:45 (23 s)

**En pantalla:** los 7 pasos. Escribe **Fernando**. Elige **10K**. Los demás
pasos, **saltar**.

**Voz en off:**
> «El nombre y la meta, y ya. Sólo la carrera es obligatoria: un onboarding de
> nueve preguntas es un onboarding que la gente abandona. Lo demás lo recoge
> hablando, que es donde la gente sí cuenta los matices.»

> **Enséñalo saltando pasos.** Que se vea que se puede.

### 1.4 · Pedir el plan — 0:45 a 1:00 (15 s)

**En pantalla:** la hoja, con «todavía no hay plan». Pulsa el orbe y di:

> «Hola, quiero que me armes un plan para un 10K.»

**Voz en off, encima de la respuesta:**
> «Y aquí está lo que más me importa de todo el proyecto.»

### 1.5 · Clarificación autónoma — 1:00 a 1:15 (15 s)

**En pantalla:** el coach **no** genera nada. Pregunta.

**Voz en off:**
> «No inventa el plan. Pregunta cuánto corre ahora, cuál es su tirada más larga,
> a qué ritmo y si tiene molestias. Y esto no es una instrucción en el prompt
> que el modelo pueda ignorar: la herramienta que crea planes **se niega** a
> funcionar sin esos datos y devuelve la pregunta ya redactada.»

Contesta, en una sola frase:

> «Corro unos diez o doce kilómetros a la semana, lo más largo han sido cinco,
> hago cinco kilómetros en treinta minutos y no tengo ninguna molestia.»

> El coach conversa: puede preguntar de otra forma o pedir sólo lo que falte. No
> intentes que diga una frase exacta. Lo que hay que ver es **que pregunta**.

### 1.6 · El plan aparece — 1:15 a 1:25 (10 s)

**En pantalla:** la tarjeta izquierda se rellena sola —semana 1, fase Base,
10K— y el coach dice qué toca hoy, llamándole **Fernando**.

**Voz en off:**
> «El plan sale en el mismo turno. La hoja se sincroniza sola. Y fíjate en que
> le llama por su nombre: se lo dijimos hace cuarenta segundos.»

> Si hoy es día de descanso en el plan nuevo, el coach dirá «hoy toca
> descanso». **Es correcto y hay que dejarlo**: la frase «el descanso es parte
> del plan, no una pausa» es del producto.

---

## ACTO 2 · El corredor avanzado y el ecosistema (escritorio) — 1:25 a 3:20

**Lo que hay que dejar claro:** que debajo del chat hay un sistema — motor,
puerta de seguridad, visión y automatizaciones.

### 2.1 · Cambio de cuenta — 1:25 a 1:35 (10 s)

**En pantalla:** pantalla completa. **Perfil → Cerrar sesión**, y entra con
`demo@adivor.com`.

**Voz en off:**
> «Ahora una cuenta con historia: semana 7 de 16 de maratón, treinta y seis
> sesiones registradas.»

### 2.2 · La hoja y el ámbar — 1:35 a 1:50 (15 s)

**En pantalla:** la sesión de hoy y **ESTADO · ENTRENA CON AJUSTE** en ámbar.

**Voz en off:**
> «Este corredor reportó una molestia de tres sobre diez. La puerta de seguridad
> está en ámbar, y el recorte ya viene aplicado desde el servidor: la pantalla
> no enseña una sesión completa que después haya que desmentir.»

> Si grabas en lunes esto dirá «Descanso». Salta a 2.3 y vuelve aquí al final.

### 2.3 · Calendario — 1:50 a 2:10 (20 s)

**En pantalla:** **Ver calendario**. Baja despacio por las 16 semanas.

**Voz en off:**
> «El plan entero. Cuatro fases: base, construcción, pico y afinamiento. Fíjate
> en las semanas de descarga —la tres, la seis, la nueve— donde el volumen baja
> a propósito. Eso no lo decide un modelo de lenguaje: son reglas de progresión
> con la regla del diez por ciento y la tirada larga topada.»

Señala el recuadro de **hoy**:

> «Y hoy va marcado con el color de su estado. Está en ámbar, así que el
> recuadro está en ámbar. El calendario habla el mismo código de color que el
> resto.»

### 2.4 · Técnica en vídeo — 2:10 a 2:35 (25 s)

**En pantalla:** **Analizar técnica** → elegir el clip → «sacando fotogramas» →
resultado.

**Voz en off, mientras extrae:**
> «Los fotogramas se sacan aquí, en el navegador. Al servidor suben diez
> imágenes, no el vídeo: en una red móvil son megas, y un clip de alguien
> corriendo lleva su cara y su calle. Lo que no se sube no se puede filtrar.»

**Al aparecer los hallazgos:**
> «El modelo describe lo que ve. Nada más: el esquema no tiene ningún campo
> donde escribir un consejo.»

**Y el remate, señalando que no hay señal:**
> «Y aquí es donde el producto se calla. Este corredor tiene una molestia
> activa, así que **no le corrige la zancada** — cambiar la mecánica de quien ya
> tiene algo es mover la carga justo donde no debe. Y lo dice: no es que se te
> vea bien, es que hoy no te toco.»

> Ésta es la escena que mejor resume el proyecto. Si tienes que recortar el
> vídeo, recorta cualquier otra.

### 2.5 · Actividad desde una captura — 2:35 a 2:55 (20 s)

**En pantalla:** **Sube tu actividad (Strava / Garmin / Runna)** → la captura →
la revisión con los campos rellenos.

**Voz en off:**
> «Cualquier app con pantalla. Cero OAuth, cero integraciones que caducan. El
> modelo lee la captura…»

**Señala el campo de ritmo, que no se puede editar:**
> «…pero el ritmo **no** lo copia: lo recalcula el motor con la distancia y el
> tiempo. Si lo leído no cuadra con lo calculado, gana el motor y la
> discrepancia queda marcada. Y nada entra a la bitácora sin que el corredor lo
> confirme.»

Pulsa **Guardar en mi bitácora**.

### 2.6 · Descarga del plan — 2:55 a 3:02 (7 s)

**En pantalla:** **Perfil → Descargar plan (CSV)**, y ábrelo en Excel.

**Voz en off:**
> «El corredor con experiencia ya lleva su hoja de cálculo. No se le pide que la
> abandone: se le llena. Con BOM, para que Excel no destroce los acentos.»

### 2.7 · n8n y Telegram — 3:02 a 3:20 (18 s)

**En pantalla:** el editor de n8n con los cinco flujos; dispara uno; el mensaje
llegando a Telegram.

**Voz en off:**
> «Cinco flujos proactivos. Y una decisión que parece de fontanería y es de
> producto: **n8n no sabe qué hora es en tu ciudad**. Corre cada hora en UTC y
> pregunta a la API quién tiene las seis de la mañana ahora mismo. Añadir un
> corredor en Tokio no toca ningún flujo.»

**Al llegar el mensaje:**
> «Los flujos tampoco redactan: la API devuelve el texto ya hecho. Así la regla
> de que toda cifra viene del motor vive en un solo sitio, con pruebas, en vez
> de repartida entre cinco JSON.»

---

## Cierre — 3:20 a 3:30 (10 s)

**En pantalla:** vuelta a la hoja, plano fijo.

**Voz en off:**
> «Un coach que conversa de verdad, que no inventa un solo número, y que sabe
> cuándo dejar de entrenarte y mandarte a un profesional. Gracias.»

---

## Planos de repuesto

Si algo falla en vivo, estos estados se fuerzan por URL. **Sólo pintan interfaz**
— no saltan la puerta del backend ni escriben nada.

| URL | para qué |
|---|---|
| `/app?estado=safety-red` | el sello **ANULADO** y la derivación médica |
| `/app?estado=safety-amber` | la sesión recortada, sin depender del día |
| `/app?estado=listening` | el orbe escuchando y la transcripción a media frase |
| `/app?estado=mic-denied` | el respaldo de texto cuando no hay micrófono |

El de **rojo** es el mejor plano suelto del producto: la hoja se anula delante
de quien mira. Si sobran quince segundos, va después de 2.4.

---

## Lo que NO conviene prometer en el vídeo

Escrito aquí para que no se cuele en la narración:

- **No digas «detecta lesiones».** No diagnostica: observa, y ante una señal
  deja de prescribir y deriva. Es una diferencia legal y real.
- **No digas que la visión «mide» la zancada.** Un vídeo de teléfono sin
  calibrar no mide nada; el propio prompt le prohíbe al modelo dar ángulos.
- **No prometas un número de semanas concreto** para el plan del Acto 1: lo
  decide el motor con la fecha y el punto de partida. Lee en pantalla el que
  salga.
- **No llames «integración con Strava» a la lectura de capturas.** Es
  deliberadamente lo contrario: funciona sin integrarse con nadie.

---

## Dos cosas conocidas que pueden salir en cámara

Están documentadas, no son sorpresas:

1. **El modelo se queda mudo tras un `toolResult`**, visto en dos de tres sondas
   por voz. En el navegador no ha ocurrido en varios intentos, pero si pasa:
   repite la frase o pasa a texto.
2. **Una pestaña con sesión de voz abierta puede quedarse pesada al navegar.**
   Si vas a cambiar de vista después de hablar, cierra el turno primero.
