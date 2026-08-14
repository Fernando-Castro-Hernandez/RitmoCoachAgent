# Reto técnico original — Adivor

Fuente de verdad de los requisitos. Transcripción del correo recibido de Adivor
para la vacante **Practicante Dual — Desarrollo de Producto y Proyectos Digitales**.

## Correo

> Recibimos tu postulación a la vacante de Practicante Dual — Desarrollo de Producto
> y Proyectos Digitales…
>
> La entrevista será de manera remota el día **viernes 14 de agosto**…
>
> El reto es construir un **chatbot de voz conversacional que funcione como entrenador
> personal (coach) para runners de todos los niveles**, ayudándolos a prepararse para
> carreras de **5k, 10k, 21k y maratón**. El formato de entrega y las tecnologías son
> **totalmente libres**: usa lo que mejor domines.
>
> Como **puntos extra opcionales**, valoramos que el chatbot tenga **memoria de
> conversaciones anteriores** y que envíe **recordatorios proactivos por WhatsApp,
> correo o Telegram**.
>
> La fecha límite para enviarlo es el **lunes 17 de agosto a las 4:00 p.m.**, al correo
> **administracion@adivor.com**.

## Requisitos extraídos

| # | Requisito | Tipo | Dónde se resuelve |
|---|---|---|---|
| R-1 | Chatbot de **voz conversacional** | Obligatorio | Nova 2 Sonic, streaming bidireccional |
| R-2 | Funciona como **entrenador personal** | Obligatorio | Motor de dominio + reglas R1–R8 |
| R-3 | Para **runners de todos los niveles** | Obligatorio | Matriz de niveles, segmentada por distancia y ritmo |
| R-4 | Distancias **5k, 10k, 21k, 42k** | Obligatorio | Generadores de plan por distancia |
| R-5 | **Memoria** de conversaciones anteriores | Extra valorado | Perfil + estado + bitácora + memoria semántica |
| R-6 | **Recordatorios proactivos** | Extra valorado | n8n → Telegram |
| R-7 | Formato y tecnologías libres | — | Justificado en los ADR |

## Restricciones de entrega

- **Fecha límite:** lunes 17 de agosto de 2026, 16:00
- **Destino:** administracion@adivor.com
- **Contexto:** 3 vacantes disponibles, proceso competitivo

## Notas de decisión

- **WhatsApp se descarta** en favor de Telegram: la verificación de Meta Business puede
  tomar días y no aporta a la evaluación. Decisión documentada en ADR 0004.
- Los dos «puntos extra opcionales» (R-5 y R-6) se tratan como **must-have**, no como
  opcionales: la memoria es lo que separa a un coach de un generador de planes, y los
  agentes autónomos con notificación proactiva son la categoría de producto que Adivor
  vende a sus clientes.
