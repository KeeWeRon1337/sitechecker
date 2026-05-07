# -*- coding: utf-8 -*-
"""
main.py v1.2 — Загрузчик SiteChecker.
Исправлено: SSL таймаут, повторные попытки, увеличенные таймауты.
"""

import os
import ssl
import threading
import urllib.request
import urllib.error

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

# ─── Конфиг ───────────────────────────────────────────────────────────────────
GITHUB_USER   = "KeeWeRon1337"
GITHUB_REPO   = "sitechecker"
GITHUB_BRANCH = "main"

RAW_BASE    = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
VERSION_URL = f"{RAW_BASE}/version.txt"
APP_URL     = f"{RAW_BASE}/app.py"

APP_DIR   = os.path.dirname(os.path.abspath(__file__))
LOCAL_APP = os.path.join(APP_DIR, "app_downloaded.py")
LOCAL_VER = os.path.join(APP_DIR, "version_downloaded.txt")

BUILTIN_VERSION = "1.0"

# Таймауты и повторы
CONNECT_TIMEOUT = 30   # секунд на SSL handshake + соединение
READ_TIMEOUT    = 30   # секунд на чтение данных
MAX_RETRIES     = 3    # попыток при ошибке

# Цвета
CLR_BG      = (0.07, 0.08, 0.10, 1)
CLR_ACCENT  = (0.22, 0.68, 0.87, 1)
CLR_TEXT    = (0.92, 0.93, 0.95, 1)
CLR_SUBTEXT = (0.55, 0.60, 0.67, 1)
CLR_GREEN   = (0.22, 0.78, 0.51, 1)
CLR_RED     = (0.93, 0.33, 0.36, 1)
CLR_YELLOW  = (0.98, 0.76, 0.18, 1)
CLR_BTN     = (0.22, 0.68, 0.87, 1)


# ─── Android разрешения ───────────────────────────────────────────────────────

def request_android_permissions():
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.INTERNET,
            Permission.ACCESS_NETWORK_STATE,
        ])
    except ImportError:
        pass


# ─── SSL контекст ─────────────────────────────────────────────────────────────

def make_ssl_context():
    """
    Создаёт SSL-контекст. На Android сертификаты могут быть недоступны,
    поэтому пробуем несколько вариантов.
    """
    # Вариант 1: стандартный контекст
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        pass
    # Вариант 2: без проверки сертификата (fallback для старых Android)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ─── Сетевые утилиты ──────────────────────────────────────────────────────────

def fetch_url(url, timeout=CONNECT_TIMEOUT, retries=MAX_RETRIES):
    """
    Скачивает URL с повторными попытками и увеличенным таймаутом.
    Возвращает (bytes | None, error_str).
    """
    last_err = "неизвестная ошибка"
    ctx = make_ssl_context()

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "SiteChecker/1.2",
                    "Connection": "close",
                }
            )
            handler = urllib.request.HTTPSHandler(context=ctx)
            opener  = urllib.request.build_opener(handler)
            with opener.open(req, timeout=timeout) as r:
                data = r.read()
            return data, None
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.reason}"
            break  # HTTP-ошибки не повторяем
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                import time
                time.sleep(2 * attempt)  # пауза перед следующей попыткой

    return None, last_err


def fetch_remote_version():
    data, err = fetch_url(VERSION_URL)
    if data is not None:
        return data.decode("utf-8").strip(), None
    return None, err


def download_app():
    data, err = fetch_url(APP_URL, timeout=CONNECT_TIMEOUT, retries=MAX_RETRIES)
    if data is None:
        return False, err
    try:
        with open(LOCAL_APP, "wb") as f:
            f.write(data)
        return True, ""
    except Exception as e:
        return False, str(e)


# ─── Хранилище версии ─────────────────────────────────────────────────────────

