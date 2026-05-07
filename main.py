# -*- coding: utf-8 -*-
"""
main.py v1.1 — Загрузчик SiteChecker.
Исправлено: версия, диагностика сети, запрос разрешений Android.
"""

import os
import sys
import threading
import urllib.request
import urllib.error

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

# ─── Конфиг — ИЗМЕНИТЕ НА СВОИ ДАННЫЕ ────────────────────────────────────────
GITHUB_USER   = "KeeWeRon1337"   # ваш GitHub username
GITHUB_REPO   = "sitechecker"    # название репозитория (должен быть PUBLIC)
GITHUB_BRANCH = "main"

RAW_BASE    = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
VERSION_URL = f"{RAW_BASE}/version.txt"
APP_URL     = f"{RAW_BASE}/app.py"

# Папка для записи файлов
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
LOCAL_APP = os.path.join(APP_DIR, "app_downloaded.py")
LOCAL_VER = os.path.join(APP_DIR, "version_downloaded.txt")

BUILTIN_VERSION = "1.0"

# Цвета
CLR_BG      = (0.07, 0.08, 0.10, 1)
CLR_ACCENT  = (0.22, 0.68, 0.87, 1)
CLR_TEXT    = (0.92, 0.93, 0.95, 1)
CLR_SUBTEXT = (0.55, 0.60, 0.67, 1)
CLR_GREEN   = (0.22, 0.78, 0.51, 1)
CLR_RED     = (0.93, 0.33, 0.36, 1)
CLR_YELLOW  = (0.98, 0.76, 0.18, 1)
CLR_BTN     = (0.22, 0.68, 0.87, 1)


# ─── Android: запрос разрешений ───────────────────────────────────────────────

def request_android_permissions():
    """Запрашивает разрешения INTERNET и ACCESS_NETWORK_STATE на Android."""
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.INTERNET,
            Permission.ACCESS_NETWORK_STATE,
        ])
    except ImportError:
        pass  # не Android — пропускаем


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def get_local_version():
    """Версия скачанного app.py."""
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


