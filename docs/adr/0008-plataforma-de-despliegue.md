# ADR 0008 — Plataforma de despliegue

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Decide:** dónde corre el sistema completo (web, API de voz, base de datos, n8n)

## Contexto

La arquitectura tiene un requisito que domina a todos los demás: el backend debe
mantener **dos conexiones largas y simultáneas por sesión de usuario**.

1. Un **WebSocket** abierto contra el navegador, por el que viajan frames de audio
   PCM de 16 kHz en ambos sentidos.
2. Un **stream bidireccional HTTP/2** abierto contra Amazon Bedrock
   (`InvokeModelWithBidirectionalStream`), con renovación cada 8 minutos.

El backend es un *puente con estado* entre ambas. No es un endpoint de
petición/respuesta, y ningún truco de diseño lo convierte en uno: el estado de la
conversación vive en la conexión.

Restricciones adicionales:

- `getUserMedia` exige contexto seguro, así que **HTTPS es obligatorio**, no opcional.
- Las credenciales de AWS no pueden vivir en el navegador (ADR 0006).
- El sistema necesita además Postgres y n8n corriendo de forma permanente.
- Presupuesto de tiempo: 4 días. Presupuesto económico: mínimo.

## Decisión

**Una sola instancia EC2 `t4g.small` (ARM Graviton) en `us-east-1`, ejecutando todo
el stack con Docker Compose detrás de Caddy como reverse proxy.**

- **Región `us-east-1`** porque es donde vive `amazon.nova-2-sonic-v1:0`.
- **Rol IAM de instancia** para hablar con Bedrock: cero credenciales estáticas en
  ningún archivo, ninguna variable de entorno y ningún commit.
- **Caddy** emite y renueva certificados TLS automáticamente y hace proxy de
  WebSocket sin configuración extra.
- **Un solo origen** sirve el frontend estático y el WebSocket: sin CORS, sin
  configuración de origen cruzado para WSS, un solo certificado.

### Por qué co-ubicarse con el modelo y no con el usuario

Cada frame de audio atraviesa los dos saltos, así que la latencia total es
comparable en ambos escenarios:

| Escenario | Usuario → backend | Backend → Bedrock | Total aprox. |
|---|---|---|---|
| Backend en `us-east-1` | 40–70 ms | 1–5 ms | **45–75 ms** |
| Backend en México | ~10 ms | 40–70 ms | 50–80 ms |

El empate en latencia se rompe por tres factores que sí son asimétricos:
el rol IAM sólo existe dentro de AWS, el tráfico backend↔Bedrock no sale a
internet público (menos jitter), y no se paga egreso entre nubes.

**Los números de la tabla son estimaciones y deben medirse.** El sistema
instrumenta `ttfa_ms` desde el primer día (ADR 0012) y el número real se publica
en el README.

## Alternativas consideradas

### Vercel — descartada para el backend

Las funciones serverless **terminan al devolver una respuesta: no existe un proceso
persistente que sostenga el socket**. Ni siquiera con Fluid Compute, cuyo tope de
duración es de 5 minutos — por debajo del ciclo de renovación de Nova Sonic. La
propia base de conocimiento de Vercel recomienda proveedores externos (Ably,
Pusher, PartyKit) para WebSockets.

Introducir un tercero sólo para transportar audio añadiría un salto de red, un
proveedor más que explicar y un costo, para resolver un problema que una instancia
de $12 al mes no tiene. Vercel sigue siendo excelente para el frontend estático,
pero eso partiría el despliegue en dos y sumaría configuración de origen cruzado
sin ganar nada.

### AWS App Runner — descartada, doble impedimento

No soporta WebSockets: está diseñado para aplicaciones HTTPS de petición/respuesta.
Además **cierra a clientes nuevos el 30 de abril de 2026**, lo que la vuelve una
elección indefendible en un ADR.

### AWS Lambda + API Gateway WebSocket — descartada por forma

API Gateway sí ofrece una API de WebSocket, pero es orientada a mensajes con un
backend sin estado. Nada sostendría el stream HTTP/2 hacia Bedrock entre
invocaciones. Habría que externalizar el estado de conexión a DynamoDB y añadir un
proceso separado que mantuviera el stream — es decir, reintroducir el servidor
persistente que Lambda evita, con más piezas. Complejidad desproporcionada para 4 días.

### ECS Fargate + ALB — correcta, pero prematura

Es la arquitectura correcta a escala y soporta WebSockets sin problema. Cuesta
definición de tarea, VPC, target groups y un ALB de ~$16/mes por sí solo. Para un
sistema con un usuario concurrente en una demo, es sobreingeniería.
**Queda documentada como la ruta de crecimiento** cuando haga falta más de un nodo.

### AWS Lightsail — descartada por el rol IAM

Más barata ($5/mes) y más simple, pero no expone roles de instancia como EC2:
requeriría claves de acceso estáticas en el servidor. Eso contradice el ADR 0006 y
debilita el argumento de seguridad, que es uno de los puntos fuertes del entregable.

### Fly.io / Railway / Render — descartadas

Despliegue de contenedores muy cómodo y con soporte real de WebSocket. Dos
inconvenientes decisivos: obligan a claves estáticas de AWS en variables de entorno,
y no están co-ubicadas con Bedrock. Fly.io tiene región en Querétaro, lo cual es
tentador por cercanía al usuario, pero la tabla de latencias muestra que acercarse
al usuario no compensa alejarse del modelo.

## Consecuencias

**A favor**

- Es la única opción que satisface el requisito de conexiones largas sin piezas extra.
- Cero credenciales estáticas de AWS en todo el sistema.
- El mismo `docker-compose.yml` corre en local y en producción: paridad dev/prod real
  y una demo reproducible con un comando.
- ~$12 USD/mes, cubierto por créditos de cuenta.

**En contra, y aceptado conscientemente**

- **Punto único de falla.** Aceptable para una demo; mitigado por el modo `TEXT_ONLY`
  y por el video grabado del ADR de contingencia.
- **Sin autoescalado.** Irrelevante a esta escala, y la ruta a Fargate está documentada.
- **El despliegue es un comando por SSH**, no un pipeline de entrega continua completo.
  CI sí corre pruebas y evals en cada push; el deploy es `make deploy`. Es una
  simplificación deliberada por presupuesto de tiempo, declarada en el README.

## Referencias

- [Vercel KB — Do Vercel Serverless Functions support WebSocket connections?](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections)
- [AWS re:Post — WebSockets on App Runner](https://repost.aws/questions/QU0jOAcOoTQqigUj6B9oGDxg/websockets-on-apprunner)
- [AWS App Runner — release notes](https://docs.aws.amazon.com/apprunner/latest/relnotes/relnotes.html)
