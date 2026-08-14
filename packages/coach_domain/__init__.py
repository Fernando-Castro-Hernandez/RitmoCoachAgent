"""Motor de dominio de Ritmo.

Este paquete es **puro**: no importa red, base de datos, framework web ni SDK de
nube. Toda la aritmética de entrenamiento y la puerta de seguridad viven aquí,
lo que permite probarlas con pruebas por propiedades y auditarlas de un vistazo.

La regla que sostiene la arquitectura: **el LLM nunca calcula un plan ni un
número.** Consulta a este motor mediante herramientas y se limita a escuchar,
preguntar y explicar. Ver ADR 0003.

La restricción de pureza se verifica en CI con `scripts/check_domain_purity.py`.
"""

__version__ = "0.1.0"
