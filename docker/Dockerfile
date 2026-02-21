FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && grep -v '^torch==' requirements.txt > requirements.no_torch.txt \
    && pip install --no-cache-dir -r requirements.no_torch.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1

COPY . .
ENV PYTHONPATH=/app/src

EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
