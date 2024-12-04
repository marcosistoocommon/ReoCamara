import logging
import asyncio
import requests
import time
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

CAMERA_IP = "TU_IP_DE_CAMARA"
RTSP_URL = f"rtsp://USER:PASSWORD@{CAMERA_IP}:PORT/h264Preview_01_main"
BOT_TOKEN = "TU_TOKEN_DE_TELEGRAMBOT"


#Rutas de movimiento de camara (presets, se configura en aplicacion de la camara o via web)
ROUTES = {
    "getsalseo": [0,1,0],  
   # "comando2": [3, 2, 4, 3],
}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

cached_token = None
token_expiry = 0

#Funcion que obtiene el token de la camara peridocamente para evitar que caduqeu
def get_token():
    global cached_token, token_expiry
    if cached_token and time.time() < token_expiry:
        return cached_token

    url = f"http://{CAMERA_IP}/api.cgi?cmd=Login"
    payload = [{"cmd": "Login", "param": {"User": {"userName": "admin", "password": "holadonpepito!"}}}]
    try:
        response = requests.post(url, json=payload, verify=False)
        if response.status_code == 200:
            cached_token = response.json()[0]["value"]["Token"]["name"]
            token_expiry = time.time() + 60 * 5  # Token valido por 5 minutos
            return cached_token
        else:
            logger.error("Error al obtener el token.")
            return None
    except requests.RequestException as e:
        logger.error(f"Error al obtener el token: {e}")
        return None

#Funcion que mueve la camara a un preset
    #params:
        #preset_id: id del preset al que se quiere mover
        #speed: velocidad de movimiento de la camara

def move_camera(token, preset_id, speed=1):
    url = f"http://{CAMERA_IP}/api.cgi?cmd=PtzCtrl&token={token}"
    payload = [{"cmd": "PtzCtrl", "param": {"channel": 0, "op": "ToPos", "id": preset_id, "speed": speed}}]
    try:
        response = requests.post(url, json=payload, verify=False)
        if response.status_code != 200:
            logger.error(f"Error moviendo la cámara al preset {preset_id}: {response.text}")
    except requests.RequestException as e:
        logger.error(f"Error al mover la cámara: {e}")

async def record_video(output_file, duration):
    try:
        logger.info("Iniciando grabación...")
        command = [
            "ffmpeg", "-y", "-i", RTSP_URL,
            "-t", str(duration), "-vf", "scale=640:360",
            "-preset", "ultrafast", "-c:v", "libx264", output_file
        ]
        process = await asyncio.create_subprocess_exec(*command)
        await process.wait()
        logger.info(f"Video guardado en {output_file}")
    except Exception as e:
        logger.error(f"Error durante la grabación: {e}")

async def execute_route(route, output_file):
    token = get_token()
    if not token:
        logger.error("No se pudo obtener el token, no se puede continuar.")
        return

    duration_per_movement = 5
    total_duration = duration_per_movement * len(route)

    #Iniciar grabacion de video a la vez
    record_task = asyncio.create_task(record_video(output_file, total_duration))

    for preset in route:
        logger.info(f"Moviendo la cámara al preset {preset}...")
        move_camera(token, preset)
        await asyncio.sleep(duration_per_movement)

    
    await record_task #Espera que la grabacin finalice
    logger.info("Ruta completada y grabación finalizada.")

async def send_video(chat_id, output_file, context, delete_after=60):
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        info_message = await context.bot.send_message(  #Avisa por el chat que el video se elimina
            chat_id=chat_id, 
            text=f"Este video se autodestruirá en {delete_after} segundos."
        )

        #Envio del video
        with open(output_file, "rb") as video:
            video_message = await context.bot.send_video(chat_id=chat_id, video=video)

        #Eliminacion de mensajes
        await asyncio.sleep(delete_after)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=video_message.message_id)
            await context.bot.delete_message(chat_id=chat_id, message_id=info_message.message_id)
            logger.info(f"Mensajes eliminados después de {delete_after} segundos.")
        except Exception as e:
            logger.error(f"Error al eliminar los mensajes: {e}")
    else:
        logger.error("El archivo de video no existe o está vacío.")
        await context.bot.send_message(chat_id=chat_id, text="No se pudo grabar el video.")

async def start_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.replace("/", "")
    if command in ROUTES:
        route = ROUTES[command]
        output_file = f"{command}.mp4"  #***ATENCION**** Si no se crea se debera crear el fichero para cada comando

        await execute_route(route, output_file)
        await send_video(update.effective_chat.id, output_file, context, delete_after=60)
    else:
        await update.message.reply_text("Comando no reconocido. Intenta con: /getsalseo o /comando2 hijo de la gran puta")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("getsalseo", start_route))
    application.add_handler(CommandHandler("comando2", start_route))
    logger.info("Bot iniciado.")
    application.run_polling()

if __name__ == "__main__":
    main()
