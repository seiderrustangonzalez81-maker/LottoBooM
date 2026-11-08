import requests
import unicodedata
<<<<<<< HEAD
=======
from datetime import datetime
from zoneinfo import ZoneInfo
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from sorteos.models import Sorteo
from resultados.models import Resultado
from resultados.views import procesar_resultado

URL_JSON = "https://raw.githubusercontent.com/seiderrustangonzalez81-maker/LottoBooM/main/resultados.json"

MAPEO_NOMBRES = {
    # ─── ANGUILA Y HAITI (Enloteria) ───
<<<<<<< HEAD
    "Anguilla 8AM": "Anguila 8 AM",
    "Anguilla 9AM": "Anguila 9 AM",
    "Anguilla 10AM": "Anguila 10 AM",
    "Anguilla 11AM": "Anguila 11 AM",
    "Anguilla 12PM": "Anguila 12 PM",
    "Anguilla 1PM": "Anguila 1 PM",
    "Anguilla 2PM": "Anguila 2 PM",
    "Anguilla 3PM": "Anguila 3 PM",
    "Anguilla 4PM": "Anguila 4 PM",
    "Anguilla 5PM": "Anguila 5 PM",
    "Anguilla 6PM": "Anguila 6 PM",
    "Anguilla 7PM": "Anguila 7 PM",
    "Anguilla 8PM": "Anguila 8 PM",
    "Anguilla 9PM": "Anguila 9 PM",
=======
    "Anguilla 8AM": "Anguila 8 AM", "Anguilla 9AM": "Anguila 9 AM",
    "Anguilla 10AM": "Anguila 10 AM", "Anguilla 11AM": "Anguila 11 AM",
    "Anguilla 12PM": "Anguila 12 PM", "Anguilla 1PM": "Anguila 1 PM",
    "Anguilla 2PM": "Anguila 2 PM", "Anguilla 3PM": "Anguila 3 PM",
    "Anguilla 4PM": "Anguila 4 PM", "Anguilla 5PM": "Anguila 5 PM",
    "Anguilla 6PM": "Anguila 6 PM", "Anguilla 7PM": "Anguila 7 PM",
    "Anguilla 8PM": "Anguila 8 PM", "Anguilla 9PM": "Anguila 9 PM",
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
    "Anguilla 10PM": "Anguila 10 PM",

    "Haiti Bolet 9:30 AM": "Haiti Bolet 9:30 AM",
    "Haiti Bolet 10:30 AM": "Haiti Bolet 10:30 AM",
    "Haiti Bolet 11:30 AM": "Haiti Bolet 11:30 AM",
    "Haiti Bolet 5:30 PM": "Haiti Bolet 5:30 PM",
    "Haiti Bolet 6:30 PM": "Haiti Bolet 6:30 PM",
    "Haiti Bolet 7:30 PM": "Haiti Bolet 7:30 PM",

    # ─── DOMINICANAS (Enloteria) ───
<<<<<<< HEAD
    "Nacional Gana Más": "Nacional Gana Más",
    "Nacional Noche": "Nacional Noche",
    "Leidsa": "Leidsa 8:55 PM",
    "Loteka Tarde": "Loteka 1:30 PM",
    "Loteka": "Loteka 7:55 PM",
    "La Primera": "La Primera",
    "La Primera Noche": "La Primera Noche",
    "La Suerte": "La Suerte",
    "La Suerte 6PM": "La Suerte 6PM",
    "LoteDom": "Lotedom",
    "LoteDom Noche": "Lotedom Noche",
    "King Lottery Día": "King Lottery 12:30 PM",
    "King Lottery Noche": "King Lottery 7:30 PM",

    # ─── VENEZOLANAS/OTRAS (Enloteria) ───
    "El Quemaito Mayor": "El Quemaito Mayor",
    "El Quemaito Mayor Noche": "El Quemaito Mayor Noche",
    "El Quinielón Día": "El Quinielón Día",
    "El Quinielón Noche": "El Quinielón Noche",
    "Real": "Real",
    "Real Noche": "Real Noche",

    # ─── USA (LotteryUSA) - Ahora los mapeamos directo a su nombre en BD ───
=======
    "Nacional Gana Más": "Nacional Gana Más", "Nacional Noche": "Nacional Noche",
    "Leidsa": "Leidsa 8:55 PM",
    "Loteka Tarde": "Loteka 1:30 PM", "Loteka": "Loteka 7:55 PM",
    "La Primera": "La Primera", "La Primera Noche": "La Primera Noche",
    "La Suerte": "La Suerte", "La Suerte 6PM": "La Suerte 6PM",
    "LoteDom": "Lotedom", "LoteDom Noche": "Lotedom Noche",
    "King Lottery Día": "King Lottery 12:30 PM", "King Lottery Noche": "King Lottery 7:30 PM",

    # ─── VENEZOLANAS/OTRAS (Enloteria) ───
    "El Quemaito Mayor": "El Quemaito Mayor", "El Quemaito Mayor Noche": "El Quemaito Mayor Noche",
    "El Quinielón Día": "El Quinielón Día", "El Quinielón Noche": "El Quinielón Noche",
    "Real": "Real", "Real Noche": "Real Noche",

    # ─── USA (LotteryUSA) ───
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
    "Texas 1:20 PM": "Texas 1:20 PM",
    "Florida 1:35 PM": "Florida 1:35 PM",
    "New York 2:30 PM": "New York 2:30 PM",
    "New Jersey 12:50 PM": "New Jersey 12:50 PM",
    "Georgia 12:30 PM": "Georgia 12:30 PM",
    "Tennessee 1:20 PM": "Tennessee 1:20 PM",
}

