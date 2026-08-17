# ADR 0015 · Despliegue en EC2 sin SSH, con HTTPS sin dominio propio

**Estado:** aceptado · 17 de agosto de 2026
**Contexto:** tarea F1

## Decisión

Una instancia `t4g.small` con Ubuntu 24.04 (arm64), administrada **por SSM**, con
el puerto 22 cerrado. El código llega desde S3, los secretos por SSM, y el
certificado lo emite Let's Encrypt para un dominio de `sslip.io`.

## Las cuatro decisiones, y qué se descartó en cada una

### 1 · SSM en vez de SSH

El grupo de seguridad abre **80 y 443, nada más**. No hay puerto 22, no hay par
de llaves y no hay una clave privada que custodiar, rotar o filtrar.

Lo que se pierde: una sesión interactiva cómoda necesita el plugin de
`session-manager`. Para automatizar no hace falta — `aws ssm send-command` basta,
y es lo que usa `scripts/deploy_remote.py`.

Lo que se gana es medible: el 22 abierto a internet recibe intentos de acceso
desde el primer minuto, y aquí no hay superficie donde intentarlo.

### 2 · El rol de instancia, con permiso mínimo de verdad

El rol `ritmo-ec2` puede hacer exactamente tres cosas:

- `bedrock:InvokeModelWithBidirectionalStream` **y `bedrock:InvokeModel`** sobre
  **los dos ARN de Nova Sonic**, no sobre `bedrock:*` ni sobre `*`.

  Lo de `InvokeModel` es un hallazgo, no un descuido. Con sólo la acción
  bidireccional, `start()` abre el stream y **el primer evento de vuelta es un
  `AccessDeniedException`**. Y lo desconcertante: `iam simulate-principal-policy`
  decía `allowed` para la acción bidireccional sobre ese ARN exacto, así que la
  simulación no basta para creerse que un permiso está completo. Se probó
  quitando `InvokeModelWithResponseStream` para confirmar que con dos acciones
  alcanza; el recurso sigue acotado a los dos modelos de voz.
- `s3:GetObject` sobre **un objeto**: `ritmo-deploy-.../ritmo.tar.gz`.
- Lo que trae `AmazonSSMManagedInstanceCore`, que es lo que hace posible el
  punto 1.

No hay ninguna credencial estática en la máquina. `scripts/deploy_remote.py`
filtra `AWS_ACCESS_KEY_ID` y compañía con una **lista blanca** al copiar el
`.env`, y hay una prueba que lo fija: mandar las claves del usuario
administrador a un servidor con el 443 abierto sería entregar la cuenta junto
con la aplicación.

### 3 · El código por S3, no por `git clone`

El repositorio es privado y la instancia no tiene con qué autenticarse. Las tres
salidas eran:

| opción | por qué no |
|---|---|
| Hacer público el repositorio | La visibilidad del repositorio de alguien no la decide un script de despliegue. |
| Un token de despliegue en la máquina | Deja una credencial de GitHub viviendo en un servidor público. |
| **Mandar el artefacto por S3** | **Elegida.** Un bucket privado, cifrado, y un rol que puede leer un objeto. |

El artefacto se empaqueta excluyendo `.env`, `.venv`, `node_modules` y `dist`.
El frontend se **compila en la instancia**, para que lo que sirve Caddy salga
del mismo árbol que la API — subir un `dist` construido en otro sitio es como
acaban desincronizados sin que nadie lo note.

### 4 · HTTPS sin comprar dominio: `sslip.io`

Esto no es una comodidad, es un requisito: **`getUserMedia` exige contexto
seguro**. Sin HTTPS no hay micrófono, y sin micrófono no hay producto.

`sslip.io` resuelve `54-80-131-31.sslip.io` a `54.80.131.31`, sin registro y sin
configuración. Let's Encrypt emite para ese nombre igual que para cualquier
otro, y Caddy lo renueva solo.

La IP es **elástica**, y eso es lo que hace que el nombre sea estable: sin ella,
parar y arrancar la instancia cambiaría la IP y con ella la URL del entregable.

Lo que hay que decir de `sslip.io`: es un servicio de terceros en la ruta de
resolución. Si desaparece, el nombre deja de resolver — la aplicación sigue
viva en su IP, pero sin HTTPS válido. Para un entregable de fin de semana el
canje es correcto; para producción de verdad, un dominio propio.

## Lo que queda como deuda, dicho de frente

- **Los secretos pasan por esta máquina.** `deploy_remote.py` lee el `.env`
  local y lo manda por SSM. Lo correcto con más tiempo es Secrets Manager y que
  el rol los lea al arrancar, sin que el portátil de nadie los toque.
- **Una sola instancia, sin copias de seguridad.** La base vive en un volumen de
  Docker en la misma máquina. Es adecuado para una demostración y no para gente
  real: un fallo del disco se lleva las bitácoras de entrenamiento.
- **n8n escucha sólo en `127.0.0.1`.** Su panel dispara los avisos y guarda las
  credenciales del bot, así que no se publica; se llega por un túnel de SSM. La
  consecuencia es que importar los flujos exige ese túnel, y está documentado en
  `automation/n8n/README.md`.
- **Sin despliegue continuo.** `python scripts/deploy_remote.py` a mano. Un
  pipeline de GitHub Actions con OIDC contra este mismo rol es el siguiente
  paso natural y no cabía en la ventana.
