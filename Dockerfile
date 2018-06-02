FROM python:3-alpine
RUN mkdir -p /opt/rating_bot/
COPY rating_bot /opt/rating_bot
COPY requirements.txt /opt/rating_bot/
RUN pip3 install --no-cache-dir -r /opt/rating_bot/requirements.txt
WORKDIR /opt/
ENTRYPOINT ["/usr/local/bin/python", "-m", "rating_bot"]