def normalizar_texto(texto):
<<<<<<< HEAD
    """Quita acentos y pasa a minúsculas para comparar de forma segura."""
=======
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
    if not texto: return ""
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

class FakeRequest:
    def __init__(self, user): self.user = user

class Command(BaseCommand):
    help = "Carga resultados desde EnLoteria y LotteryUSA, calculando premios automáticamente."

    def handle(self, *args, **kwargs):
        try:
            resp = requests.get(URL_JSON, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error descargando JSON: {e}"))
            return

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR("No hay superusuario"))
            return
        req = FakeRequest(admin)

<<<<<<< HEAD
        # Diccionario auxiliar normalizado para búsquedas sin acentos
        mapeo_normalizado = {normalizar_texto(k): v for k, v in MAPEO_NOMBRES.items()}
=======
        mapeo_normalizado = {normalizar_texto(k): v for k, v in MAPEO_NOMBRES.items()}
        hoy_cuba = datetime.now(ZoneInfo('America/Havana')).date()
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c

        creados = actualizados = errores = premios_ok = premios_err = 0

        for item in data:
            try:
                nombre_web = item.get("sorteo_nombre", "").strip()
<<<<<<< HEAD

                # 1. Búsqueda exacta
                nombre_db = MAPEO_NOMBRES.get(nombre_web)

                # 2. Si falla, búsqueda normalizada (sin acentos)
                if not nombre_db:
                    nombre_db = mapeo_normalizado.get(normalizar_texto(nombre_web))

=======
                nombre_db = MAPEO_NOMBRES.get(nombre_web) or mapeo_normalizado.get(normalizar_texto(nombre_web))
                
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
                if not nombre_db:
                    continue

                sorteo = Sorteo.objects.filter(nombre__iexact=nombre_db).first()
                if not sorteo:
                    self.stdout.write(self.style.WARNING(f"⚠️ Sorteo no encontrado en BD: {nombre_db}"))
                    continue

                fecha = parse_date(item.get("fecha", ""))
                if not fecha: continue

                numeros = item.get("numeros", [])
<<<<<<< HEAD
                if not numeros or len(numeros) < 2:
                    continue

                # ─── LÓGICA INTELIGENTE PARA PICK 2 / 3 / 4 / TRADICIONAL ───
=======
                if not numeros or len(numeros) < 2: continue
                    
                fuente = item.get("fuente", "")

                # ─── VALIDACIÓN DE FECHA PARA USA (Evitar días anteriores) ───
                if fuente == "lotteryusa" and fecha != hoy_cuba:
                    self.stdout.write(self.style.WARNING(f"⚠️ Saltando {nombre_db} de LotteryUSA: la fecha {fecha} no es hoy."))
                    continue

                # ─── LÓGICA SEGÚN LA FUENTE ───
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
                formas = [str(f).lower().strip() for f in (sorteo.formas_juego or [])]
                pick2_val = pick3_val = pick4_val = pick5_val = ''
                fijo_val = corrido1_val = corrido2_val = ''

