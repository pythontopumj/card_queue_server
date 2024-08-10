FROM python:3.10-slim
card_queue_server /server_script
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "card_queue_server.py"]
