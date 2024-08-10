FROM python:3.10-slim
WORKDIR /server_work
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "card_server.py"]
