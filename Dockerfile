FROM python:3.10.1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ARG OPTION_ORACLE=N
RUN if [[ "${OPTION_ORACLE}" == "Y" ]]; then pip install -r requirements_oracle.txt; fi
RUN if [[ "${OPTION_ORACLE}" == "Y" ]]; then apt-get update && apt-get install libaio1; fi

COPY mythic /app/mythic
COPY startup.sh /app/
RUN chmod +x /app/startup.sh

ENTRYPOINT ["/bin/bash", "/app/startup.sh"]

