/**
 * El isotipo de Ritmo, en vectores.
 *
 * ## Por qué esto no es un `<img src="logo.svg">`
 *
 * El SVG original (`public/assets/LOGO  RITMO COUCH FER.svg`) **no se puede
 * servir tal cual**, y el motivo tardaría en notarse: la palabra «ITMO» va como
 * `<text>` vivo en *Lorimer No 2 Condensed*, una fuente comercial que no está
 * en el repositorio ni se puede empaquetar. En la máquina del diseñador se ve
 * perfecta; en cualquier otra, el navegador la sustituye por la que tenga a
 * mano y el logotipo sale con otra letra, otro ancho y sin la cursiva negra.
 * Un logo que se ve bien sólo donde se hizo no es un logo.
 *
 * Además el archivo trae tres capas `display:none` —guías de construcción de
 * Illustrator— que pesan 8 de sus 11 KB y no pintan nada.
 *
 * Así que aquí vive únicamente **la parte que no depende de ninguna fuente**:
 * las cinco figuras que forman la R. El viewBox va recortado a su caja real
 * (476 645 1522 1548) en vez del lienzo de 3000×3000 original, que era casi
 * todo aire y hacía imposible alinearlo con nada.
 *
 * ## El color
 *
 * `currentColor`, no el azul de marca. El isotipo se pone encima de papel, de
 * tinta y de azul de proceso según dónde vaya, y un color fijo obligaría a
 * tener tres archivos. Además el azul de marca (#3450d2) y el azul del sistema
 * (#1b4fd8) no son el mismo: pintarlos juntos se ve como un error de impresión,
 * no como dos azules.
 *
 * Para el logotipo completo —la R **y** «RITMO» escrito— está el PNG, que se
 * exportó con la fuente de verdad. Se usa en la portada, donde la marca se
 * presenta y el nombre tiene que leerse tal cual se diseñó.
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
      viewBox="476 645 1522 1548"
      className={className}
      fill="currentColor"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : "true"}
    >
      <polygon points="685.17 648.48 866.25 645.33 584.17 919.33 755.36 689.01 685.17 648.48" />
      <polygon points="475.9 1000.28 1233.77 1000.28 475.9 2046.59 826.52 1100 475.9 1000.28" />
      <polygon points="878.48 1500 1233.77 1500 878.48 2046.59 1015.13 1572.05 878.48 1500" />
      <polygon points="1002.58 853.82 1997.42 853.82 1027.39 2193.05 1475.59 981.29 1002.58 853.82" />
      <polygon points="1542.67 1493.44 1997.42 1493.44 1542.67 2193.05 1718.47 1586.33 1542.67 1493.44" />
    </svg>
  );
}
