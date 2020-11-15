FROM python:3.8.5

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY mythic /app/mythic
COPY templates /app/templates
COPY mythic.yml /app/

ENTRYPOINT [ "python", "-u", "-m", "mythic.main" ]
