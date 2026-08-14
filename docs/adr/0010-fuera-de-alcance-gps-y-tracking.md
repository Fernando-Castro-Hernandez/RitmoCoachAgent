# ADR 0010 — Sin rastreo GPS: el coach no compite con el reloj

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Origen:** entrevista a corredor experimentado (ver [Fase 2](../fases/fase-2-investigacion-usuario.md))

## Contexto

La investigación de usuario arrojó una petición explícita y repetida:

> «Lo que una persona necesita de primera instancia es primero que nada que tenga
> acceso a la ubicación. Porque si no tiene acceso a la ubicación no puedes registrar
> la ruta que hizo. Otro punto el tiempo en el que la hizo. El ritmo en el que la
> hizo. […] Y la distancia, obviamente. Eso es indispensable.»

Y una segunda, sobre fricción:

> «Y que no te gusta salir de la aplicación.»

Tomada literalmente, la petición describe un rastreador GPS: Strava o Nike Run Club.
Ignorarla sería descartar investigación real. Implementarla consumiría el proyecto
entero y produciría una versión peor de un producto que el usuario ya tiene instalado.

## Decisión

**No se implementa rastreo GPS, grabación de ruta ni mapas.** El sistema se
posiciona explícitamente como **la capa de entrenamiento encima del rastreador**,
no como su reemplazo.

En su lugar se implementa **registro de sesión por voz**, que captura las mismas
métricas que el usuario nombró como indispensables:

> «Corrí ocho kilómetros en cuarenta y cinco minutos.»
> → el motor calcula el ritmo (5:37/km), lo registra, lo compara con el plan y
> responde con contexto.

## Justificación

1. **El reto pide un coach conversacional, no un rastreador.** El enunciado de
   Adivor es «un chatbot de voz conversacional que funcione como entrenador
   personal». El GPS no aparece.
2. **La geolocalización en segundo plano no es viable en una PWA.** iOS suspende el
   seguimiento cuando la pantalla se apaga. Hacerlo bien exige aplicación nativa,
   permisos de background y gestión de batería: semanas, no días.
3. **Sería competir donde el competidor es más fuerte.** Strava lleva más de una
   década puliendo suavizado de GPS, segmentos y renderizado de rutas. Ningún
   entregable de 4 días mejora eso.
4. **El ritmo se obtiene sin GPS.** El usuario dijo que el ritmo es *la* métrica
   («es como lo que mide tu capacidad»), y el ritmo es distancia sobre tiempo. Dos
   datos que se dicen en voz alta en tres segundos. **Obtenemos el 80 % del valor
   que él describió con el 5 % del costo, y por la modalidad que ya estamos
   construyendo.**
5. **La ruta era medio, no fin.** Al escuchar la entrevista completa, la ruta nunca
   se menciona como algo que le ayude a mejorar. Lo que le ayudó a mejorar, según él
   mismo, fue aprender técnica. La ruta es un artefacto del registro, no del
   entrenamiento.

## Sobre «no te gusta salir de la aplicación»

Esta fricción se reconoce y se ataca por otro lado. El registro por voz significa
que el usuario **nunca abandona la conversación para anotar nada**: dice lo que hizo
y sigue. La fricción que la investigación identificó era la de *registrar*, y esa sí
la eliminamos.

## Ruta de crecimiento documentada

La integración con Strava vía OAuth resuelve el hueco de forma correcta: importar
actividades ya rastreadas en lugar de rastrearlas de nuevo. Queda **fuera del MVP**
porque OAuth de terceros consume aproximadamente un día de los cuatro disponibles y
no es donde está la diferenciación.

Frase de posicionamiento para el README y la entrevista:

> **No competimos con tu reloj. Nos conectamos a él.**

## Consecuencias

- Los datos de sesión dependen de que el usuario los reporte, con el riesgo de
  imprecisión que eso implica. Aceptado: un coach humano opera exactamente con esa
  misma limitación.
- No hay mapas ni visualización de ruta en la interfaz. El espacio se usa para lo
  que sí diferencia: la tarjeta de sesión, la justificación de la decisión y la
  señal de técnica del día.
- Se pierde el registro automático de cadencia, que habría alimentado el módulo de
  técnica ([ADR 0011](0011-modulo-de-tecnica-de-carrera.md)). Se sustituye por
  autorreporte y por la lectura del reloj del usuario si lo tiene.