def fetch_remote_version():
    """Скачивает version.txt. Возвращает (version_str | None, error_str)."""
    try:
        req = urllib.request.Request(
            VERSION_URL,
            headers={"User-Agent": "SiteChecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode().strip(), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"URL ошибка: {e.reason}"
    except Exception as e:
        return None, str(e)


def download_app():
    """Скачивает app.py. Возвращает (success, error_str)."""
    try:
        req = urllib.request.Request(
            APP_URL,
            headers={"User-Agent": "SiteChecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.read()
        with open(LOCAL_APP, "wb") as f:
            f.write(code)
        return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


def launch_app():
    """Запускает app_downloaded.py через exec."""
    if not os.path.exists(LOCAL_APP):
        return False, "Файл не найден"
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

        # Заголовок
        self.add_widget(Label(
            text="SiteChecker", font_size=dp(30), bold=True,
            color=CLR_ACCENT, size_hint_y=None, height=dp(48)
        ))

        # Версия — показываем скачанную, если есть
        local_ver = get_local_version() or BUILTIN_VERSION
        self.lbl_version = Label(
            text=f"Версия: {local_ver}",
            font_size=dp(13), color=CLR_SUBTEXT,
            size_hint_y=None, height=dp(24)
        )
        self.add_widget(self.lbl_version)

        # Диагностическая строка (URL для проверки)
        self.lbl_url = Label(
            text=f"Источник: github.com/{GITHUB_USER}/{GITHUB_REPO}",
            font_size=dp(11), color=CLR_SUBTEXT,
            size_hint_y=None, height=dp(20)
        )
        self.add_widget(self.lbl_url)

        # Статус
        self.lbl_status = Label(
            text="Проверка обновлений...",
            font_size=dp(14), color=CLR_TEXT,
            halign="center", valign="middle",
            size_hint_y=None, height=dp(52)
        )
        self.lbl_status.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self.add_widget(self.lbl_status)

        self.add_widget(Label(size_hint_y=1))  # спейсер

        # Кнопка запуска
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

        # Кнопка обновления
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

        # Запрашиваем разрешения и стартуем проверку
        request_android_permissions()
        threading.Thread(target=self._auto_check, daemon=True).start()

    # ── Логика ─────────────────────────────────────────────────────────────

    def _set_status(self, text, color=None):
        self.lbl_status.text  = text
        self.lbl_status.color = color or CLR_TEXT

    def _auto_check(self):
        remote_ver, err = fetch_remote_version()
        Clock.schedule_once(lambda dt: self._after_check(remote_ver, err))

    def _after_check(self, remote_ver, err):
        local_ver  = get_local_version() or BUILTIN_VERSION
        has_app    = os.path.exists(LOCAL_APP)

        if remote_ver is None:
            # Нет доступа к GitHub
            detail = err or "неизвестная ошибка"
            if has_app:
                self._set_status(
                    f"Нет связи с GitHub ({detail}).\n"
                    f"Запускаем сохранённую версию {local_ver}.",
                    CLR_YELLOW
                )
                self.btn_launch.disabled  = False
                self.btn_update.disabled  = False
            else:
                self._set_status(
                    f"Нет связи с GitHub.\nОшибка: {detail}\n\n"
                    f"Убедитесь что репозиторий PUBLIC\n"
                    f"и есть файл app.py в ветке {GITHUB_BRANCH}.",
                    CLR_RED
                )
                self.btn_update.disabled = False
            return

        # Есть связь
        if not has_app or remote_ver != local_ver:
            self._set_status(
                f"Доступна версия {remote_ver}. Скачиваем...",
                CLR_ACCENT
            )
            threading.Thread(
                target=self._do_update, args=(remote_ver,), daemon=True
            ).start()
        else:
            self._set_status(f"Версия актуальна ({local_ver}) ✔", CLR_GREEN)
            self.btn_launch.disabled = False
            self.btn_update.disabled = False

    def _do_update(self, remote_ver):
        success, err = download_app()
        Clock.schedule_once(
            lambda dt: self._after_update(success, err, remote_ver))

    def _after_update(self, success, err, remote_ver):
        if success:
            save_version(remote_ver)
            self.lbl_version.text = f"Версия: {remote_ver}"
            self._set_status(f"Обновлено до версии {remote_ver} ✔", CLR_GREEN)
        else:
            self._set_status(f"Ошибка загрузки:\n{err}", CLR_RED)
        self.btn_launch.disabled = not os.path.exists(LOCAL_APP)
        self.btn_update.disabled = False

    def _on_update(self, *_):
        self.btn_update.disabled = True
        self.btn_launch.disabled = True
        self._set_status("Загружаем обновление...", CLR_ACCENT)
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _fetch_and_update(self):
        remote_ver, err = fetch_remote_version()
        if remote_ver is None:
            Clock.schedule_once(lambda dt: (
                self._set_status(f"Нет связи:\n{err}", CLR_RED),
                setattr(self.btn_update, "disabled", False),
                setattr(self.btn_launch, "disabled",
                        not os.path.exists(LOCAL_APP))
            ))
            return
        Clock.schedule_once(
            lambda dt: self._do_update_ui(remote_ver))

    def _do_update_ui(self, remote_ver):
        threading.Thread(
            target=self._do_update, args=(remote_ver,), daemon=True
        ).start()

    def _on_launch(self, *_):
        self._set_status("Запускаем...", CLR_ACCENT)
        Clock.schedule_once(lambda dt: self._do_launch(), 0.1)

    def _do_launch(self):
        ok, err = launch_app()
        if not ok:
            self._set_status(f"Ошибка запуска:\n{err}", CLR_RED)


# ─── Приложение ───────────────────────────────────────────────────────────────

class LauncherApp(App):
    def build(self):
        Window.clearcolor = CLR_BG
        return LoaderScreen()


if __name__ == "__main__":
    LauncherApp().run()
