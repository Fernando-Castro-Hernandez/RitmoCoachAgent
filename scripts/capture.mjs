/**
 * Capturas de la interfaz para la revisión de diseño.
 *
 * Existe porque la extensión del navegador captura la VENTANA y no el viewport
 * emulado: pedir 390 px devolvía siempre la misma imagen de 1528. Playwright sí
 * emula el dispositivo, así que la captura móvil es real y no una ventana
 * estrecha.
 *
 * Uso:  node scripts/capture.mjs [url-base]
 */

import { mkdirSync } from "node:fs";
import { chromium, devices } from "playwright";

const BASE = process.argv[2] ?? "http://localhost:5199";
const SALIDA = ".impeccable/review";

const MOVIL = { width: 390, height: 844 };
const ESCRITORIO = { width: 1440, height: 960 };

/** Cada toma: archivo, ruta, viewport, idioma y espera extra. */
const TOMAS = [
  { archivo: "mobile.png", ruta: "/", vp: MOVIL },
  { archivo: "mobile-en.png", ruta: "/", vp: MOVIL, idioma: "en" },
  { archivo: "desktop.png", ruta: "/", vp: ESCRITORIO },
  { archivo: "onboarding.png", ruta: "/?estado=onboarding", vp: MOVIL },
  { archivo: "upload.png", ruta: "/?estado=upload", vp: MOVIL },
  { archivo: "state-listening.png", ruta: "/?estado=listening", vp: MOVIL },
  { archivo: "state-error.png", ruta: "/?estado=error", vp: MOVIL },
  { archivo: "state-mic-denied.png", ruta: "/?estado=mic-denied", vp: MOVIL },
  { archivo: "state-safety-red.png", ruta: "/?estado=safety-red", vp: MOVIL },
];

mkdirSync(SALIDA, { recursive: true });

const navegador = await chromium.launch();

for (const toma of TOMAS) {
  const contexto = await navegador.newContext({
    ...devices["Pixel 7"],
    viewport: toma.vp,
    isMobile: toma.vp === MOVIL,
    hasTouch: toma.vp === MOVIL,
    deviceScaleFactor: 2,
    locale: toma.idioma === "en" ? "en-US" : "es-MX",
    // El perfil ya existe: así la hoja se abre directamente y no el carrusel,
    // salvo cuando la toma pide el carrusel a propósito.
    storageState: {
      cookies: [],
      origins: [
        {
          origin: BASE,
          localStorage: [
            { name: "ritmo.userId", value: "captura-revision" },
            { name: "ritmo.onboarded", value: "1" },
            { name: "ritmo.locale", value: toma.idioma ?? "es" },
          ],
        },
      ],
    },
  });

  const pagina = await contexto.newPage();
  await pagina.goto(BASE + toma.ruta, { waitUntil: "networkidle" });

  // Las tipografías tienen que estar cargadas o la captura miente sobre el
  // ajuste de línea, que es justo lo que hay que revisar.
  await pagina.evaluate(() => document.fonts.ready);
  // Y la animación de entrada del sello tiene que haber terminado: un elemento
  // a media animación se lee como un elemento roto.
  await pagina.waitForTimeout(900);

  await pagina.screenshot({ path: `${SALIDA}/${toma.archivo}`, fullPage: true });
  console.log(`${toma.archivo.padEnd(26)} ${toma.vp.width}×${toma.vp.height}`);
  await contexto.close();
}

await navegador.close();
console.log(`\n${TOMAS.length} capturas en ${SALIDA}/`);
