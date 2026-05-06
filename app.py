# -*- coding: utf-8 -*-
"""
app.py v1.1 — Основной код SiteChecker.
Обновления: русский язык, папки, удаление сайтов, задержка в мс.
"""

import socket
import subprocess
import platform
import threading
import time
import json
import os

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

PING_TIMEOUT   = 3
SOCKET_TIMEOUT = 3

# Файл хранения данных (папки и сайты)
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
    """Возвращает задержку TCP в мс или None."""
    try:
        t0 = time.monotonic()
        with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT):
            pass
        return int((time.monotonic() - t0) * 1000)
    except Exception:
        return None


def measure_ping_ms(host):
    """Возвращает задержку ping в мс или None."""
    s = platform.system().lower()
    if s == "windows":
        cmd = ["ping", "-n", "1", "-w", str(PING_TIMEOUT * 1000), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(PING_TIMEOUT), host]
    try:
        t0 = time.monotonic()
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=PING_TIMEOUT + 2)
        elapsed = int((time.monotonic() - t0) * 1000)
        return elapsed if r.returncode == 0 else None
    except Exception:
        return None


def check_dns(host):
    try:
        return True, socket.gethostbyname(host)
    except socket.gaierror:
        return False, None


def check_site(host):
    """Возвращает (sent: bool, returned: bool, latency_ms: int|None)."""
    sent, _ = check_dns(host)
    if not sent:
        return False, False, None
    # Сначала ping, потом TCP как fallback
    ms = measure_ping_ms(host)
    if ms is not None:
        return True, True, ms
    ms = measure_tcp_ms(host)
    if ms is not None:
        return True, True, ms
    return True, False, None


# ─── Вспомогательные виджеты ─────────────────────────────────────────────────

def make_popup(title, content_widget, size=(dp(320), dp(200))):
    """Создаёт простой Popup с тёмным фоном."""
    popup = Popup(
        title=title,
        content=content_widget,
        size_hint=(None, None),
        size=size,
        background_color=(0.10, 0.12, 0.16, 1),
        title_color=CLR_TEXT,
        separator_color=CLR_ACCENT,
    )
    return popup


# ─── Строка сайта ─────────────────────────────────────────────────────────────

