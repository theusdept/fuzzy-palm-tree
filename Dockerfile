FROM python:3.13-slim
WORKDIR /app
COPY app.py billing.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]

