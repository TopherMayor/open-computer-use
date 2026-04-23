FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --no-install-recommends -y \
    python3.12 \
    python3-pip \
    xvfb \
    x11vnc \
    novnc \
    xdotool \
    wmctrl \
    xclip \
    x11-utils \
    scrot \
    dbus-x11 \
    at-spi2-core \
    python3-gi \
    gir1.2-atspi-2.0 \
    gir1.2-gtk-3.0 \
    openbox \
    curl \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash testuser
USER testuser
WORKDIR /home/testuser/repo

COPY --chown=testuser:testuser requirements-linux.txt .
RUN pip3 install --no-cache-dir --break-system-packages pytest -r requirements-linux.txt

COPY --chown=testuser:testuser . /home/testuser/repo

EXPOSE 6080

CMD ["bash"]
