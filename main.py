# -*- coding: utf-8 -*-
"""
main.py — Загрузчик (Launcher).
Этот файл входит в APK и никогда не меняется.
Вся логика приложения живёт в app.py, который обновляется с GitHub.
"""

import os
import sys
import threading
import urllib.request

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

# ─── Конфиг ───────────────────────────────────────────────────────────────────

# Ваш GitHub: поменяйте на свой username и repo
GITHUB_USER = "KeeWeRon1337"
GITHUB_REPO = "sitechecker"
GITHUB_BRANCH = "main"

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
VERSION_URL = f"{RAW_BASE}/version.txt"
APP_URL     = f"{RAW_BASE}/app.py"

# Папка данных приложения — сюда можно писать на Android
APP_DIR     = os.path.dirname(os.path.abspath(__file__))
LOCAL_APP   = os.path.join(APP_DIR, "app_downloaded.py")
LOCAL_VER   = os.path.join(APP_DIR, "version_downloaded.txt")

# Встроенная версия (версия загрузчика)
BUILTIN_VERSION = "1.0"

# Цвета
CLR_BG     = (0.07, 0.08, 0.10, 1)
CLR_ACCENT = (0.22, 0.68, 0.87, 1)
CLR_TEXT   = (0.92, 0.93, 0.95, 1)
CLR_SUBTEXT= (0.55, 0.60, 0.67, 1)
CLR_GREEN  = (0.22, 0.78, 0.51, 1)
CLR_RED    = (0.93, 0.33, 0.36, 1)
CLR_BTN    = (0.22, 0.68, 0.87, 1)


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def get_local_version():
    """Возвращает версию скачанного app.py (или None если не скачан)."""
    if os.path.exists(LOCAL_VER):
        try:
            with open(LOCAL_VER, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    return None


def fetch_remote_version():
    """Скачивает version.txt с GitHub. Возвращает строку или None."""
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=8) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def download_app():
    """Скачивает app.py с GitHub. Возвращает (success: bool, error: str)."""
    try:
        with urllib.request.urlopen(APP_URL, timeout=15) as r:
            code = r.read()
        with open(LOCAL_APP, "wb") as f:
            f.write(code)
        return True, ""
    except Exception as e:
        return False, str(e)


def save_version(version):
    try:
        with open(LOCAL_VER, "w") as f:
            f.write(version)
    except Exception:
        pass


def launch_app():
    """Запускает скачанный app.py если он есть, иначе встроенный."""
    if os.path.exists(LOCAL_APP):
        ns = {"__file__": LOCAL_APP, "__name__": "__main__"}
        try:
            with open(LOCAL_APP, "r", encoding="utf-8") as f:
                code = f.read()
            exec(compile(code, LOCAL_APP, "exec"), ns)
            return True
        except Exception as e:
            print(f"[Loader] Ошибка запуска app_downloaded.py: {e}")
    return False


# ─── Экран загрузчика ─────────────────────────────────────────────────────────

