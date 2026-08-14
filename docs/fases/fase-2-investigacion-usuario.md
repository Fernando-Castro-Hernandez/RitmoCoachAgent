# Fase 2 — Investigación de usuario y reajuste de alcance

- **Fecha:** 2026-08-13
- **Método:** entrevista abierta, un participante, corredor experimentado
- **Entrada:** [Fase 1 — alcance y viabilidad](fase-1-alcance-y-viabilidad.html)

## Nota sobre el método

Una entrevista con un solo participante no es una muestra. No permite afirmar que
«los corredores quieren X», y este documento no lo hace. Sí permite dos cosas
valiosas: **detectar huecos que el análisis de escritorio no vio**, y **validar o
refutar supuestos concretos** del diseño previo. Ambas ocurrieron.

Reportar esa limitación explícitamente es parte del entregable: un evaluador técnico
distingue de inmediato entre «investigación de usuario» y «una plática con un amigo
presentada como investigación de usuario».

## El principio de análisis

La entrevista se procesa separando dos cosas que casi siempre se confunden:

> **Lo que el usuario pide** describe la solución que ya conoce.
> **Lo que el usuario revela** describe el problema que tiene.

Aquí el participante pidió un rastreador GPS —porque es la categoría de aplicación
que existe en su cabeza— y reveló un hueco de enseñanza que ningún producto del
mercado cubre.

## Análisis línea por línea

| Lo que dijo | Lo que revela | Veredicto |
|---|---|---|
| «Acceso a la ubicación… registrar la ruta que hizo» | Quiere registro sin fricción, no cartografía | **OUT** el GPS · **IN** el registro por voz |
| «El ritmo es muy importante… es lo que mide tu capacidad» | El ritmo es identidad, no un dato más | **IN** — el ritmo es la unidad de conversación |
| «No es lo mismo 21 km a 6:00 que a 4:30, eso es otro nivel» | La segmentación por nivel debe ser por ritmo, no sólo por distancia | **IN** — corrige la matriz de Fase 1 |
| «Que te pregunte cuál es tu ritmo, tu máxima distancia» | Valida el onboarding diseñado en Fase 1 | **Confirmado** |
| «Que te pregunte por los principales problemas que tiene la persona al correr» | Campo de perfil que Fase 1 no tenía | **IN** — nuevo campo |
| «No tenía dónde transportar mi agua» | La logística práctica bloquea el entrenamiento | **IN** — consejos logísticos por sesión |
| «No sabía cómo pisar bien… tardé un chingo en aprender a correr bien» | **Nadie le enseñó técnica y le costó años** | **IN** — módulo titular |
| «La base es la técnica, la neta es lo más importante» | Modelo mental de prioridad del propio usuario | **IN** — estructura el coaching |
| «Tenis, ropa, gorra, reloj… son frikadas de tercer nivel» | Él mismo lo desprioriza | **OUT** — con permiso explícito |
| «Y que no te gusta salir de la aplicación» | El cambio de contexto es fricción real | **Atendido** por el registro por voz |

## La pirámide

El participante construyó, sin que se le pidiera, un modelo de prioridades:

```
          ╱  3 · EQUIPO           ╲     tenis, ropa, gorra, reloj
        ╱                           ╲   «frikadas… no es lo que te da mayor resultado»
      ╱    2 · CARGA                  ╲  volumen, ritmo, progresión
    ╱                                   ╲ «ir subiendo poco a poco»
  ╱      1 · TÉCNICA                      ╲ pisada, cadencia, postura, brazos
╱                                           ╲ «la base… lo más importante»
```

El diagnóstico competitivo de Fase 1 encaja de forma incómoda en esta pirámide:

| Nivel | Quién lo cubre hoy |
|---|---|
| 3 · Equipo | Marcas, reseñas, influencers — saturado |
| 2 · Carga | Runna, Garmin Coach, Nike Run Club — competido |
| **1 · Técnica** | **Nadie, en ninguna de las aplicaciones analizadas** |

