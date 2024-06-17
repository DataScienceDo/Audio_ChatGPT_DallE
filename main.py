# Стандартные библиотеки
import os
import json
import subprocess

# Библиотеки сторонних разработчиков
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydub import AudioSegment
import openai
import requests
from gradio_client import Client


load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/openai/whisper-small"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = os.getenv("DALLE_API_KEY")
TTS_CLIENT = Client("https://suno-bark.hf.space/")

app = FastAPI()
# Подключение статических файлов (для аудио ответов)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Установка путей к ffmpeg и ffprobe
AudioSegment.converter = "/opt/homebrew/bin/ffmpeg"
AudioSegment.ffprobe = "/opt/homebrew/bin/ffprobe"

@app.get("/", response_class=HTMLResponse)
async def main_page():
    content = '''
    <html>
        <head>
            <title>Чат с ChatGPT</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f0f0f0;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                }
                h1 {
                    color: #333;
                }
                #main-container {
                    background-color: #fff;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    text-align: center;
                }
                #image-container {
                    width: 100%;
                    display: flex;
                    justify-content: center;
                    margin-bottom: 20px;
                }
                #progress-container {
                    width: 100%;
                    background-color: #f3f3f3;
                    margin-top: 20px;
                    display: none;
                }
                #progress-bar {
                    width: 0%;
                    height: 30px;
                    background-color: #4caf50;
                    text-align: center;
                    line-height: 30px;
                    color: white;
                }
                .button-container {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    gap: 10px;
                }
                .button {
                    background-color: #4caf50;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 5px;
                    width: 200px;
                    height: 50px;
                }
                .button.recording {
                    background-color: red;
                }
                .button svg {
                    margin-right: 10px;
                }
                #restartButton {
                    background-color: #f44336;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    cursor: pointer;
                    display: none;
                    width: 200px;
                    height: 50px;
                    margin-top: 20px;
                }
                #responseContainer {
                    margin-top: 20px;
                    text-align: left;
                }
            </style>
        </head>
        <body>
            <div id="image-container">
                <img src="/static/IMG_7077.jpg" alt="Заголовок" style="max-width: 240px; height: 240px;">
            </div>
            <div id="main-container">
                <h1>Отправьте свой голос ChatGPT</h1>
                <div class="button-container">
                    <button id="recordButton" class="button">
                        <svg class="microphone-icon" viewBox="0 0 24 24" width="24" height="24">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm4.3-3c0 2.3-1.56 4.24-3.66 4.77в2.48h2в2h-6в-2h2в-2.48c-2.1-.53-3.66-2.47-3.66-4.77H5c0 3.05 2.19 5.63 5 6.32В21h2в-3.68c2.81-.69 5-3.27 5-6.32h-1.7z"/>
                        </svg>
                        Нажмите и держите для записи
                    </button>
                </div>
                <button id="restartButton" class="button">
                    <svg class="microphone-icon" viewBox="0 0 24 24" width="24" height="24">
                        <path d="M12 14c1.66 0 3-1.34 3-3В5c0-1.66-1.34-3-3-3S9 3.34 9 5в6c0 1.66 1.34 3 3 3zm4.3-3c0 2.3-1.56 4.24-3.66 4.77в2.48h2в2h-6в-2h2в-2.48c-2.1-.53-3.66-2.47-3.66-4.77H5c0 3.05 2.19 5.63 5 6.32В21h2в-3.68c2.81-.69 5-3.27 5-6.32h-1.7z"/>
                    </svg>
                    Перезапуск
                </button>
                <div id="progress-container">
                    <div id="progress-bar">0%</div>
                </div>
                <div id="responseContainer"></div>
            </div>
            <script>
                let mediaRecorder;
                let audioChunks = [];
                const recordButton = document.getElementById('recordButton');
                const restartButton = document.getElementById('restartButton');
                const progressBar = document.getElementById('progress-bar');
                const progressContainer = document.getElementById('progress-container');

                recordButton.addEventListener('mousedown', async function() {
                    audioChunks = [];
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm; codecs=opus' });
                    mediaRecorder.start();
                    recordButton.classList.add('recording');
                    recordButton.innerHTML = `
                        <svg class="microphone-icon" viewBox="0 0 24 24" width="24" height="24">
                            <path d="M12 14c1.66 0 3-1.34 3-3В5c0-1.66-1.34-3-3-3S9 3.34 9 5в6c0 1.66 1.34 3 3 3zm4.3-3c0 2.3-1.56 4.24-3.66 4.77в2.48h2в2h-6в-2h2в-2.48c-2.1-.53-3.66-2.47-3.66-4.77H5c0 3.05 2.19 5.63 5 6.32В21h2в-3.68c2.81-.69 5-3.27 5-6.32h-1.7z"/>
                        </svg>
                        Запись...
                    `;

                    mediaRecorder.addEventListener('dataavailable', event => {
                        audioChunks.push(event.data);
                    });
                });

                recordButton.addEventListener('mouseup', function() {
                    mediaRecorder.stop();
                    recordButton.classList.remove('recording');
                    recordButton.innerHTML = `
                        <svg class="microphone-icon" viewBox="0 0 24 24" width="24" height="24">
                            <path d="M12 14c1.66 0 3-1.34 3-3В5c0-1.66-1.34-3-3-3S9 3.34 9 5в6c0 1.66 1.34 3 3 3zm4.3-3c0 2.3-1.56 4.24-3.66 4.77в2.48h2в2h-6в-2h2в-2.48c-2.1-.53-3.66-2.47-3.66-4.77H5c0 3.05 2.19 5.63 5 6.32В21h2в-3.68c2.81-.69 5-3.27 5-6.32h-1.7z"/>
                        </svg>
                        Нажмите и держите для записи
                    `;

                    mediaRecorder.addEventListener('stop', async () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/webm; codecs=opus' });
                        const formData = new FormData();
                        formData.append('file', audioBlob, 'recording.webm');

                        progressContainer.style.display = 'block';
                        progressBar.style.width = '30%';
                        progressBar.innerText = 'Загрузка...';

                        const response = await fetch('/upload/', {
                            method: 'POST',
                            body: formData
                        });

                        progressBar.style.width = '60%';
                        progressBar.innerText = 'Обработка...';

                        const result = await response.json();
                        progressBar.style.width = '100%';
                        progressBar.innerText = 'Завершено';

                        const container = document.getElementById('responseContainer');
                        container.innerHTML = `
                            <p><strong>Вопрос:</strong> ${result.Question}</p>
                            <p><strong>Ответ:</strong> ${result.Answer}</p>
                            <audio id="audioResponse" controls autoplay>
                                <source src="${result.Audio}" type="audio/wav">
                                Ваш браузер не поддерживает аудио элемент.
                            </audio>
                        `;
                        if (result.Image) {
                            const imageElement = document.createElement('img');
                            imageElement.src = result.Image;
                            imageElement.alt = "Сгенерированное изображение";
                            imageElement.style = "max-width: 100%; height: auto; margin-top: 20px;";
                            container.appendChild(imageElement);
                            container.innerHTML += `<p><strong>Предлагаю Вам картинку созданную по Вашему запросу:</strong></p>`;
                        }
                        recordButton.style.display = 'none';
                        restartButton.style.display = 'inline-flex';
                    });
                });

                restartButton.addEventListener('click', function() {
                    recordButton.style.display = 'inline-flex';
                    restartButton.style.display = 'none';
                    progressContainer.style.display = 'none';
                    progressBar.style.width = '0%';
                    progressBar.innerText = '0%';
                    document.getElementById('responseContainer').innerHTML = '';
                });
            </script>
        </body>
    </html>
    '''
    return HTMLResponse(content=content)

