# -*- coding: utf-8 -*-
"""
app.py v1.4 — SiteChecker
Нововведения: темы, сворачивание папок, читаемый текст кнопок,
проверка отдельного сайта по тапу, поле ввода над клавиатурой.
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
from kivy.uix.switch import Switch
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.app import App

try:
    from android.runnable import run_on_ui_thread
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False

# ─── Темы ─────────────────────────────────────────────────────────────────────

THEMES = {
    "dark": {
        "bg":        (0.07, 0.08, 0.10, 1),
        "card":      (0.12, 0.14, 0.18, 1),
        "card_tap":  (0.18, 0.22, 0.28, 1),
        "folder":    (0.10, 0.13, 0.17, 1),
        "accent":    (0.22, 0.68, 0.87, 1),
        "green":     (0.22, 0.78, 0.51, 1),
        "red":       (0.93, 0.33, 0.36, 1),
        "yellow":    (0.98, 0.76, 0.18, 1),
        "text":      (0.92, 0.93, 0.95, 1),
        "subtext":   (0.55, 0.60, 0.67, 1),
        "input_bg":  (0.16, 0.18, 0.23, 1),
        "btn":       (0.22, 0.68, 0.87, 1),
        "btn_text":  (0.90, 0.93, 0.95, 1),
        "del":       (0.75, 0.22, 0.25, 1),
        "secondary": (0.18, 0.22, 0.28, 1),
    },
    "light": {
        "bg":        (0.93, 0.94, 0.96, 1),
        "card":      (1.00, 1.00, 1.00, 1),
        "card_tap":  (0.88, 0.92, 0.98, 1),
        "folder":    (0.85, 0.88, 0.93, 1),
        "accent":    (0.10, 0.53, 0.82, 1),
        "green":     (0.13, 0.65, 0.40, 1),
        "red":       (0.85, 0.18, 0.22, 1),
        "yellow":    (0.80, 0.55, 0.05, 1),
        "text":      (0.10, 0.11, 0.13, 1),
        "subtext":   (0.40, 0.43, 0.50, 1),
        "input_bg":  (0.87, 0.89, 0.93, 1),
        "btn":       (0.10, 0.53, 0.82, 1),
        "btn_text":  (0.95, 0.97, 1.00, 1),
        "del":       (0.85, 0.18, 0.22, 1),
        "secondary": (0.75, 0.79, 0.86, 1),
    },
}

_current_theme = "dark"

def T(key):
    return THEMES[_current_theme][key]

def set_theme(name):
    global _current_theme
    _current_theme = name


# ─── Хранилище ────────────────────────────────────────────────────────────────

APP_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "sitechecker_data.json")

DEFAULT_DATA = {
    "theme": "dark",
    "folders": [
        {"name": "Российские", "sites": ["ya.ru", "vk.com", "mail.ru", "gosuslugi.ru"]},
        {"name": "Зарубежные", "sites": ["google.com", "github.com", "wikipedia.org"]},
    ]
}

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if "theme" not in d:
                    d["theme"] = "dark"
                return d
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

PING_TIMEOUT   = 3
SOCKET_TIMEOUT = 3

def measure_ping_ms(host):
    s = platform.system().lower()
    cmd = (["ping", "-n", "1", "-w", str(PING_TIMEOUT * 1000), host]
           if s == "windows" else
           ["ping", "-c", "1", "-W", str(PING_TIMEOUT), host])
    try:
        t0 = time.monotonic()
        r  = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=PING_TIMEOUT + 2)
        return int((time.monotonic() - t0) * 1000) if r.returncode == 0 else None
    except Exception:
        return None

def measure_tcp_ms(host, port=80):
    try:
        t0 = time.monotonic()
        with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT):
            pass
        return int((time.monotonic() - t0) * 1000)
    except Exception:
        return None

def check_dns(host):
    try:
        return True, socket.gethostbyname(host)
    except socket.gaierror:
        return False, None

def check_site(host):
    sent, _ = check_dns(host)
    if not sent:
        return False, False, None
    ms = measure_ping_ms(host)
    if ms is not None:
        return True, True, ms
    ms = measure_tcp_ms(host)
    if ms is not None:
        return True, True, ms
    return True, False, None


# ─── Popup ────────────────────────────────────────────────────────────────────

def make_popup(title, content, size=(dp(300), dp(200))):
    return Popup(
        title=title, content=content,
        size_hint=(None, None), size=size,
        background_color=T("card"),
        title_color=T("text"),
        separator_color=T("accent"),
    )


# ─── Строка сайта ─────────────────────────────────────────────────────────────

class SiteRow(BoxLayout):
    """
    Строка сайта. Тап по строке — одиночная проверка этого сайта.
    Кнопка X — удаление.
    """
    def __init__(self, host, on_delete, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(52), padding=[dp(10), dp(6)],
                         spacing=dp(6), **kw)
        self.host      = host
        self.on_delete = on_delete
        self._checking = False

        with self.canvas.before:
            Color(*T("card"))
            self._bg_color = Color(*T("card"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(8)])
        self.bind(pos=self._u, size=self._u)

        # Кнопка-обёртка на всю строку для тапа
        self._tap_btn = Button(
            background_color=(0, 0, 0, 0),
            background_normal="",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0}
        )
        self._tap_btn.bind(on_press=self._on_tap)

        self.lbl_host = Label(
            text=host, font_size=dp(13), color=T("text"),
            halign="left", valign="middle", size_hint=(0.32, 1))
        self.lbl_host.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        self.lbl_sent = Label(text="--", font_size=dp(12), color=T("subtext"),
                              halign="center", valign="middle", size_hint=(0.20, 1))
        self.lbl_recv = Label(text="--", font_size=dp(12), color=T("subtext"),
                              halign="center", valign="middle", size_hint=(0.20, 1))
        self.lbl_ms   = Label(text="--", font_size=dp(12), color=T("subtext"),
                              halign="center", valign="middle", size_hint=(0.16, 1))

        btn_del = Button(
            text="X", font_size=dp(13), bold=True,
            background_color=T("del"), color=T("btn_text"),
            size_hint=(None, None), size=(dp(34), dp(34)))
        btn_del.bind(on_press=lambda _: self.on_delete(self.host))

        for w in (self.lbl_host, self.lbl_sent, self.lbl_recv,
                  self.lbl_ms, btn_del):
            self.add_widget(w)

        # Прозрачная кнопка поверх — перехватывает тап на строку
        self.add_widget(self._tap_btn)

    def _u(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size

    def _on_tap(self, *_):
        """Одиночная проверка при тапе на строку."""
        if self._checking:
            return
        self._checking = True
        self.set_checking()
        threading.Thread(target=self._check_self, daemon=True).start()

    def _check_self(self):
        result = check_site(self.host)
        Clock.schedule_once(lambda dt: self._apply_single(result))

    def _apply_single(self, result):
        self.set_result(*result)
        self._checking = False

    def set_checking(self):
        self.lbl_sent.text  = "..."
        self.lbl_recv.text  = "..."
        self.lbl_ms.text    = "..."
        for lbl in (self.lbl_sent, self.lbl_recv, self.lbl_ms):
            lbl.color = T("subtext")

    def set_result(self, sent, returned, ms):
        self.lbl_sent.text  = "Да"  if sent     else "Нет"
        self.lbl_sent.color = T("green") if sent     else T("red")
        self.lbl_recv.text  = "Да"  if returned  else "Нет"
        self.lbl_recv.color = T("green") if returned  else T("red")
        if ms is not None:
            self.lbl_ms.text  = f"{ms} мс"
            self.lbl_ms.color = (T("green") if ms < 100 else
                                 T("yellow") if ms < 300 else T("red"))
        else:
            self.lbl_ms.text  = "--"
            self.lbl_ms.color = T("subtext")


# ─── Попап добавления сайта ───────────────────────────────────────────────────

class AddSitePopup(Popup):
    """
    Отдельный popup для ввода сайта — поле всегда над клавиатурой,
    не перекрывается.
    """
    def __init__(self, on_add, **kw):
        content = BoxLayout(orientation="vertical",
                            spacing=dp(12), padding=dp(14))
        super().__init__(
            title="Добавить сайт",
            content=content,
            size_hint=(0.92, None), height=dp(180),
            pos_hint={"center_x": 0.5, "top": 1.0},
            background_color=T("card"),
            title_color=T("text"),
            separator_color=T("accent"),
            **kw
        )
        self.on_add = on_add

        content.add_widget(Label(
            text="Введите адрес сайта:", font_size=dp(13),
            color=T("subtext"), size_hint_y=None, height=dp(22),
            halign="left"))

        self.txt = TextInput(
            hint_text="example.com",
            font_size=dp(15), multiline=False,
            background_color=T("input_bg"),
            foreground_color=T("text"),
            hint_text_color=T("subtext"),
            cursor_color=T("accent"),
            padding=[dp(12), dp(12)],
            size_hint_y=None, height=dp(46))
        self.txt.bind(on_text_validate=self._do_add)
        content.add_widget(self.txt)

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        btn_ok = Button(
            text="Добавить", font_size=dp(14), bold=True,
            background_color=T("accent"), color=T("btn_text"))
        btn_ok.bind(on_press=self._do_add)
        btn_no = Button(
            text="Отмена", font_size=dp(14),
            background_color=T("secondary"), color=T("text"))
        btn_no.bind(on_press=lambda _: self.dismiss())
        btns.add_widget(btn_ok)
        btns.add_widget(btn_no)
        content.add_widget(btns)

        # Поднимаем popup над клавиатурой при её появлении
        Window.bind(on_keyboard_height=self._on_kb)
        self.bind(on_dismiss=lambda _: Window.unbind(
            on_keyboard_height=self._on_kb))

        Clock.schedule_once(lambda dt: setattr(self.txt, "focus", True), 0.2)

    def _on_kb(self, win, height):
        """Сдвигаем popup вверх когда появляется клавиатура."""
        if height > 0:
            self.y = height + dp(10)
        else:
            self.pos_hint = {"center_x": 0.5, "top": 1.0}

    def _do_add(self, *_):
        host = self.txt.text.strip().lower()
        for p in ("https://", "http://", "www."):
            if host.startswith(p):
                host = host[len(p):]
        host = host.rstrip("/")
        if host:
            self.on_add(host)
        self.dismiss()


# ─── Блок папки ───────────────────────────────────────────────────────────────

class FolderBlock(BoxLayout):
    def __init__(self, folder_name, sites, on_folder_delete,
                 on_data_change, **kw):
        super().__init__(orientation="vertical", size_hint_y=None,
                         spacing=dp(4), **kw)
        self.folder_name      = folder_name
        self.on_folder_delete = on_folder_delete
        self.on_data_change   = on_data_change
        self._rows      = {}
        self._collapsed = False

        self.bind(minimum_height=self.setter("height"))
        self._build_header()
        self._build_sites(sites)
        self._update_height()

    def _build_header(self):
        self._hdr = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(46), spacing=dp(6), padding=[dp(10), dp(4)])
        with self._hdr.canvas.before:
            Color(*T("folder"))
            self._hdr_rect = RoundedRectangle(
                pos=self._hdr.pos, size=self._hdr.size, radius=[dp(8)])
        self._hdr.bind(
            pos=lambda *_: setattr(self._hdr_rect, "pos", self._hdr.pos),
            size=lambda *_: setattr(self._hdr_rect, "size", self._hdr.size))

        self.btn_toggle = Button(
            text="v", font_size=dp(14), bold=True,
            background_color=(0, 0, 0, 0), color=T("accent"),
            size_hint=(None, 1), width=dp(28))
        self.btn_toggle.bind(on_press=self._toggle)

        self.lbl_name = Label(
            text=self.folder_name, font_size=dp(15), bold=True,
            color=T("text"), halign="left", valign="middle",
            size_hint=(1, 1))
        self.lbl_name.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        self.lbl_count = Label(
            text=self._count_text(0), font_size=dp(11),
            color=T("subtext"), halign="right", valign="middle",
            size_hint=(None, 1), width=dp(70))

        btn_add = Button(
            text="+", font_size=dp(18), bold=True,
            background_color=T("accent"), color=T("btn_text"),
            size_hint=(None, 1), width=dp(36))
        btn_add.bind(on_press=self._open_add_popup)

        btn_del = Button(
            text="X", font_size=dp(13), bold=True,
            background_color=(0, 0, 0, 0), color=T("red"),
            size_hint=(None, 1), width=dp(28))
        btn_del.bind(on_press=lambda _: self.on_folder_delete(self.folder_name))

        for w in (self.btn_toggle, self.lbl_name, self.lbl_count,
                  btn_add, btn_del):
            self._hdr.add_widget(w)
        self.add_widget(self._hdr)

    def _build_sites(self, sites):
        self._sites_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4))
        self._sites_box.bind(
            minimum_height=self._sites_box.setter("height"))
        for s in sites:
            self._add_row(s)
        self.add_widget(self._sites_box)

    def _count_text(self, n=None):
        if n is None:
            n = len(self._rows)
        return f"{n} сайт{'ов' if n % 10 != 1 or n % 100 == 11 else ''}"

    def _open_add_popup(self, *_):
        popup = AddSitePopup(on_add=self._add_from_popup)
        popup.open()

    def _add_from_popup(self, host):
        if host and host not in self._rows:
            self._add_row(host)
            self.on_data_change()

    def _add_row(self, host):
        if host in self._rows:
            return
        row = SiteRow(host, on_delete=self._on_delete_site)
        self._rows[host] = row
        self._sites_box.add_widget(row)
        self.lbl_count.text = self._count_text()
        self._update_height()

    def _on_delete_site(self, host):
        if host in self._rows:
            self._sites_box.remove_widget(self._rows.pop(host))
            self.lbl_count.text = self._count_text()
            self._update_height()
            self.on_data_change()

    def _toggle(self, *_):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._sites_box.opacity = 0
            self._sites_box.height  = 0
            self.btn_toggle.text    = ">"
        else:
            self._sites_box.opacity = 1
            self._sites_box.height  = self._sites_box.minimum_height
            self.btn_toggle.text    = "v"
        self._update_height()

    def _update_height(self):
        h = dp(46) + dp(4)
        if not self._collapsed:
            h += self._sites_box.minimum_height + dp(4)
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
        self._data = load_data()
        set_theme(self._data.get("theme", "dark"))
        self._folder_blocks = {}

        with self.canvas.before:
            Color(*T("bg"))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))
        Window.clearcolor = T("bg")

        self._build_header()
        self._build_table_header()
        self._build_scroll()
        self._build_footer()
        self._populate_folders()

    def _build_header(self):
        hdr = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(54), spacing=dp(8))

        left = BoxLayout(orientation="vertical", size_hint=(1, 1))
        t1 = Label(text="SiteChecker", font_size=dp(20), bold=True,
                   color=T("accent"), halign="left", valign="bottom",
                   size_hint_y=None, height=dp(30))
        t2 = Label(text="Проверка доступности сайтов",
                   font_size=dp(11), color=T("subtext"),
                   halign="left", valign="top",
                   size_hint_y=None, height=dp(18))
        for l in (t1, t2):
            l.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            left.add_widget(l)

        right = BoxLayout(orientation="horizontal",
                          size_hint=(None, 1), width=dp(160), spacing=dp(8))

        theme_box = BoxLayout(orientation="vertical",
                              size_hint=(None, 1), width=dp(64))
        self._lbl_theme = Label(
            text="Светлая" if _current_theme == "light" else "Тёмная",
            font_size=dp(9), color=T("subtext"),
            size_hint_y=None, height=dp(16))
        sw = Switch(active=(_current_theme == "light"),
                    size_hint=(1, None), height=dp(32))
        sw.bind(active=self._on_theme_switch)
        theme_box.add_widget(self._lbl_theme)
        theme_box.add_widget(sw)

        btn_new = Button(
            text="+ Папка", font_size=dp(12), bold=True,
            background_color=T("accent"), color=T("btn_text"),
            size_hint=(None, 1), width=dp(84))
        btn_new.bind(on_press=self._popup_new_folder)

        right.add_widget(theme_box)
        right.add_widget(btn_new)
        hdr.add_widget(left)
        hdr.add_widget(right)
        self.add_widget(hdr)

    def _on_theme_switch(self, sw, value):
        new_theme = "light" if value else "dark"
        set_theme(new_theme)
        self._data["theme"] = new_theme
        save_data(self._data)
        Window.clearcolor = T("bg")
        app  = App.get_running_app()
        root = app.root
        root.clear_widgets()
        root.add_widget(MainScreen())

    def _build_table_header(self):
        th = BoxLayout(orientation="horizontal", size_hint_y=None,
                       height=dp(22), padding=[dp(10), 0], spacing=dp(6))
        for text, hint in [("Сайт", 0.32), ("Отправлен", 0.20),
                            ("Вернулся", 0.20), ("Задержка", 0.16),
                            ("", 0.12)]:
            th.add_widget(Label(
                text=text, font_size=dp(10), color=T("subtext"),
                halign="center", valign="middle", size_hint=(hint, 1)))
        self.add_widget(th)

    def _build_scroll(self):
        self.scroll  = ScrollView(size_hint=(1, 1))
        self.content = GridLayout(cols=1, spacing=dp(8),
                                  size_hint_y=None, padding=[0, dp(4)])
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.add_widget(self.scroll)

    def _build_footer(self):
        self.btn_check = Button(
            text=">> Проверить все", font_size=dp(15), bold=True,
            background_color=T("btn"), color=T("btn_text"),
            size_hint_y=None, height=dp(52))
        self.btn_check.bind(on_press=self._check_all)
        self.add_widget(self.btn_check)

    def _populate_folders(self):
        for folder in self._data["folders"]:
            self._add_folder_block(folder["name"], folder["sites"])

    def _add_folder_block(self, name, sites):
        block = FolderBlock(
            folder_name=name, sites=sites,
            on_folder_delete=self._on_folder_delete,
            on_data_change=self._save)
        self._folder_blocks[name] = block
        self.content.add_widget(block)

    def _on_folder_delete(self, folder_name):
        box   = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
        popup = make_popup("Подтверждение", box, size=(dp(300), dp(210)))
        box.add_widget(Label(
            text=f'Удалить папку\n"{folder_name}"\nи все её сайты?',
            font_size=dp(14), color=T("text"), halign="center"))
        btns    = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        btn_yes = Button(text="Удалить", background_color=T("red"),
                         color=T("btn_text"), font_size=dp(14))
        btn_no  = Button(text="Отмена",  background_color=T("secondary"),
                         color=T("text"), font_size=dp(14))

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
        box    = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
        popup  = make_popup("Новая папка", box, size=(dp(300), dp(190)))
        box.add_widget(Label(text="Название папки:", font_size=dp(14),
                             color=T("text"), size_hint_y=None, height=dp(28)))
        txt = TextInput(
            hint_text="Например: Работа", font_size=dp(14), multiline=False,
            background_color=T("input_bg"), foreground_color=T("text"),
            hint_text_color=T("subtext"), cursor_color=T("accent"),
            padding=[dp(10), dp(10)], size_hint_y=None, height=dp(42))
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        btn_ok  = Button(text="Создать", background_color=T("accent"),
                         color=T("btn_text"), font_size=dp(14))
        btn_no  = Button(text="Отмена",  background_color=T("secondary"),
                         color=T("text"), font_size=dp(14))

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
        Clock.schedule_once(lambda dt: setattr(txt, "focus", True), 0.2)

    def _check_all(self, *_):
        all_items = []
        for block in self._folder_blocks.values():
            all_items.extend(block.check_all())
        if not all_items:
            return
        self.btn_check.text     = "Проверяем..."
        self.btn_check.disabled = True
        threading.Thread(
            target=self._run_checks, args=(all_items,), daemon=True).start()

    def _run_checks(self, items):
        results = {host: check_site(host) for host, _ in items}
        Clock.schedule_once(lambda dt: self._apply_results(results))

    def _apply_results(self, results):
        for block in self._folder_blocks.values():
            block.apply_results(results)
        self.btn_check.text     = ">> Проверить все"
        self.btn_check.disabled = False

    def _save(self):
        self._data["folders"] = [
            {"name": name, "sites": block.get_sites()}
            for name, block in self._folder_blocks.items()
        ]
        save_data(self._data)