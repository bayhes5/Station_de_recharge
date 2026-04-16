FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#CMD ["tail", "-f", "/dev/null"]
#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD ["sleep", "infinity"]