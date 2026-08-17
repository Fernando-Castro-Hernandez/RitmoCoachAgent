"""Lo que el coach sabe que puede pedir.

Las herramientas existían y estaban probadas desde la tarea C2, pero **nunca se
le habían declarado al modelo**: `prompt_start` aceptaba `tools` y nadie se los
pasaba. El coach hablaba muy bien y no podía hacer nada. Esto lo cierra.

## Las descripciones son prompt, no documentación

El modelo no lee `tools.py`; lee esto. Cada descripción está escrita para
decidir **cuándo** llamar, no para explicar qué hace por dentro — que es la
diferencia entre un coach que consulta el plan y uno que se lo imagina.

Dos van más lejos y llevan escrito el límite, no la capacidad:

- `create_plan` avisa de que **puede negarse** y devolver preguntas. Que el
  modelo sepa de antemano que ese camino existe es lo que hace que preguntar no
  se sienta un fallo suyo.
- `log_run` avisa de que el ritmo lo calcula el motor. Si no, el modelo intenta
  mandarlo, y ahí es donde empiezan las cifras inventadas.

## Por qué no se generan desde las firmas

Se podrían derivar por introspección de `CoachTools`. No se hace a propósito: lo
que el modelo necesita saber para decidir cuándo llamar no está en la firma de
Python, está en la descripción. Un generador produciría esquemas correctos y
descripciones inútiles.

El precio es que hay que acordarse de tocar los dos sitios. Una prueba comprueba
que toda herramienta declarada aquí existe en `CoachTools` y al revés, así que
el olvido falla el build en vez de aparecer en producción como un coach que
llama a una herramienta que no está.
"""

from __future__ import annotations

import json
from typing import Any

# `additionalProperties: false` en todos: si el modelo inventa un argumento, es
# mejor que falle la validación a que llegue a la herramienta y se ignore en
# silencio — un argumento ignorado es una instrucción del corredor perdida.
_ESQUEMAS: dict[str, tuple[str, dict[str, Any]]] = {
    "get_today_session": (
        "La sesión que le toca hoy al corredor, con distancia, ritmo objetivo y "
        "el porqué. Úsala SIEMPRE antes de decir qué entrenamiento toca: nunca "
        "digas una distancia ni un ritmo que no venga de aquí.",
        {},
    ),
    "get_week_context": (
        "Cómo va la semana: volumen acumulado, sesiones hechas y el estado de la "
        "puerta de seguridad. Úsala para responder «¿cómo voy?» y antes de "
        "cualquier ajuste.",
        {},
    ),
    "log_run": (
        "Registra una carrera que el corredor acaba de contar. **No mandes el "
        "ritmo: lo calcula el motor** a partir de la distancia y el tiempo, y te "
        "lo devuelve. Si sólo tienes uno de los dos datos, pregunta el otro.",
        {
            "distance_km": {"type": "number", "description": "kilómetros recorridos"},
            "duration_sec": {"type": "integer", "description": "duración en segundos"},
            "rpe": {
                "type": "integer",
                "description": "esfuerzo percibido de 1 a 10, si lo dijo",
            },
            "notes": {"type": "string"},
        },
    ),
    "report_wellness": (
        "Registra cualquier señal del cuerpo, antes de responder nada sobre "
        "entrenamiento: la puerta de seguridad se evalúa con esto y puede cambiar "
        "lo que tienes permitido decir.\n"
        "\n"
        "**El mecanismo cuenta tanto como el síntoma.** Llámala aunque el "
        "corredor NO use la palabra «dolor», aunque diga que es cero, y aunque le "
        "quite importancia él mismo. Todo esto la dispara:\n"
        "- Cambió la forma de correr para esquivar algo: «corro raro», «cojeo», "
        "«voy apoyando distinto», «piso con cuidado» → altered_gait\n"
        "- Le molesta en reposo o de noche, sin haber corrido → night_or_rest_pain\n"
        "- Empeora mientras corre en vez de aflojar → worsens_during_run\n"
        "- Un punto exacto del hueso → bone_point_pain\n"
        "- Se le duerme algo, hormigueo → numbness_tingling\n"
        "- Hinchazón visible → swelling\n"
        "- Pecho, mareo, falta de aire desproporcionada → la bandera que toque\n"
        "\n"
        "«No me duele casi nada, pero llevo dos semanas corriendo raro» ES un "
        "reporte: pon el dolor que él diga y la bandera del mecanismo. Frenar de "
        "más cuesta una sesión; no registrar un mecanismo cuesta una lesión.\n"
        "\n"
        "Las banderas van en inglés, tal como se listan.",
        {
            "pain_score": {
                "type": "integer",
                "description": (
                    "dolor de 0 a 10, tal como lo diga el corredor. Un 0 es válido "
                    "y NO es razón para saltarse la llamada si hay un mecanismo."
                ),
            },
            "pain_area": {"type": "string", "description": "dónde, en palabras del corredor"},
            "flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "señales presentes, de esta lista exacta: chest_pain, "
                    "dizziness_syncope, disproportionate_dyspnea, altered_gait, "
                    "bone_point_pain, worsens_during_run, night_or_rest_pain, "
                    "swelling, numbness_tingling, pregnancy, known_cardiac_condition"
                ),
            },
            "sleep_hours": {"type": "number"},
        },
    ),
    "create_plan": (
        "Genera el plan de entrenamiento completo.\n"
        "\n"
        "**PASA TODO LO QUE YA TE HAYA CONTADO, EN LA MISMA LLAMADA.** Si en la "
        "conversación te dijo cuánto corre, cuál es su tirada más larga, a qué "
        "ritmo o si tiene molestias, mándalo aquí: se guarda en su perfil y el "
        "plan sale en este mismo turno. Volver a preguntarle lo que acaba de "
        "decirte es el error más caro que puedes cometer.\n"
        "\n"
        "Si dijo que NO tiene molestias, manda `injuries: []` — la lista vacía "
        "es una respuesta, y es la que hace que deje de preguntarse.\n"
        "\n"
        "La respuesta trae `today` con la sesión de hoy YA RESUELTA. Úsala tal "
        "cual. NO deduzcas lo de hoy dividiendo el volumen de la semana entre "
        "los días: esa cuenta da una cifra que ningún motor produjo, y algunos "
        "días son de descanso. Si `today.rest_day` es cierto, hoy se descansa.\n"
        "\n"
        "**Puede negarse**: si de verdad falta algo, devuelve `ok: false` con "
        "`needs_context` y una pregunta ya redactada en `next_question`. Haz esa "
        "pregunta —UNA, conversacional— y vuelve a llamar añadiendo lo que te "
        "conteste. Insistir sin datos nuevos no cambia el resultado.",
        {
            "distance": {
                "type": "string",
                "enum": ["5k", "10k", "21k", "42k"],
                "description": "la meta del corredor",
            },
            "race_date": {"type": "string", "description": "fecha de la carrera, AAAA-MM-DD"},
            "weekly_volume_km": {
                "type": "number",
                "description": "kilómetros que corre por semana AHORA, tal como te lo dijo",
            },
            "longest_run_km": {
                "type": "number",
                "description": "la distancia más larga que YA corrió, no la que quiere correr",
            },
            "reference_pace": {
                "type": "string",
                "description": (
                    "su ritmo habitual en minutos por kilómetro, formato «7:00». "
                    "Sirve para anclar las zonas."
                ),
            },
            "injuries": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "molestias o lesiones que mencione, en sus palabras. "
                    "LISTA VACÍA si dijo que no tiene ninguna."
                ),
            },
            "days_per_week": {
                "type": "integer",
                "description": "cuántos días a la semana puede correr",
            },
        },
    ),
    "adjust_plan": (
        "Recalcula el plan con lo que ha pasado desde que se creó. Úsala cuando "
        "el corredor se salte sesiones, cambie de disponibilidad o vuelva de una "
        "molestia. Nunca ajustes el plan describiéndolo con palabras: se ajusta "
        "aquí o no se ajusta.",
        {
            "reason": {"type": "string", "description": "por qué se ajusta, en una frase"},
        },
    ),
    "explain_technique_cue": (
        "El texto exacto de una señal de técnica. Úsala en vez de explicar la "
        "técnica de memoria: estas señales están escritas para decirse en voz "
        "alta mientras alguien corre.",
        {"cue_id": {"type": "string", "description": "identificador de la señal"}},
    ),
    "get_target_cadence": (
        "La cadencia objetivo de este corredor, ya progresada. La cadencia sube "
        "poco a poco desde la suya; no la inventes ni cites los 180 pasos por "
        "minuto de internet.",
        {
            "weeks_worked": {"type": "integer", "description": "semanas trabajando la cadencia"},
        },
    ),
    "environment_check": (
        "Si el calor o la calidad del aire obligan a modificar la sesión (R8). "
        "Úsala cuando el corredor mencione que hace mucho calor o que el aire "
        "está mal.",
        {
            "temp_c": {"type": "number", "description": "temperatura en grados Celsius"},
            "aqi": {"type": "integer", "description": "índice de calidad del aire, si se sabe"},
        },
    ),
}

