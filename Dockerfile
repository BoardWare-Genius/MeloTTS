FROM python:3.9-slim
WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y \
    build-essential libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -e .
RUN pip install torch==2.2.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu121
RUN python -m unidic download
# RUN python melo/init_downloads.py

CMD ["python", "./app.py", "--host", "0.0.0.0", "--port", "5000"]
