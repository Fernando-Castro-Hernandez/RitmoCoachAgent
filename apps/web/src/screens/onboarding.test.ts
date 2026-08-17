/**
 * Validación del carrusel y elección de plantilla.
 *
 * El carrusel guarda una sola vez, al final. Sin validación por paso, alguien
 * teclea «cincuenta minutos» en el tiempo de referencia, avanza cinco pasos, y
 * descubre el problema al pulsar «Terminar» — con el error lejos del campo que
 * lo causó y el dato ya olvidado.
 *
 * Lo que se prueba aquí es dónde está la frontera de «basura»: qué se acepta y
 * qué no. El backend valida igual; esto es la cortesía de decirlo a tiempo.
 */

import { describe, expect, it } from "vitest";

import { esNumero, esTiempo, plantillaMasCercana } from "./Onboarding";

describe("esNumero", () => {
  it.each(["10", "10.5", "10,5", "5", "42.2"])("acepta %s", (v) => {
    expect(esNumero(v)).toBe(true);
  });

  it.each(["", "  ", "diez", "10km", "10 km", "-5", "0", "1.2.3", "10.", "e5"])(
    "rechaza %s",
    (v) => {
      expect(esNumero(v)).toBe(false);
    },
  );

  it("rechaza el cero: correr cero kilómetros no es una referencia", () => {
    expect(esNumero("0")).toBe(false);
    expect(esNumero("0.0")).toBe(false);
  });
});

describe("esTiempo", () => {
  it.each(["50:00", "5:30", "1:02:03", "120:00"])("acepta %s", (v) => {
    expect(esTiempo(v)).toBe(true);
  });

  it.each(["", "cincuenta minutos", "50", "50m", "50:0", "50-00", "1:2:3"])(
    "rechaza %s",
    (v) => {
      expect(esTiempo(v)).toBe(false);
    },
  );

  it("rechaza segundos fuera de rango", () => {
    // Un tiempo con 99 segundos no existe, y aceptarlo produce un ritmo mal
    // calculado que nadie va a cuestionar después.
    expect(esTiempo("50:99")).toBe(false);
    expect(esTiempo("50:60")).toBe(false);
    expect(esTiempo("1:02:99")).toBe(false);
  });
});

describe("plantillaMasCercana", () => {
  it.each([
    ["3", "5k"],
    ["7", "5k"],
    ["8", "10k"],
    ["15", "10k"],
    ["16", "21k"],
    ["30", "21k"],
    ["32", "42k"],
    ["50", "42k"],
    ["100", "42k"],
  ])("%s km se prepara con el plan de %s", (km, esperado) => {
    expect(plantillaMasCercana(km)).toBe(esperado);
  });

  it("entiende la coma decimal, que es como se escribe en español", () => {
    expect(plantillaMasCercana("21,1")).toBe("21k");
  });

  it("siempre devuelve una de las cuatro que el motor tiene validadas", () => {
    // El motor no improvisa una plantilla nueva: cada plan tiene su progresión,
    // su tirada larga y su descarga probadas. Se elige la más cercana y se dice
    // cuál, en vez de fabricar una sin validar para que el formulario quede
    // bonito.
    const validas = ["5k", "10k", "21k", "42k"];
    for (let km = 1; km <= 120; km++) {
      expect(validas).toContain(plantillaMasCercana(String(km)));
    }
  });
});
