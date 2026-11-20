FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . todo_app/

ENV PYTHONUNBUFFERED=1
ENV PORT=3000
ENV HOST=0.0.0.0
ENV APP_TIMEZONE=Asia/Kolkata
ENV DB_PATH=/app/todo_app/todo.db

EXPOSE 3000

CMD ["python", "-m", "todo_app.server"]
