# -*- coding: utf-8 -*-
"""
Улучшенные компоненты GUI для приложения TEM-104.
Включает валидацию, прогресс-бары и улучшенную обработку ошибок.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
from typing import Optional, Callable, Any, Dict
import re
import logging

logger = logging.getLogger(__name__)


class ValidatedEntry(ttk.Entry):
    """
    Поле ввода с валидацией.
    
    Использование:
        entry = ValidatedEntry(
            parent,
            validator='ip',  # или 'port', 'number', 'com_port', или функция
            error_message="Неверный формат IP адреса"
        )
    """
    
    # Предустановленные валидаторы
    VALIDATORS = {
        'ip': lambda s: bool(re.match(r'^(\d{1,3}\.){3}\d{1,3}$', s) and 
                            all(0 <= int(p) <= 255 for p in s.split('.'))),
        'port': lambda s: s.isdigit() and 1 <= int(s) <= 65535,
        'number': lambda s: s.isdigit(),
        'com_port': lambda s: bool(re.match(r'^COM\d+$', s, re.IGNORECASE)),
        'baudrate': lambda s: s in ['300', '600', '1200', '2400', '4800', 
                                    '9600', '19200', '38400', '57600', '115200'],
        'address': lambda s: s.isdigit() and 1 <= int(s) <= 247
    }
    
    def __init__(
        self, 
        parent, 
        validator: Optional[str | Callable] = None,
        error_message: str = "Неверный формат",
        default_value: str = "",
        **kwargs
    ):
        """
        Инициализация валидируемого поля.
        
        Args:
            parent: Родительский виджет
            validator: Имя валидатора или функция валидации
            error_message: Сообщение об ошибке
            default_value: Значение по умолчанию
            **kwargs: Дополнительные параметры для ttk.Entry
        """
        super().__init__(parent, **kwargs)
        
        # Настройка валидатора
        if isinstance(validator, str):
            self.validator = self.VALIDATORS.get(validator)
        else:
            self.validator = validator
        
        self.error_message = error_message
        self.is_valid = True
        self.default_style = "TEntry"
        self.error_style = "Error.TEntry"
        
        # Установка значения по умолчанию
        if default_value:
            self.insert(0, default_value)
        
        # Привязка событий
        self.bind('<FocusOut>', self._validate)
        self.bind('<KeyRelease>', self._on_key_release)
        
        # Создание всплывающей подсказки
        self.tooltip = None
        
    def _validate(self, event=None) -> bool:
        """Выполняет валидацию поля."""
        value = self.get().strip()
        
        # Пустое поле считается валидным (если не требуется обязательное заполнение)
        if not value:
            self._set_valid()
            return True
        
        if self.validator:
            try:
                if self.validator(value):
                    self._set_valid()
                    return True
                else:
                    self._set_invalid()
                    return False
            except Exception as e:
                logger.debug(f"Ошибка валидации: {e}")
                self._set_invalid()
                return False
        
        self._set_valid()
        return True
    
    def _on_key_release(self, event):
        """Обработчик нажатия клавиш для мгновенной валидации."""
        if self.is_valid:
            # Сбрасываем стиль при вводе, если поле было невалидным
            self.configure(style=self.default_style)
    
    def _set_valid(self):
        """Устанавливает валидное состояние."""
        self.is_valid = True
        self.configure(style=self.default_style)
        self._hide_tooltip()
    
    def _set_invalid(self):
        """Устанавливает невалидное состояние."""
        self.is_valid = False
        self.configure(style=self.error_style)
        self._show_tooltip()
    
    def _show_tooltip(self):
        """Показывает всплывающую подсказку с ошибкой."""
        if self.tooltip:
            return
        
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.tooltip,
            text=self.error_message,
            background="#FFE4E4",
            foreground="#CC0000",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack()
        
        # Автоскрытие через 3 секунды
        self.after(3000, self._hide_tooltip)
    
    def _hide_tooltip(self):
        """Скрывает всплывающую подсказку."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
    
    def get_validated(self) -> Optional[str]:
        """
        Возвращает значение, если оно валидно, иначе None.
        
        Returns:
            Валидное значение или None
        """
        if self._validate():
            return self.get().strip()
        return None


class ProgressDialog(tk.Toplevel):
    """
    Диалог с прогресс-баром для длительных операций.
    
    Использование:
        with ProgressDialog(parent, "Опрос устройств") as progress:
            for i in range(100):
                progress.update(i, f"Обработка {i}/100")
                time.sleep(0.1)
    """
    
    def __init__(
        self,
        parent,
        title: str = "Выполнение операции",
        message: str = "Пожалуйста, подождите...",
        maximum: int = 100,
        cancelable: bool = True
    ):
        """
        Инициализация диалога прогресса.
        
        Args:
            parent: Родительское окно
            title: Заголовок окна
            message: Начальное сообщение
            maximum: Максимальное значение прогресса
            cancelable: Можно ли отменить операцию
        """
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        
        # Центрирование окна
        self.transient(parent)
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.winfo_screenheight() // 2) - (150 // 2)
        self.geometry(f"+{x}+{y}")
        
        # Флаг отмены
        self.cancelled = False
        self.maximum = maximum
        
        # Создание виджетов
        self.create_widgets(message, cancelable)
        
        # Блокировка родительского окна
        self.grab_set()
        
    def create_widgets(self, message: str, cancelable: bool):
        """Создает виджеты диалога."""
        # Сообщение
        self.label_message = ttk.Label(self, text=message, font=("Segoe UI", 10))
        self.label_message.pack(pady=(20, 10), padx=20)
        
        # Прогресс-бар
        self.progressbar = ttk.Progressbar(
            self,
            length=350,
            mode='determinate',
            maximum=self.maximum
        )
        self.progressbar.pack(pady=10, padx=20)
        
        # Метка прогресса
        self.label_progress = ttk.Label(self, text="0%", font=("Segoe UI", 9))
        self.label_progress.pack(pady=5)
        
        # Кнопка отмены
        if cancelable:
            self.btn_cancel = ttk.Button(
                self,
                text="Отмена",
                command=self.cancel
            )
            self.btn_cancel.pack(pady=10)
    
    def update(self, value: int, message: Optional[str] = None):
        """
        Обновляет прогресс и сообщение.
        
        Args:
            value: Текущее значение прогресса
            message: Новое сообщение (опционально)
        """
        if self.cancelled:
            return
        
        self.progressbar['value'] = value
        percentage = int((value / self.maximum) * 100)
        self.label_progress.config(text=f"{percentage}%")
        
        if message:
            self.label_message.config(text=message)
        
        self.update_idletasks()
    
    def cancel(self):
        """Отменяет операцию."""
        self.cancelled = True
        self.destroy()
    
    def __enter__(self):
        """Контекстный менеджер - вход."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход."""
        if not self.cancelled:
            self.destroy()


