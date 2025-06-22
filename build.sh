#!/usr/bin/env bash
# exit on error
set -o errexit

# Устанавливаем системные зависимости, которые требует Playwright
apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk-bridge2.0-0 \
    libcups2 \
    libatspi2.0-0 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libx11-6 \
    libxext6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libglib2.0-0