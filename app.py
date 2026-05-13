# -*- coding: utf-8 -*-
"""
app.py v1.7 — SiteChecker
Нововведения: перемещение папок и сайтов вверх/вниз, перенос сайта
между папками, кнопка обновления прямо в приложении, новая шапка
(центр + тема справа), кнопка "+ Папка" внизу.
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
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.app import App

# ─── Темы ─────────────────────────────────────────────────────────────────────

THEMES = {
    "dark": {
        "bg":        (0.07, 0.08, 0.10, 1),
        "card":      (0.12, 0.14, 0.18, 1),
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
        "del":       (0.65, 0.15, 0.18, 1),
        "secondary": (0.18, 0.22, 0.28, 1),
        "move":      (0.18, 0.22, 0.30, 1),
    },
    "light": {
        "bg":        (0.93, 0.94, 0.96, 1),
        "card":      (1.00, 1.00, 1.00, 1),
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
        "move":      (0.78, 0.83, 0.92, 1),
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


# ─── Константы вёрстки ────────────────────────────────────────────────────────

ROW_H  = dp(46)
W_MOVE = dp(22)   # кнопки ↑↓
W_HOST = dp(100)
W_SENT = dp(48)
W_RECV = dp(48)
W_MS   = dp(66)
W_DEL  = dp(34)


# ─── Строка сайта ─────────────────────────────────────────────────────────────

class SiteRow(BoxLayout):
    def __init__(self, host, on_delete, on_move, on_move_to_folder,
                 get_folder_names, **kw):
        super().__init__(
            orientation="horizontal",
            size_hint=(1, None), height=ROW_H,
            padding=[dp(4), dp(4)], spacing=dp(3), **kw)
        self.host             = host
        self.on_delete        = on_delete
        self.on_move          = on_move           # on_move(host, direction)
        self.on_move_to_folder = on_move_to_folder  # on_move_to_folder(host, target)
        self.get_folder_names = get_folder_names
        self._checking        = False

        with self.canvas.before:
            Color(*T("card"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(7)])
        self.bind(pos=self._u, size=self._u)

        # ↑↓ кнопки
        arrows = BoxLayout(orientation="vertical",
                           size_hint=(None, 1), width=W_MOVE,
                           spacing=dp(1))
        for sym, d in [("^", -1), ("v", 1)]:
            b = Button(text=sym, font_size=dp(10), bold=True,
                       background_normal="", background_color=(0,0,0,0),
                       color=T("subtext"), size_hint=(1, 1))
            b.bind(on_press=lambda _, dir=d: self.on_move(self.host, dir))
            arrows.add_widget(b)
        self.add_widget(arrows)

        # Название — кнопка для одиночной проверки
        self.btn_host = Button(
            text=host, font_size=dp(12),
            halign="left", valign="middle",
            background_normal="", background_color=(0, 0, 0, 0),
            color=T("text"),
            size_hint=(None, 1), width=W_HOST,
            text_size=(W_HOST - dp(6), None),
            shorten=True, shorten_from="right")
        self.btn_host.bind(on_press=self._on_tap)
        self.add_widget(self.btn_host)

        # Результаты
        self.lbl_sent = Label(text="--", font_size=dp(11), color=T("subtext"),
                              halign="center", valign="middle",
                              size_hint=(None, 1), width=W_SENT)
        self.lbl_recv = Label(text="--", font_size=dp(11), color=T("subtext"),
                              halign="center", valign="middle",
                              size_hint=(None, 1), width=W_RECV)
        self.lbl_ms   = Label(text="--", font_size=dp(11), color=T("subtext"),
                              halign="center", valign="middle",
                              size_hint=(None, 1), width=W_MS)

        for w in (self.lbl_sent, self.lbl_recv, self.lbl_ms):
            self.add_widget(w)

        # Кнопка переноса в другую папку
        btn_mv = Button(
            text=">", font_size=dp(12), bold=True,
            background_normal="", background_color=T("move"),
            color=T("btn_text"),
            size_hint=(None, 1), width=W_DEL)
        btn_mv.bind(on_press=self._popup_move_folder)
        self.add_widget(btn_mv)

        # Кнопка удаления
        btn_del = Button(
            text="X", font_size=dp(12), bold=True,
            background_normal="", background_color=T("del"),
            color=T("btn_text"),
            size_hint=(None, 1), width=W_DEL)
        btn_del.bind(on_press=lambda _: self.on_delete(self.host))
        self.add_widget(btn_del)

    def _u(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size

    def _on_tap(self, *_):
        if self._checking:
            return
        self._checking = True
        self.set_checking()
        threading.Thread(target=self._check_self, daemon=True).start()

    def _check_self(self):
        result = check_site(self.host)
        Clock.schedule_once(lambda dt: self._apply(result))

    def _apply(self, result):
        self.set_result(*result)
        self._checking = False

    def _popup_move_folder(self, *_):
        """Popup выбора папки для переноса сайта."""
        folders = [f for f in self.get_folder_names()]
        if len(folders) <= 1:
            return

        box   = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
        popup = make_popup("Перенести в папку", box, size=(dp(280), dp(220)))
        box.add_widget(Label(
            text=f"Куда перенести\n{self.host}?",
            font_size=dp(13), color=T("text"), halign="center",
            size_hint_y=None, height=dp(44)))

        for fname in folders:
            btn = Button(
                text=fname, font_size=dp(13),
                background_color=T("secondary"), color=T("text"),
                size_hint_y=None, height=dp(40))
            def do_move(_, target=fname):
                popup.dismiss()
                self.on_move_to_folder(self.host, target)
            btn.bind(on_press=do_move)
            box.add_widget(btn)

        box.add_widget(Button(
            text="Отмена", font_size=dp(13),
            background_color=T("del"), color=T("btn_text"),
            size_hint_y=None, height=dp(36),
            on_press=lambda _: popup.dismiss()))
        popup.open()

    def set_checking(self):
        for lbl in (self.lbl_sent, self.lbl_recv, self.lbl_ms):
            lbl.text  = "..."
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


# ─── Popup добавления сайта ───────────────────────────────────────────────────

class AddSitePopup(Popup):
    def __init__(self, on_add, **kw):
        content = BoxLayout(orientation="vertical",
                            spacing=dp(12), padding=dp(14))
        super().__init__(
            title="Добавить сайт", content=content,
            size_hint=(0.92, None), height=dp(190),
            pos_hint={"center_x": 0.5, "top": 1.0},
            background_color=T("card"),
            title_color=T("text"),
            separator_color=T("accent"), **kw)
        self.on_add_cb = on_add

        content.add_widget(Label(
            text="Введите адрес сайта:", font_size=dp(13),
            color=T("subtext"), halign="left",
            size_hint_y=None, height=dp(22)))

        self.txt = TextInput(
            hint_text="example.com", font_size=dp(15), multiline=False,
            background_color=T("input_bg"), foreground_color=T("text"),
            hint_text_color=T("subtext"), cursor_color=T("accent"),
            padding=[dp(12), dp(12)], size_hint_y=None, height=dp(48))
        self.txt.bind(on_text_validate=self._do_add)
        content.add_widget(self.txt)

        btns   = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        btn_ok = Button(text="Добавить", font_size=dp(14), bold=True,
                        background_color=T("accent"), color=T("btn_text"))
        btn_ok.bind(on_press=self._do_add)
        btn_no = Button(text="Отмена", font_size=dp(14),
                        background_color=T("secondary"), color=T("text"))
        btn_no.bind(on_press=lambda _: self.dismiss())
        btns.add_widget(btn_ok)
        btns.add_widget(btn_no)
        content.add_widget(btns)

        Window.bind(on_keyboard_height=self._on_kb)
        self.bind(on_dismiss=lambda _: Window.unbind(
            on_keyboard_height=self._on_kb))
        Clock.schedule_once(lambda dt: setattr(self.txt, "focus", True), 0.2)

    def _on_kb(self, win, height):
        if height > 0:
            self.y = height + dp(10)

    def _do_add(self, *_):
        host = self.txt.text.strip().lower()
        for p in ("https://", "http://", "www."):
            if host.startswith(p):
                host = host[len(p):]
        host = host.rstrip("/")
        if host:
            self.on_add_cb(host)
        self.dismiss()


# ─── Блок папки ───────────────────────────────────────────────────────────────

class FolderBlock(BoxLayout):
    def __init__(self, folder_name, sites,
                 on_folder_delete, on_folder_move,
                 on_data_change, get_folder_names,
                 on_site_move_to_folder, **kw):
        super().__init__(orientation="vertical", size_hint_y=None,
                         spacing=dp(3), **kw)
        self.folder_name          = folder_name
        self.on_folder_delete     = on_folder_delete
        self.on_folder_move       = on_folder_move
        self.on_data_change       = on_data_change
        self.get_folder_names     = get_folder_names
        self.on_site_move_to_folder = on_site_move_to_folder
        self._rows      = {}
        self._order     = []
        self._collapsed = False

        self.bind(minimum_height=self.setter("height"))
        self._build_header()
        self._build_sites(sites)
        self._update_height()

    # ── Шапка папки ────────────────────────────────────────────────────────

    def _build_header(self):
        self._hdr = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(46), spacing=dp(4), padding=[dp(8), dp(5)])
        with self._hdr.canvas.before:
            Color(*T("folder"))
            self._hdr_rect = RoundedRectangle(
                pos=self._hdr.pos, size=self._hdr.size, radius=[dp(8)])
        self._hdr.bind(
            pos=lambda *_: setattr(self._hdr_rect, "pos", self._hdr.pos),
            size=lambda *_: setattr(self._hdr_rect, "size", self._hdr.size))

        # ↑↓ папки
        fold_arrows = BoxLayout(orientation="vertical",
                                size_hint=(None, 1), width=dp(20), spacing=dp(1))
        for sym, d in [("^", -1), ("v", 1)]:
            b = Button(text=sym, font_size=dp(10), bold=True,
                       background_normal="", background_color=(0,0,0,0),
                       color=T("subtext"), size_hint=(1, 1))
            b.bind(on_press=lambda _, dir=d: self.on_folder_move(self.folder_name, dir))
            fold_arrows.add_widget(b)
        self._hdr.add_widget(fold_arrows)

        # Кнопка свернуть
        self.btn_toggle = Button(
            text="v", font_size=dp(13), bold=True,
            background_normal="", background_color=(0,0,0,0),
            color=T("accent"), size_hint=(None, 1), width=dp(22))
        self.btn_toggle.bind(on_press=self._toggle)
        self._hdr.add_widget(self.btn_toggle)

        # Название
        self.lbl_name = Label(
            text=self.folder_name, font_size=dp(15), bold=True,
            color=T("text"), halign="left", valign="middle", size_hint=(1, 1))
        self.lbl_name.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self._hdr.add_widget(self.lbl_name)

        # Счётчик
        self.lbl_count = Label(
            text=self._count_text(), font_size=dp(11),
            color=T("subtext"), halign="right", valign="middle",
            size_hint=(None, 1), width=dp(62))
        self._hdr.add_widget(self.lbl_count)

        # + добавить сайт
        btn_add = Button(
            text="+", font_size=dp(18), bold=True,
            background_normal="",
            background_color=T("accent"), color=T("btn_text"),
            size_hint=(None, 1), width=dp(32))
        btn_add.bind(on_press=self._open_add_popup)
        self._hdr.add_widget(btn_add)

        # Удалить папку
        btn_del = Button(
            text="X", font_size=dp(12), bold=True,
            background_normal="", background_color=(0,0,0,0),
            color=T("red"), size_hint=(None, 1), width=dp(24))
        btn_del.bind(on_press=lambda _: self.on_folder_delete(self.folder_name))
        self._hdr.add_widget(btn_del)

        self.add_widget(self._hdr)

    # ── Список сайтов ──────────────────────────────────────────────────────

    def _build_sites(self, sites):
        self._sites_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(3))
        self._sites_box.bind(minimum_height=self._sites_box.setter("height"))
        for s in sites:
            self._add_row(s)
        self.add_widget(self._sites_box)

    def _count_text(self):
        n = len(self._order) if hasattr(self, "_order") else 0
        end = "ов" if (n % 10 != 1 or n % 100 == 11) else ""
        return f"{n} сайт{end}"

    def _open_add_popup(self, *_):
        AddSitePopup(on_add=self._add_from_popup).open()

    def _add_from_popup(self, host):
        if host and host not in self._rows:
            self._add_row(host)
            self.on_data_change()

    def _add_row(self, host):
        if host in self._rows:
            return
        row = SiteRow(
            host=host,
            on_delete=self._on_delete_site,
            on_move=self._on_move_site,
            on_move_to_folder=self.on_site_move_to_folder,
            get_folder_names=self.get_folder_names,
        )
        self._rows[host] = row
        self._order.append(host)
        self._sites_box.add_widget(row)
        self.lbl_count.text = self._count_text()
        self._update_height()

    def _on_delete_site(self, host):
        if host in self._rows:
            self._sites_box.remove_widget(self._rows.pop(host))
            self._order.remove(host)
            self.lbl_count.text = self._count_text()
            self._update_height()
            self.on_data_change()

    def _on_move_site(self, host, direction):
        """Перемещает сайт на одну позицию вверх (-1) или вниз (+1)."""
        if host not in self._order:
            return
        idx = self._order.index(host)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._order):
            return
        # Меняем в списке
        self._order[idx], self._order[new_idx] = self._order[new_idx], self._order[idx]
        # Перестраиваем виджеты
        self._rebuild_sites_box()
        self.on_data_change()

    def _rebuild_sites_box(self):
        self._sites_box.clear_widgets()
        for host in self._order:
            if host in self._rows:
                self._sites_box.add_widget(self._rows[host])

    def remove_site(self, host):
        """Удаляет сайт без вызова on_data_change (вызывается при переносе)."""
        if host in self._rows:
            self._sites_box.remove_widget(self._rows.pop(host))
            self._order.remove(host)
            self.lbl_count.text = self._count_text()
            self._update_height()

    def add_site_external(self, host):
        """Добавляет сайт, пришедший из другой папки."""
        self._add_row(host)
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
        h = dp(46) + dp(3)
        if not self._collapsed:
            h += self._sites_box.minimum_height + dp(3)
        self.height = h

    def get_sites(self):
        return list(self._order)

    def check_all(self):
        for row in self._rows.values():
            row.set_checking()
        return [(h, self._rows[h]) for h in self._order]

    def apply_results(self, results):
        for host, (sent, returned, ms) in results.items():
            if host in self._rows:
                self._rows[host].set_result(sent, returned, ms)


# ─── Шапка таблицы ────────────────────────────────────────────────────────────

def build_table_header():
    row = BoxLayout(orientation="horizontal", size_hint_y=None,
                    height=dp(20), padding=[dp(4), 0], spacing=dp(3))
    def lbl(text, width):
        return Label(text=text, font_size=dp(9), color=T("subtext"),
                     halign="center", valign="middle",
                     size_hint=(None, 1), width=width)
    row.add_widget(lbl("",          W_MOVE))
    row.add_widget(lbl("Сайт",      W_HOST))
    row.add_widget(lbl("Отпр.",     W_SENT))
    row.add_widget(lbl("Верн.",     W_RECV))
    row.add_widget(lbl("Задержка",  W_MS))
    row.add_widget(lbl(">",         W_DEL))
    row.add_widget(lbl("X",         W_DEL))
    return row


# ─── Главный экран ────────────────────────────────────────────────────────────

class MainScreen(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical",
                         padding=dp(10), spacing=dp(6), **kw)
        self._data          = load_data()
        set_theme(self._data.get("theme", "dark"))
        self._folder_blocks = {}
        self._folder_order  = []

        with self.canvas.before:
            Color(*T("bg"))
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))
        Window.clearcolor = T("bg")

        self._build_header()
        self.add_widget(build_table_header())
        self._build_scroll()
        self._build_footer()
        self._populate_folders()

    # ── Шапка ──────────────────────────────────────────────────────────────

    def _build_header(self):
        SIDE_W = dp(100)
        hdr = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(54), spacing=0)

        # Левый блок — кнопка возврата
        left = BoxLayout(orientation="vertical", size_hint=(None, 1),
                         width=SIDE_W, padding=[0, dp(10)])
        btn_upd = Button(
            text="< Обновить", font_size=dp(10),
            background_normal="",
            background_color=T("secondary"), color=T("subtext"),
            size_hint=(1, None), height=dp(28))
        btn_upd.bind(on_press=self._go_to_loader)
        left.add_widget(btn_upd)

        # Центр — название + описание
        center = BoxLayout(orientation="vertical", size_hint=(1, 1),
                           padding=[0, dp(5)])
        t1 = Label(text="SiteChecker", font_size=dp(20), bold=True,
                   color=T("accent"), halign="center", valign="bottom",
                   size_hint_y=None, height=dp(26))
        t2 = Label(text="Проверка доступности сайтов",
                   font_size=dp(10), color=T("subtext"),
                   halign="center", valign="top",
                   size_hint_y=None, height=dp(14))
        for l in (t1, t2):
            l.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            center.add_widget(l)

        # Правый блок — переключатель темы
        right = BoxLayout(orientation="vertical", size_hint=(None, 1),
                          width=SIDE_W, padding=[dp(8), dp(6)], spacing=dp(2))
        self._lbl_theme = Label(
            text="Светлая" if _current_theme == "light" else "Тёмная",
            font_size=dp(8), color=T("subtext"),
            size_hint_y=None, height=dp(12), halign="center")
        sw = Switch(active=(_current_theme == "light"),
                    size_hint=(1, None), height=dp(26))
        sw.bind(active=self._on_theme_switch)
        right.add_widget(self._lbl_theme)
        right.add_widget(sw)

        hdr.add_widget(left)
        hdr.add_widget(center)
        hdr.add_widget(right)
        self.add_widget(hdr)

    def _on_theme_switch(self, sw, value):
        new_theme = "light" if value else "dark"
        set_theme(new_theme)
        self._lbl_theme.text = "Светлая" if value else "Тёмная"
        self._data["theme"]  = new_theme
        save_data(self._data)
        Window.clearcolor = T("bg")
        app  = App.get_running_app()
        root = app.root
        root.clear_widgets()
        root.add_widget(MainScreen())

    def _go_to_loader(self, *_):
        """Возвращает на экран загрузчика для проверки обновлений."""
        try:
            import main as loader_module
            screen = loader_module.LoaderScreen()
            app    = App.get_running_app()
            root   = app.root
            root.clear_widgets()
            root.add_widget(screen)
        except Exception as e:
            # Если не удалось — просто перезапускаем MainScreen
            app  = App.get_running_app()
            root = app.root
            root.clear_widgets()
            root.add_widget(MainScreen())

    # ── Список ─────────────────────────────────────────────────────────────

    def _build_scroll(self):
        self.scroll  = ScrollView(size_hint=(1, 1))
        self.content = GridLayout(cols=1, spacing=dp(6),
                                  size_hint_y=None, padding=[0, dp(2)])
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.add_widget(self.scroll)

    # ── Нижняя панель ──────────────────────────────────────────────────────

    def _build_footer(self):
        footer = BoxLayout(orientation="vertical",
                           size_hint_y=None, height=dp(88), spacing=dp(6))

        # Кнопка добавления папки — во всю ширину, но не высокая
        btn_new_folder = Button(
            text="+ Добавить папку", font_size=dp(12),
            background_normal="",
            background_color=T("secondary"), color=T("subtext"),
            size_hint_y=None, height=dp(32))
        btn_new_folder.bind(on_press=self._popup_new_folder)

        # Кнопка проверки всех
        self.btn_check = Button(
            text=">> Проверить все", font_size=dp(15), bold=True,
            background_normal="",
            background_color=T("btn"), color=T("btn_text"),
            size_hint_y=None, height=dp(50))
        self.btn_check.bind(on_press=self._check_all)

        footer.add_widget(btn_new_folder)
        footer.add_widget(self.btn_check)
        self.add_widget(footer)

    # ── Папки ──────────────────────────────────────────────────────────────

    def _populate_folders(self):
        for folder in self._data["folders"]:
            self._add_folder_block(folder["name"], folder["sites"])

    def _add_folder_block(self, name, sites):
        block = FolderBlock(
            folder_name=name, sites=sites,
            on_folder_delete=self._on_folder_delete,
            on_folder_move=self._on_folder_move,
            on_data_change=self._save,
            get_folder_names=self._get_folder_names,
            on_site_move_to_folder=self._on_site_move_to_folder,
        )
        self._folder_blocks[name] = block
        self._folder_order.append(name)
        self.content.add_widget(block)

    def _get_folder_names(self):
        return list(self._folder_order)

    def _on_folder_move(self, folder_name, direction):
        """Перемещает папку вверх (-1) или вниз (+1)."""
        if folder_name not in self._folder_order:
            return
        idx     = self._folder_order.index(folder_name)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._folder_order):
            return
        self._folder_order[idx], self._folder_order[new_idx] = \
            self._folder_order[new_idx], self._folder_order[idx]
        self._rebuild_content()
        self._save()

    def _rebuild_content(self):
        self.content.clear_widgets()
        for name in self._folder_order:
            if name in self._folder_blocks:
                self.content.add_widget(self._folder_blocks[name])

    def _on_site_move_to_folder(self, host, target_folder):
        """Переносит сайт из его текущей папки в target_folder."""
        if target_folder not in self._folder_blocks:
            return
        # Найдём исходную папку
        source = None
        for name, block in self._folder_blocks.items():
            if host in block.get_sites():
                source = name
                break
        if source is None or source == target_folder:
            return
        # Удаляем из исходной
        self._folder_blocks[source].remove_site(host)
        # Добавляем в целевую — нужно пересоздать SiteRow с новыми коллбэками
        self._folder_blocks[target_folder].add_site_external(host)
        self._save()

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
                self._folder_order.remove(folder_name)
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

    # ── Проверка всех ──────────────────────────────────────────────────────

    def _check_all(self, *_):
        all_items = []
        for name in self._folder_order:
            if name in self._folder_blocks:
                all_items.extend(self._folder_blocks[name].check_all())
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

    # ── Сохранение ─────────────────────────────────────────────────────────

    def _save(self):
        self._data["folders"] = [
            {"name": name, "sites": self._folder_blocks[name].get_sites()}
            for name in self._folder_order
            if name in self._folder_blocks
        ]
        save_data(self._data)