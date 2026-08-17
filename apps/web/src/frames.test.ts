/**
 * Extracción de fotogramas: las decisiones que sí se pueden probar sin vídeo.
 *
 * `extraerFotogramas` necesita un decodificador de vídeo de verdad, y jsdom no
 * lo tiene: probarlo aquí sería probar un doble. Lo que sí se prueba es la
 * aritmética que decide QUÉ se sube, que es donde estaban los dos fallos
 * reales:
 *
 * - pedir el segundo 0 y el segundo final. El primero suele pillar el teléfono
 *   moviéndose y el último puede no existir — Safari no dispara `seeked` y la
 *   extracción se queda colgada para siempre.
 * - escalar mal. Un cuadro a resolución de teléfono son diez veces los bytes
 *   que hacen falta para ver una postura.
 */

import { describe, expect, it } from "vitest";

import {
  LADO_MAXIMO,
  MAX_SEGUNDOS,
  MIN_FOTOGRAMAS,
  NUM_FOTOGRAMAS,
  VideoInvalidoError,
  escalar,
  instantes,
} from "./frames";

describe("instantes", () => {
  it("saca tantos como fotogramas se suben", () => {
    expect(instantes(10)).toHaveLength(NUM_FOTOGRAMAS);
  });

  it("no pide el segundo cero ni el final", () => {
    const t = instantes(10);
    expect(t[0]).toBeGreaterThan(0);
    expect(t[t.length - 1]).toBeLessThan(10);
  });

  it("los reparte de forma pareja", () => {
    const t = instantes(11);
    const saltos = t.slice(1).map((v, i) => Number((v - t[i]).toFixed(3)));
    expect(new Set(saltos).size).toBe(1);
  });

  it("funciona igual con un clip muy corto", () => {
    const t = instantes(1.2);
    expect(t).toHaveLength(NUM_FOTOGRAMAS);
    expect(new Set(t).size).toBe(NUM_FOTOGRAMAS);
    expect(t.every((v) => v > 0 && v < 1.2)).toBe(true);
  });
});

describe("escalar", () => {
  it("no agranda un vídeo que ya es pequeño", () => {
    expect(escalar(320, 240)).toEqual({ ancho: 320, alto: 240 });
  });

  it("deja el lado mayor en el tope", () => {
    expect(escalar(1920, 1080).ancho).toBe(LADO_MAXIMO);
    // Vertical, que es como graba la gente con el teléfono.
    expect(escalar(1080, 1920).alto).toBe(LADO_MAXIMO);
  });

  it("conserva la proporción", () => {
    const { ancho, alto } = escalar(1920, 1080);
    expect(ancho / alto).toBeCloseTo(1920 / 1080, 2);
  });

  it("no divide entre cero con un vídeo sin dimensiones", () => {
    expect(escalar(0, 0)).toEqual({ ancho: 0, alto: 0 });
  });
});

describe("el motivo del rechazo", () => {
  it("viaja como campo y no como texto del mensaje", () => {
    // La pantalla elige la frase traducida a partir de esto. Cuando el motivo
    // vivía dentro del mensaje, la interfaz comparaba contra una cadena en
    // español —`e.message.includes("dura")`— que nadie recordaba que era un
    // contrato: traducir el error habría roto el mensaje sin romper ninguna
    // prueba.
    const e = new VideoInvalidoError("muy-largo");
    expect(e.motivo).toBe("muy-largo");
    expect(e).toBeInstanceOf(Error);
  });
});

describe("los límites que se le prometen al corredor", () => {
  it("hacen falta al menos tres cuadros para hablar de una secuencia", () => {
    expect(MIN_FOTOGRAMAS).toBeGreaterThanOrEqual(3);
    expect(MIN_FOTOGRAMAS).toBeLessThan(NUM_FOTOGRAMAS);
  });

  it("el texto de la pantalla y el código dicen el mismo número", () => {
    // La pantalla dice «unos {MAX_SEGUNDOS} segundos» y «{NUM_FOTOGRAMAS}
    // fotogramas» interpolando estas mismas constantes. Si alguien cambia una
    // sin la otra, la promesa deja de ser cierta.
    expect(MAX_SEGUNDOS).toBe(15);
    expect(NUM_FOTOGRAMAS).toBe(10);
  });
});
