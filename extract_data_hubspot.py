# 🔧 Librerías estándar
import os
import json
import time
import mimetypes
from io import BytesIO
from datetime import datetime, timezone

# Dependencias externas
import requests
from dotenv import load_dotenv
import hubspot
from hubspot import Client

# Módulos específicos de HubSpot
from hubspot.crm.deals import ApiException as DealsApiException
from hubspot.crm.objects.notes import (
    SimplePublicObjectInputForCreate,
    BasicApi,
    ApiException as NotesApiException,
)
from hubspot.crm.objects import ApiException as ObjectsApiException
from hubspot.crm.associations import PublicAssociation

load_dotenv() 

class GestorDatosHubspot:
    def __init__(self):
        self.datos_negocio = {}
        self.cliente = hubspot.Client.create(access_token=os.getenv("API_KEY"))
    
    def obtener_datos_negocio(self, id_negocio):
        """
        Extrae propiedades relevantes de un negocio en HubSpot usando su ID.
        """
        campos_a_extraer = [
            "nombre_negocio",
            "telefono_contacto",
            "direccion_empresa",
            "actividad_comercial",
            "tipo_instalacion_factura",
            "tipo_instalacion_negocio",
            "descripcion_empresa",
            "url_video_trayectoria",
            "archivo_factura_id"
        ]
        
        try:
            respuesta_api = self.cliente.crm.deals.basic_api.get_by_id(
                deal_id=id_negocio,
                properties=campos_a_extraer,
                archived=False
            )
            
            tipo_instalacion_factura = respuesta_api.properties.get('tipo_instalacion_factura')
            tipo_instalacion_pdr = respuesta_api.properties.get('tipo_instalacion_pdr')
            
            tipo_instalacion = tipo_instalacion_factura or tipo_instalacion_pdr or ""
            
            datos_extraidos = {
                'nombre_negocio': respuesta_api.properties.get('nombre_negocio'),
                'telefono_contacto': respuesta_api.properties.get('telefono_contacto'),
                'direccion_empresa': respuesta_api.properties.get('direccion_empresa'),
                'actividad_comercial': respuesta_api.properties.get('actividad_comercial'),
                'tipo_instalacion': tipo_instalacion,
                'descripcion_empresa': respuesta_api.properties.get('descripcion_empresa'),
                'url_video_trayectoria': respuesta_api.properties.get('url_video_trayectoria'),
                'archivo_factura_id': respuesta_api.properties.get('archivo_factura_id')
            }
            
            self.datos_negocio.update(datos_extraidos)
            return self.datos_negocio
        
        except ApiException as e:
            print(f"Error API HubSpot: {e}")
            return {}


    def crear_nota_en_negocio(self, id_negocio, contenido_nota, id_archivo_pdf):
        """
        Crea una nota en HubSpot asociada a un negocio y adjunta un archivo PDF.
        """
        api_key = os.getenv("API_KEY")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        timestamp_actual = int(time.time() * 1000)
        payload_nota = {
            "properties": {
                "hs_note_body": contenido_nota,
                "hs_timestamp": str(timestamp_actual),
                "hs_attachment_ids": id_archivo_pdf
            }
        }

        # Crear la nota
        try:
            respuesta = requests.post(
                "https://api.hubapi.com/crm/v3/objects/notes",
                headers=headers,
                json=payload_nota
            )
            respuesta.raise_for_status()
            id_nota = respuesta.json()["id"]
            print(f"✅ Nota creada con ID: {id_nota}")
        except Exception as e:
            print(f"❌ Error al crear nota con adjunto: {e}")
            return None

        # Obtener el tipo de asociación válido para notas a negocios
        try:
            respuesta_asociacion = requests.get(
                "https://api.hubapi.com/crm/v4/associations/notes/deals/labels",
                headers=headers
            )
            respuesta_asociacion.raise_for_status()
            tipo_asociacion_id = respuesta_asociacion.json()["results"][0]["typeId"]
        except Exception as e:
            print(f"❌ Error al obtener tipo de asociación: {e}")
            return None

        # Asociar la nota al negocio
        payload_asociacion = {
            "inputs": [{
                "from": {"id": id_nota},
                "to": {"id": id_negocio},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": tipo_asociacion_id
                }]
            }]
        }

        try:
            respuesta_final = requests.post(
                "https://api.hubapi.com/crm/v4/associations/notes/deals/batch/create",
                headers=headers,
                json=payload_asociacion
            )
            respuesta_final.raise_for_status()
            print(f"✅ Nota {id_nota} asociada correctamente al negocio {id_negocio}.")
        except Exception as e:
            print(f"❌ Error al asociar nota con negocio: {e}")
            return None

        return id_nota

    def subir_pdf_desde_memoria(self, contenido_pdf_bytesio, nombre_archivo="documento.pdf"):
        """
        Sube un archivo PDF a HubSpot desde un objeto BytesIO y devuelve el ID y URL del archivo.
        """
        url_subida = "https://api.hubapi.com/files/v3/files"
        headers = {
            "Authorization": f"Bearer {os.getenv('API_KEY')}"
        }

        archivos = {
            "file": (nombre_archivo, contenido_pdf_bytesio, "application/pdf"),
            "folderId": (None, "123456789012"),  # ID carpeta, ajustar según necesidad
            "fileName": (None, nombre_archivo),
            "options": (None, json.dumps({"access": "PRIVATE"}), "application/json")
        }

        try:
            respuesta = requests.post(url_subida, headers=headers, files=archivos)
            respuesta.raise_for_status()
            datos_archivo = respuesta.json()
            print(f"✅ Archivo subido: {datos_archivo}")
            return datos_archivo.get("id"), datos_archivo.get("url")
        except Exception as e:
            print(f"❌ Error subiendo PDF: {e}")
            return None, None