class LoaderScreen(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical",
                         padding=dp(30), spacing=dp(16), **kw)
        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        # Заголовок
        self.add_widget(Label(
            text="SiteChecker", font_size=dp(28), bold=True,
            color=CLR_ACCENT, size_hint_y=None, height=dp(44)
        ))

        # Версия
        local_ver = get_local_version() or BUILTIN_VERSION
        self.lbl_version = Label(
            text=f"Версия: {local_ver}",
            font_size=dp(13), color=CLR_SUBTEXT,
            size_hint_y=None, height=dp(24)
        )
        self.add_widget(self.lbl_version)

        # Статус
        self.lbl_status = Label(
            text="Проверка обновлений...",
            font_size=dp(14), color=CLR_TEXT,
            size_hint_y=None, height=dp(32)
        )
        self.add_widget(self.lbl_status)

        # Спейсер
        self.add_widget(Label(size_hint_y=1))

        # Кнопка запуска
        self.btn_launch = Button(
            text="Запустить приложение",
            font_size=dp(15), bold=True,
            background_color=CLR_BTN,
            color=(0.04, 0.04, 0.06, 1),
            size_hint_y=None, height=dp(54),
            disabled=True
        )
        self.btn_launch.bind(on_press=self._on_launch)
        self.add_widget(self.btn_launch)

        # Кнопка обновления
        self.btn_update = Button(
            text="Обновить с GitHub",
            font_size=dp(13),
            background_color=(0.18, 0.22, 0.28, 1),
            color=CLR_TEXT,
            size_hint_y=None, height=dp(44),
            disabled=True
        )
        self.btn_update.bind(on_press=self._on_update)
        self.add_widget(self.btn_update)

        # Автопроверка при старте
        threading.Thread(target=self._auto_check, daemon=True).start()

    # ── Логика ─────────────────────────────────────────────────────────────

    def _auto_check(self):
        """Фоновая проверка обновлений при старте."""
        remote_ver = fetch_remote_version()
        Clock.schedule_once(lambda dt: self._after_check(remote_ver))

    def _after_check(self, remote_ver):
        local_ver = get_local_version() or BUILTIN_VERSION
        has_app = os.path.exists(LOCAL_APP)

        if remote_ver is None:
            # Нет интернета
            if has_app:
                self.lbl_status.text = "Нет сети. Запускаем сохранённую версию."
                self.lbl_status.color = CLR_TEXT
            else:
                self.lbl_status.text = "Нет сети и нет сохранённой версии.\nПодключитесь к интернету для первого запуска."
                self.lbl_status.color = CLR_RED
            self.btn_launch.disabled = not has_app
            self.btn_update.disabled = True
            return

        # Есть интернет
        if not has_app or remote_ver != local_ver:
            # Нужно скачать
            self.lbl_status.text = f"Доступна версия {remote_ver}. Скачиваем..."
            self.lbl_status.color = CLR_ACCENT
            threading.Thread(target=self._do_update,
                             args=(remote_ver,), daemon=True).start()
        else:
            self.lbl_status.text = f"Версия актуальна ({local_ver})"
            self.lbl_status.color = CLR_GREEN
            self.btn_launch.disabled = False
            self.btn_update.disabled = False

    def _do_update(self, remote_ver):
        success, err = download_app()
        Clock.schedule_once(lambda dt: self._after_update(success, err, remote_ver))

    def _after_update(self, success, err, remote_ver):
        if success:
            save_version(remote_ver)
            self.lbl_version.text = f"Версия: {remote_ver}"
            self.lbl_status.text = f"Обновлено до версии {remote_ver}!"
            self.lbl_status.color = CLR_GREEN
        else:
            self.lbl_status.text = f"Ошибка загрузки: {err}"
            self.lbl_status.color = CLR_RED
        self.btn_launch.disabled = not os.path.exists(LOCAL_APP)
        self.btn_update.disabled = False

    def _on_update(self, *_):
        self.btn_update.disabled = True
        self.btn_launch.disabled = True
        self.lbl_status.text = "Загружаем обновление..."
        self.lbl_status.color = CLR_ACCENT
        remote_ver = fetch_remote_version() or "unknown"
        threading.Thread(target=self._do_update,
                         args=(remote_ver,), daemon=True).start()

    def _on_launch(self, *_):
        self.lbl_status.text = "Запускаем..."
        App.get_running_app().load_main_app()


# ─── Приложение-загрузчик ────────────────────────────────────────────────────

class LauncherApp(App):
    def build(self):
        Window.clearcolor = CLR_BG
        self.screen = LoaderScreen()
        return self.screen

    def load_main_app(self):
        """Запускает скачанный app.py поверх загрузчика."""
        if not launch_app():
            self.screen.lbl_status.text = "Ошибка запуска. Попробуйте обновить."
            self.screen.lbl_status.color = CLR_RED


if __name__ == "__main__":
    LauncherApp().run()
