FROM debian:testing
RUN apt-get update && apt-get install -y python3 python3-pip && apt-get clean
RUN mkdir -p /opt/rating_bot/
COPY rating_bot /opt/rating_bot
COPY requirements.txt /opt/rating_bot/
RUN pip3 install --no-cache-dir -r /opt/rating_bot/requirements.txt
WORKDIR /opt/
ENTRYPOINT ["/usr/bin/python3", "-m", "rating_bot"]
