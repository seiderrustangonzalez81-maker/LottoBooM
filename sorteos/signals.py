# -*- coding: utf-8 -*-
"""
Signals de la app sorteos.

NOTA: Históricamente este archivo creaba registros en `SorteoFormaJuego`
cada vez que se guardaba un `Sorteo`. Desde la refactorización, las formas
de juego se guardan directamente en el campo JSON `Sorteo.formas_juego`,
por lo que ya no se necesita ningún signal.

Se deja el archivo vacío (pero existente) para no romper la importación
desde `sorteos/apps.py`.
"""