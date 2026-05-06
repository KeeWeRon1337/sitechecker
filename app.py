# -*- coding: utf-8 -*-
"""
app.py v1.2 — Основной код SiteChecker.
✅ ИСПРАВЛЕНО: убран subprocess.run для ping (запрещён на Android),
   заменён на TCP + HTTP проверку.
"""

import socket
import threading
import time
import json
import os
import ssl

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.app import App

# ─── Цвета ────────────────────────────────────────────────────────────────────
CLR_BG        = (0.07, 0.08, 0.10, 1)
CLR_CARD      = (0.12, 0.14, 0.18, 1)
CLR_FOLDER    = (0.10, 0.13, 0.17, 1)
CLR_ACCENT    = (0.22, 0.68, 0.87, 1)
CLR_GREEN     = (0.22, 0.78, 0.51, 1)
CLR_RED       = (0.93, 0.33, 0.36, 1)
CLR_YELLOW    = (0.98, 0.76, 0.18, 1)
CLR_TEXT      = (0.92, 0.93, 0.95, 1)
CLR_SUBTEXT   = (0.55, 0.60, 0.67, 1)
CLR_INPUT_BG  = (0.16, 0.18, 0.23, 1)
CLR_BTN       = (0.22, 0.68, 0.87, 1)
CLR_DEL       = (0.93, 0.33, 0.36, 1)

SOCKET_TIMEOUT = 4

APP_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(APP_DIR, "sitechecker_data.json")

DEFAULT_DATA = {
    "folders": [
        {
            "name": "Российские",
            "sites": ["ya.ru", "vk.com", "mail.ru", "gosuslugi.ru"]
        },
        {
            "name": "Зарубежные",
            "sites": ["google.com", "github.com", "wikipedia.org"]
        }
    ]
}


# ─── Хранилище ────────────────────────────────────────────────────────────────

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return DEFAULT_DATA.copy()


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[save_data] {e}")


# ─── Проверка сайтов ──────────────────────────────────────────────────────────

def measure_tcp_ms(host, port=80):
    """TCP соединение на порт 80."""
    try:
        t0 = time.monotonic()
        with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT):
            pass
        return int((time.monotonic() - t0) * 1000)
    except Exception:
        return None


def measure_https_ms(host):
    """✅ НОВОЕ: HTTPS соединение на порт 443 (работает на Android)."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        t0 = time.monotonic()
        conn = socket.create_connection((host, 443), timeout=SOCKET_TIMEOUT)
        s = ctx.wrap_socket(conn, server_hostname=host)
        s.close()
        return int((time.monotonic() - t0) * 1000)
    except Exception:
        return None


def check_dns(host):
    try:
        ip = socket.getaddrinfo(host, None, socket.AF_UNSPEC,
                                socket.SOCK_STREAM, 0,
                                socket.AI_ADDRCONFIG)
        return True, ip[0][4][0] if ip else None
    except socket.gaierror:
        return False, None


def check_site(host):
    """
    ✅ ИСПРАВЛЕНО: вместо subprocess ping используем:
       1. DNS-резолвинг
       2. TCP на порт 443 (HTTPS)
       3. TCP на порт 80 (HTTP) как fallback
    Возвращает (sent: bool, returned: bool, latency_ms: int|None).
    """
    sent, ip = check_dns(host)
    if not sent:
        return False, False, None

    # Пробуем HTTPS (443)
    ms = measure_https_ms(host)
    if ms is not None:
        return True, True, ms

    # Fallback: HTTP (80)
    ms = measure_tcp_ms(host, port=80)
    if ms is not None:
        return True, True, ms

    # DNS прошёл, но TCP не отвечает
    return True, False, None
