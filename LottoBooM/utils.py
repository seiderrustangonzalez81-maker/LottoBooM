# LottoBooM/utils.py
from datetime import datetime, date, timedelta

def es_verano_cuba(fecha):
    """
    Devuelve True si la fecha está en horario de verano en Cuba.
    Acepta date o datetime.
    """
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    elif not isinstance(fecha, date):
        raise TypeError("fecha debe ser date o datetime")

    year = fecha.year

    # Segundo domingo de marzo
    inicio = datetime(year, 3, 1)
    while inicio.weekday() != 6:
        inicio += timedelta(days=1)
    inicio += timedelta(days=7)
    inicio = inicio.date()

    # Primer domingo de noviembre
    fin = datetime(year, 11, 1)
    while fin.weekday() != 6:
        fin += timedelta(days=1)
    fin = fin.date()

    return inicio <= fecha <= fin