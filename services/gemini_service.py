import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json

load_dotenv()

# Configurar API de Gemini
api_key = os.getenv("GEMINI_API_KEY")

def extract_invoice_data(image_path: str):
    """
    Usa Gemini para extraer los datos de la factura en formato JSON.
    """
    try:
        if not api_key or api_key == "pon_aqui_tu_api_key_gratuita_de_google":
            print("API Key no configurada correctamente.")
            return None

        client = genai.Client(api_key=api_key)

        # Cargar el archivo de imagen
        sample_file = client.files.upload(file=image_path)

        # Prompt para Gemini
        prompt = """
        Eres un asistente experto en contabilidad. Extrae los siguientes datos de la factura proporcionada:
        1. fecha_factura (formato YYYY-MM-DD)
        2. nombre_proveedor (string)
        3. nit_proveedor (string, opcional si no aparece)
        4. total_factura (número decimal sin símbolos de moneda)
        5. productos (una lista de objetos con: nombre_producto, cantidad, precio_unitario)

        Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni comillas invertidas, con esta estructura:
        {
            "fecha_factura": "2023-10-25",
            "nombre_proveedor": "Proveedor S.A.",
            "total_factura": 150000.50,
            "productos": [
                {"nombre_producto": "Item 1", "cantidad": 2, "precio_unitario": 75000.25}
            ]
        }
        """

        # Generar contenido usando un modelo moderno disponible
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[sample_file, prompt]
        )
        
        # Limpiar la respuesta por si Gemini devuelve markdown como ```json ... ```
        response_text = response.text.replace('```json', '').replace('```', '').strip()
        
        # Parsear a diccionario
        invoice_data = json.loads(response_text)
        return invoice_data

    except Exception as e:
        print(f"Error procesando factura con IA: {e}")
        return None
