FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

# Base packages
RUN apt-get update && apt-get install --no-install-recommends -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-tk \
    python3-pip \
    gcc \
    xvfb \
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
    x11-apps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Chromium from Debian (real binary, not snap)
RUN apt-get update && apt-get install --no-install-recommends -y \
    chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash testuser
USER testuser
WORKDIR /home/testuser/repo

COPY --chown=testuser:testuser requirements-linux.txt .
RUN python3.11 -m venv --system-site-packages /home/testuser/.venv && \
    /home/testuser/.venv/bin/pip install --no-cache-dir pytest "pytesseract>=0.3.10" -r requirements-linux.txt

ENV PATH="/home/testuser/.venv/bin:$PATH"

COPY --chown=testuser:testuser . /home/testuser/repo

CMD ["bash"]
