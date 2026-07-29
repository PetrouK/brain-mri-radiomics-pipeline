try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None


class NullProgress:
    def update(self, task=None, message=None, current=None, total=None):
        pass

    def close(self):
        pass


class ProgressWindow:
    def __init__(self, title="Progress"):
        if tk is None or ttk is None:
            raise RuntimeError("tkinter is not available.")

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("420x160")
        self.root.resizable(False, False)

        self.task_var = tk.StringVar(value="Starting...")
        self.message_var = tk.StringVar(value="")
        self.percent_var = tk.StringVar(value="0%")
        self.progress_var = tk.DoubleVar(value=0)

        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        task_label = ttk.Label(
            frame,
            textvariable=self.task_var,
            font=("Segoe UI", 11, "bold"),
        )

        task_label.pack(anchor="w")

        message_label = ttk.Label(
            frame,
            textvariable=self.message_var,
            font=("Segoe UI", 9),
        )

        message_label.pack(anchor="w", pady=(6, 12))

        self.progress_bar = ttk.Progressbar(
            frame,
            variable=self.progress_var,
            maximum=100,
        )
        self.progress_bar.pack(fill="x")

        percent_label = ttk.Label(
            frame,
            textvariable=self.percent_var,
            font=("Segoe UI", 9),
        )

        percent_label.pack(anchor="e", pady=(6, 0))

    def update(self, task=None, message=None, current=None, total=None):

        if task is not None:
            self.task_var.set(str(task))

        if message is not None:
            self.message_var.set(str(message))

        if current is not None and total is not None and total > 0:
            percent = (current / total) * 100
            self.progress_var.set(percent)
            self.percent_var.set(f"{percent:.0f}%")

        self.root.update_idletasks()
        self.root.update()

    def close(self):
        self.root.destroy()


def create_progress_window(title="Progress"):
    try:
        return ProgressWindow(title=title)
    except Exception:
        return NullProgress()
