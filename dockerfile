FROM mcr.microsoft.com/playwright/python:v1.44.0

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080

CMD ["python", "app.py"]