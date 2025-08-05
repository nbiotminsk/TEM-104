# -*- coding: utf-8 -*-
"""
Графический интерфейс для опроса счетчиков ТЭМ-104 (ARVAS, TESMART и др.)
Работает через COM-порт или TCP/IP, использует существующую логику из test104.py.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import io
import json
import os

OBJECTS_FILE = "objects.json"

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core_library'))
from test104 import TEM104_Serial_Client, TEM104_TCP_Client

class RedirectText(io.StringIO):
    """Класс для перенаправления вывода print в текстовое поле tkinter."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    def write(self, s):
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, s)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')
    def flush(self):
        pass

class TEM104GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Опрос счетчиков ТЭМ-104")
        self.geometry("600x540")
        self.resizable(False, False)
        self.objects = []
        self.load_objects()
        self.create_widgets()

    def load_objects(self):
        if os.path.exists(OBJECTS_FILE):
            try:
                with open(OBJECTS_FILE, "r", encoding="utf-8") as f:
                    self.objects = json.load(f)
            except Exception:
                self.objects = []
        else:
            self.objects = []

    def save_objects(self):
        with open(OBJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.objects, f, ensure_ascii=False, indent=2)

    def create_widgets(self):
        # 1. Заголовок
        ttk.Label(self, text="Утилита для опроса счетчиков ТЭМ-104", font=("Arial", 14, "bold")).pack(pady=8)

        # 2. Список объектов
        frame_obj = ttk.Frame(self)
        frame_obj.pack(pady=4)
        ttk.Label(frame_obj, text="Объект:").pack(side=tk.LEFT)
        self.obj_var = tk.StringVar()
        self.combo_obj = ttk.Combobox(frame_obj, textvariable=self.obj_var, state="readonly", width=30)
        self.combo_obj.pack(side=tk.LEFT, padx=4)
        self.update_object_list()
        self.combo_obj.bind("<<ComboboxSelected>>", self.on_object_selected)
        ttk.Button(frame_obj, text="Добавить объект", command=self.add_object_dialog).pack(side=tk.LEFT, padx=4)

        # 3. Переключатель типа подключения
        self.conn_type = tk.StringVar(value="COM")
        frame_type = ttk.Frame(self)
        frame_type.pack(pady=4)
        ttk.Radiobutton(frame_type, text="Локальный COM-порт", variable=self.conn_type, value="COM", command=self.toggle_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(frame_type, text="Сеть TCP/IP (модем)", variable=self.conn_type, value="TCP", command=self.toggle_fields).pack(side=tk.LEFT, padx=10)

        # 4. Поля для параметров
        self.frame_params = ttk.Frame(self)
        self.frame_params.pack(pady=4)
        # COM
        self.label_com = ttk.Label(self.frame_params, text="COM-порт:")
        self.entry_com = ttk.Entry(self.frame_params, width=10)
        self.entry_com.insert(0, "COM3")
        self.label_baud = ttk.Label(self.frame_params, text="Скорость:")
        self.entry_baud = ttk.Entry(self.frame_params, width=8)
        self.entry_baud.insert(0, "9600")
        # TCP
        self.label_ip = ttk.Label(self.frame_params, text="IP-адрес:")
        self.entry_ip = ttk.Entry(self.frame_params, width=15)
        self.entry_ip.insert(0, "192.168.1.100")
        self.label_port = ttk.Label(self.frame_params, text="TCP-порт:")
        self.entry_port = ttk.Entry(self.frame_params, width=8)
        self.entry_port.insert(0, "5009")
        # Общий адрес
        self.label_addr = ttk.Label(self.frame_params, text="Адрес счетчика:")
        self.entry_addr = ttk.Entry(self.frame_params, width=5)
        self.entry_addr.insert(0, "1")
        self.toggle_fields()

        # 5. Кнопка "Опросить"
        self.btn_poll = ttk.Button(self, text="Опросить", command=self.start_poll)
        self.btn_poll.pack(pady=8)

        # 6. Текстовое поле для вывода
        self.text_output = scrolledtext.ScrolledText(self, width=72, height=16, state='disabled', font=("Consolas", 10))
        self.text_output.pack(padx=8, pady=4)

        # 7. Кнопка "Выход"
        ttk.Button(self, text="Выход", command=self.destroy).pack(pady=4)

    def toggle_fields(self):
        # Очищаем
        for widget in self.frame_params.winfo_children():
            widget.pack_forget()
        if self.conn_type.get() == "COM":
            self.label_com.pack(side=tk.LEFT, padx=2)
            self.entry_com.pack(side=tk.LEFT, padx=2)
            self.label_baud.pack(side=tk.LEFT, padx=2)
            self.entry_baud.pack(side=tk.LEFT, padx=2)
        else:
            self.label_ip.pack(side=tk.LEFT, padx=2)
            self.entry_ip.pack(side=tk.LEFT, padx=2)
            self.label_port.pack(side=tk.LEFT, padx=2)
            self.entry_port.pack(side=tk.LEFT, padx=2)
        self.label_addr.pack(side=tk.LEFT, padx=2)
        self.entry_addr.pack(side=tk.LEFT, padx=2)

    def update_object_list(self):
        names = [obj['name'] for obj in self.objects]
        self.combo_obj['values'] = names
        if names:
            self.combo_obj.current(0)

    def on_object_selected(self, event=None):
        idx = self.combo_obj.current()
        if idx < 0 or idx >= len(self.objects):
            return
        obj = self.objects[idx]
        self.conn_type.set(obj['type'])
        if obj['type'] == 'COM':
            self.entry_com.delete(0, tk.END)
            self.entry_com.insert(0, obj.get('com', 'COM3'))
            self.entry_baud.delete(0, tk.END)
            self.entry_baud.insert(0, str(obj.get('baud', '9600')))
        else:
            self.entry_ip.delete(0, tk.END)
            self.entry_ip.insert(0, obj.get('ip', '192.168.1.100'))
            self.entry_port.delete(0, tk.END)
            self.entry_port.insert(0, str(obj.get('port', '5009')))
        self.entry_addr.delete(0, tk.END)
        self.entry_addr.insert(0, str(obj.get('addr', '1')))
        self.toggle_fields()

    def add_object_dialog(self):
        win = tk.Toplevel(self)
        win.title("Добавить объект")
        win.geometry("350x250")
        win.resizable(False, False)
        # Имя
        ttk.Label(win, text="Имя объекта:").pack(pady=4)
        entry_name = ttk.Entry(win, width=30)
        entry_name.pack(pady=2)
        # Тип
        type_var = tk.StringVar(value=self.conn_type.get())
        frame_type = ttk.Frame(win)
        frame_type.pack(pady=2)
        ttk.Radiobutton(frame_type, text="COM", variable=type_var, value="COM").pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(frame_type, text="TCP", variable=type_var, value="TCP").pack(side=tk.LEFT, padx=8)
        # Параметры
        frame_params = ttk.Frame(win)
        frame_params.pack(pady=2)
        label_com = ttk.Label(frame_params, text="COM-порт:")
        entry_com = ttk.Entry(frame_params, width=10)
        entry_com.insert(0, self.entry_com.get())
        label_baud = ttk.Label(frame_params, text="Скорость:")
        entry_baud = ttk.Entry(frame_params, width=8)
        entry_baud.insert(0, self.entry_baud.get())
        label_ip = ttk.Label(frame_params, text="IP-адрес:")
        entry_ip = ttk.Entry(frame_params, width=15)
        entry_ip.insert(0, self.entry_ip.get())
        label_port = ttk.Label(frame_params, text="TCP-порт:")
        entry_port = ttk.Entry(frame_params, width=8)
        entry_port.insert(0, self.entry_port.get())
        label_addr = ttk.Label(frame_params, text="Адрес:")
        entry_addr = ttk.Entry(frame_params, width=5)
        entry_addr.insert(0, self.entry_addr.get())
        def toggle_params():
            for w in (label_com, entry_com, label_baud, entry_baud, label_ip, entry_ip, label_port, entry_port):
                w.pack_forget()
            if type_var.get() == 'COM':
                label_com.pack(side=tk.LEFT, padx=2)
                entry_com.pack(side=tk.LEFT, padx=2)
                label_baud.pack(side=tk.LEFT, padx=2)
                entry_baud.pack(side=tk.LEFT, padx=2)
            else:
                label_ip.pack(side=tk.LEFT, padx=2)
                entry_ip.pack(side=tk.LEFT, padx=2)
                label_port.pack(side=tk.LEFT, padx=2)
                entry_port.pack(side=tk.LEFT, padx=2)
            label_addr.pack(side=tk.LEFT, padx=2)
            entry_addr.pack(side=tk.LEFT, padx=2)
        type_var.trace_add('write', lambda *a: toggle_params())
        toggle_params()
        # Кнопки
        def save_obj():
            name = entry_name.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Введите имя объекта!")
                return
            addr = entry_addr.get().strip()
            if not addr.isdigit():
                messagebox.showerror("Ошибка", "Адрес должен быть числом!")
                return
            obj = {'name': name, 'type': type_var.get(), 'addr': int(addr)}
            if type_var.get() == 'COM':
                obj['com'] = entry_com.get().strip()
                obj['baud'] = int(entry_baud.get().strip())
            else:
                obj['ip'] = entry_ip.get().strip()
                obj['port'] = int(entry_port.get().strip())
            self.objects.append(obj)
            self.save_objects()
            self.update_object_list()
            win.destroy()
        ttk.Button(win, text="Сохранить", command=save_obj).pack(pady=10)

    def start_poll(self):
        self.text_output.configure(state='normal')
        self.text_output.delete(1.0, tk.END)
        self.text_output.configure(state='disabled')
        self.btn_poll.config(state='disabled')
        threading.Thread(target=self.poll_device, daemon=True).start()

    def poll_device(self):
        """
        4. Опрос счетчика и вывод только ключевых параметров
        """
        # Перенаправляем print в текстовое поле
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.text_output)
        try:
            addr = int(self.entry_addr.get())
            if self.conn_type.get() == "COM":
                port = self.entry_com.get()
                baud = int(self.entry_baud.get())
                client = TEM104_Serial_Client(port=port, baudrate=baud, address=addr)
            else:
                host = self.entry_ip.get()
                port = int(self.entry_port.get())
                client = TEM104_TCP_Client(host=host, port=port, address=addr)
            client.connect()
            data = client.read_all_data()
            # Форматированный вывод только нужных параметров
            print(f"  Статус: ОНЛАЙН | Протокол: {getattr(client, 'protocol_type', '---')}")
            print(f"    Q (Энергия): {data.get('Q', '---'):.3f}")
            print(f"    M1 (Масса):  {data.get('M1', '---'):.3f}")
            print(f"    T1 (Темп.):  {data.get('T1', '---'):.2f} °C")
            print(f"    T2 (Темп.):  {data.get('T2', '---'):.2f} °C")
            print(f"    G1 (Расход): {data.get('G1', '---'):.3f} м³/ч")
            print(f"    T_нар (Наработка): {int(data.get('T_nar', 0) / 3600)} ч.\n")
            client.disconnect()
        except Exception as e:
            print(f"\nОШИБКА: {e}")
        finally:
            sys.stdout = old_stdout
            self.btn_poll.config(state='normal')

if __name__ == "__main__":
    app = TEM104GUI()
    app.mainloop() 