# Qué es indispensable en cada una.
#
# **`user_id` no aparece en ningún esquema, y eso lo enseñó una sonda en vivo.**
# Lo declaré obligatorio razonando que así el modelo no lo omitiría. El modelo
# no lo omitió: contestó «dime tu user_id para seguir». Claro — no lo tiene, y
# un parámetro obligatorio que no puede rellenar lo convierte en una pregunta
# al corredor. Un identificador interno filtrado a la conversación.
#
# La forma correcta es la que ya estaba en el ejecutor: se impone, no se pide.
# Si el modelo no puede verlo, no puede preguntarlo ni equivocarse con él.
_OBLIGATORIOS: dict[str, list[str]] = {
    "get_today_session": [],
    "get_week_context": [],
    "log_run": ["distance_km", "duration_sec"],
    "report_wellness": ["pain_score"],
    "create_plan": ["distance"],
    "adjust_plan": ["reason"],
    "explain_technique_cue": ["cue_id"],
    "get_target_cadence": [],
    "environment_check": ["temp_c"],
}

TOOL_NAMES = tuple(_ESQUEMAS)


def tool_specs() -> list[dict[str, Any]]:
    """Las herramientas en el formato que espera `promptStart` de Nova Sonic.

    `inputSchema.json` va como **cadena**, no como objeto: es lo que exige la
    API, y mandarlo como objeto falla con un error de validación que no dice
    cuál de los dos formatos quería.
    """
    especificaciones = []
    for nombre, (descripcion, propiedades) in _ESQUEMAS.items():
        esquema = {
            "type": "object",
            "properties": propiedades,
            "required": _OBLIGATORIOS[nombre],
            "additionalProperties": False,
        }
        especificaciones.append(
            {
                "toolSpec": {
                    "name": nombre,
                    "description": descripcion,
                    "inputSchema": {"json": json.dumps(esquema, ensure_ascii=False)},
                }
            }
        )
    return especificaciones
