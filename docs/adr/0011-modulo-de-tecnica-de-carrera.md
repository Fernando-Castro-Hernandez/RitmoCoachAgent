# ADR 0011 — Módulo de técnica de carrera

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Origen:** entrevista a corredor experimentado
- **Relacionada:** [ADR 0003](0003-motor-determinista-vs-llm-para-planes.md)

## Contexto

El hallazgo más fuerte de la investigación de usuario no fue una petición de
función, sino la descripción de un hueco vivido:

> «Estaría chido que tengan apartado de técnica, o sea, técnica de correr. Porque yo
> tardé un chingo en aprender a correr bien. Cómo pisar bien, cómo levantar bien la
> rodilla, las piernas, los brazos, las manos, la cabeza. O sea, todo. Es un apartado
> muy importante.»

Y lo enmarcó en un modelo mental de prioridades que él construyó solo:

```
        ╱  3 · Equipo         ╲   «frikadas» — tenis, ropa, gorra, reloj
      ╱    2 · Carga            ╲  subir ritmo y distancia poco a poco
    ╱      1 · TÉCNICA            ╲ «la base es la técnica, la neta es lo más importante»
```

Su conclusión textual sobre el tercer nivel: *«son frikadas de tercer nivel que no
son lo que te va a dar mayor resultado»*.

Ninguno de los competidores analizados en Fase 1 cubre la base de esa pirámide.
Strava registra, Nike Run Club acompaña, Runna planifica carga. Ninguno enseña a
correr.

## Decisión

**Se incorpora un módulo de técnica al MVP como característica titular**, servido
por una biblioteca curada de señales, no por generación libre del LLM.

### Por qué es la característica correcta para un producto de voz

La técnica es **nativa del audio**. No se puede leer una pantalla mientras se corre,
pero sí se puede escuchar *«acorta el paso, aterriza bajo tu cadera»* en el
kilómetro tres. Una aplicación basada en formularios y pantallas está
estructuralmente incapacitada para entregar coaching de técnica durante la carrera.
Nosotros no.

Esto justifica la voz por segunda vez y por una razón distinta a la de Fase 1: allá
la voz era el instrumento para *capturar* señal que un formulario pierde; aquí es el
canal para *entregar* corrección en el único momento en que sirve.

Además cierra el círculo de la tesis de seguridad. Fase 1 encontró lesiones causadas
por progresión agresiva. La técnica deficiente es la otra mitad de la misma
ecuación. La pirámide y la puerta de seguridad cuentan la misma historia.

## Diseño

### Las señales son datos, no generación

Igual que los números (ADR 0003), **las señales de técnica salen de una biblioteca
curada y versionada**, nunca de generación libre. El motivo es idéntico: un consejo
de técnica inventado puede lesionar a alguien.

```yaml
- id: cadencia-incremento
  categoria: cadencia
  nivel: [principiante, intermedio, avanzado]
  momento: pre-sesion
  texto_voz: >
    Hoy fíjate sólo en una cosa: da pasos un poquito más cortos y
    más frecuentes de lo que te sale natural. Nada más eso.
  explicacion_larga: >
    Acortar el paso hace que aterrices más cerca de tu centro de masa,
    lo que reduce la fuerza de frenado en cada zancada.
  contraindicaciones: [dolor_agudo_activo]
```

### La cadencia objetivo la calcula el motor

Aquí hay una corrección importante respecto a la creencia popular. **El objetivo de
180 pasos por minuto para todo el mundo es un mito**: proviene de una observación de
Jack Daniels sobre corredores de élite en los Juegos de 1984.

La evidencia real respalda **un incremento del 5–10 % sobre la cadencia propia del
corredor**, no un número universal:

- Un estudio de 2011 midió que aumentar la cadencia un 10 % redujo el impacto tibial
  máximo un 14 % y las fuerzas patelofemorales un 26 %.
- Un estudio de 2014 encontró reducción en la tasa de carga sobre la rodilla, un
  predictor de fractura por estrés.
- El mecanismo protector viene de **eliminar la sobrezancada**, y se consigue a
  cadencias muy por debajo de 180.

Por lo tanto es una fórmula del motor, no un número que el LLM recite:

```python
def cadencia_objetivo(base_spm: int, semanas_trabajadas: int) -> int:
    incremento = min(0.05 + 0.01 * semanas_trabajadas, 0.10)
    return round(base_spm * (1 + incremento))
```

Si no se conoce la cadencia base, **el sistema no inventa un objetivo**: pide al
usuario que la cuente durante 30 segundos, o la lee de su reloj.

### Entrega: una señal a la vez

Un entrenador real no dicta una lista de ocho correcciones. **Una señal por sesión,
repetida durante ~2 semanas hasta que se automatiza**, y sólo entonces la siguiente.
La biblioteca del MVP cubre cadencia, sobrezancada, postura, brazos, manos, mirada,
hombros y respiración.

### Tres preguntas en el onboarding

1. ¿Alguien te ha dado alguna vez indicaciones de técnica al correr?
2. ¿Sabes más o menos tu cadencia, o tu reloj la mide?
3. ¿Sientes que tu pie aterriza bastante por delante de tu cuerpo?

## Honestidad sobre la evidencia

La afirmación «la técnica previene lesiones» es más débil de lo que se repite en el
medio. Lo que sí tiene respaldo razonable es que **reducir la sobrezancada disminuye
la carga articular**. No existe una única forma correcta de correr, y la prescripción
de tipo de pisada (talón contra mediopié) sigue siendo discutida en la literatura.

En consecuencia el módulo es deliberadamente conservador: sugiere ajustes graduales,
no rediseña la zancada de nadie, y **nunca presenta la técnica como garantía de no
lesionarse**. La puerta de seguridad (`safety.py`) tiene siempre prioridad sobre
cualquier señal de técnica: con dolor activo en ámbar o rojo, no se emiten señales.

## Consecuencias

- Coste estimado: ~4 horas. Biblioteca en YAML, tres campos nuevos de perfil, una
  regla de selección determinista y una herramienta para que el coach explique una
  señal cuando se la pregunten.
- El nivel 3 de la pirámide (equipo, tenis, ropa, reloj) queda **fuera de alcance por
  decisión del propio usuario entrevistado**, que lo calificó como lo que menos
  resultado da. Es la clase de recorte que la investigación autoriza explícitamente.
- La biblioteca requiere curaduría humana. Se versiona en el repo y se revisa como
  código, no como contenido.

## Referencias

- Evidencia sobre cadencia y carga articular: estudios de 2011 y 2014 citados en
  revisiones divulgativas; el mecanismo aceptado es la reducción de sobrezancada.
- Origen del mito de 180 spm: observación de Jack Daniels, Juegos Olímpicos de 1984.
