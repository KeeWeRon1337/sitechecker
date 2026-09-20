# -*- coding: utf-8 -*-
"""
main.py v2.0 — Загрузчик SiteChecker.
Кнопка "Проверка скорости" открывает SpeedTestScreen из app.py
(обновляется через OTA вместе с остальным приложением).
v2.1: все HTTPS-запросы идут с сертификатами certifi (и при редиректах),
убран небезопасный http-зеркальный источник и отключение проверки SSL,
в ошибке показываются причины по каждому источнику.
"""

import os
import ssl
import threading
import urllib.request
import urllib.error
import importlib.util
import sys
import certifi

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["SSL_CERT_DIR"] = os.path.dirname(certifi.where())

# ─── Конфиг ───────────────────────────────────────────────────────────────────
GITHUB_USER   = "KeeWeRon1337"
GITHUB_REPO   = "sitechecker"
GITHUB_BRANCH = "main"

def make_urls(filename):
    return [
        f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@{GITHUB_BRANCH}/{filename}",
        f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}",
    ]

APP_DIR   = os.path.dirname(os.path.abspath(__file__))
LOCAL_APP = os.path.join(APP_DIR, "app_downloaded.py")
LOCAL_VER = os.path.join(APP_DIR, "version_downloaded.txt")

BUILTIN_VERSION = "1.0"
TIMEOUT     = 20
MAX_RETRIES = 2

CLR_BG      = (0.07, 0.08, 0.10, 1)
CLR_ACCENT  = (0.22, 0.68, 0.87, 1)
CLR_TEXT    = (0.92, 0.93, 0.95, 1)
CLR_SUBTEXT = (0.55, 0.60, 0.67, 1)
CLR_GREEN   = (0.22, 0.78, 0.51, 1)
CLR_RED     = (0.93, 0.33, 0.36, 1)
CLR_YELLOW  = (0.98, 0.76, 0.18, 1)
CLR_BTN     = (0.22, 0.68, 0.87, 1)
CLR_SPEED   = (0.55, 0.35, 0.85, 1)


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


# ─── SSL ──────────────────────────────────────────────────────────────────────

def make_ssl_context():
    """SSL-контекст с сертификатами из certifi.

    Проверку сертификатов НЕ отключаем ни при каких условиях:
    приложение скачивает и выполняет код (app.py), и без проверки
    его можно подменить при перехвате трафика.
    """
    return ssl.create_default_context(cafile=certifi.where())


# ─── Сеть ─────────────────────────────────────────────────────────────────────

def _source_name(url):
    """Короткое имя источника для сообщений об ошибках."""
    try:
        return url.split("/")[2]
    except Exception:
        return url


def fetch_with_fallback(filename, on_progress=None):
    urls    = make_urls(filename)
    ssl_ctx = make_ssl_context()
    # HTTPSHandler с нашим контекстом используется для ВСЕХ запросов,
    # в том числе после редиректов на https.
    opener  = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_ctx))
    errors  = []

    for i, url in enumerate(urls):
        if on_progress:
            on_progress(f"Источник {i+1}/{len(urls)}...")
        last_err = "нет ответа"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "SiteChecker/2.1",
                                  "Connection": "close"})
                with opener.open(req, timeout=TIMEOUT) as r:
                    return r.read(), None
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                break
            except urllib.error.URLError as e:
                last_err = str(e.reason)
            except Exception as e:
                last_err = str(e)
            if attempt < MAX_RETRIES:
                import time; time.sleep(2)
        errors.append(f"{_source_name(url)}: {last_err}")

    return None, "\n".join(errors) if errors else "нет ответа"


def fetch_remote_version(on_progress=None):
    data, err = fetch_with_fallback("version.txt", on_progress)
    if data is not None:
        return data.decode("utf-8").strip(), None
    return None, err


def download_app(on_progress=None):
    data, err = fetch_with_fallback("app.py", on_progress)
    if data is None:
        return False, err
    try:
        with open(LOCAL_APP, "wb") as f:
            f.write(data)
        return True, ""
    except Exception as e:
        return False, str(e)


# ─── Версия ───────────────────────────────────────────────────────────────────

