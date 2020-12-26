FROM python:3-alpine
RUN mkdir -p /app
COPY requirements.txt /app/
RUN apk add --no-cache --virtual build-deps gcc musl-dev python3-dev libffi-dev libressl-dev && \
    apk add --no-cache ca-certificates libffi libressl && \
    pip3 install --no-cache-dir -r /app/requirements.txt && \
    apk del build-deps
COPY rating_bot /app/rating_bot

RUN adduser -DH appuser nogroup
RUN chown -R appuser /app
USER appuser

WORKDIR /app/
ENTRYPOINT ["/usr/local/bin/python", "-m", "rating_bot"]