class SiteRow(BoxLayout):
    def __init__(self, host, on_delete, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(52), padding=[dp(10), dp(6)],
                         spacing=dp(6), **kw)
        self.host = host
        self.on_delete = on_delete

        with self.canvas.before:
            Color(*CLR_CARD)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(8)])
        self.bind(pos=self._u, size=self._u)

        # Название сайта
        self.lbl_host = Label(
            text=host, font_size=dp(13), color=CLR_TEXT,
            halign="left", valign="middle", size_hint=(0.32, 1)
        )
        self.lbl_host.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        # Отправлен
        self.lbl_sent = Label(
            text="—", font_size=dp(12), color=CLR_SUBTEXT,
            halign="center", valign="middle", size_hint=(0.20, 1)
        )

        # Вернулся
        self.lbl_recv = Label(
            text="—", font_size=dp(12), color=CLR_SUBTEXT,
            halign="center", valign="middle", size_hint=(0.20, 1)
        )

        # Задержка
        self.lbl_ms = Label(
            text="—", font_size=dp(12), color=CLR_SUBTEXT,
            halign="center", valign="middle", size_hint=(0.18, 1)
        )

        # Кнопка удаления
        btn_del = Button(
            text="✕", font_size=dp(14),
            background_color=CLR_DEL,
            color=CLR_TEXT,
            size_hint=(None, None),
            size=(dp(34), dp(34))
        )
        btn_del.bind(on_press=lambda _: self.on_delete(self.host))

        for w in (self.lbl_host, self.lbl_sent, self.lbl_recv,
                  self.lbl_ms, btn_del):
            self.add_widget(w)

    def _u(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_checking(self):
        for lbl in (self.lbl_sent, self.lbl_recv, self.lbl_ms):
            lbl.text = "..."
            lbl.color = CLR_SUBTEXT

    def set_result(self, sent, returned, ms):
        self.lbl_sent.text  = "Да"  if sent     else "Нет"
        self.lbl_sent.color = CLR_GREEN if sent     else CLR_RED
        self.lbl_recv.text  = "Да"  if returned  else "Нет"
        self.lbl_recv.color = CLR_GREEN if returned  else CLR_RED

        if ms is not None:
            self.lbl_ms.text = f"{ms} мс"
            if ms < 100:
                self.lbl_ms.color = CLR_GREEN
            elif ms < 300:
                self.lbl_ms.color = CLR_YELLOW
            else:
                self.lbl_ms.color = CLR_RED
        else:
            self.lbl_ms.text  = "—"
            self.lbl_ms.color = CLR_SUBTEXT


# ─── Блок папки ───────────────────────────────────────────────────────────────

class FolderBlock(BoxLayout):
    def __init__(self, folder_name, sites, on_site_delete,
                 on_folder_delete, on_data_change, **kw):
        super().__init__(orientation="vertical", size_hint_y=None,
                         spacing=dp(4), **kw)
        self.folder_name   = folder_name
        self.on_site_delete  = on_site_delete
        self.on_folder_delete = on_folder_delete
        self.on_data_change  = on_data_change
        self._rows = {}
        self._collapsed = False

        self.bind(minimum_height=self.setter("height"))
        self._build_header()
        self._build_sites(sites)
        self._build_add_row()
        self._update_height()

    # ── Шапка папки ────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(42), spacing=dp(6),
                        padding=[dp(10), dp(4)])
        with hdr.canvas.before:
            Color(*CLR_FOLDER)
            self._hdr_rect = RoundedRectangle(pos=hdr.pos, size=hdr.size,
                                              radius=[dp(8)])
        hdr.bind(pos=lambda *_: setattr(self._hdr_rect, "pos", hdr.pos),
                 size=lambda *_: setattr(self._hdr_rect, "size", hdr.size))

        # Кнопка свернуть/развернуть
        self.btn_toggle = Button(
            text="▼", font_size=dp(14),
            background_color=(0, 0, 0, 0),
            color=CLR_ACCENT,
            size_hint=(None, 1), width=dp(28)
        )
        self.btn_toggle.bind(on_press=self._toggle)

        # Название папки
        lbl = Label(text=f"📁  {self.folder_name}", font_size=dp(15),
                    bold=True, color=CLR_TEXT, halign="left",
                    valign="middle", size_hint=(1, 1))
        lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        # Кнопка удалить папку
        btn_del = Button(
            text="🗑", font_size=dp(15),
            background_color=(0, 0, 0, 0),
            color=CLR_RED,
            size_hint=(None, 1), width=dp(34)
        )
        btn_del.bind(on_press=lambda _: self.on_folder_delete(self.folder_name))

        hdr.add_widget(self.btn_toggle)
        hdr.add_widget(lbl)
        hdr.add_widget(btn_del)
        self.add_widget(hdr)
        self._hdr = hdr

    # ── Сайты ──────────────────────────────────────────────────────────────

    def _build_sites(self, sites):
        self._sites_box = BoxLayout(orientation="vertical",
                                    size_hint_y=None, spacing=dp(4))
        self._sites_box.bind(minimum_height=self._sites_box.setter("height"))
        for s in sites:
            self._add_row(s)
        self.add_widget(self._sites_box)

    def _build_add_row(self):
        self._add_row_box = BoxLayout(orientation="horizontal",
                                      size_hint_y=None, height=dp(40),
                                      spacing=dp(6))
        self._txt = TextInput(
            hint_text="Добавить сайт...", font_size=dp(13),
            multiline=False,
            background_color=CLR_INPUT_BG,
            foreground_color=CLR_TEXT,
            hint_text_color=CLR_SUBTEXT,
            cursor_color=CLR_ACCENT,
            padding=[dp(10), dp(10)],
            size_hint=(1, 1)
        )
        self._txt.bind(on_text_validate=self._on_add)
        btn = Button(
            text="＋", font_size=dp(16),
            background_color=CLR_ACCENT,
            color=(0.04, 0.04, 0.06, 1),
            size_hint=(None, 1), width=dp(40)
        )
        btn.bind(on_press=self._on_add)
        self._add_row_box.add_widget(self._txt)
        self._add_row_box.add_widget(btn)
        self.add_widget(self._add_row_box)

    # ── Логика ─────────────────────────────────────────────────────────────

    def _add_row(self, host):
        if host in self._rows:
            return
        row = SiteRow(host, on_delete=self._on_delete_site)
        self._rows[host] = row
        self._sites_box.add_widget(row)
        self._update_height()

    def _on_add(self, *_):
        host = self._txt.text.strip().lower()
        for p in ("https://", "http://", "www."):
            if host.startswith(p):
                host = host[len(p):]
        host = host.rstrip("/")
        if host and host not in self._rows:
            self._add_row(host)
            self._txt.text = ""
            self.on_data_change()

    def _on_delete_site(self, host):
        if host in self._rows:
            self._sites_box.remove_widget(self._rows.pop(host))
            self._update_height()
            self.on_data_change()

    def _toggle(self, *_):
        self._collapsed = not self._collapsed
        self._sites_box.opacity  = 0 if self._collapsed else 1
        self._add_row_box.opacity = 0 if self._collapsed else 1
        self._sites_box.height   = 0 if self._collapsed else self._sites_box.minimum_height
        self._add_row_box.height = 0 if self._collapsed else dp(40)
        self.btn_toggle.text = "▶" if self._collapsed else "▼"
        self._update_height()

    def _update_height(self):
        h = dp(42) + dp(4)  # шапка
        if not self._collapsed:
            h += self._sites_box.minimum_height + dp(40) + dp(8)
        self.height = h

    def get_sites(self):
        return list(self._rows.keys())

    def check_all(self):
        for row in self._rows.values():
            row.set_checking()
        return list(self._rows.items())

    def apply_results(self, results):
        for host, (sent, returned, ms) in results.items():
            if host in self._rows:
                self._rows[host].set_result(sent, returned, ms)


