FROM python:3.8.5

WORKDIR /app

ADD requirements.txt /app
RUN python -m venv .venv
RUN .venv/bin/pip install --upgrade pip
RUN .venv/bin/pip install -r requirements.txt

ADD mythic /app/mythic
CMD . .venv/bin/activate && python -u -m mythic.main
