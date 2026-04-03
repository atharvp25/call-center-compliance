FROM python:3.11-slim

# Install ffmpeg (required by pydub for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# HF Spaces uses port 7860 by default
ENV PORT=7860

# Start the API server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]