def get_local_version():
    try:
        if os.path.exists(LOCAL_VER):
            with open(LOCAL_VER, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def save_version(version):
    try:
        with open(LOCAL_VER, "w", encoding="utf-8") as f:
            f.write(version)
    except Exception as e:
        print(f"[save_version] {e}")


# ─── Запуск app.py ────────────────────────────────────────────────────────────

def launch_app():
    if not os.path.exists(LOCAL_APP):
        return False, "Файл app.py не найден"
    try:
        ns = {"__file__": LOCAL_APP, "__name__": "__main__"}
        with open(LOCAL_APP, "r", encoding="utf-8") as f:
            code = f.read()
        exec(compile(code, LOCAL_APP, "exec"), ns)
        return True, ""
    except Exception as e:
        return False, str(e)


# ─── Экран загрузчика ─────────────────────────────────────────────────────────

class LoaderScreen(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical",
                         padding=dp(30), spacing=dp(14), **kw)
        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        self.add_widget(Label(
            text="SiteChecker", font_size=dp(30), bold=True,
            color=CLR_ACCENT, size_hint_y=None, height=dp(48)
        ))

        local_ver = get_local_version() or BUILTIN_VERSION
        self.lbl_version = Label(
            text=f"Версия: {local_ver}",
            font_size=dp(13), color=CLR_SUBTEXT,
            size_hint_y=None, height=dp(24)
        )
        self.add_widget(self.lbl_version)

        self.add_widget(Label(
            text=f"github.com/{GITHUB_USER}/{GITHUB_REPO}",
            font_size=dp(11), color=CLR_SUBTEXT,
            size_hint_y=None, height=dp(20)
        ))

        self.lbl_status = Label(
            text="Подключаемся к GitHub...",
            font_size=dp(14), color=CLR_TEXT,
            halign="center", valign="middle",
            size_hint_y=None, height=dp(70)
        )
        self.lbl_status.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self.add_widget(self.lbl_status)

        # Индикатор попытки
        self.lbl_attempt = Label(
            text="", font_size=dp(11), color=CLR_SUBTEXT,
            size_hint_y=None, height=dp(20)
        )
        self.add_widget(self.lbl_attempt)

        self.add_widget(Label(size_hint_y=1))

        self.btn_launch = Button(
            text="▶  Запустить приложение",
            font_size=dp(15), bold=True,
            background_color=CLR_BTN,
            color=(0.04, 0.04, 0.06, 1),
            size_hint_y=None, height=dp(54),
            disabled=True
        )
        self.btn_launch.bind(on_press=self._on_launch)
        self.add_widget(self.btn_launch)

        self.btn_update = Button(
            text="🔄  Проверить обновления",
            font_size=dp(13),
            background_color=(0.18, 0.22, 0.28, 1),
            color=CLR_TEXT,
            size_hint_y=None, height=dp(44),
            disabled=True
        )
        self.btn_update.bind(on_press=self._on_update)
        self.add_widget(self.btn_update)

        request_android_permissions()
        # Небольшая задержка — даём Android время поднять сеть
        Clock.schedule_once(lambda dt: self._start_check(), 1.5)

    # ── Логика ─────────────────────────────────────────────────────────────

    def _set_status(self, text, color=None):
        self.lbl_status.text  = text
        self.lbl_status.color = color or CLR_TEXT

    def _set_attempt(self, text):
        self.lbl_attempt.text = text

    def _start_check(self):
        self._set_status("Проверяем версию на GitHub...", CLR_TEXT)
        threading.Thread(target=self._auto_check, daemon=True).start()

    def _auto_check(self):
        for attempt in range(1, MAX_RETRIES + 1):
            Clock.schedule_once(
                lambda dt, a=attempt: self._set_attempt(
                    f"Попытка {a} из {MAX_RETRIES}..."))
            remote_ver, err = fetch_remote_version()
            if remote_ver is not None:
                Clock.schedule_once(
                    lambda dt, v=remote_ver: self._after_check(v, None))
                return
            if attempt < MAX_RETRIES:
                import time
                time.sleep(3)

        Clock.schedule_once(lambda dt: self._after_check(None, err))

    def _after_check(self, remote_ver, err):
        self._set_attempt("")
        local_ver = get_local_version() or BUILTIN_VERSION
        has_app   = os.path.exists(LOCAL_APP)

        if remote_ver is None:
            if has_app:
                self._set_status(
                    f"Нет связи с GitHub.\nЗапускаем версию {local_ver}.",
                    CLR_YELLOW
                )
                self.btn_launch.disabled = False
            else:
                self._set_status(
                    f"Нет связи с GitHub.\n{err}\n\n"
                    f"Репозиторий должен быть PUBLIC.",
                    CLR_RED
                )
            self.btn_update.disabled = False
            return

        if not has_app or remote_ver != local_ver:
            self._set_status(
                f"Загружаем версию {remote_ver}...", CLR_ACCENT)
            threading.Thread(
                target=self._do_update, args=(remote_ver,), daemon=True
            ).start()
        else:
            self._set_status(f"Версия актуальна: {local_ver} ✔", CLR_GREEN)
            self.btn_launch.disabled = False
            self.btn_update.disabled = False

    def _do_update(self, remote_ver):
        Clock.schedule_once(
            lambda dt: self._set_attempt("Загружаем app.py..."))
        success, err = download_app()
        Clock.schedule_once(
            lambda dt: self._after_update(success, err, remote_ver))

    def _after_update(self, success, err, remote_ver):
        self._set_attempt("")
        if success:
            save_version(remote_ver)
            self.lbl_version.text = f"Версия: {remote_ver}"
            self._set_status(
                f"Обновлено до версии {remote_ver} ✔", CLR_GREEN)
        else:
            self._set_status(f"Ошибка загрузки:\n{err}", CLR_RED)
        self.btn_launch.disabled = not os.path.exists(LOCAL_APP)
        self.btn_update.disabled = False

    def _on_update(self, *_):
        self.btn_update.disabled = True
        self.btn_launch.disabled = True
        self._set_status("Подключаемся...", CLR_ACCENT)
        Clock.schedule_once(lambda dt: threading.Thread(
            target=self._auto_check, daemon=True).start(), 0.2)

    def _on_launch(self, *_):
        self._set_status("Запускаем...", CLR_ACCENT)
        Clock.schedule_once(lambda dt: self._do_launch(), 0.15)

    def _do_launch(self):
        ok, err = launch_app()
        if not ok:
            self._set_status(f"Ошибка запуска:\n{err}", CLR_RED)
            self.btn_launch.disabled = False


# ─── Приложение ───────────────────────────────────────────────────────────────

class LauncherApp(App):
    def build(self):
        Window.clearcolor = CLR_BG
        return LoaderScreen()


if __name__ == "__main__":
    LauncherApp().run()
