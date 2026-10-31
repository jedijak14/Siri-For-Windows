"""Visible Tk desktop interface for Siri for Windows."""

import base64
import math
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from actions import ActionError, open_onedrive, open_photos
from ollama_client import OllamaClient, OllamaError
from speech import SpeechError, listen_once, speak


BACKGROUND = "#090b18"
PANEL = "#12162a"
TEXT = "#f4f4fb"
MUTED = "#a8adc4"
MAX_IMAGE_BYTES = 8 * 1024 * 1024

TOOL_ACTIONS = {
    "[TOOL:PHOTOS_OPEN]": ("Open Windows Photos", open_photos),
    "[TOOL:ONEDRIVE_OPEN]": ("Open the OneDrive folder", open_onedrive),
}

ORB_STOPS = [
    (0.0, (244, 241, 255)),
    (0.28, (88, 206, 255)),
    (0.58, (119, 106, 255)),
    (0.82, (204, 119, 218)),
    (1.0, (227, 188, 112)),
]


def _mix_color(start, end, amount):
    channels = [round(a + (b - a) * amount) for a, b in zip(start, end)]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _orb_color(position):
    for index in range(len(ORB_STOPS) - 1):
        left_at, left_color = ORB_STOPS[index]
        right_at, right_color = ORB_STOPS[index + 1]
        if position <= right_at:
            amount = (position - left_at) / (right_at - left_at)
            return _mix_color(left_color, right_color, amount)
    return "#e3bc70"


