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
        self.geometry("600x500")
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        # 1. Заголовок
        ttk.Label(self, text="Утилита для опроса счетчиков ТЭМ-104", font=("Arial", 14, "bold")).pack(pady=8)

        # 2. Переключатель типа подключения
        self.conn_type = tk.StringVar(value="COM")
        frame_type = ttk.Frame(self)
        frame_type.pack(pady=4)
        ttk.Radiobutton(frame_type, text="Локальный COM-порт", variable=self.conn_type, value="COM", command=self.toggle_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(frame_type, text="Сеть TCP/IP (модем)", variable=self.conn_type, value="TCP", command=self.toggle_fields).pack(side=tk.LEFT, padx=10)

        # 3. Поля для параметров
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

        # 4. Кнопка "Опросить"
        self.btn_poll = ttk.Button(self, text="Опросить", command=self.start_poll)
        self.btn_poll.pack(pady=8)

        # 5. Текстовое поле для вывода
        self.text_output = scrolledtext.ScrolledText(self, width=72, height=18, state='disabled', font=("Consolas", 10))
        self.text_output.pack(padx=8, pady=4)

        # 6. Кнопка "Выход"
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

    def start_poll(self):
        self.text_output.configure(state='normal')
        self.text_output.delete(1.0, tk.END)
        self.text_output.configure(state='disabled')
        self.btn_poll.config(state='disabled')
        threading.Thread(target=self.poll_device, daemon=True).start()

    def poll_device(self):
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
            client.read_all_data()
            client.disconnect()
        except Exception as e:
            print(f"\nОШИБКА: {e}")
        finally:
            sys.stdout = old_stdout
            self.btn_poll.config(state='normal')

if __name__ == "__main__":
    app = TEM104GUI()
    app.mainloop() 