def extraer_url_archivo(valor_crudo):
    """
    Intenta obtener una URL válida desde un string JSON o un ID de archivo.
    Si es un ID, consulta la API de HubSpot para obtener la URL real del archivo.
    """
    try:
        # Caso JSON con lista de objetos que contienen 'url'
        datos = json.loads(valor_crudo)
        if isinstance(datos, list) and datos and "url" in datos[0]:
            return datos[0]["url"]
    except (json.JSONDecodeError, IndexError, KeyError, TypeError):
        pass

    # Caso ID numérico o string numérico
    if str(valor_crudo).isdigit():
        api_key = os.getenv("API_KEY")
        headers = {"Authorization": f"Bearer {api_key}"}
        url_api = f"https://api.hubapi.com/files/v3/files/{valor_crudo}"
        try:
            respuesta = requests.get(url_api, headers=headers)
            respuesta.raise_for_status()
            datos_archivo = respuesta.json()
            return datos_archivo.get("url")  # URL real del archivo
        except Exception as e:
            print(f"❌ Error al obtener URL del archivo {valor_crudo}: {e}")
            return None
    return None


def obtener_imagen_desde_url(url):
    """
    Descarga una imagen desde una URL y la retorna como BytesIO.
    Lanza excepción si el contenido no es una imagen válida.
    """
    respuesta = requests.get(url)
    respuesta.raise_for_status()

    tipo_contenido = respuesta.headers.get("Content-Type", "")
    if not tipo_contenido.startswith("image/"):
        raise ValueError(f"La URL no es una imagen válida. Content-Type: {tipo_contenido}")

    return BytesIO(respuesta.content)


def cortar_texto_sin_romper_palabras(texto, longitud_max):
    """
    Corta un texto sin romper palabras, respetando espacios y máximo longitud dada.
    """
    if not texto:
        return "--"
    palabras = texto.split()
    resultado = ""
    for palabra in palabras:
        if len(resultado) + len(palabra) + (1 if resultado else 0) > longitud_max:
            break
        if resultado:
            resultado += " "
        resultado += palabra
    return resultado


def obtener_urls_videos_desde_ids(ids_videos_str):
    """
    Dado un string con IDs separados por punto y coma, devuelve lista con URLs de videos desde HubSpot.
    """
    if not isinstance(ids_videos_str, str):
        return 'No hay video'

    ids_videos = [vid.strip() for vid in ids_videos_str.split(";") if vid.strip()]
    urls_videos = []
    api_key = os.getenv("API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for id_video in ids_videos:
        try:
            respuesta = requests.get(f"https://api.hubapi.com/files/v3/files/{id_video}", headers=headers)
            respuesta.raise_for_status()
            datos_archivo = respuesta.json()
            urls_videos.append(datos_archivo.get("url"))
        except requests.exceptions.RequestException as err:
            print(f"Error al obtener archivo {id_video}: {err}")

    return urls_videos


def generar_url_previsualizacion_factura(file_id, portal_id="6613024"):
    """
    Genera URL de previsualización de factura de luz en HubSpot a partir del ID de archivo.
    """
    if not file_id:
        return None
    return f"https://app.hubspot.com/file-preview/{portal_id}/file/{file_id}/"


def filtrar_videos_validos(lista_urls_videos):
    """
    Filtra la lista de URLs para devolver solo videos con extensiones válidas, 
    rellena hasta 3 elementos con cadena vacía si hay menos.
    """
    extensiones_validas = ('.mp4', '.mov', '.avi', '.mkv')
    videos_filtrados = []

    if isinstance(lista_urls_videos, list):
        for url in lista_urls_videos:
            if isinstance(url, str) and url.startswith("http") and url.lower().endswith(extensiones_validas):
                videos_filtrados.append(url)

    # Asegurar que la lista tenga exactamente 3 elementos, rellenando con ""
    return videos_filtrados[:3] + [""] * (3 - len(videos_filtrados))



# def crear_nota_en_negocio(self, id_negocio, contenido_nota, id_archivo_pdf):

# def subir_pdf_desde_memoria(self, contenido_pdf_bytesio, nombre_archivo="documento.pdf"):

# def extraer_url_archivo(self, valor_crudo):

# def obtener_imagen_desde_url(self, url):

# def cortar_texto_sin_romper_palabras(self, texto, longitud_max):

# def obtener_urls_videos_desde_ids(self, ids_videos_str):


# def generar_url_previsualizacion_factura(self, file_id, portal_id="6613024"):

# def filtrar_videos_validos(self, lista_urls_videos):