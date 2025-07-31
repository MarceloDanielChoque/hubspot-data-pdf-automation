# 📄 Generador de PDFs a partir de datos de HubSpot

Este proyecto permite generar documentos PDF automáticamente usando datos extraídos desde **negocios (deals) en HubSpot**, insertando textos, imágenes y enlaces de forma visual sobre una plantilla PDF editable. 

Incluye generación de dos versiones del documento:
- 📝 Un PDF editable con campos rellenados.
- ✅ Un PDF aplanado (no editable), listo para compartir o almacenar en HubSpot.

---

## 🚀 ¿Qué hace este proyecto?

1. Recibe un `HubSpot Deal ID` mediante una petición HTTP (`/generate_pdf`).
2. Extrae información clave del negocio desde HubSpot usando su API.
3. Inserta textos, imágenes (como fotos de instalaciones) y enlaces (videos, facturas, etc.) en una plantilla PDF.
4. Genera el PDF en dos versiones (editable y aplanado).
5. Sube automáticamente el PDF a HubSpot y crea una nota asociada al negocio.

---

## 🧠 Tecnologías usadas

- **Python 3.12**
- **Flask** – API REST para generar el PDF bajo demanda.
- **PyMuPDF (fitz)** – Edición de PDFs con textos, imágenes, enlaces.
- **hubspot-api-client** – Conector con la API de HubSpot (simulada / desconectada).
- **reportlab / pdfrw** – Procesamiento interno de PDFs (en caso de ser requerido).

---

⚠️ Nota: Este proyecto ha sido despersonalizado para fines de portafolio. La conexión con HubSpot está desactivada por motivos legales, pero el flujo completo de procesamiento de datos y generación de PDFs está documentado.