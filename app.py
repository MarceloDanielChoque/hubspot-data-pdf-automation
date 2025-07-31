from flask import Flask, request, jsonify
from fill_pdf import generar_pdfs_en_memoria
from extract_data_hubspot import (
    GestorDatosHubspot, 
    extraer_url_archivo,
    obtener_imagen_desde_url,
    generar_url_previsualizacion_factura, 
    cortar_texto_sin_romper_palabras,
    obtener_urls_videos_desde_ids,
    filtrar_videos_validos
    )
import os

app = Flask(__name__)


@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    try:
        # 1. Validación de entrada
        data = request.get_json()
        hubspot_id = data.get("id")
        if not hubspot_id:
            return jsonify({"error": "Falta el parámetro 'id' en el JSON"}), 400

        # 2. Obtener datos desde HubSpot
        hubspot = GestorDatosHubspot()
        data_hubspot = hubspot.obtener_datos_negocio(hubspot_id)
        if not data_hubspot:
            return jsonify({"error": "No se pudo obtener datos desde HubSpot"}), 404

        # 3. Obtener y preparar URLs de video
        raw_video_urls = obtener_urls_videos_desde_ids(data_hubspot.get("url_video_trayectoria", ""))
        video_lista = filtrar_videos_validos(raw_video_urls)

        # 4. Construir diccionario de campos PDF
        def safe_get(value):
            return "" if value is None else value

        pdf_data = {
            'campo_nombre': safe_get((data_hubspot.get('nombre_negocio') or '').split('-')[0]),
            'campo_telefono': safe_get(data_hubspot.get('telefono_contacto')),
            'campo_direccion': safe_get(cortar_texto_sin_romper_palabras(data_hubspot.get("direccion_empresa", ""), 110)),
            'campo_actividad_comercial': safe_get(data_hubspot.get("actividad_comercial")),
            'campo_tipo_instalacion': safe_get(data_hubspot.get("tipo_instalacion_factura")),
            'campo_numero_presupuesto': safe_get(data_hubspot.get("tipo_instalacion_negocio")),
            'descripcion_empresa': safe_get(data_hubspot.get("descripcion_empresa")),
            'campo_url_video_1': safe_get(video_lista[0]),
            'campo_url_video_2': safe_get(video_lista[1]),
            'campo_url_video_3': safe_get(video_lista[2]),
            'archivo_factura_id': safe_get(extraer_url_archivo(data_hubspot.get("archivo_factura_id"))),
        }

        # 5. Generar PDFs en memoria
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, "plantilla_pdf", "Archivoeditable.pdf")
        pdf_editable_io, pdf_flattened_io = generar_pdfs_en_memoria(template_path, pdf_data)

        # 6. Subir PDF a HubSpot
        file_id, file_url = hubspot.subir_pdf_desde_memoria(pdf_flattened_io, filename=f"Empresa123-{hubspot_id}.pdf")
        if not file_id:
            return jsonify({"error": "No se pudo subir el PDF a HubSpot"}), 500

        # 7. Crear nota asociada
        note_text = "Generado nuevo documento"
        note_id = hubspot.crear_nota_en_negocio(hubspot_id, note_text, file_id)
        if not note_id:
            return jsonify({"error": "No se pudo crear la nota"}), 500

        # 8. Devolver respuesta final
        return jsonify({
            "message": "PDF generado correctamente",
            "url_pdf_subido": file_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
