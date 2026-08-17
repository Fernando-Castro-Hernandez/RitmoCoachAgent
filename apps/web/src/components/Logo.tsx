/**
 * El isotipo de Ritmo: la R en forma de rayo.
 *
 * ## Por qué va en línea y no como `<img src="logo.svg">`
 *
 * Dos razones, y la segunda es la que manda.
 *
 * 1. **Hereda el color.** `currentColor` deja ponerlo sobre papel, sobre tinta
 *    y sobre azul de proceso sin tener tres archivos. El azul de la marca
 *    (#3450d2) y el del sistema (#1b4fd8) no son el mismo, y juntos se ven como
 *    un error de impresión: aquí el isotipo toma el del sistema y deja de
 *    competir consigo mismo.
 *
 * 2. **El archivo original no se puede servir.** `LOGO  RITMO COUCH FER.svg`
 *    lleva la palabra «ITMO» como `<text>` vivo en *Lorimer No 2 Condensed*,
 *    una fuente comercial que no está en el repositorio. En la máquina del
 *    diseñador se ve perfecta; en cualquier otra el navegador la sustituye y el
 *    logotipo sale con otra letra y otro ancho.
 *
 * `apps/web/public/assets/logo.svg` existe y es este mismo isotipo, generado
 * quitándole el `<text>` al original. Está ahí para quien lo necesite fuera de
 * React —el favicon, una miniatura, un README—, pero la aplicación usa este
 * componente.
 *
 * ## Cómo salieron estas dos figuras, y por qué antes salieron mal
 *
 * La primera vez las elegí a mano leyendo el XML y me llevé cinco polígonos.
 * Tres de ellos viven en capas `display:none` de Illustrator —guías de
 * construcción— que mi filtro no supo excluir porque los grupos van anidados.
 * El resultado se veía como un montón de galones sueltos: Fernando lo llamó
 * «un marcador genérico», y tenía razón.
 *
 * La segunda vez no elegí nada: le quité el `<text>` al archivo, lo abrí en el
 * navegador y le pregunté por `getBBox()`. Contestó `1002 853 995 1340`, y
 * dentro de esa caja sólo caben estas dos figuras. La lección es la de siempre
 * —mirar en vez de deducir— y aquí el que mira es el motor de render, que es el
 * único que sabe de verdad qué se pinta.
 */

export function Logo({
  className = "",
  title,
}: {
  className?: string;
  /** Si se pasa, el logo es una imagen con nombre; si no, es decoración. */
  title?: string;
}) {
  return (
    <svg
      viewBox="1002 853 995 1340"
      className={className}
      fill="currentColor"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : "true"}
    >
      <polygon points="1002.58 853.82 1997.42 853.82 1027.39 2193.05 1475.59 981.29 1002.58 853.82" />
      <polygon points="1542.67 1493.44 1997.42 1493.44 1542.67 2193.05 1718.47 1586.33 1542.67 1493.44" />
    </svg>
  );
}
