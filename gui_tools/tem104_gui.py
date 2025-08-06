# -*- coding: utf-8 -*-
"""
Графический интерфейс для опроса счетчиков ТЭМ-104 (ARVAS, TESMART и др.)
Работает через COM-порт или TCP/IP, использует существующую логику из test104.py.
"""

import io
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Добавляем родительскую директорию в путь, чтобы найти core_library
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_library.test104 import TEM104_Serial_Client, TEM104_TCP_Client


OBJECTS_FILE = "objects.json"


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


class AddObjectDialog(tk.Toplevel):
    """Диалоговое окно для добавления нового объекта."""
    def __init__(self, parent):
        """Инициализирует диалоговое окно."""
        super().__init__(parent)
        self.parent = parent
        self.title("Добавить объект")
        self.geometry("350x250")
        self.resizable(False, False)
        self.widgets = {}
        self.create_widgets()

    def create_widgets(self):
        """Создает и размещает все виджеты в диалоговом окне."""
        # Имя
        ttk.Label(self, text="Имя объекта:").pack(pady=4)
        self.widgets['entry_name'] = ttk.Entry(self, width=30)
        self.widgets['entry_name'].pack(pady=2)
        # Тип
        self.type_var = tk.StringVar(value=self.parent.conn_type.get())
        frame_type = ttk.Frame(self)
        frame_type.pack(pady=2)
        ttk.Radiobutton(frame_type, text="COM", variable=self.type_var, value="COM").pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(frame_type, text="TCP", variable=self.type_var, value="TCP").pack(side=tk.LEFT, padx=8)
        # Параметры
        self.widgets['frame_params'] = ttk.Frame(self)
        self.widgets['frame_params'].pack(pady=2)
        self.widgets['label_com'] = ttk.Label(self.widgets['frame_params'], text="COM-порт:")
        self.widgets['entry_com'] = ttk.Entry(self.widgets['frame_params'], width=10)
        self.widgets['entry_com'].insert(0, self.parent.widgets['entry_com'].get())
        self.widgets['label_baud'] = ttk.Label(self.widgets['frame_params'], text="Скорость:")
        self.widgets['entry_baud'] = ttk.Entry(self.widgets['frame_params'], width=8)
        self.widgets['entry_baud'].insert(0, self.parent.widgets['entry_baud'].get())
        self.widgets['label_ip'] = ttk.Label(self.widgets['frame_params'], text="IP-адрес:")
        self.widgets['entry_ip'] = ttk.Entry(self.widgets['frame_params'], width=15)
        self.widgets['entry_ip'].insert(0, self.parent.widgets['entry_ip'].get())
        self.widgets['label_port'] = ttk.Label(self.widgets['frame_params'], text="TCP-порт:")
        self.widgets['entry_port'] = ttk.Entry(self.widgets['frame_params'], width=8)
        self.widgets['entry_port'].insert(0, self.parent.widgets['entry_port'].get())
        self.widgets['label_addr'] = ttk.Label(self.widgets['frame_params'], text="Адрес:")
        self.widgets['entry_addr'] = ttk.Entry(self.widgets['frame_params'], width=5)
        self.widgets['entry_addr'].insert(0, self.parent.widgets['entry_addr'].get())
        self.type_var.trace_add('write', lambda *a: self.toggle_params())
        self.toggle_params()
        # Кнопки
        ttk.Button(self, text="Сохранить", command=self.save_obj).pack(pady=10)

    def toggle_params(self):
        """Переключает видимость полей в зависимости от типа подключения (COM/TCP)."""
        for w_name in ('label_com', 'entry_com', 'label_baud', 'entry_baud', 'label_ip', 'entry_ip', 'label_port', 'entry_port'):
            self.widgets[w_name].pack_forget()
        if self.type_var.get() == 'COM':
            self.widgets['label_com'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_com'].pack(side=tk.LEFT, padx=2)
            self.widgets['label_baud'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_baud'].pack(side=tk.LEFT, padx=2)
        else:
            self.widgets['label_ip'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_ip'].pack(side=tk.LEFT, padx=2)
            self.widgets['label_port'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_port'].pack(side=tk.LEFT, padx=2)
        self.widgets['label_addr'].pack(side=tk.LEFT, padx=2)
        self.widgets['entry_addr'].pack(side=tk.LEFT, padx=2)

    def save_obj(self):
        """Сохраняет новый объект и закрывает диалоговое окно."""
        name = self.widgets['entry_name'].get().strip()
        if not name:
            messagebox.showerror("Ошибка", "Введите имя объекта!")
            return
        addr = self.widgets['entry_addr'].get().strip()
        if not addr.isdigit():
            messagebox.showerror("Ошибка", "Адрес должен быть числом!")
            return
        obj = {'name': name, 'type': self.type_var.get(), 'addr': int(addr)}
        if self.type_var.get() == 'COM':
            obj['com'] = self.widgets['entry_com'].get().strip()
            obj['baud'] = int(self.widgets['entry_baud'].get().strip())
        else:
            obj['ip'] = self.widgets['entry_ip'].get().strip()
            obj['port'] = int(self.widgets['entry_port'].get().strip())
        self.parent.objects.append(obj)
        self.parent.save_objects()
        self.parent.update_object_list()
        self.destroy()


class TEM104GUI(tk.Tk):
    """Основной класс графического интерфейса для утилиты опроса ТЭМ-104."""
    def __init__(self):
        super().__init__()
        self.title("Опрос счетчиков ТЭМ-104")
        self.geometry("600x540")
        self.resizable(False, False)
        self.objects = []
        self.widgets = {}
        self.load_objects()
        self.create_widgets()

    def load_objects(self):
        """Загружает список объектов из файла JSON."""
        if os.path.exists(OBJECTS_FILE):
            try:
                with open(OBJECTS_FILE, "r", encoding="utf-8") as f:
                    self.objects = json.load(f)
            except Exception:
                self.objects = []
        else:
            self.objects = []

    def save_objects(self):
        """Сохраняет список объектов в файл JSON."""
        with open(OBJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.objects, f, ensure_ascii=False, indent=2)

    def create_widgets(self):
        """Создает и размещает все виджеты в главном окне."""
        # 1. Заголовок
        ttk.Label(self, text="Утилита для опроса счетчиков ТЭМ-104", font=("Arial", 14, "bold")).pack(pady=8)

        # 2. Список объектов
        frame_obj = ttk.Frame(self)
        frame_obj.pack(pady=4)
        ttk.Label(frame_obj, text="Объект:").pack(side=tk.LEFT)
        self.obj_var = tk.StringVar()
        self.widgets['combo_obj'] = ttk.Combobox(frame_obj, textvariable=self.obj_var, state="readonly", width=30)
        self.widgets['combo_obj'].pack(side=tk.LEFT, padx=4)
        self.update_object_list()
        self.widgets['combo_obj'].bind("<<ComboboxSelected>>", self.on_object_selected)
        ttk.Button(frame_obj, text="Добавить объект", command=self.add_object_dialog).pack(side=tk.LEFT, padx=4)

        # 3. Переключатель типа подключения
        self.conn_type = tk.StringVar(value="COM")
        frame_type = ttk.Frame(self)
        frame_type.pack(pady=4)
        ttk.Radiobutton(frame_type, text="Локальный COM-порт", variable=self.conn_type, value="COM", command=self.toggle_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(frame_type, text="Сеть TCP/IP (модем)", variable=self.conn_type, value="TCP", command=self.toggle_fields).pack(side=tk.LEFT, padx=10)

        # 4. Поля для параметров
        self.widgets['frame_params'] = ttk.Frame(self)
        self.widgets['frame_params'].pack(pady=4)
        # COM
        self.widgets['label_com'] = ttk.Label(self.widgets['frame_params'], text="COM-порт:")
        self.widgets['entry_com'] = ttk.Entry(self.widgets['frame_params'], width=10)
        self.widgets['entry_com'].insert(0, "COM3")
        self.widgets['label_baud'] = ttk.Label(self.widgets['frame_params'], text="Скорость:")
        self.widgets['entry_baud'] = ttk.Entry(self.widgets['frame_params'], width=8)
        self.widgets['entry_baud'].insert(0, "9600")
        # TCP
        self.widgets['label_ip'] = ttk.Label(self.widgets['frame_params'], text="IP-адрес:")
        self.widgets['entry_ip'] = ttk.Entry(self.widgets['frame_params'], width=15)
        self.widgets['entry_ip'].insert(0, "192.168.1.100")
        self.widgets['label_port'] = ttk.Label(self.widgets['frame_params'], text="TCP-порт:")
        self.widgets['entry_port'] = ttk.Entry(self.widgets['frame_params'], width=8)
        self.widgets['entry_port'].insert(0, "5009")
        # Общий адрес
        self.widgets['label_addr'] = ttk.Label(self.widgets['frame_params'], text="Адрес счетчика:")
        self.widgets['entry_addr'] = ttk.Entry(self.widgets['frame_params'], width=5)
        self.widgets['entry_addr'].insert(0, "1")
        self.toggle_fields()

        # 5. Кнопка "Опросить"
        self.widgets['btn_poll'] = ttk.Button(self, text="Опросить", command=self.start_poll)
        self.widgets['btn_poll'].pack(pady=8)

        # 6. Текстовое поле для вывода
        self.widgets['text_output'] = scrolledtext.ScrolledText(self, width=72, height=16, state='disabled', font=("Consolas", 10))
        self.widgets['text_output'].pack(padx=8, pady=4)

        # 7. Кнопка "Выход"
        ttk.Button(self, text="Выход", command=self.destroy).pack(pady=4)

    def toggle_fields(self):
        """Переключает видимость полей в зависимости от типа подключения (COM/TCP)."""
        # Очищаем
        for widget in self.widgets['frame_params'].winfo_children():
            widget.pack_forget()
        if self.conn_type.get() == "COM":
            self.widgets['label_com'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_com'].pack(side=tk.LEFT, padx=2)
            self.widgets['label_baud'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_baud'].pack(side=tk.LEFT, padx=2)
        else:
            self.widgets['label_ip'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_ip'].pack(side=tk.LEFT, padx=2)
            self.widgets['label_port'].pack(side=tk.LEFT, padx=2)
            self.widgets['entry_port'].pack(side=tk.LEFT, padx=2)
        self.widgets['label_addr'].pack(side=tk.LEFT, padx=2)
        self.widgets['entry_addr'].pack(side=tk.LEFT, padx=2)

    def update_object_list(self):
        """Обновляет выпадающий список объектов."""
        names = [obj['name'] for obj in self.objects]
        self.widgets['combo_obj']['values'] = names
        if names:
            self.widgets['combo_obj'].current(0)

    def on_object_selected(self, _event=None):
        """Заполняет поля данными выбранного объекта."""
        idx = self.widgets['combo_obj'].current()
        if idx < 0 or idx >= len(self.objects):
            return
        obj = self.objects[idx]
        self.conn_type.set(obj['type'])
        if obj['type'] == 'COM':
            self.widgets['entry_com'].delete(0, tk.END)
            self.widgets['entry_com'].insert(0, obj.get('com', 'COM3'))
            self.widgets['entry_baud'].delete(0, tk.END)
            self.widgets['entry_baud'].insert(0, str(obj.get('baud', '9600')))
        else:
            self.widgets['entry_ip'].delete(0, tk.END)
            self.widgets['entry_ip'].insert(0, obj.get('ip', '192.168.1.100'))
            self.widgets['entry_port'].delete(0, tk.END)
            self.widgets['entry_port'].insert(0, str(obj.get('port', '5009')))
        self.widgets['entry_addr'].delete(0, tk.END)
        self.widgets['entry_addr'].insert(0, str(obj.get('addr', '1')))
        self.toggle_fields()

    def add_object_dialog(self):
        """Открывает диалоговое окно для добавления нового объекта."""
        AddObjectDialog(self)

    def start_poll(self):
        """Запускает опрос устройства в отдельном потоке."""
        self.widgets['text_output'].configure(state='normal')
        self.widgets['text_output'].delete(1.0, tk.END)
        self.widgets['text_output'].configure(state='disabled')
        self.widgets['btn_poll'].config(state='disabled')
        threading.Thread(target=self.poll_device, daemon=True).start()

    def poll_device(self):
        """
        4. Опрос счетчика и вывод только ключевых параметров
        """
        # Перенаправляем print в текстовое поле
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.widgets['text_output'])
        try:
            addr = int(self.widgets['entry_addr'].get())
            if self.conn_type.get() == "COM":
                port = self.widgets['entry_com'].get()
                baud = int(self.widgets['entry_baud'].get())
                client = TEM104_Serial_Client(port=port, baudrate=baud, address=addr)
            else:
                host = self.widgets['entry_ip'].get()
                port = int(self.widgets['entry_port'].get())
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
            self.widgets['btn_poll'].config(state='normal')

if __name__ == "__main__":
    app = TEM104GUI()
    app.mainloop()