class AsyncPollingWorker(threading.Thread):
    """
    Асинхронный работник для опроса устройств.
    Предотвращает блокировку GUI во время опроса.
    """
    
    def __init__(
        self,
        task_queue: queue.Queue,
        result_callback: Callable,
        progress_callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None
    ):
        """
        Инициализация асинхронного работника.
        
        Args:
            task_queue: Очередь задач для выполнения
            result_callback: Функция для обработки результатов
            progress_callback: Функция для обновления прогресса
            error_callback: Функция для обработки ошибок
        """
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.result_callback = result_callback
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        self._stop_event = threading.Event()
        
    def run(self):
        """Основной цикл обработки задач."""
        while not self._stop_event.is_set():
            try:
                # Получаем задачу из очереди с таймаутом
                task = self.task_queue.get(timeout=0.1)
                
                if task is None:  # Сигнал остановки
                    break
                
                # Выполняем задачу
                try:
                    result = self._execute_task(task)
                    self.result_callback(task, result)
                except Exception as e:
                    logger.error(f"Ошибка выполнения задачи: {e}")
                    if self.error_callback:
                        self.error_callback(task, e)
                
                # Обновляем прогресс
                if self.progress_callback:
                    self.progress_callback()
                
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Критическая ошибка в работнике: {e}")
    
    def _execute_task(self, task: Dict[str, Any]) -> Any:
        """
        Выполняет задачу опроса.
        
        Args:
            task: Словарь с параметрами задачи
            
        Returns:
            Результат выполнения задачи
        """
        # Здесь должна быть логика опроса устройства
        # Это заглушка для демонстрации
        time.sleep(0.5)  # Имитация работы
        return {"status": "OK", "data": task}
    
    def stop(self):
        """Останавливает работника."""
        self._stop_event.set()


class DeviceStatusIndicator(ttk.Frame):
    """
    Индикатор статуса устройства с цветовой индикацией.
    """
    
    COLORS = {
        'online': '#00FF00',
        'offline': '#FF0000',
        'warning': '#FFA500',
        'unknown': '#808080',
        'connecting': '#0080FF'
    }
    
    def __init__(self, parent, device_name: str = "Устройство", **kwargs):
        """
        Инициализация индикатора статуса.
        
        Args:
            parent: Родительский виджет
            device_name: Имя устройства
            **kwargs: Дополнительные параметры для Frame
        """
        super().__init__(parent, **kwargs)
        
        self.device_name = device_name
        self.status = 'unknown'
        
        # Создание виджетов
        self.create_widgets()
    
    def create_widgets(self):
        """Создает виджеты индикатора."""
        # Имя устройства
        self.label_name = ttk.Label(self, text=self.device_name, font=("Segoe UI", 10, "bold"))
        self.label_name.pack(side=tk.LEFT, padx=5)
        
        # Индикатор (цветной круг)
        self.canvas = tk.Canvas(self, width=16, height=16, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=2)
        
        self.indicator = self.canvas.create_oval(2, 2, 14, 14, 
                                                 fill=self.COLORS['unknown'],
                                                 outline="")
        
        # Текст статуса
        self.label_status = ttk.Label(self, text="Неизвестно", font=("Segoe UI", 9))
        self.label_status.pack(side=tk.LEFT, padx=5)
    
    def set_status(self, status: str, message: Optional[str] = None):
        """
        Устанавливает статус устройства.
        
        Args:
            status: Статус ('online', 'offline', 'warning', 'unknown', 'connecting')
            message: Дополнительное сообщение
        """
        if status not in self.COLORS:
            status = 'unknown'
        
        self.status = status
        self.canvas.itemconfig(self.indicator, fill=self.COLORS[status])
        
        # Обновление текста статуса
        status_texts = {
            'online': 'В сети',
            'offline': 'Не в сети',
            'warning': 'Предупреждение',
            'unknown': 'Неизвестно',
            'connecting': 'Подключение...'
        }
        
        text = status_texts.get(status, 'Неизвестно')
        if message:
            text = f"{text}: {message}"
        
        self.label_status.config(text=text)
    
    def pulse(self):
        """Создает эффект пульсации для индикатора."""
        if self.status == 'connecting':
            # Анимация для состояния подключения
            self._pulse_animation()
    
    def _pulse_animation(self):
        """Анимация пульсации."""
        # Простая анимация изменения размера
        for size in [18, 16, 18, 16]:
            offset = (20 - size) // 2
            self.canvas.coords(self.indicator, offset, offset, 
                              20-offset, 20-offset)
            self.update_idletasks()
            time.sleep(0.1)
