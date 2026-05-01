FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install --no-install-recommends -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-tk \
    python3-pip \
    gcc \
    xvfb \
    x11vnc \
    novnc \
    xdotool \
    wmctrl \
    xclip \
    x11-utils \
    dbus-x11 \
    at-spi2-core \
    python3-gi \
    gir1.2-atspi-2.0 \
    gir1.2-gtk-3.0 \
    openbox \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    ca-certificates \
    ffmpeg \
    firefox \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash testuser
USER testuser
WORKDIR /home/testuser/repo

COPY --chown=testuser:testuser requirements-linux.txt .
RUN python3.12 -m venv --system-site-packages /home/testuser/.venv && \
    /home/testuser/.venv/bin/pip install --no-cache-dir pytest "pytesseract>=0.3.10" -r requirements-linux.txt

ENV PATH="/home/testuser/.venv/bin:$PATH"

COPY --chown=testuser:testuser . /home/testuser/repo

EXPOSE 6080

CMD ["bash"]