<<<<<<< HEAD
                # Si el sorteo es de tipo Pick (ej. Texas Pick 3)
                if 'pick3' in formas and len(numeros) >= 3:
                    pick3_val = "".join(numeros[:3])  # Ej: ["1", "3", "5"] -> "135"
                elif 'pick4' in formas and len(numeros) >= 4:
                    pick4_val = "".join(numeros[:4])
                elif 'pick2' in formas and len(numeros) >= 2:
                    pick2_val = "".join(numeros[:2])
                else:
                    # Comportamiento tradicional (Enloteria)
                    fijo_val = numeros[0] if len(numeros) > 0 else ''
                    corrido1_val = numeros[1] if len(numeros) > 1 else ''
                    corrido2_val = numeros[2] if len(numeros) > 2 else ''

                # ─── Verificar si ya existe para saber si es actualización ───
                resultado_existente = Resultado.objects.filter(sorteo=sorteo, fecha=fecha).first()

                # Actualizamos la metadata del objeto existente (si lo hay) con la nueva fuente
                if resultado_existente:
                    if not resultado_existente.metadata:
                        resultado_existente.metadata = {}
                    resultado_existente.metadata['fuente'] = item.get("fuente", "desconocida")

                # ─── Armamos el diccionario de datos para procesar_resultado ───
                datos = {
                    'sorteo': sorteo,
                    'fecha': fecha,
                    'hora': sorteo.hora_salida,
                    'pick2': pick2_val,
                    'pick3': pick3_val,
                    'pick4': pick4_val,
                    'pick5': pick5_val,
                    'fijo': fijo_val,
                    'corrido_1': corrido1_val,
                    'corrido_2': corrido2_val,
                    'pf': '',
                    'centena_corrida_1': '',
                    'centena_corrida_2': '',
                }

                # ─── Procesar de forma atómica (Crea o Actualiza + Calcula Premios) ───
                resultado_obj, premios_count = procesar_resultado(
                    req, datos, resultado_existente=resultado_existente
                )

                # Actualizamos la metadata del objeto guardado
                resultado_obj.metadata['fuente'] = item.get("fuente", "desconocida")
=======
                if fuente == "lotteryusa":
                    # Lógica exclusiva para USA (Pick 3, 4, etc.)
                    if 'pick3' in formas and len(numeros) >= 3:
                        pick3_val = "".join(numeros[:3])
                    elif 'pick4' in formas and len(numeros) >= 4:
                        pick4_val = "".join(numeros[:4])
                    elif 'pick2' in formas and len(numeros) >= 2:
                        pick2_val = "".join(numeros[:2])
                else:
                    # Lógica para Enloteria (Fijo y Corridos SIEMPRE se llenan)
                    fijo_val = numeros[0] if len(numeros) > 0 else ''
                    corrido1_val = numeros[1] if len(numeros) > 1 else ''
                    corrido2_val = numeros[2] if len(numeros) > 2 else ''
                    
                    # Si además el sorteo tiene Pick 3, se lo pasamos también
                    if 'pick3' in formas and len(numeros) >= 3:
                        pick3_val = "".join(numeros[:3])

                # ─── Verificar si ya existe ───
                resultado_existente = Resultado.objects.filter(sorteo=sorteo, fecha=fecha).first()

                datos = {
                    'sorteo': sorteo, 'fecha': fecha, 'hora': sorteo.hora_salida,
                    'pick2': pick2_val, 'pick3': pick3_val, 'pick4': pick4_val, 'pick5': pick5_val,
                    'fijo': fijo_val, 'corrido_1': corrido1_val, 'corrido_2': corrido2_val,
                    'pf': '', 'centena_corrida_1': '', 'centena_corrida_2': '',
                }

                # ─── Procesar de forma atómica ───
                resultado_obj, premios_count = procesar_resultado(req, datos, resultado_existente=resultado_existente)
                
                resultado_obj.metadata = resultado_obj.metadata or {}
                resultado_obj.metadata['fuente'] = fuente
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
                resultado_obj.procesamiento_estado = 'completado'
                resultado_obj.save(update_fields=['metadata', 'procesamiento_estado'])

                if resultado_existente:
                    actualizados += 1
                    self.stdout.write(self.style.SUCCESS(f"🔄 Actualizado: {nombre_db} -> {pick3_val or pick2_val or fijo_val}"))
                else:
                    creados += 1
                    self.stdout.write(self.style.SUCCESS(f"✅ Nuevo: {nombre_db} -> {pick3_val or pick2_val or fijo_val}"))
<<<<<<< HEAD

                premios_ok += 1

            except ValueError as ve:
                # Errores de validación de procesar_resultado (ej. pick3 no tiene 3 dígitos)
=======
                premios_ok += 1

            except ValueError as ve:
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
                errores += 1
                self.stdout.write(self.style.ERROR(f"❌ Error de validación en {nombre_web}: {str(ve)}"))
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"❌ Error procesando {nombre_web}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(
<<<<<<< HEAD
            f"\nResumen Final -> Creados={creados}, Actualizados={actualizados}, "
            f"Premios OK={premios_ok}, Errores={errores}"
        ))
=======
            f"\nResumen Final -> Creados={creados}, Actualizados={actualizados}, Premios OK={premios_ok}, Errores={errores}"
        ))
>>>>>>> 795d29dd8d586fd14643080495bfe1fe7405f62c
