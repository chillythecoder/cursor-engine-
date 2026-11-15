"""Cursor Engine - pick any image or GIF and make it your Windows cursor."""
import os, sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import engine

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
FILETYPES = [("Images and cursors", "*.png *.gif *.jpg *.jpeg *.webp *.bmp *.ico *.apng *.tiff *.cur *.ani"), ("All files", "*.*")]


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Cursor Engine")
        if sys.platform == "win32":
            # CTk sets its own icon shortly after startup, so set ours after that
            self.after(250, lambda: self.iconbitmap(resource("icon.ico")))
        self.geometry("800x600")
        self.resizable(False, False)
        self.src, self.preview, self.delays, self.i = None, [], [], 0
        self.thumbs = {}

        # ---- left: create a cursor ----
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(20, 10), pady=10)
        ctk.CTkLabel(left, text="Cursor Engine", font=("Segoe UI", 26, "bold")).pack(pady=(8, 2))
        ctk.CTkLabel(left, text="Turn any image or GIF into your cursor", text_color="gray").pack()

        self.view = ctk.CTkLabel(left, text="No file selected", width=160, height=160,
                                 fg_color=("gray80", "gray17"), corner_radius=12)
        self.view.pack(pady=14)
        ctk.CTkButton(left, text="Choose file...", command=self.pick).pack()

        self.size_lbl = ctk.CTkLabel(left, text="Size: 48 px")
        self.size_lbl.pack(pady=(14, 0))
        self.size = ctk.CTkSlider(left, from_=16, to=128, number_of_steps=28, command=self.on_size)
        self.size.set(48)
        self.size.pack()

        ctk.CTkLabel(left, text="Click point (hotspot)").pack(pady=(10, 0))
        self.hot = ctk.CTkSegmentedButton(left, values=["Top-left", "Center"], command=lambda _: self.load())
        self.hot.set("Top-left")
        self.hot.pack()

        ctk.CTkLabel(left, text="Apply to").pack(pady=(10, 0))
        self.target = ctk.CTkOptionMenu(left, values=list(engine.TARGETS))
        self.target.pack()

        ctk.CTkButton(left, text="Apply cursor", height=40, command=self.apply).pack(pady=(18, 4))
        self.status = ctk.CTkLabel(left, text="", text_color="gray")
        self.status.pack(pady=6)

        # ---- right: switch between saved cursors ----
        right = ctk.CTkFrame(self)
        right.pack(side="right", fill="both", expand=True, padx=(10, 20), pady=20)
        ctk.CTkLabel(right, text="Your cursors", font=("Segoe UI", 18, "bold")).pack(pady=(12, 0))
        ctk.CTkLabel(right, text="Click Use to switch back anytime", text_color="gray").pack()
        self.lib = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.lib.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkButton(right, text="Reset to Windows default", fg_color="gray30",
                      hover_color="gray40", command=self.reset).pack(pady=(0, 14))

        self.refresh_library()
        self.tick()

    # ---- preview ----
    def on_size(self, v):
        self.size_lbl.configure(text=f"Size: {int(v)} px")
        if getattr(self, "_t", None):
            self.after_cancel(self._t)
        self._t = self.after(250, self.load)

    def pick(self):
        p = filedialog.askopenfilename(filetypes=FILETYPES)
        if p:
            self.src = p
            self.load()

    def load(self):
        if not self.src:
            return
        native = engine.is_native(self.src)
        state = "disabled" if native else "normal"
        self.size.configure(state=state)
        self.hot.configure(state=state)
        self.size_lbl.configure(text="Size: original" if native else f"Size: {int(self.size.get())} px")
        try:
            frames, self.delays = engine.load_any(self.src, int(self.size.get()),
                                                  self.hot.get() == "Center")
        except Exception as e:
            messagebox.showerror("Cursor Engine", f"Couldn't read that file:\n{e}")
            return
        if native:   # keep tiny cursors crisp in the preview
            frames = [f.resize((128, 128), Image.NEAREST) for f in frames]
        self.preview = [ctk.CTkImage(f, f, size=(128, 128)) for f in frames]
        self.i = 0
        note = " · original size and click point kept" if native else ""
        self.status.configure(text=f"{len(frames)} frame(s) loaded{note}")

    def tick(self):
        if self.preview:
            self.view.configure(image=self.preview[self.i % len(self.preview)], text="")
            delay = self.delays[self.i % len(self.delays)]
            self.i += 1
            self.after(max(20, delay), self.tick)
        else:
            self.after(200, self.tick)

    # ---- library ----
    def thumb(self, path):
        if path not in self.thumbs:
            try:
                f = engine.load_any(path, 32)[0][0].resize((32, 32))
                self.thumbs[path] = ctk.CTkImage(f, f, size=(32, 32))
            except Exception:
                self.thumbs[path] = None
        return self.thumbs[path]

    def refresh_library(self):
        for w in self.lib.winfo_children():
            w.destroy()
        items = engine.load_library()
        if not items:
            ctk.CTkLabel(self.lib, text="Cursors you apply will show up here.",
                         text_color="gray").pack(pady=30)
        for e in items:
            row = ctk.CTkFrame(self.lib)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text="", image=self.thumb(e["file"]), width=40).pack(side="left", padx=6, pady=4)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=e["name"][:22], anchor="w", font=("Segoe UI", 13, "bold")).pack(fill="x")
            ctk.CTkLabel(info, text=f'{str(e["size"]) + "px" if e["size"] else "original size"} · {e["target"]}', anchor="w",
                         text_color="gray", font=("Segoe UI", 11)).pack(fill="x")
            ctk.CTkButton(row, text="✕", width=28, fg_color="gray30", hover_color="#a33",
                          command=lambda e=e: self.delete(e)).pack(side="right", padx=(2, 6))
            ctk.CTkButton(row, text="Use", width=52,
                          command=lambda e=e: self.use(e)).pack(side="right", padx=2)

    def use(self, entry):
        if not self.check_windows():
            return
        try:
            n = engine.apply_entry(entry)
            self.status.configure(text=f'Switched to "{entry["name"]}"')
        except Exception as ex:
            messagebox.showerror("Cursor Engine", str(ex))

    def delete(self, entry):
        engine.remove_from_library(entry)
        self.refresh_library()

    # ---- actions ----
    def check_windows(self):
        if sys.platform != "win32":
            messagebox.showerror("Cursor Engine", "Applying cursors only works on Windows.")
            return False
        return True

    def apply(self):
        if not self.src:
            return messagebox.showinfo("Cursor Engine", "Choose a file first.")
        if not self.check_windows():
            return
        try:
            size, center = int(self.size.get()), self.hot.get() == "Center"
            if engine.is_native(self.src):
                size, center = 0, False
            path, n = engine.build_cursor(self.src, size, center)
            engine.apply_cursor(path, engine.TARGETS[self.target.get()])
            entry = engine.add_to_library(self.src, size, center, self.target.get())
            self.status.configure(text=f"Applied! ({'animated' if n > 1 else 'static'}) and saved")
            self.refresh_library()
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
