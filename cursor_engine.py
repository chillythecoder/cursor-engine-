"""Cursor Engine - pick any image or GIF and make it your Windows cursor."""
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
import engine

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
FILETYPES = [("Images", "*.png *.gif *.jpg *.jpeg *.webp *.bmp *.ico *.apng *.tiff"), ("All files", "*.*")]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Cursor Engine")
        self.geometry("420x560")
        self.resizable(False, False)
        self.src, self.preview, self.delays, self.i = None, [], [], 0

        ctk.CTkLabel(self, text="Cursor Engine", font=("Segoe UI", 26, "bold")).pack(pady=(18, 2))
        ctk.CTkLabel(self, text="Turn any image or GIF into your cursor", text_color="gray").pack()

        self.view = ctk.CTkLabel(self, text="No file selected", width=160, height=160,
                                 fg_color=("gray80", "gray17"), corner_radius=12)
        self.view.pack(pady=16)

        ctk.CTkButton(self, text="Choose file...", command=self.pick).pack()

        self.size_lbl = ctk.CTkLabel(self, text="Size: 48 px")
        self.size_lbl.pack(pady=(16, 0))
        self.size = ctk.CTkSlider(self, from_=16, to=128, number_of_steps=28, command=self.on_size)
        self.size.set(48)
        self.size.pack()

        ctk.CTkLabel(self, text="Click point (hotspot)").pack(pady=(12, 0))
        self.hot = ctk.CTkSegmentedButton(self, values=["Top-left", "Center"], command=lambda _: self.load())
        self.hot.set("Top-left")
        self.hot.pack()

        ctk.CTkLabel(self, text="Apply to").pack(pady=(12, 0))
        self.target = ctk.CTkOptionMenu(self, values=list(engine.TARGETS))
        self.target.pack()

        ctk.CTkButton(self, text="Apply cursor", height=40, command=self.apply).pack(pady=(20, 6))
        ctk.CTkButton(self, text="Reset to Windows default", fg_color="gray30",
                      hover_color="gray40", command=self.reset).pack()
        self.status = ctk.CTkLabel(self, text="", text_color="gray")
        self.status.pack(pady=10)
        self.tick()

    def on_size(self, v):
        self.size_lbl.configure(text=f"Size: {int(v)} px")
        self.after_cancel(getattr(self, "_t", "")) if getattr(self, "_t", None) else None
        self._t = self.after(250, self.load)

    def pick(self):
        p = filedialog.askopenfilename(filetypes=FILETYPES)
        if p:
            self.src = p
            self.load()

    def load(self):
        if not self.src:
            return
        try:
            frames, self.delays, _ = engine.load_frames(self.src, int(self.size.get()),
                                                        self.hot.get() == "Center")
        except Exception as e:
            messagebox.showerror("Cursor Engine", f"Couldn't read that file:\n{e}")
            return
        self.preview = [ctk.CTkImage(f, f, size=(128, 128)) for f in frames]
        self.i = 0
        self.status.configure(text=f"{len(frames)} frame(s) loaded")

    def tick(self):
        if self.preview:
            self.view.configure(image=self.preview[self.i % len(self.preview)], text="")
            delay = self.delays[self.i % len(self.delays)]
            self.i += 1
            self.after(max(20, delay), self.tick)
        else:
            self.after(200, self.tick)

    def apply(self):
        if not self.src:
            return messagebox.showinfo("Cursor Engine", "Choose a file first.")
        if sys.platform != "win32":
            return messagebox.showerror("Cursor Engine", "Applying cursors only works on Windows.")
        try:
            path, n = engine.build_cursor(self.src, int(self.size.get()), self.hot.get() == "Center")
            engine.apply_cursor(path, engine.TARGETS[self.target.get()])
            self.status.configure(text=f"Applied! ({'animated' if n > 1 else 'static'})")
        except Exception as e:
            messagebox.showerror("Cursor Engine", str(e))

    def reset(self):
        try:
            engine.reset_cursors()
            self.status.configure(text="Restored your original cursors")
        except Exception as e:
            messagebox.showerror("Cursor Engine", str(e))


if __name__ == "__main__":
    App().mainloop()
