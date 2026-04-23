FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.12 \
    python3-pip \
    xvfb \
    x11vnc \
    novnc \
    xdotool \
    wmctrl \
    xclip \
    xsel \
    x11-utils \
    scrot \
    dbus-x11 \
    at-spi2-core \
    python3-gi \
    gir1.2-atspi-2.0 \
    gir1.2-gtk-3.0 \
    openbox \
    wget \
    curl

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

COPY requirements-linux.txt .
RUN pip3 install --no-cache-dir --break-system-packages pytest -r requirements-linux.txt

COPY . /repo

EXPOSE 6080

CMD ["bash"]