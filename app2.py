import os
import uvicorn
import asyncio
from fastapi import FastAPI, Body, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from melo.api import TTS
from dotenv import load_dotenv
import uuid
from concurrent.futures import ThreadPoolExecutor

load_dotenv()
DEFAULT_SPEED = float(os.getenv('DEFAULT_SPEED', '1.0'))
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'EN')
DEFAULT_SPEAKER_ID = os.getenv('DEFAULT_SPEAKER_ID', '0')
device = 'auto'

class TextModel(BaseModel):
    text: str
    speed: float = DEFAULT_SPEED
    language: str = DEFAULT_LANGUAGE
    speaker_id: str = DEFAULT_SPEAKER_ID

tts_models: dict[str, TTS] = {}

def get_tts_model(language: str) -> TTS:
    if language not in tts_models:
        tts_models[language] = TTS(language=language, device=device)
    return tts_models[language]

async def run_tts_to_file(model: TTS, text: str, spk: int, path: str, speed: float):
    """
    在线程池中执行同步的 tts_to_file 方法，确保它是同步执行，不阻塞主 loop。
    """
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=8))
    await loop.run_in_executor(None, model.tts_to_file, text, spk, path, speed)

def iter_file_chunks(file_path: str, chunk_size: int = 64 * 1024):
    """
    一个同步生成器，从文件读块返回 bytes，用于 StreamingResponse。
    """
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def remove_file(path: str):
    try:
        os.remove(path)
    except Exception as e:
        # 可加日志记录删除失败的情况
        print(f"Error removing file {path}: {e}")

app = FastAPI()

@app.post("/convert/tts")
async def convert_tts(body: TextModel = Body(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    model = get_tts_model(body.language)
    speaker_ids = model.hps.data.spk2id
    if body.speaker_id not in speaker_ids:
        raise HTTPException(status_code=400, detail="Invalid speaker_id")

    # 生成唯一文件名，避免并发覆盖
    unique_id = uuid.uuid4().hex
    output_path = f"tts_out_{body.language}_{body.speaker_id}_{unique_id}.wav"

    # 执行 tts 并写文件
    try:
        await run_tts_to_file(model, body.text, speaker_ids[body.speaker_id], output_path, body.speed)
    except Exception as e:
        # 如果推理或写文件出错，清理残余文件（如果有的话）
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

    # 检查文件是否写入成功且非空
    try:
        st = os.stat(output_path)
        if st.st_size == 0:
            raise HTTPException(status_code=500, detail="Empty audio file generated")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"File access error: {e}")

    # 用 StreamingResponse 安全返回文件内容
    # 这样 HTTP 不会设置 Content-Length（会使用 chunked），减少因长度不匹配产生的错误
    response = StreamingResponse(iter_file_chunks(output_path), media_type="audio/wav")
    # 可选：在 headers 中提示文件名
    response.headers["Content-Disposition"] = f'attachment; filename="{os.path.basename(output_path)}"'

    # 添加后台任务：在响应完毕后删除这个文件
    background_tasks.add_task(remove_file, output_path)

    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
