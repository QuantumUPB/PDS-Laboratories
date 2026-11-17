FROM python:3.12-slim

RUN pip install --no-cache-dir apache-beam==2.77.0
WORKDIR /lab
COPY stream.py ./
CMD ["python", "stream.py"]