class SiriWindow:
    def __init__(self, root):
        self.root = root
        self.client = OllamaClient()
        self.pending_image = None
        self.busy = False
        self.speak_replies = tk.BooleanVar(value=False)
        self.events = queue.Queue()
        self.orb_phase = 0

        root.title("Siri for Windows")
        root.geometry("480x760")
        root.minsize(420, 620)
        root.configure(background=BACKGROUND)
        self._build_ui()
        self._animate_orb()
        self._poll_events()

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BACKGROUND)
        header.pack(fill="x", padx=22, pady=(18, 8))

        tk.Label(
            header, text="SIRI", font=("Segoe UI", 13, "bold"),
            fg=TEXT, bg=BACKGROUND,
        ).pack()
        tk.Label(
            header, text="LOCAL INTELLIGENCE · ON-DEVICE", font=("Segoe UI", 8),
            fg=MUTED, bg=BACKGROUND,
        ).pack(pady=(2, 0))

        self.orb = tk.Canvas(
            self.root, height=154, background=BACKGROUND,
            highlightthickness=0, borderwidth=0,
        )
        self.orb.pack(fill="x", padx=20)

        self.status = tk.StringVar(value="Ready · Actions always ask first")
        tk.Label(
            self.root, textvariable=self.status, font=("Segoe UI", 9),
            fg=MUTED, bg=BACKGROUND,
        ).pack(pady=(0, 12))

        self.transcript = scrolledtext.ScrolledText(
            self.root,
            wrap="word",
            state="disabled",
            height=14,
            font=("Segoe UI", 10),
            background=PANEL,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            padx=14,
            pady=12,
            borderwidth=0,
        )
        self.transcript.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self.transcript.tag_configure("user", foreground="#b8aaff", spacing1=10)
        self.transcript.tag_configure("assistant", foreground=TEXT, spacing1=10)
        self._append("assistant", "Hi. I’m your local assistant. Ask a question, attach an image, or use the microphone.")

        self.image_label = tk.StringVar(value="")
        tk.Label(
            self.root, textvariable=self.image_label, font=("Segoe UI", 8),
            fg="#d4cfff", bg=BACKGROUND, anchor="w",
        ).pack(fill="x", padx=22, pady=(0, 4))

        self.composer = tk.Text(
            self.root, height=3, wrap="word", font=("Segoe UI", 10),
            background=PANEL, foreground=TEXT, insertbackground=TEXT,
            relief="flat", padx=12, pady=10, borderwidth=0,
        )
        self.composer.pack(fill="x", padx=18)
        self.composer.bind("<Return>", self._on_return)
        self.composer.bind("<Shift-Return>", lambda _event: None)

        controls = tk.Frame(self.root, bg=BACKGROUND)
        controls.pack(fill="x", padx=18, pady=(8, 14))
        first_row = tk.Frame(controls, bg=BACKGROUND)
        first_row.pack(fill="x")
        self._button(first_row, "Image", self._choose_image).pack(side="left", padx=(0, 6))
        self._button(first_row, "Listen", self._listen).pack(side="left", padx=6)
        self._button(first_row, "Speak", self._speak_latest).pack(side="left", padx=6)
        second_row = tk.Frame(controls, bg=BACKGROUND)
        second_row.pack(fill="x", pady=(8, 0))
        self._button(second_row, "Polish", self._polish).pack(side="left")
        tk.Checkbutton(
            second_row, text="Speak replies", variable=self.speak_replies,
            fg=MUTED, bg=BACKGROUND, selectcolor=PANEL, activebackground=BACKGROUND,
            activeforeground=TEXT, font=("Segoe UI", 8), relief="flat",
        ).pack(side="left", padx=(12, 0))
        self._button(second_row, "Send", self._send, primary=True).pack(side="right")

    def _button(self, parent, label, command, primary=False):
        return tk.Button(
            parent,
            text=label,
            command=command,
            font=("Segoe UI", 9, "bold" if primary else "normal"),
            fg=TEXT if primary else MUTED,
            bg="#6359ba" if primary else PANEL,
            activeforeground=TEXT,
            activebackground="#786de0" if primary else "#202541",
            relief="flat",
            padx=13,
            pady=7,
            cursor="hand2",
        )

    def _animate_orb(self):
        canvas = self.orb
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        center_x = width / 2
        center_y = 77
        pulse = 2.5 * (1 + math.sin(self.orb_phase / 8))
        radius = 48 + pulse
        for index in range(48):
            ratio = index / 47
            current_radius = radius * (1 - ratio * 0.88)
            color = _orb_color(ratio)
            canvas.create_oval(
                center_x - current_radius,
                center_y - current_radius,
                center_x + current_radius,
                center_y + current_radius,
                fill=color,
                outline=color,
            )
        for start, color in ((25, "#edc878"), (150, "#77dcff"), (270, "#bc9aff")):
            canvas.create_arc(
                center_x - radius - 4,
                center_y - radius - 4,
                center_x + radius + 4,
                center_y + radius + 4,
                start=start + self.orb_phase,
                extent=86,
                style="arc",
                outline=color,
                width=2,
            )
        self.orb_phase += 1
        self.root.after(70, self._animate_orb)

    def _append(self, role, content):
        self.transcript.configure(state="normal")
        label = "You" if role == "user" else "Siri"
        tag = "user" if role == "user" else "assistant"
        self.transcript.insert("end", f"{label}\n", tag)
        self.transcript.insert("end", content.strip() + "\n\n", tag)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _on_return(self, event):
        if not (event.state & 0x0001):
            self._send()
            return "break"
        return None

    def _choose_image(self):
        path = filedialog.askopenfilename(
            title="Choose an image to send to your local model",
            filetypes=[
                ("Supported images", "*.png *.jpg *.jpeg *.webp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.pending_image = path
            self.image_label.set(f"Attached: {os.path.basename(path)}")

    def _send(self):
        if self.busy:
            return
        prompt = self.composer.get("1.0", "end").strip()
        if not prompt and not self.pending_image:
            return
        image_path = self.pending_image
        if not prompt:
            prompt = "Describe this image."
        self.composer.delete("1.0", "end")
        self.pending_image = None
        self.image_label.set("")
        display_prompt = prompt
        if image_path:
            display_prompt += f"\n[Image attached: {os.path.basename(image_path)}]"
        self._append("user", display_prompt)
        self._start_worker(
            lambda: self._request_answer(prompt, image_path),
            self._show_answer,
        )

    def _polish(self):
        if self.busy:
            return
        text = self.composer.get("1.0", "end").strip()
        if not text:
            return
        self._append("user", f"Polish this text:\n{text}")
        self._start_worker(
            lambda: self.client.polish_text(text),
            self._show_polished,
        )

    def _show_polished(self, revised_text):
        self.composer.delete("1.0", "end")
        self.composer.insert("1.0", revised_text)
        self._append("assistant", revised_text)

    def _request_answer(self, prompt, image_path):
        image_data = None
        if image_path:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read(MAX_IMAGE_BYTES + 1)
            if len(image_bytes) > MAX_IMAGE_BYTES:
                raise ValueError("Choose an image smaller than 8 MB.")
            image_data = [base64.b64encode(image_bytes).decode("ascii")]
        return self.client.generate(prompt, image_data=image_data)

    def _show_answer(self, answer):
        action = TOOL_ACTIONS.get(answer)
        if action:
            description, callback = action
            if messagebox.askyesno(
                "Siri for Windows",
                f"Allow Siri to {description.lower()}?",
                parent=self.root,
            ):
                try:
                    callback()
                    answer = f"Done — {description}."
                except ActionError as exc:
                    answer = f"Could not complete the action: {exc}"
            else:
                answer = "Cancelled. I did not perform that action."
        self._append("assistant", answer)
        if self.client.model:
            self.status.set(f"Ready · Local model: {self.client.model}")
        if self.speak_replies.get():
            self._start_worker(lambda: speak(answer), lambda _result: None)

    def _listen(self):
        if not self.busy:
            self._start_worker(
                listen_once,
                self._insert_transcript,
                status="Listening with Windows speech…",
            )

    def _insert_transcript(self, transcript):
        self.composer.insert("end", transcript)
        self.composer.focus_set()

    def _speak_latest(self):
        if self.busy:
            return
        latest = self.transcript.get("1.0", "end").strip()
        segments = latest.rsplit("Siri\n", 1)
        if len(segments) < 2:
            return
        response = segments[-1].split("\n\n", 1)[0].strip()
        if response:
            self._start_worker(
                lambda: speak(response),
                lambda _result: None,
                status="Speaking with Windows voice…",
            )

    def _start_worker(self, operation, on_success, status="Working locally…"):
        self.busy = True
        self.status.set(status)

        def run():
            try:
                result = operation()
            except (OllamaError, ActionError, SpeechError, OSError, ValueError) as exc:
                self.events.put(("error", str(exc)))
            except (RuntimeError, TypeError) as exc:
                self.events.put(("error", f"Unexpected error: {exc}"))
            else:
                self.events.put(("success", on_success, result))
        threading.Thread(target=run, daemon=True).start()

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                self.busy = False
                model = f" · Local model: {self.client.model}" if self.client.model else ""
                self.status.set(f"Ready · Actions always ask first{model}")
                if event[0] == "error":
                    messagebox.showerror("Siri for Windows", event[1], parent=self.root)
                else:
                    _, callback, result = event
                    callback(result)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)


def launch():
    root = tk.Tk()
    SiriWindow(root)
    root.mainloop()
