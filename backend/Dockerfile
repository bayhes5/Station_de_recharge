# FROM python:3.11-slim

# WORKDIR /app

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# #CMD ["tail", "-f", "/dev/null"]
# #CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
# CMD ["sleep", "infinity"]
FROM python:3.11-slim

WORKDIR /app

# Installe les dépendances système (nécessaire pour psycopg2)
# RUN apt-get update && apt-get install -y \
#     gcc \
#     python3-dev \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
#CMD ["tail", "-f", "/dev/null"]
CMD ["sleep", "infinity"]