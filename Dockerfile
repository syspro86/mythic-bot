FROM python:3.8.5

WORKDIR /app

COPY requirements.txt /app/
RUN python -m venv .venv
RUN .venv/bin/pip install --upgrade pip
RUN .venv/bin/pip install -r requirements.txt

COPY mythic /app/mythic
COPY mythic.yml /app/
CMD . .venv/bin/activate && python -u -m mythic.main
