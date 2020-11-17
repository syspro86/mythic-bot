FROM python:3.8.5

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY mythic /app/mythic
COPY mythic.yml /app/
COPY startup.sh /app/
RUN chmod +x /app/startup.sh

ENTRYPOINT /app/startup.sh
