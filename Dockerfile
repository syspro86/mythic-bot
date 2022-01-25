FROM python:3.10.1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN apt-get update && apt-get install libaio1

COPY mythic /app/mythic
COPY startup.sh /app/
RUN chmod +x /app/startup.sh

ENTRYPOINT ["/bin/bash", "/app/startup.sh"]
