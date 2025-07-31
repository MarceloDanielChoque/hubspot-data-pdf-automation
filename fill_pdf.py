import fitz  # PyMuPDF para manipulación avanzada de PDFs
from pdfrw import PdfReader, PdfWriter, PdfDict  # Para aplanar PDFs y eliminar campos editables
import requests
from io import BytesIO
import textwrap
import tempfile
import os

# Importamos función para descargar imagenes desde URL y devolver en memoria
from extraer_datos_hubspot import obtener_imagen_url  


def generar_pdfs_en_memoria(ruta_plantilla_pdf, datos_cliente):
    """
    Genera dos versiones de un PDF en memoria a partir de una plantilla:
    - PDF editable con campos rellenados con datos del cliente
    - PDF aplanado (no editable), con textos e imágenes incrustadas

    Parámetros:
    - ruta_plantilla_pdf (str): ruta local al archivo PDF plantilla
    - datos_cliente (dict): diccionario con los datos a insertar en el PDF

    Retorna:
    - tuple (BytesIO, BytesIO): PDF editable y PDF no editable en memoria
    """

    # Archivos temporales para guardar versiones intermedias del PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_editable_file, \
         tempfile.NamedTemporaryFile(suffix=".tmp.pdf", delete=False) as pdf_temp_file, \
         tempfile.NamedTemporaryFile(suffix=".final.pdf", delete=False) as pdf_final_file:

        ruta_pdf_editable = pdf_editable_file.name
        ruta_pdf_temporal = pdf_temp_file.name
        ruta_pdf_final = pdf_final_file.name

    try:
        # Paso 1: rellenar campos editables con datos del cliente
        _rellenar_campos_editables(ruta_plantilla_pdf, datos_cliente, ruta_pdf_editable)

        # Cargamos PDF editable en memoria
        with open(ruta_pdf_editable, "rb") as f:
            pdf_editable_en_memoria = BytesIO(f.read())

        # Paso 2: generar versión aplanada con imágenes y textos incrustados
        _insertar_imagenes_y_textos(ruta_plantilla_pdf, datos_cliente, ruta_pdf_temporal)
        _eliminar_campos_editables_pdf(ruta_pdf_temporal, ruta_pdf_final)

        # Cargamos PDF final no editable en memoria
        with open(ruta_pdf_final, "rb") as f:
            pdf_no_editable_en_memoria = BytesIO(f.read())

        return pdf_editable_en_memoria, pdf_no_editable_en_memoria

    finally:
        # Limpieza de archivos temporales para evitar dejar rastros en disco
        for ruta in (ruta_pdf_editable, ruta_pdf_temporal, ruta_pdf_final):
            try:
                os.unlink(ruta)
            except Exception as e:
                print(f"⚠️ No se pudo eliminar archivo temporal {ruta}: {e}")


def _rellenar_campos_editables(ruta_plantilla, datos, ruta_salida):
    """
    Rellena campos editables (widgets) en el PDF plantilla con los datos proporcionados.

    Parámetros:
    - ruta_plantilla (str): ruta al PDF plantilla
    - datos (dict): datos para insertar en los campos
    - ruta_salida (str): ruta donde guardar el PDF editado
    """
    documento = fitz.open(ruta_plantilla)
    for pagina in documento:
        widgets = pagina.widgets()
        if not widgets:
            continue
        for widget in widgets:
            nombre_campo = widget.field_name
            if nombre_campo in datos:
                widget.field_value = str(datos[nombre_campo])
                widget.update()
    documento.save(ruta_salida)
    documento.close()


def _insertar_imagenes_y_textos(ruta_pdf, datos, ruta_salida):
    """
    Inserta imágenes y textos directamente en el PDF en las posiciones de los campos,
    para generar una versión visual que no depende de campos editables.

    Parámetros:
    - ruta_pdf (str): PDF original plantilla
    - datos (dict): datos con URLs o textos a insertar
    - ruta_salida (str): archivo donde guardar PDF modificado
    """
    documento = fitz.open(ruta_pdf)
    for pagina in documento:
        widgets = pagina.widgets()
        if not widgets:
            continue
        for widget in widgets:
            nombre_campo = widget.field_name
            if nombre_campo in datos:
                valor = datos[nombre_campo]
                rect = widget.rect
                # Insertar imagen si es URL válida a imagen
                if isinstance(valor, str) and valor.startswith("https") and any(valor.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".FLAG_IMAGEN"]):
                    try:
                        flujo_imagen = obtener_imagen_url(valor)
                        pagina.insert_image(rect, stream=flujo_imagen, keep_proportion=True)
                    except Exception as e:
                        print(f"Error al insertar imagen desde {valor}: {e}")
                # Insertar enlace y texto para videos
                elif isinstance(valor, str) and valor.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
                    try:
                        texto_enlaces = "\n".join(textwrap.wrap(valor, width=80))
                        pagina.insert_textbox(rect, texto_enlaces, fontname="helv", fontsize=8, color=(0, 0, 1), align=0)
                        zona_enlace = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + 12)
                        pagina.insert_link({"kind": fitz.LINK_URI, "from": zona_enlace, "uri": valor})
                    except Exception as e:
                        print(f"Error al insertar enlace de video desde {valor}: {e}")
                # Insertar enlace y texto para URLs de factura (preview en HubSpot)
                elif isinstance(valor, str) and valor.startswith("https://app.hubspot.com/file-preview/"):
                    try:
                        texto_enlaces = "\n".join(textwrap.wrap(valor, width=40))
                        pagina.insert_textbox(rect, texto_enlaces, fontname="helv", fontsize=8, color=(0, 0, 1), align=0)
                        zona_enlace = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + 12)
                        pagina.insert_link({"kind": fitz.LINK_URI, "from": zona_enlace, "uri": valor})
                    except Exception as e:
                        print(f"Error al insertar enlace de factura: {e}")
                # Para otros campos solo insertar texto plano
                else:
                    widget.field_value = str(valor)
                    widget.update()
                    pagina.insert_textbox(rect, str(valor), fontname="helv", fontsize=8, color=(0, 0, 0), align=0)
    documento.save(ruta_salida)
    documento.close()


def _eliminar_campos_editables_pdf(ruta_entrada, ruta_salida):
    """
    Aplana un PDF eliminando todos los campos editables y anotaciones,
    para generar una versión no editable.

    Parámetros:
    - ruta_entrada (str): PDF con campos editables
    - ruta_salida (str): PDF sin campos editables
    """
    pdf = PdfReader(ruta_entrada)
    if "/AcroForm" in pdf.Root:
        # Limpiamos lista de campos para que no existan más
        pdf.Root.AcroForm.update(PdfDict(Fields=[]))
    for pagina in pdf.pages:
        if "/Annots" in pagina:
            # Eliminamos todas las anotaciones (campos, comentarios)
            pagina.Annots = []
    PdfWriter(ruta_salida, trailer=pdf).write()


# Nota: para utilizar este módulo se recomienda instalar PyMuPDF y pdfrw:
# pip install pymupdf pdfrw
