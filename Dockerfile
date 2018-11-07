FROM python:3-alpine
RUN mkdir -p /opt/rating_bot/
COPY rating_bot /opt/rating_bot
COPY requirements.txt /opt/rating_bot/
RUN apk add --no-cache --virtual build-deps gcc musl-dev python3-dev libffi-dev libressl-dev && \
    apk add --no-cache ca-certificates libffi libressl && \
    pip3 install --no-cache-dir -r /opt/rating_bot/requirements.txt && \
    apk del build-deps
WORKDIR /opt/
ENTRYPOINT ["/usr/local/bin/python", "-m", "rating_bot"]
