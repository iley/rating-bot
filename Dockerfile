FROM ubuntu:latest
RUN apt-get update && apt-get install -y python3 python3-pip python3-dev
RUN pip3 install --no-cache-dir -r /opt/rating_bot/requirements.txt
RUN mkdir -p /opt/rating_bot/
COPY rating_bot /opt/rating_bot
COPY requirements.txt /opt/rating_bot/
WORKDIR /opt/
CMD /usr/bin/python3 -m rating_bot