@app.post("/upload/")
async def handle_query(file: UploadFile = File(...)):
    if not file.filename.endswith(".webm"):
        raise HTTPException(status_code=400, detail="Формат файла не поддерживается. Пожалуйста, загрузите файл WebM.")

    source_path = f"temp_{file.filename}"
    target_path = source_path.replace('.webm', '.flac')

    # Сохранение загруженного аудиофайла
    with open(source_path, "wb") as buffer:
        buffer.write(await file.read())

    # Конвертация в формат FLAC
    try:
        convert_webm_to_flac(source_path, target_path)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка конвертации FFmpeg: {e}")

    # Запрос к Whisper API для транскрипции
    text = query_whisper(target_path)
    if 'text' not in text:
        raise HTTPException(status_code=500, detail=f"Не удалось транскрибировать аудио. Ответ: {text}")

    # Проверка, хочет ли пользователь сгенерировать изображение
    print(f"Transcribed text: {text['text']}")  # Отладка
    if "создай картинку" in text['text'].lower() or "нарисуй картинку" in text['text'].lower() or "нарисуй " in text['text'].lower() or "нарисуй рисунок" in text['text'].lower() or "создай рисунок" in text['text'].lower():
        print("Запрос на создание изображения обнаружен")  # Отладка
        image_prompt = text['text'].lower().replace("создай картинку", "").replace("нарисуй картинку", "").replace("нарисуй ", "").replace("нарисуй рисунок", "").replace("создай рисунок", "").strip()
        image_url = generate_image(image_prompt)
        if not image_url:
            raise HTTPException(status_code=500, detail="Не удалось сгенерировать изображение")
        return {
            "Question": text['text'],
            "Answer": "Предлагаю Вам картинку созданную по Вашему запросу",
            "Image": image_url
        }
    else:
        # Получение ответа от ChatGPT
        chat_response = chat(text['text'])

        # Генерация аудиоответа
        audio_response_path = text_to_speech(chat_response, "response_audio.wav")

        # Очистка временных файлов
        os.remove(source_path)
        os.remove(target_path)

        # Возврат результатов
        return {
            "Question": text['text'],
            "Answer": chat_response,
            "Audio": f"/static/{audio_response_path}"
        }

