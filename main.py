import requests
import logging

# Configuración de la cámara
CAMERA_IP = "10.0.158.5"  # Dirección IP de la cámara
USER = "admin"  # Usuario para la cámara
PASSWORD = "holadonpepito!"  # Contraseña para la cámara

# Configura el logger
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Función para obtener el token de la cámara
def get_token():
    url = f"http://{CAMERA_IP}/api.cgi?cmd=Login"
    payload = [
        {
            "cmd": "Login",
            "param": {
                "User": {
                    "userName": USER,
                    "password": PASSWORD
                }
            }
        }
    ]
    
    try:
        # Realizar la solicitud para obtener el token
        response = requests.post(url, json=payload, verify=False)
        
        # Si la respuesta es exitosa, obtenemos el token
        if response.status_code == 200:
            token = response.json()[0]["value"]["Token"]["name"]
            logger.info(f"Token obtenido: {token}")
            return token
        else:
            logger.error(f"Error al obtener el token: {response.text}")
            return None
    except requests.RequestException as e:
        logger.error(f"Error en la solicitud de token: {e}")
        return None

# Función para obtener los presets de la cámara
def get_ptz_presets(token):
    if not token:
        logger.error("No se pudo obtener el token, no se puede continuar.")
        return

    url = f"http://{CAMERA_IP}/api.cgi?cmd=GetPtzPreset&token={token}"
    payload = [
        {
            "cmd": "GetPtzPreset",
            "action": 1,
            "param": {
                "channel": 0
            }
        }
    ]
    
    try:
        # Realizamos la solicitud para obtener los presets
        response = requests.post(url, json=payload, verify=False)
        
        # Si la respuesta es exitosa, la procesamos
        if response.status_code == 200:
            logger.info(f"Respuesta de la cámara: {response.json()}")
            return response.json()  # Devuelve la respuesta en formato JSON
        else:
            logger.error(f"Error al obtener los presets: {response.text}")
    except requests.RequestException as e:
        logger.error(f"Error en la solicitud: {e}")

# Llamada a la función principal para obtener el token y los presets
if __name__ == "__main__":
    token = get_token()  # Obtener el token automáticamente
    get_ptz_presets(token)  # Obtener los presets con el token
