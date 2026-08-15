"""Ruta de visión: REST y `Converse`, separada de la ruta de voz (ADR 0014).

Nova 2 Sonic sólo acepta `SPEECH`, así que el modelo de voz no puede ser también
el de visión. Las dos rutas nunca se cruzan: ésta escribe en la base, y la de
voz lee de la base a través de sus herramientas.
"""
