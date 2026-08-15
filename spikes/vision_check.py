"""Verificación de la ruta de visión contra Bedrock real.

Código desechable, igual que los spikes de la Fase A. Genera una captura de
reloj sintética —fondo negro, tipografía condensada, unidades pegadas al número:
la peor entrada posible para un OCR clásico— y la pasa por el modelo de visión
para confirmar tres cosas:

1. Que `amazon.nova-2-lite-v1:0` responde y respeta el `toolConfig`.
2. Que lee las cifras correctas.
3. Que el motor recalcula el ritmo y detecta el que está mal puesto a propósito.

Uso:  uv run python spikes/vision_check.py
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from apps.api.credentials import ensure_aws_credentials  # noqa: E402
from apps.api.logging_setup import configure_logging  # noqa: E402
from apps.api.vision.client import BedrockVisionClient  # noqa: E402
from apps.api.vision.workout import extract_workout, reconcile  # noqa: E402

# Lo que "muestra" el reloj. El ritmo está puesto MAL a propósito: 8.42 km en
# 47:18 son 5:37/km, no 5:50. Si el sistema devuelve 5:37 y marca la
# discrepancia, la regla «si es un número, viene del motor» está viva.
DISTANCIA = "8.42"
TIEMPO = "47:18"
RITMO_EN_PANTALLA = "5:50"
PULSO = "152"


def _fuente(tam: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for nombre in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default(tam)


def captura_falsa() -> bytes:
    """Una pantalla de reloj creíble: fondo negro y números grandes."""
    img = Image.new("RGB", (480, 640), (8, 8, 10))
    d = ImageDraw.Draw(img)

    d.text((24, 28), "CARRERA AL AIRE LIBRE", font=_fuente(20), fill=(120, 120, 128))
    d.text((24, 56), "Sáb 15 ago · 6:41", font=_fuente(18), fill=(110, 110, 118))

    filas = [
        ("DISTANCIA", f"{DISTANCIA} km", (255, 255, 255)),
        ("TIEMPO", TIEMPO, (255, 255, 255)),
        ("RITMO MEDIO", f"{RITMO_EN_PANTALLA} /km", (0, 220, 180)),
        ("FC MEDIA", f"{PULSO} ppm", (255, 120, 90)),
    ]
    y = 120
    for etiqueta, valor, color in filas:
        d.text((24, y), etiqueta, font=_fuente(20), fill=(120, 120, 128))
        d.text((24, y + 26), valor, font=_fuente(64), fill=color)
        y += 128

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


async def main() -> int:
    configure_logging()
    ensure_aws_credentials()

    imagen = captura_falsa()
    Path("spikes/captura_sintetica.png").write_bytes(imagen)
    print(f"captura generada · {len(imagen)} bytes")
    print(f"la pantalla dice: {DISTANCIA} km · {TIEMPO} · {RITMO_EN_PANTALLA}/km · {PULSO} ppm")
    print("(el ritmo de la pantalla está mal a propósito)\n")

    cliente = BedrockVisionClient()
    inicio = time.monotonic()
    extraccion = await extract_workout(cliente, imagen, "image/png")
    tardanza = (time.monotonic() - inicio) * 1000

    print(f"── lo que LEYÓ el modelo ({tardanza:.0f} ms)")
    print(f"   distancia .......... {extraccion.distance_km}")
    print(f"   duración ........... {extraccion.duration_sec} s")
    print(f"   ritmo (leído) ...... {extraccion.avg_pace_sec_per_km} s/km")
    print(f"   pulso .............. {extraccion.avg_hr}")
    print(f"   confianza .......... {extraccion.confidence}")
    print(f"   ilegibles .......... {extraccion.unreadable_fields}\n")

    propuesta = reconcile(extraccion)
    minutos, segundos = divmod(propuesta.pace_sec_per_km, 60)
    print("── lo que PROPONE el sistema")
    print(f"   ritmo (calculado) .. {minutos}:{segundos:02d}/km")
    print(f"   fuente ............. {propuesta.source}")
    print(f"   discrepancia ....... {propuesta.discrepancy_flag}")
    print(f"   pide confirmar ..... {propuesta.needs_confirmation}\n")

    ok = True
    if extraccion.distance_km != float(DISTANCIA):
        print(f"✗ leyó {extraccion.distance_km} km, esperaba {DISTANCIA}")
        ok = False
    if propuesta.pace_sec_per_km != 337:
        print(f"✗ el motor calculó {propuesta.pace_sec_per_km} s/km, esperaba 337")
        ok = False
    if not propuesta.discrepancy_flag:
        print("✗ no detectó que el ritmo de la pantalla no cuadra")
        ok = False

    print("TODO CORRECTO ✓" if ok else "REVISAR ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