**El hueco de mercado está en la base de la pirámide, que es justo donde el usuario
dice que está el mayor retorno.**

## Por qué esto refuerza la apuesta por la voz

Fase 1 justificó la voz como **instrumento de captura**: una conversación extrae la
señal que un formulario pierde («bien… bueno, algo me molestó la rodilla»).

La investigación de usuario la justifica por una segunda razón, independiente de la
primera: la voz es el único **canal de entrega** posible para la técnica.

No se puede leer una pantalla mientras se corre. Sí se puede escuchar *«acorta el
paso, aterriza bajo tu cadera»* en el kilómetro tres. Un producto basado en
formularios y pantallas está estructuralmente incapacitado para entregar corrección
de técnica en el momento en que sirve.

Y cierra el círculo de seguridad: Fase 1 documentó lesiones causadas por progresión
agresiva; la técnica deficiente es la otra mitad de la misma ecuación. La pirámide y
la puerta de seguridad cuentan la misma historia.

## Qué entra al MVP

| Adición | Qué implica | Coste |
|---|---|---|
| **Módulo de técnica** | Biblioteca curada de ~10 señales, 3 preguntas de onboarding, una señal por sesión. Ver [ADR 0011](../adr/0011-modulo-de-tecnica-de-carrera.md) | ~4 h |
| **Registro de sesión por voz** | «Corrí 8 km en 45 minutos» → el motor calcula ritmo, registra y compara con el plan | ~2 h |
| **Ritmo como ciudadano de primera** | Toda sesión prescribe rango de ritmo; el perfil guarda ritmo actual por distancia; el coach habla en ritmo | ya previsto, se eleva |
| **Campo «problemas al correr»** | Hidratación, rozaduras, respiración, calzado, dolor recurrente. Alimenta consejos y contexto | ~1 h |
| **Consejos logísticos por sesión** | Tirada larga → hidratación. Primera vez sobre 10 km → rozaduras | ~30 min |
| **Nivel por ritmo, no sólo por distancia** | Un 21K a 6:00/km y uno a 4:30/km son planes distintos | ajuste a la matriz |

Total aproximado: **un día de los cuatro**. Asumible, y es donde está la diferenciación.

## Qué queda fuera, y por qué

| Descartado | Razón |
|---|---|
| **Rastreo GPS, rutas y mapas** | No es lo que pide el reto; la geolocalización en segundo plano no es viable en PWA; competir con Strava donde Strava es fuerte. Ver [ADR 0010](../adr/0010-fuera-de-alcance-gps-y-tracking.md) |
| **Recomendación de equipo** | Descartado por el propio entrevistado: nivel 3 de su pirámide, «no es lo que te va a dar mayor resultado» |
| **Coaching de técnica en vivo durante la carrera** | Requiere GPS y audio en segundo plano. Es la v2 natural y donde la voz gana para siempre, pero no cabe en 4 días |
| **Planes de nutrición** | Territorio clínico. El coach da consejos logísticos, no pautas nutricionales |
| **Integración con Strava** | OAuth de terceros consume ~1 día. Documentado como ruta de crecimiento |

## Correcciones al diseño de Fase 1

1. **La matriz de niveles se segmenta también por ritmo.** El participante fue
   enfático: dos corredores con la misma distancia y distinto ritmo son casos
   distintos. La matriz de Fase 1 segmentaba sólo por distancia objetivo.
2. **El perfil suma tres campos de técnica y uno de problemas prácticos.**
3. **El registro por voz sube de «nice-to-have» a must-have**, porque es la
   respuesta económica a la petición más insistente de la entrevista.

## Posicionamiento resultante

> **Los demás te dicen cuánto correr. Ritmo te enseña a correr, y luego cuánto.**
>
> No competimos con tu reloj. Nos conectamos a él.
