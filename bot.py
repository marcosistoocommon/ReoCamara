import asyncio
import requests
import time
import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Load environment variables
load_dotenv()

# Configuración de la cámara y bot
CAMERA_IP = os.getenv("CAMERA_IP")
USER = os.getenv("USERBOT")
PASSWORD = os.getenv("PASSWORD")
PORT = os.getenv("PORT")
RTSP_URL = f"rtsp://{USER}:{PASSWORD}@{CAMERA_IP}:{PORT}/h264Preview_01_main"
BOT_TOKEN = os.getenv("TOKEN")

# Rutas de movimiento de cámara (presets)
ROUTES = {
    "getSalseo": [0, 1, 0],
    "getNevera": [0, 2, 0],
    # Añadir más rutas aquí
}

# Lista de comandos disponibles y sus descripciones
COMMANDS_DESCRIPTIONS = {
    "getSalseo": "Inicia una ruta predefinida llamada 'salseo' y graba un video.",
    "getNevera": "Inicia una ruta predefinida llamada 'nevera' y graba un video.",
    "getImage": "Obtiene una imagen del punto inicial de la cámara.",
    "getVideo": "Obtiene un video del punto inicial de la cámara.",
}

MESSAGE_LIFETIME = 30  # Tiempo en segundos para eliminar mensajes

# Variables globales para token de la cámara
cached_token = None
token_expiry = 0

def get_token():
    """Obtiene y almacena en caché el token de la cámara."""
    global cached_token, token_expiry
    if cached_token and time.time() < token_expiry:
        return cached_token

    url = f"http://{CAMERA_IP}/api.cgi?cmd=Login"
    payload = [{"cmd": "Login", "param": {"User": {"userName": "admin", "password": "holadonpepito!"}}}]
    try:
        response = requests.post(url, json=payload, verify=False)
        if response.status_code == 200:
            cached_token = response.json()[0]["value"]["Token"]["name"]
            token_expiry = time.time() + 60 * 5  # Token válido por 5 minutos
            return cached_token
    except requests.RequestException:
        pass

    return None

def move_camera(token, preset_id, speed=1):
    """Mueve la cámara a un preset específico."""
    url = f"http://{CAMERA_IP}/api.cgi?cmd=PtzCtrl&token={token}"
    payload = [{"cmd": "PtzCtrl", "param": {"channel": 0, "op": "ToPos", "id": preset_id, "speed": speed}}]
    try:
        response = requests.post(url, json=payload, verify=False)
    except requests.RequestException:
        pass

async def record_video(output_file, duration):
    """Graba un video desde la cámara durante un tiempo determinado."""
    try:
        command = [
            "ffmpeg", "-y", "-i", RTSP_URL,
            "-t", str(duration), "-vf", "scale=640:360",
            "-preset", "ultrafast", "-c:v", "libx264", output_file
        ]
        process = await asyncio.create_subprocess_exec(*command)
        await process.wait()
    except Exception:
        pass

async def execute_route(route, output_file):
    """Ejecuta una ruta de movimiento de la cámara y graba el video."""
    token = get_token()
    if not token:
        return

    duration_per_movement = 5
    total_duration = duration_per_movement * len(route)

    # Iniciar grabación en paralelo
    record_task = asyncio.create_task(record_video(output_file, total_duration))

    for preset in route:
        move_camera(token, preset)
        await asyncio.sleep(duration_per_movement)

    await record_task  # Espera a que la grabación finalice

async def send_video(chat_id, output_file, context, delete_after=MESSAGE_LIFETIME):
    """Envía un video al chat y lo elimina después de un tiempo."""
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        info_message = await context.bot.send_message(chat_id=chat_id, text=f"Este video se autodestruirá en {delete_after} segundos.")
        with open(output_file, "rb") as video:
            video_message = await context.bot.send_video(chat_id=chat_id, video=video)
        await asyncio.sleep(delete_after)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=video_message.message_id)
            await context.bot.delete_message(chat_id=chat_id, message_id=info_message.message_id)
        except Exception:
            pass
    else:
        await context.bot.send_message(chat_id=chat_id, text="No se pudo grabar el video.")

async def start_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia la ejecución de una ruta de cámara basada en el comando recibido."""
    command = update.message.text.replace("/", "")
    if command in ROUTES:
        route = ROUTES[command]
        output_file = f"{command}.mp4"
        await execute_route(route, output_file)
        await send_video(update.effective_chat.id, output_file, context, delete_after=MESSAGE_LIFETIME)
    else:
        await unknown_command(update, context)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja comandos no reconocidos."""
    commands_list = "\n".join([f"/{cmd} - {desc}" for cmd, desc in COMMANDS_DESCRIPTIONS.items()])
    error_message = (
        "Comando no reconocido. Por favor, utiliza uno de los siguientes comandos disponibles:\n\n"
        f"{commands_list}"
    )
    await update.message.reply_text(error_message)

async def send_image(chat_id, image_file, context, delete_after=MESSAGE_LIFETIME):
    """Envía una imagen al chat y la elimina después de un tiempo."""
    if os.path.exists(image_file) and os.path.getsize(image_file) > 0:
        info_message = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"Esta imagen se autodestruirá en {delete_after} segundos."
        )
        with open(image_file, 'rb') as image:
            image_message = await context.bot.send_photo(chat_id=chat_id, photo=image)
        
        # Esperar el tiempo de autodestrucción
        await asyncio.sleep(delete_after)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=image_message.message_id)
            await context.bot.delete_message(chat_id=chat_id, message_id=info_message.message_id)
            os.remove(image_file)
        except Exception:
            pass
    else:
        await context.bot.send_message(chat_id=chat_id, text="No se pudo obtener la imagen de la cámara.")

async def get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /getimage y envía una imagen del punto inicial."""
    token = get_token()
    if not token:
        await update.message.reply_text("Error al obtener el token de la cámara.")
        return

    url = f"https://{CAMERA_IP}/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=flsYJfZgM6RTB_os&token={token}"
    image_file = "getImage.jpg"

    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        with open(image_file, 'wb') as f:
            f.write(response.content)
    except requests.RequestException:
        await update.message.reply_text("Error al obtener la imagen de la cámara.")
        return

    # Enviar la imagen usando la función send_image
    await send_image(update.effective_chat.id, image_file, context, delete_after=MESSAGE_LIFETIME)

async def get_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Graba un video de 10 segundos desde la posición actual de la cámara y lo envía."""
    output_file = "getVideo.mp4"  # Nombre del archivo del video
    duration = 10  # Duración del video en segundos

    try:
        # Llama a record_video para grabar el video
        await record_video(output_file, duration)

        # Verifica si el archivo de video se creó correctamente
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            await update.message.reply_text("No se pudo grabar el video.")
            return

        # Usa send_video para enviar el archivo al chat y programar su eliminación
        await send_video(update.effective_chat.id, output_file, context, delete_after=MESSAGE_LIFETIME)
    except Exception:
        await update.message.reply_text("Ocurrió un error al grabar el video.")

def main():
    """Función principal para iniciar el bot."""
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("getSalseo", start_route))
    application.add_handler(CommandHandler("getNevera", start_route))
    application.add_handler(CommandHandler("getImage", get_image))
    application.add_handler(CommandHandler("getVideo", get_video))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    application.run_polling()

if __name__ == "__main__":
    main()