def get_local_version():
    try:
        if os.path.exists(LOCAL_VER):
            with open(LOCAL_VER, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None

def save_version(v):
    try:
        with open(LOCAL_VER, "w", encoding="utf-8") as f:
            f.write(v)
    except Exception:
        pass


# ─── Загрузка модулей ─────────────────────────────────────────────────────────

def load_module_from_file(path, module_key):
    """Универсальная загрузка любого скачанного .py файла как модуля."""
    if not os.path.exists(path):
        return None, "Файл не найден"
    try:
        spec = importlib.util.spec_from_file_location(module_key, path)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = mod
        spec.loader.exec_module(mod)
        return mod, ""
    except Exception as e:
        return None, str(e)


def load_app_module():
    return load_module_from_file(LOCAL_APP, "sitechecker_app")


# ─── Экран загрузчика ─────────────────────────────────────────────────────────

class LoaderScreen(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical",
                         padding=dp(30), spacing=dp(12), **kw)
        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        self.add_widget(Label(
            text="SiteChecker", font_size=dp(30), bold=True,
            color=CLR_ACCENT, size_hint_y=None, height=dp(46)))

        local_ver = get_local_version() or BUILTIN_VERSION
        self.lbl_version = Label(
            text=f"Версия: {local_ver}", font_size=dp(13),
            color=CLR_SUBTEXT, size_hint_y=None, height=dp(22))
        self.add_widget(self.lbl_version)

        self.lbl_status = Label(
            text="Инициализация...", font_size=dp(14), color=CLR_TEXT,
            halign="center", valign="middle",
            size_hint_y=None, height=dp(110))
        self.lbl_status.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self.add_widget(self.lbl_status)

        self.lbl_detail = Label(
            text="", font_size=dp(11), color=CLR_SUBTEXT,
            halign="center", size_hint_y=None, height=dp(30))
        self.lbl_detail.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self.add_widget(self.lbl_detail)

        self.add_widget(Label(size_hint_y=1))

        self.btn_launch = Button(
            text="Запустить приложение",
            font_size=dp(15), bold=True,
            background_normal="",
            background_color=CLR_BTN, color=(0.04, 0.04, 0.06, 1),
            size_hint_y=None, height=dp(54), disabled=True)
        self.btn_launch.bind(on_press=self._on_launch)
        self.add_widget(self.btn_launch)

        self.btn_speed = Button(
            text="Проверка скорости",
            font_size=dp(14), bold=True,
            background_normal="",
            background_color=CLR_SPEED, color=(0.97, 0.97, 0.99, 1),
            size_hint_y=None, height=dp(48))
        self.btn_speed.bind(on_press=self._on_speedtest)
        self.add_widget(self.btn_speed)

        self.btn_update = Button(
            text="Проверить обновления",
            font_size=dp(13),
            background_normal="",
            background_color=(0.18, 0.22, 0.28, 1), color=CLR_TEXT,
            size_hint_y=None, height=dp(44), disabled=True)
        self.btn_update.bind(on_press=self._on_update)
        self.add_widget(self.btn_update)

        request_android_permissions()
        Clock.schedule_once(lambda dt: self._start_check(), 2.0)

    # ── Общие утилиты статуса ────────────────────────────────────────────────

    def _set_status(self, text, color=None):
        self.lbl_status.text  = text
        self.lbl_status.color = color or CLR_TEXT

    def _set_detail(self, text):
        self.lbl_detail.text = text

    # ── Проверка версии app.py ────────────────────────────────────────────────

    def _start_check(self):
        self._set_status("Подключаемся к GitHub...", CLR_TEXT)
        threading.Thread(target=self._bg_check, daemon=True).start()

    def _bg_check(self):
        def prog(msg):
            Clock.schedule_once(lambda dt: self._set_detail(msg))
        remote_ver, err = fetch_remote_version(on_progress=prog)
        Clock.schedule_once(lambda dt: self._after_check(remote_ver, err))

    def _after_check(self, remote_ver, err):
        self._set_detail("")
        local_ver = get_local_version() or BUILTIN_VERSION
        has_app   = os.path.exists(LOCAL_APP)

        if remote_ver is None:
            if has_app:
                self._set_status(
                    f"Нет связи.\nЗапускаем версию {local_ver}.", CLR_YELLOW)
                self.btn_launch.disabled = False
            else:
                self._set_status(
                    f"Не удалось подключиться:\n{err}", CLR_RED)
            self.btn_update.disabled = False
            return

        if not has_app or remote_ver != local_ver:
            self._set_status(f"Загружаем версию {remote_ver}...", CLR_ACCENT)
            threading.Thread(
                target=self._bg_update, args=(remote_ver,), daemon=True
            ).start()
        else:
            self._set_status(f"Версия актуальна: {local_ver}", CLR_GREEN)
            self.btn_launch.disabled = False
            self.btn_update.disabled = False

    def _bg_update(self, remote_ver):
        def prog(msg):
            Clock.schedule_once(lambda dt: self._set_detail(msg))
        success, err = download_app(on_progress=prog)
        Clock.schedule_once(
            lambda dt: self._after_update(success, err, remote_ver))

    def _after_update(self, success, err, remote_ver):
        self._set_detail("")
        if success:
            save_version(remote_ver)
            self.lbl_version.text = f"Версия: {remote_ver}"
            self._set_status(f"Обновлено до {remote_ver}", CLR_GREEN)
        else:
            self._set_status(f"Ошибка загрузки:\n{err}", CLR_RED)
        self.btn_launch.disabled = not os.path.exists(LOCAL_APP)
        self.btn_update.disabled = False

    def _on_update(self, *_):
        self.btn_update.disabled = True
        self.btn_launch.disabled = True
        self._set_status("Подключаемся...", CLR_ACCENT)
        Clock.schedule_once(
            lambda dt: threading.Thread(
                target=self._bg_check, daemon=True).start(), 0.2)

    def _on_launch(self, *_):
        self.btn_launch.disabled = True
        self.btn_update.disabled = True
        self._set_status("Загружаем модуль...", CLR_ACCENT)
        Clock.schedule_once(lambda dt: self._do_launch(), 0.2)

    def _do_launch(self):
        mod, err = load_app_module()
        if mod is None:
            self._set_status(f"Ошибка загрузки модуля:\n{err}", CLR_RED)
            self.btn_launch.disabled = False
            self.btn_update.disabled = False
            return
        try:
            app    = App.get_running_app()
            screen = mod.MainScreen()
            root   = app.root
            root.clear_widgets()
            root.add_widget(screen)
        except Exception as e:
            self._set_status(f"Ошибка запуска экрана:\n{e}", CLR_RED)
            self.btn_launch.disabled = False
            self.btn_update.disabled = False

    # ── Проверка скорости ──────────────────────────────────────────────────

    def _on_speedtest(self, *_):
        self.btn_speed.disabled  = True
        self.btn_launch.disabled = True
        self.btn_update.disabled = True
        self._set_status("Открываем проверку скорости...", CLR_SPEED)
        if os.path.exists(LOCAL_APP):
            Clock.schedule_once(lambda dt: self._open_speedtest(), 0.1)
        else:
            # app.py ещё не скачан (например, первый запуск без сети) —
            # скачиваем его, экран спидтеста находится в нём.
            threading.Thread(target=self._bg_load_speedtest, daemon=True).start()

    def _bg_load_speedtest(self):
        def prog(msg):
            Clock.schedule_once(lambda dt: self._set_detail(msg))
        success, err = download_app(on_progress=prog)
        Clock.schedule_once(lambda dt: self._after_speedtest_download(success, err))

    def _after_speedtest_download(self, success, err):
        self._set_detail("")
        if not success:
            self._set_status(f"Не удалось загрузить модуль:\n{err}", CLR_RED)
            self._restore_buttons()
            return
        self._open_speedtest()

    def _open_speedtest(self):
        mod, load_err = load_app_module()
        if mod is None:
            self._set_status(f"Ошибка запуска модуля:\n{load_err}", CLR_RED)
            self._restore_buttons()
            return
        if not hasattr(mod, "SpeedTestScreen"):
            self._set_status(
                "В текущей версии app.py нет проверки скорости.\n"
                "Нажмите «Проверить обновления».", CLR_YELLOW)
            self._restore_buttons()
            return

        try:
            try:
                screen = mod.SpeedTestScreen(on_back=self._return_to_loader)
            except TypeError:
                # старая версия app.py без параметра on_back
                screen = mod.SpeedTestScreen()
            app  = App.get_running_app()
            root = app.root
            root.clear_widgets()
            root.add_widget(screen)
        except Exception as e:
            self._set_status(f"Ошибка экрана скорости:\n{e}", CLR_RED)
            self._restore_buttons()

    def _return_to_loader(self):
        """Callback для возврата из экрана скорости обратно сюда."""
        app  = App.get_running_app()
        root = app.root
        root.clear_widgets()
        new_screen = LoaderScreen()
        root.add_widget(new_screen)

    def _restore_buttons(self):
        self.btn_speed.disabled  = False
        self.btn_launch.disabled = not os.path.exists(LOCAL_APP)
        self.btn_update.disabled = False


# ─── Приложение ───────────────────────────────────────────────────────────────

class LauncherApp(App):
    def build(self):
        Window.clearcolor = CLR_BG
        root = BoxLayout()
        root.add_widget(LoaderScreen())
        return root


if __name__ == "__main__":
    LauncherApp().run()