def convert_webm_to_flac(source_path, target_path):
    command = [
        "ffmpeg",
        "-y",  # Перезаписывать выходные файлы без запроса
        "-i", source_path,
        "-acodec", "flac",
        target_path
    ]
    subprocess.run(command, check=True)

def query_whisper(filename):
    with open(filename, "rb") as f:
        data = f.read()
    response = requests.post(API_URL, headers=HEADERS, data=data)
    if response.status_code != 200:
        return {"error": f"Запрос к Whisper API завершился неудачей со статус-кодом {response.status_code}"}
    return response.json()

def chat(input_message):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Вы - полезный помощник."},
            {"role": "user", "content": input_message},
        ]
    )
    chat_response = response['choices'][0]['message']['content']
    return chat_response

def text_to_speech(text, output_filename):
    result = TTS_CLIENT.predict(
        [text],  # Входной текст
        "Speaker 1 (ru)",  # Динамик
        fn_index=3
    )
    file_path = result.split('\n')[-1]  # Предполагаем, что путь к файлу находится на новой строке после основного сообщения

    with open(file_path, 'rb') as file:
        audio_data = file.read()

    output_path = f"static/{output_filename}"
    with open(output_path, 'wb') as new_file:
        new_file.write(audio_data)
    
    return output_filename

def generate_image(prompt):
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )
        print(f"URL сгенерированного изображения: {response['data'][0]['url']}")  # Отладка
        return response['data'][0]['url']
    except Exception as e:
        print(f"Ошибка при создании изображения: {str(e)}")
        return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



#http://localhost:8000/ - по этому адресу смотреть
# "/static/IMG_7077.jpg"