# ─── Главный экран ────────────────────────────────────────────────────────────

class MainScreen(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical",
                         padding=dp(10), spacing=dp(8), **kw)
        with self.canvas.before:
            Color(*CLR_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        self._data = load_data()
        self._folder_blocks = {}

        self._build_header()
        self._build_table_header()
        self._build_scroll()
        self._build_footer()
        self._populate_folders()

    # ── Шапка ──────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(52), spacing=dp(8))

        title = BoxLayout(orientation="vertical", size_hint=(1, 1))
        title.add_widget(Label(text="SiteChecker", font_size=dp(20),
                               bold=True, color=CLR_ACCENT,
                               halign="left", valign="bottom",
                               size_hint_y=None, height=dp(30)))
        title.add_widget(Label(text="Проверка доступности сайтов",
                               font_size=dp(11), color=CLR_SUBTEXT,
                               halign="left", valign="top",
                               size_hint_y=None, height=dp(18)))
        for lbl in title.children:
            lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        btn_new_folder = Button(
            text="＋ Папка", font_size=dp(13),
            background_color=CLR_ACCENT,
            color=(0.04, 0.04, 0.06, 1),
            size_hint=(None, 1), width=dp(90)
        )
        btn_new_folder.bind(on_press=self._popup_new_folder)

        hdr.add_widget(title)
        hdr.add_widget(btn_new_folder)
        self.add_widget(hdr)

    # ── Шапка таблицы ──────────────────────────────────────────────────────

    def _build_table_header(self):
        th = BoxLayout(orientation="horizontal", size_hint_y=None,
                       height=dp(24), padding=[dp(10), 0], spacing=dp(6))
        cols = [("Сайт", 0.32), ("Отправлен", 0.20),
                ("Вернулся", 0.20), ("Задержка", 0.18), ("", 0.10)]
        for text, hint in cols:
            th.add_widget(Label(
                text=text, font_size=dp(10), color=CLR_SUBTEXT,
                halign="center", valign="middle", size_hint=(hint, 1)
            ))
        self.add_widget(th)

    # ── Прокручиваемый список ──────────────────────────────────────────────

    def _build_scroll(self):
        self.scroll = ScrollView(size_hint=(1, 1))
        self.content = GridLayout(cols=1, spacing=dp(8),
                                  size_hint_y=None, padding=[0, dp(4)])
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.add_widget(self.scroll)

    # ── Нижняя панель ──────────────────────────────────────────────────────

    def _build_footer(self):
        self.btn_check = Button(
            text="🔍  Проверить все", font_size=dp(15), bold=True,
            background_color=CLR_BTN,
            color=(0.04, 0.04, 0.06, 1),
            size_hint_y=None, height=dp(52)
        )
        self.btn_check.bind(on_press=self._check_all)
        self.add_widget(self.btn_check)

    # ── Папки ──────────────────────────────────────────────────────────────

    def _populate_folders(self):
        for folder in self._data["folders"]:
            self._add_folder_block(folder["name"], folder["sites"])

    def _add_folder_block(self, name, sites):
        block = FolderBlock(
            folder_name=name,
            sites=sites,
            on_site_delete=lambda host, n=name: self._on_site_deleted(n, host),
            on_folder_delete=self._on_folder_delete,
            on_data_change=self._save
        )
        self._folder_blocks[name] = block
        self.content.add_widget(block)

    def _on_site_deleted(self, folder_name, host):
        self._save()

    def _on_folder_delete(self, folder_name):
        """Подтверждение удаления папки."""
        box = BoxLayout(orientation="vertical", spacing=dp(12),
                        padding=dp(14))
        box.add_widget(Label(
            text=f'Удалить папку\n"{folder_name}"\nи все её сайты?',
            font_size=dp(14), color=CLR_TEXT,
            halign="center", valign="middle"
        ))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))

        popup = make_popup("Подтверждение", box, size=(dp(300), dp(200)))

        btn_yes = Button(text="Удалить", background_color=CLR_RED,
                         color=CLR_TEXT, font_size=dp(14))
        btn_no  = Button(text="Отмена",
                         background_color=(0.2, 0.2, 0.25, 1),
                         color=CLR_TEXT, font_size=dp(14))

        def do_delete(_):
            popup.dismiss()
            if folder_name in self._folder_blocks:
                self.content.remove_widget(self._folder_blocks.pop(folder_name))
                self._save()

        btn_yes.bind(on_press=do_delete)
        btn_no.bind(on_press=lambda _: popup.dismiss())
        btns.add_widget(btn_yes)
        btns.add_widget(btn_no)
        box.add_widget(btns)
        popup.open()

    def _popup_new_folder(self, *_):
        """Диалог создания новой папки."""
        box = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
        box.add_widget(Label(text="Название папки:", font_size=dp(14),
                             color=CLR_TEXT, size_hint_y=None, height=dp(28)))
        txt = TextInput(
            hint_text="Например: Работа",
            font_size=dp(14), multiline=False,
            background_color=CLR_INPUT_BG,
            foreground_color=CLR_TEXT,
            hint_text_color=CLR_SUBTEXT,
            cursor_color=CLR_ACCENT,
            padding=[dp(10), dp(10)],
            size_hint_y=None, height=dp(42)
        )
        popup = make_popup("Новая папка", box, size=(dp(300), dp(180)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        btn_ok  = Button(text="Создать", background_color=CLR_ACCENT,
                         color=(0.04, 0.04, 0.06, 1), font_size=dp(14))
        btn_no  = Button(text="Отмена",
                         background_color=(0.2, 0.2, 0.25, 1),
                         color=CLR_TEXT, font_size=dp(14))

        def do_create(_):
            name = txt.text.strip()
            if name and name not in self._folder_blocks:
                self._add_folder_block(name, [])
                self._save()
            popup.dismiss()

        txt.bind(on_text_validate=do_create)
        btn_ok.bind(on_press=do_create)
        btn_no.bind(on_press=lambda _: popup.dismiss())
        btn_row.add_widget(btn_ok)
        btn_row.add_widget(btn_no)
        box.add_widget(txt)
        box.add_widget(btn_row)
        popup.open()
        txt.focus = True

    # ── Проверка ───────────────────────────────────────────────────────────

    def _check_all(self, *_):
        all_items = []
        for block in self._folder_blocks.values():
            all_items.extend(block.check_all())
        if not all_items:
            return
        self.btn_check.text = "⏳  Проверяем..."
        self.btn_check.disabled = True
        threading.Thread(target=self._run_checks,
                         args=(all_items,), daemon=True).start()

    def _run_checks(self, items):
        results = {}
        for host, row in items:
            results[host] = check_site(host)
        Clock.schedule_once(lambda dt: self._apply_results(results))

    def _apply_results(self, results):
        for block in self._folder_blocks.values():
            block.apply_results(results)
        self.btn_check.text = "🔍  Проверить все"
        self.btn_check.disabled = False

    # ── Сохранение ─────────────────────────────────────────────────────────

    def _save(self):
        folders = []
        for name, block in self._folder_blocks.items():
            folders.append({"name": name, "sites": block.get_sites()})
        self._data["folders"] = folders
        save_data(self._data)


# ─── Точка входа ──────────────────────────────────────────────────────────────

def run():
    running_app = App.get_running_app()
    if running_app:
        screen = MainScreen()
        win = running_app.root_window
        if win.children:
            win.children[0].clear_widgets()
            win.children[0].add_widget(screen)
    else:
        from kivy.app import App as KivyApp
        class StandaloneApp(KivyApp):
            def build(self):
                Window.clearcolor = CLR_BG
                return MainScreen()
        StandaloneApp().run()

run()
