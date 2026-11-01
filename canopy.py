"""Canopy: a frameless PyQt6 voice-assistant panel for Windows."""

from __future__ import annotations

import ctypes
import math
import sys
import threading
import time
from collections import deque
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Deque, Optional, Sequence

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QThread,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QHideEvent,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPalette,
    QPaintEvent,
    QPen,
    QScreen,
    QShortcut,
    QShowEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


CANOPY_MOD_ALT = 0x0001
CANOPY_MOD_NOREPEAT = 0x4000
CANOPY_VK_SPACE = 0x20
CANOPY_WM_HOTKEY = 0x0312
CANOPY_WM_QUIT = 0x0012
CANOPY_PM_NOREMOVE = 0x0000

# RegisterHotKey IDs for a thread without an HWND must be in 0x0000–0xBFFF.
CANOPY_HOTKEY_ID = 0x0CA1

CANOPY_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
CANOPY_DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY = 19
CANOPY_DWMWA_SYSTEMBACKDROP_TYPE = 38
CANOPY_DWMWA_WINDOW_CORNER_PREFERENCE = 33
CANOPY_DWMWA_MICA_EFFECT_LEGACY = 1029

CANOPY_DWMSBT_TRANSIENTWINDOW = 3
CANOPY_DWMWCP_DONOTROUND = 1
CANOPY_ENABLE_GLOBAL_HOTKEY = sys.platform == "win32"


class _CanopyPOINT(ctypes.Structure):
    """Win32 POINT layout used by the Canopy hotkey message pump."""

    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class _CanopyMSG(ctypes.Structure):
    """Win32 MSG layout used by the Canopy hotkey message pump."""

    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("pt", _CanopyPOINT),
        ("lPrivate", wintypes.DWORD),
    ]


def _canopy_user32() -> Any:
    """Load user32 on Windows; callers guard access by platform."""
    return ctypes.WinDLL("user32", use_last_error=True)


def _apply_canopy_native_backdrop(hwnd: int) -> bool:
    """Apply Windows Acrylic/Mica where available, retaining Qt as fallback.

    Windows 11's transient system backdrop provides native Acrylic for this
    compact assistant panel. Older Windows builds may support the legacy Mica
    attribute or the older Accent Policy Acrylic effect.
    """
    if sys.platform != "win32" or not hwnd:
        return False

    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        set_attribute = dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = (
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        set_attribute.restype = ctypes.c_long

        def apply_attribute(attribute: int, value: int) -> bool:
            value_buffer = ctypes.c_int(value)
            result = set_attribute(
                wintypes.HWND(hwnd),
                wintypes.DWORD(attribute),
                ctypes.cast(ctypes.byref(value_buffer), ctypes.c_void_p),
                wintypes.DWORD(ctypes.sizeof(value_buffer)),
            )
            return int(result) == 0

        if not apply_attribute(CANOPY_DWMWA_USE_IMMERSIVE_DARK_MODE, 1):
            apply_attribute(CANOPY_DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY, 1)

        apply_attribute(
            CANOPY_DWMWA_WINDOW_CORNER_PREFERENCE,
            CANOPY_DWMWCP_DONOTROUND,
        )

        if apply_attribute(
            CANOPY_DWMWA_SYSTEMBACKDROP_TYPE,
            CANOPY_DWMSBT_TRANSIENTWINDOW,
        ):
            return True

        if apply_attribute(
            CANOPY_DWMWA_MICA_EFFECT_LEGACY,
            1,
        ):
            return True

    except (AttributeError, OSError, TypeError, ctypes.ArgumentError):
        pass

    try:
        user32 = _canopy_user32()

        class _CanopyAccentPolicy(ctypes.Structure):
            _fields_ = [
                ("accent_state", wintypes.DWORD),
                ("accent_flags", wintypes.DWORD),
                ("gradient_color", wintypes.DWORD),
                ("animation_id", wintypes.DWORD),
            ]

        class _CanopyWindowCompositionAttributeData(ctypes.Structure):
            _fields_ = [
                ("attribute", ctypes.c_int),
                ("data", ctypes.c_void_p),
                ("size_of_data", ctypes.c_size_t),
            ]

        set_composition_attribute = user32.SetWindowCompositionAttribute
        set_composition_attribute.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(_CanopyWindowCompositionAttributeData),
        )
        set_composition_attribute.restype = wintypes.BOOL

        accent_policy = _CanopyAccentPolicy(
            4,             # ACCENT_ENABLE_ACRYLICBLURBEHIND
            2,
            0xCC121715,    # dark translucent tint, ARGB
            0,
        )
        attribute_data = _CanopyWindowCompositionAttributeData(
            19,            # WCA_ACCENT_POLICY
            ctypes.cast(ctypes.pointer(accent_policy), ctypes.c_void_p),
            ctypes.sizeof(accent_policy),
        )
        return bool(
            set_composition_attribute(
                wintypes.HWND(hwnd),
                ctypes.byref(attribute_data),
            )
        )

    except (AttributeError, OSError, TypeError, ctypes.ArgumentError):
        return False


@dataclass(frozen=True)
class CanopyHotkeyBinding:
    """Immutable Win32 hotkey registration parameters."""

    modifiers: int = CANOPY_MOD_ALT | CANOPY_MOD_NOREPEAT
    virtual_key: int = CANOPY_VK_SPACE
    hotkey_id: int = CANOPY_HOTKEY_ID
    display_name: str = "Alt+Space"


class CanopyGlobalHotkeyListener(QThread):
    """Thread-owned Windows global-hotkey message loop for Canopy.

    The worker creates its own native message queue, registers the configured
    binding with RegisterHotKey, and forwards WM_HOTKEY as a Qt signal. The
    worker owns registration and unregistration, keeping all widget operations
    on Qt's GUI thread.
    """

    canopyHotkeyActivated = pyqtSignal()
    canopyHotkeyRegistered = pyqtSignal()
    canopyHotkeyError = pyqtSignal(str)

    def __init__(
        self,
        binding: Optional[CanopyHotkeyBinding] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CanopyGlobalHotkeyListener")

        self._binding = binding or CanopyHotkeyBinding()
        self._stop_requested = threading.Event()
        self._queue_ready = threading.Event()
        self._state_lock = threading.Lock()
        self._native_thread_id: Optional[int] = None
        self._user32: Optional[Any] = None
        self._registered = False

    def start_listener(self) -> None:
        """Start the native hotkey listener if it is not already running."""
        if sys.platform != "win32":
            self.canopyHotkeyError.emit(
                "Canopy global hotkeys are available only on Windows."
            )
            return

        if self.isRunning():
            return

        self._stop_requested.clear()
        self._queue_ready.clear()
        self.start()

    def run(self) -> None:
        """Register the hotkey and pump native messages until Canopy stops."""
        try:
            if sys.platform != "win32":
                self.canopyHotkeyError.emit(
                    "Canopy global hotkeys are available only on Windows."
                )
                return

            self._configure_native_api()
            user32 = self._user32
            if user32 is None:
                self.canopyHotkeyError.emit(
                    "Canopy could not initialize its Windows hotkey listener."
                )
                return

            message = _CanopyMSG()

            # Ensure this thread owns a message queue before another thread
            # attempts to post WM_QUIT to it.
            user32.PeekMessageW(
                ctypes.byref(message),
                None,
                0,
                0,
                CANOPY_PM_NOREMOVE,
            )

            with self._state_lock:
                self._native_thread_id = int(user32.GetCurrentThreadId())

            self._queue_ready.set()

            if self._stop_requested.is_set():
                return

            if not self._register_hotkey():
                return

            self.canopyHotkeyRegistered.emit()

            while not self._stop_requested.is_set():
                result = int(
                    user32.GetMessageW(
                        ctypes.byref(message),
                        None,
                        0,
                        0,
                    )
                )

                if result == -1:
                    error_code = ctypes.get_last_error()
                    self.canopyHotkeyError.emit(
                        "Canopy's hotkey message loop failed "
                        f"(Windows error {error_code})."
                    )
                    break

                if result == 0:
                    break

                self._dispatch_native_message(
                    int(message.message),
                    int(message.wParam),
                    int(message.lParam),
                )

        except Exception as error:
            self.canopyHotkeyError.emit(
                "Canopy's hotkey listener failed "
                f"({type(error).__name__})."
            )

        finally:
            self._unregister_hotkey()
            with self._state_lock:
                self._native_thread_id = None
            self._queue_ready.set()

    def stop(self, timeout_ms: int = 1500) -> None:
        """Request a native message-loop exit and wait up to ``timeout_ms``."""
        self._stop_requested.set()

        if not self.isRunning():
            return

        timeout_seconds = max(0, timeout_ms) / 1000.0
        deadline = time.monotonic() + timeout_seconds
        self._queue_ready.wait(
            max(0.0, deadline - time.monotonic())
        )

        with self._state_lock:
            thread_id = self._native_thread_id

        if thread_id and self._user32 is not None:
            try:
                self._user32.PostThreadMessageW(
                    wintypes.DWORD(thread_id),
                    wintypes.UINT(CANOPY_WM_QUIT),
                    ctypes.c_size_t(0),
                    ctypes.c_ssize_t(0),
                )
            except (AttributeError, OSError, TypeError, ctypes.ArgumentError):
                pass

        remaining_ms = max(
            0,
            int((deadline - time.monotonic()) * 1000),
        )
        self.wait(remaining_ms)

    def _configure_native_api(self) -> None:
        """Declare Win32 signatures before calling the global-hotkey APIs."""
        user32 = _canopy_user32()
        self._user32 = user32

        user32.GetCurrentThreadId.argtypes = ()
        user32.GetCurrentThreadId.restype = wintypes.DWORD

        user32.PeekMessageW.argtypes = (
            ctypes.POINTER(_CanopyMSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
            wintypes.UINT,
        )
        user32.PeekMessageW.restype = wintypes.BOOL

        user32.GetMessageW.argtypes = (
            ctypes.POINTER(_CanopyMSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        )
        user32.GetMessageW.restype = ctypes.c_int

        user32.RegisterHotKey.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        )
        user32.RegisterHotKey.restype = wintypes.BOOL

        user32.UnregisterHotKey.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
        )
        user32.UnregisterHotKey.restype = wintypes.BOOL

        user32.PostThreadMessageW.argtypes = (
            wintypes.DWORD,
            wintypes.UINT,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )
        user32.PostThreadMessageW.restype = wintypes.BOOL

    def _register_hotkey(self) -> bool:
        """Register the configured Canopy shortcut on this worker thread."""
        if self._user32 is None:
            return False

        registered = bool(
            self._user32.RegisterHotKey(
                None,
                self._binding.hotkey_id,
                self._binding.modifiers,
                self._binding.virtual_key,
            )
        )

        if not registered:
            error_code = ctypes.get_last_error()
            self.canopyHotkeyError.emit(
                f"Canopy could not register {self._binding.display_name} "
                f"(Windows error {error_code})."
            )
            return False

        self._registered = True
        return True

    def _unregister_hotkey(self) -> None:
        """Release the Canopy shortcut on the thread that registered it."""
        if not self._registered or self._user32 is None:
            return

        try:
            self._user32.UnregisterHotKey(
                None,
                self._binding.hotkey_id,
            )
        finally:
            self._registered = False

    def _dispatch_native_message(
        self,
        message_id: int,
        wparam: int,
        lparam: int,
    ) -> None:
        """Translate this thread's WM_HOTKEY message into a Qt signal."""
        del lparam

        if (
            message_id == CANOPY_WM_HOTKEY
            and wparam == self._binding.hotkey_id
        ):
            self.canopyHotkeyActivated.emit()


@dataclass
class CanopyForegroundContext:
    """Foreground-window data captured for one Canopy panel session."""

    foreground_hwnd: Optional[int] = None
    captured: bool = False
    dim_layer_active: bool = False


class CanopyWin32WindowController(QObject):
    """Capture the previously active application before Canopy appears.

    This controller deliberately avoids modifying unrelated application
    windows. The captured HWND is available to an integration layer that owns
    any optional dim overlay or focus-restoration policy.
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CanopyWin32WindowController")
        self._context = CanopyForegroundContext()

    @property
    def context(self) -> CanopyForegroundContext:
        """Return the current Canopy foreground-session context."""
        return self._context

    def capture_foreground_window(self) -> Optional[int]:
        """Capture the current Win32 foreground HWND before panel activation."""
        self._context = CanopyForegroundContext()

        if sys.platform != "win32":
            return None

        try:
            user32 = _canopy_user32()
            user32.GetForegroundWindow.argtypes = ()
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.IsWindow.argtypes = (wintypes.HWND,)
            user32.IsWindow.restype = wintypes.BOOL

            raw_hwnd = user32.GetForegroundWindow()
            if not raw_hwnd:
                return None

            hwnd = int(raw_hwnd)
            if not user32.IsWindow(wintypes.HWND(hwnd)):
                return None

            self._context.foreground_hwnd = hwnd
            self._context.captured = True
            return hwnd

        except (AttributeError, OSError, TypeError, ctypes.ArgumentError):
            return None

    def prepare_for_panel_open(
        self,
        foreground_hwnd: Optional[int],
    ) -> None:
        """Store the active-window context before Canopy takes focus."""
        self._context.foreground_hwnd = foreground_hwnd
        self._context.captured = foreground_hwnd is not None
        self._context.dim_layer_active = False

    def restore_after_panel_close(
        self,
        foreground_hwnd: Optional[int],
    ) -> None:
        """Release Canopy's session state after the panel has retracted."""
        del foreground_hwnd
        self._context = CanopyForegroundContext()


class CanopyPanelState:
    """String constants representing Canopy's geometry-transition states."""

    HIDDEN = "hidden"
    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"


class CanopyActivityLine(QWidget):
    """Low-cost animated progress line for live Canopy speech activity."""

    CYCLE_SECONDS = 1.15
    TIMER_INTERVAL_MS = 16

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CanopyActivityLine")
        self.setAccessibleName("Canopy audio activity indicator")
        self.setAccessibleDescription("Canopy audio activity is idle.")
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(10)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._streaming = False
        self._phase = 0.0
        self._last_tick = time.monotonic()
        self._track_color = QColor(245, 248, 242, 42)
        self._segment_color = QColor(183, 199, 176, 235)

        self._timer = QTimer(self)
        self._timer.setObjectName("CanopyActivityTimer")
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self.TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    @property
    def is_streaming(self) -> bool:
        """Whether the Canopy voice activity indicator is active."""
        return self._streaming

    def set_streaming(self, streaming: bool) -> None:
        """Start or stop the animated progress segment."""
        streaming = bool(streaming)
        if streaming == self._streaming:
            return

        self._streaming = streaming
        self._phase = 0.0
        self._last_tick = time.monotonic()
        self.setAccessibleDescription(
            "Canopy audio activity is streaming."
            if streaming
            else "Canopy audio activity is idle."
        )

        if streaming and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()

        self.update()

    def _advance(self) -> None:
        """Advance the segment by elapsed monotonic time."""
        if not self._streaming or not self.isVisible():
            self._timer.stop()
            return

        now = time.monotonic()
        elapsed = max(0.0, now - self._last_tick)
        self._last_tick = now
        self._phase = (self._phase + elapsed / self.CYCLE_SECONDS) % 1.0
        self.update()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._streaming:
            self._last_tick = time.monotonic()
            self._timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event

        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        track_height = 2
        track_y = (height - track_height) // 2

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(
            QRect(0, track_y, width, track_height),
            self._track_color,
        )

        if self._streaming:
            segment_width = min(width, max(36, int(width * 0.22)))
            travel_width = width + segment_width
            segment_x = int(self._phase * travel_width) - segment_width
            painter.fillRect(
                QRect(segment_x, track_y, segment_width, track_height),
                self._segment_color,
            )

        painter.end()


@dataclass(frozen=True)
class CanopyAudioFrame:
    """One normalized audio callback frame for Canopy's waveform renderer."""

    captured_at_monotonic: float
    rms: float
    peak: float
    samples: tuple[float, ...] = ()


class CanopyAudioWaveformPainter(QWidget):
    """Thread-safe audio-frame ingestion and vector waveform visualization.

    Audio callbacks may call ``push_audio_frame`` from a capture thread. Frames
    enter a bounded, lock-protected queue; a GUI-thread timer drains it and the
    painter renders a single vector path or a compact RMS/peak representation.
    """

    DEFAULT_FRAME_CAPACITY = 96
    DEFAULT_HEIGHT = 10
    TIMER_INTERVAL_MS = 33

    _streaming_requested = pyqtSignal(bool)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        frame_capacity: int = DEFAULT_FRAME_CAPACITY,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CanopyAudioWaveformPainter")
        self.setAccessibleName("Canopy audio waveform")
        self.setAccessibleDescription("Canopy waveform visualization.")
        self.setFixedHeight(self.DEFAULT_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._frame_capacity = max(2, int(frame_capacity))
        self._incoming_frames: Deque[CanopyAudioFrame] = deque(
            maxlen=self._frame_capacity
        )
        self._incoming_lock = threading.Lock()
        self._frames: Deque[CanopyAudioFrame] = deque(
            maxlen=self._frame_capacity
        )
        self._streaming = False
        self._phase = 0.0
        self._last_tick = time.monotonic()

        self._track_color = QColor(245, 248, 242, 42)
        self._wave_color = QColor(183, 199, 176, 235)

        self._timer = QTimer(self)
        self._timer.setObjectName("CanopyWaveformTimer")
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self.TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        self._streaming_requested.connect(
            self._apply_streaming,
            Qt.ConnectionType.QueuedConnection,
        )

    @staticmethod
    def _clamp(value: object, low: float, high: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0

        if not math.isfinite(number):
            return 0.0

        return max(low, min(high, number))

    def set_streaming(self, streaming: bool) -> None:
        """Request a streaming-state update from any calling thread."""
        self._streaming_requested.emit(bool(streaming))

    @pyqtSlot(bool)
    def _apply_streaming(self, streaming: bool) -> None:
        """Apply the streaming state on the waveform widget's GUI thread."""
        if streaming == self._streaming:
            return

        self._streaming = streaming
        self._phase = 0.0
        self._last_tick = time.monotonic()

        if not streaming:
            with self._incoming_lock:
                self._incoming_frames.clear()
            self._frames.clear()

        if streaming and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()

        self.update()

    def push_audio_frame(self, frame: CanopyAudioFrame) -> None:
        """Queue one normalized frame without touching GUI-owned state."""
        if not isinstance(frame, CanopyAudioFrame):
            raise TypeError("Canopy expects a CanopyAudioFrame instance.")

        timestamp = self._clamp(
            frame.captured_at_monotonic,
            0.0,
            float("inf"),
        )
        if timestamp == 0.0:
            timestamp = time.monotonic()

        rms = abs(self._clamp(frame.rms, 0.0, 1.0))
        peak = max(rms, abs(self._clamp(frame.peak, 0.0, 1.0)))
        samples = tuple(
            self._clamp(sample, -1.0, 1.0)
            for sample in frame.samples
        )

        sanitized = CanopyAudioFrame(
            captured_at_monotonic=timestamp,
            rms=rms,
            peak=peak,
            samples=samples,
        )

        with self._incoming_lock:
            self._incoming_frames.append(sanitized)

    def _drain_incoming_frames(self) -> bool:
        """Move callback frames into the GUI-thread-owned render buffer."""
        with self._incoming_lock:
            if not self._incoming_frames:
                return False

            pending = tuple(self._incoming_frames)
            self._incoming_frames.clear()

        self._frames.extend(pending)
        return True

    def _tick(self) -> None:
        """Drain audio frames and schedule a bounded-rate repaint."""
        if not self._streaming or not self.isVisible():
            self._timer.stop()
            return

        now = time.monotonic()
        elapsed = max(0.0, now - self._last_tick)
        self._last_tick = now
        self._phase = (self._phase + elapsed / 1.15) % 1.0

        self._drain_incoming_frames()
        self.update()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._streaming:
            self._last_tick = time.monotonic()
            self._timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event

        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        center_y = height / 2.0
        radius = max(1.0, (height - 2.0) / 2.0)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QPen(
                self._track_color,
                1.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(
            QPointF(0.0, center_y),
            QPointF(float(width), center_y),
        )

        if not self._streaming:
            painter.end()
            return

        frames = tuple(self._frames)
        if frames:
            samples: list[float] = []
            for frame in frames[-12:]:
                if frame.samples:
                    samples.extend(frame.samples)

            if samples:
                if len(samples) > 1024:
                    samples = samples[-1024:]

                point_count = min(max(2, width), len(samples))
                path = QPainterPath()

                for index in range(point_count):
                    source_index = round(
                        index * (len(samples) - 1) / (point_count - 1)
                    )
                    x = index * width / max(1, point_count - 1)
                    y = center_y - samples[source_index] * radius

                    if index == 0:
                        path.moveTo(QPointF(x, y))
                    else:
                        path.lineTo(QPointF(x, y))

                waveform_pen = QPen(
                    self._wave_color,
                    1.5,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.setPen(waveform_pen)
                painter.drawPath(path)

            else:
                bar_count = min(len(frames), max(1, width // 4))
                waveform_pen = QPen(
                    self._wave_color,
                    1.5,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.setPen(waveform_pen)

                for index in range(bar_count):
                    frame_index = round(
                        index * (len(frames) - 1) / max(1, bar_count - 1)
                    )
                    frame = frames[frame_index]
                    amplitude = max(frame.rms, frame.peak * 0.55) * radius
                    if amplitude <= 0.35:
                        continue

                    x = (
                        (index + 0.5) * width / bar_count
                        if bar_count
                        else center_y
                    )
                    painter.drawLine(
                        QPointF(x, center_y - amplitude),
                        QPointF(x, center_y + amplitude),
                    )

        else:
            segment_width = min(40.0, max(12.0, width * 0.2))
            x = (
                self._phase * (width + segment_width)
                - segment_width
            )
            progress_pen = QPen(
                self._wave_color,
                2.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
            painter.setPen(progress_pen)
            painter.drawLine(
                QPointF(x, center_y),
                QPointF(x + segment_width, center_y),
            )

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(320, self.DEFAULT_HEIGHT)


class CanopyWindow(QWidget):
    """Frameless, translucent, top-centered Canopy assistant panel."""

    PANEL_WIDTH = 680
    PANEL_HEIGHT = 150
    HIDDEN_Y = -150
    SLIDE_DURATION_MS = 225

    canopyQuerySubmitted = pyqtSignal(str)
    canopyVisibilityChanged = pyqtSignal(bool)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        enable_global_hotkey: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CanopyWindow")
        self.setWindowTitle("Canopy")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Canopy voice assistant")
        self.setAccessibleDescription(
            "Canopy voice and text assistant input panel."
        )

        self._panel_state = CanopyPanelState.HIDDEN
        self._native_backdrop_attempted = False
        self._native_backdrop_applied = False
        self._active_foreground_hwnd: Optional[int] = None
        self._foreground_context_prepared = False
        self._connected_screen: Optional[QScreen] = None

        self._set_responsive_size()
        self._window_controller = CanopyWin32WindowController(self)
        self._build_interface()

        self._slide_animation = QPropertyAnimation(
            self,
            b"geometry",
            self,
        )
        self._slide_animation.setObjectName("CanopySlideAnimation")
        self._slide_animation.finished.connect(
            self._on_slide_animation_finished
        )

        self._input.installEventFilter(self)

        self._quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self._quit_shortcut.setObjectName("CanopyQuitShortcut")
        self._quit_shortcut.setContext(
            Qt.ShortcutContext.WindowShortcut
        )
        self._quit_shortcut.activated.connect(self._quit_application)

        self._hotkey_listener = CanopyGlobalHotkeyListener(parent=self)
        self._hotkey_listener.canopyHotkeyActivated.connect(
            self.toggle_panel
        )
        self._hotkey_listener.canopyHotkeyError.connect(
            self._on_hotkey_error
        )
        self._hotkey_listener.canopyHotkeyRegistered.connect(
            self._on_hotkey_registered
        )

        self._connect_screen_events()
        self.setGeometry(self._hidden_geometry())

        if enable_global_hotkey:
            self.start_global_hotkey_listener()

    @property
    def panel_state(self) -> str:
        """Return Canopy's current panel transition state."""
        return self._panel_state

    @property
    def active_foreground_hwnd(self) -> Optional[int]:
        """Return the HWND captured before the current panel-open session."""
        return self._active_foreground_hwnd

    @property
    def native_backdrop_applied(self) -> bool:
        """Whether a Windows-native backdrop was successfully requested."""
        return self._native_backdrop_applied

    def _primary_screen_geometry(self) -> QRect:
        """Return the primary monitor's full desktop geometry."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            return QRect(screen.geometry())

        return QRect(0, 0, 1920, 1080)

    def _set_responsive_size(self) -> None:
        """Fit the panel to the primary display while respecting its design."""
        screen_geometry = self._primary_screen_geometry()
        width = max(
            240,
            min(self.PANEL_WIDTH, max(1, screen_geometry.width() - 48)),
        )
        height = min(
            self.PANEL_HEIGHT,
            max(96, screen_geometry.height() - 16),
        )
        self.setFixedSize(width, height)

    def _target_geometry(self) -> QRect:
        """Return the top-centered final rectangle on the primary display."""
        screen_geometry = self._primary_screen_geometry()
        x = screen_geometry.x() + (
            screen_geometry.width() - self.width()
        ) // 2

        return QRect(
            x,
            screen_geometry.top(),
            self.width(),
            self.height(),
        )

    def _hidden_geometry(self) -> QRect:
        """Return the fully retracted rectangle above the primary display."""
        target = self._target_geometry()
        return QRect(
            target.x(),
            target.y() + self.HIDDEN_Y,
            target.width(),
            target.height(),
        )

    def _connect_screen_events(self) -> None:
        """Keep Canopy centered if the primary display changes."""
        application = QApplication.instance()
        if application is not None:
            primary_screen_changed = getattr(
                application,
                "primaryScreenChanged",
                None,
            )
            if primary_screen_changed is not None:
                primary_screen_changed.connect(
                    self._on_primary_screen_changed
                )

        self._connect_primary_screen(QApplication.primaryScreen())

    def _connect_primary_screen(
        self,
        screen: Optional[QScreen],
    ) -> None:
        if screen is self._connected_screen:
            return

        if self._connected_screen is not None:
            try:
                self._connected_screen.geometryChanged.disconnect(
                    self._on_primary_screen_geometry_changed
                )
            except (TypeError, RuntimeError):
                pass

        self._connected_screen = screen
        if screen is not None:
            screen.geometryChanged.connect(
                self._on_primary_screen_geometry_changed
            )

    def _on_primary_screen_changed(
        self,
        screen: Optional[QScreen],
    ) -> None:
        self._connect_primary_screen(screen)
        self._apply_primary_screen_layout()

    def _on_primary_screen_geometry_changed(
        self,
        *_args: object,
    ) -> None:
        self._apply_primary_screen_layout()

    def _apply_primary_screen_layout(self) -> None:
        self._set_responsive_size()

        if self._panel_state == CanopyPanelState.HIDDEN:
            self.setGeometry(self._hidden_geometry())
        elif self._panel_state == CanopyPanelState.OPEN:
            self.setGeometry(self._target_geometry())
        elif self._panel_state == CanopyPanelState.OPENING:
            self._animate_geometry_to(
                self._target_geometry(),
                QEasingCurve.Type.OutCubic,
            )
        elif self._panel_state == CanopyPanelState.CLOSING:
            self._animate_geometry_to(
                self._hidden_geometry(),
                QEasingCurve.Type.InCubic,
            )

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setObjectName("CanopyWindowLayout")
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._surface = QFrame(self)
        self._surface.setObjectName("CanopySurface")
        self._surface.setFrameShape(QFrame.Shape.NoFrame)
        self._surface.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )
        root_layout.addWidget(self._surface)

        surface_layout = QVBoxLayout(self._surface)
        surface_layout.setObjectName("CanopySurfaceLayout")
        surface_layout.setContentsMargins(24, 15, 24, 13)
        surface_layout.setSpacing(0)
        surface_layout.addStretch(1)

        self._input_frame = QFrame(self._surface)
        self._input_frame.setObjectName("CanopyInputFrame")
        self._input_frame.setProperty("focused", False)
        self._input_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._input_frame.setFixedHeight(62)
        self._input_frame.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        input_layout = QVBoxLayout(self._input_frame)
        input_layout.setObjectName("CanopyInputLayout")
        input_layout.setContentsMargins(13, 5, 13, 5)
        input_layout.setSpacing(2)

        self._input = QLineEdit(self._input_frame)
        self._input.setObjectName("CanopyInput")
        self._input.setAccessibleName("Canopy request input")
        self._input.setAccessibleDescription(
            "Type a request or insert a Canopy speech transcript."
        )
        self._input.setPlaceholderText("Ask Canopy")
        self._input.setFrame(False)
        self._input.setClearButtonEnabled(False)
        self._input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._input.setMinimumHeight(34)
        self._input.setTextMargins(0, 0, 0, 0)
        self._input.setTextFormat(Qt.TextFormat.PlainText)

        input_font = QFont("Segoe UI", 19)
        input_font.setWeight(QFont.Weight.Normal)
        self._input.setFont(input_font)

        input_palette = self._input.palette()
        input_palette.setColor(
            QPalette.ColorRole.PlaceholderText,
            QColor(205, 213, 207, 155),
        )
        self._input.setPalette(input_palette)
        self._input.returnPressed.connect(self._submit_query)

        self._indicator_stack = QStackedWidget(self._input_frame)
        self._indicator_stack.setObjectName("CanopyIndicatorStack")
        self._indicator_stack.setFixedHeight(10)

        self._activity_line = CanopyActivityLine(self._indicator_stack)
        self._waveform_painter = CanopyAudioWaveformPainter(
            self._indicator_stack
        )
        self._indicator_stack.addWidget(self._activity_line)
        self._indicator_stack.addWidget(self._waveform_painter)
        self._indicator_stack.setCurrentWidget(self._activity_line)

        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(self._indicator_stack, 0)
        surface_layout.addWidget(self._input_frame)
        surface_layout.addSpacing(9)

        footer_layout = QHBoxLayout()
        footer_layout.setObjectName("CanopyFooterLayout")
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)

        self._hint_label = QLabel("VOICE OR TEXT", self._surface)
        self._hint_label.setObjectName("CanopyHintLabel")
        self._hint_label.setAccessibleName("Canopy input hint")
        self._hint_label.setTextFormat(Qt.TextFormat.PlainText)
        self._hint_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self._status_label = QLabel("READY", self._surface)
        self._status_label.setObjectName("CanopyStatusLabel")
        self._status_label.setAccessibleName("Canopy assistant status")
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self._status_label.setMinimumWidth(86)

        hint_font = QFont("Segoe UI", 8)
        hint_font.setWeight(QFont.Weight.Medium)
        hint_font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            0.9,
        )
        self._hint_label.setFont(hint_font)

        status_font = QFont("Segoe UI", 9)
        status_font.setWeight(QFont.Weight.DemiBold)
        status_font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            1.1,
        )
        self._status_label.setFont(status_font)

        footer_layout.addWidget(self._hint_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._status_label)
        surface_layout.addLayout(footer_layout)
        surface_layout.addStretch(1)

        self._input.textEdited.connect(self._on_input_edited)

        self.setStyleSheet(
            """
            QWidget#CanopyWindow {
                background-color: transparent;
            }

            QFrame#CanopySurface {
                background-color: rgba(18, 23, 21, 205);
                border: 1px solid rgba(239, 244, 238, 58);
            }

            QFrame#CanopyInputFrame {
                background-color: rgba(255, 255, 255, 7);
                border: 1px solid rgba(239, 244, 238, 60);
            }

            QFrame#CanopyInputFrame[focused="true"] {
                border: 1px solid rgba(218, 229, 215, 150);
            }

            QLineEdit#CanopyInput {
                color: rgba(250, 251, 247, 248);
                background-color: transparent;
                border: none;
                selection-background-color: rgba(135, 158, 129, 150);
                font-family: "Segoe UI";
                font-size: 19px;
            }

            QStackedWidget#CanopyIndicatorStack {
                background-color: transparent;
                border: none;
            }

            QLabel#CanopyHintLabel {
                color: rgba(211, 219, 212, 150);
                background-color: transparent;
                font-family: "Segoe UI";
                font-size: 8px;
            }

            QLabel#CanopyStatusLabel {
                color: rgba(239, 244, 238, 218);
                background-color: transparent;
                font-family: "Segoe UI";
                font-size: 9px;
            }
            """
        )

    def _prepare_for_slide_in(self) -> None:
        """Capture the active application before Canopy takes focus."""
        self._foreground_context_prepared = True
        self._active_foreground_hwnd = (
            self._window_controller.capture_foreground_window()
        )
        self._window_controller.prepare_for_panel_open(
            self._active_foreground_hwnd
        )

    def _restore_foreground_context(self) -> None:
        """Release Canopy's temporary foreground-session data."""
        if not self._foreground_context_prepared:
            return

        self._window_controller.restore_after_panel_close(
            self._active_foreground_hwnd
        )
        self._foreground_context_prepared = False
        self._active_foreground_hwnd = None

    def _focus_input(self) -> None:
        """Give the request field immediate keyboard focus."""
        if not self.isVisible():
            return

        self._input.setCursorPosition(len(self._input.text()))
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def show_panel(self, focus_input: bool = True) -> None:
        """Animate Canopy from y=-150 to the primary screen's top edge."""
        if (
            self.isVisible()
            and self._panel_state
            in (CanopyPanelState.OPENING, CanopyPanelState.OPEN)
        ):
            if focus_input:
                self._focus_input()
            return

        self._slide_animation.stop()

        if not self.isVisible():
            # Capture the foreground HWND before showing or activating Canopy.
            self._prepare_for_slide_in()
            self.setGeometry(self._hidden_geometry())

        self._panel_state = CanopyPanelState.OPENING
        self.show()
        self.raise_()
        self.activateWindow()

        if focus_input:
            self._focus_input()
            QTimer.singleShot(0, self._focus_input)

        self._animate_geometry_to(
            self._target_geometry(),
            QEasingCurve.Type.OutCubic,
        )

    def hide_panel(self) -> None:
        """Retract Canopy above the display using a geometry animation."""
        if not self.isVisible():
            self._panel_state = CanopyPanelState.HIDDEN
            self._restore_foreground_context()
            return

        if self._panel_state == CanopyPanelState.CLOSING:
            return

        self._slide_animation.stop()
        self._panel_state = CanopyPanelState.CLOSING
        self._animate_geometry_to(
            self._hidden_geometry(),
            QEasingCurve.Type.InCubic,
        )

    def toggle_panel(self) -> None:
        """Toggle Canopy and reverse an in-flight transition if needed."""
        if not self.isVisible():
            self.show_panel()
        elif self._panel_state == CanopyPanelState.CLOSING:
            self.show_panel()
        else:
            self.hide_panel()

    def _animate_geometry_to(
        self,
        target_geometry: QRect,
        easing: QEasingCurve.Type,
    ) -> None:
        """Run the shared 225 ms geometry transition."""
        self._slide_animation.stop()
        self._slide_animation.setDuration(self.SLIDE_DURATION_MS)
        self._slide_animation.setEasingCurve(easing)
        self._slide_animation.setStartValue(self.geometry())
        self._slide_animation.setEndValue(QRect(target_geometry))
        self._slide_animation.start()

    def _on_slide_animation_finished(self) -> None:
        """Commit Canopy's stable state after the animation completes."""
        if self._panel_state == CanopyPanelState.OPENING:
            self.setGeometry(self._target_geometry())
            self._panel_state = CanopyPanelState.OPEN
            self.canopyVisibilityChanged.emit(True)
            return

        if self._panel_state == CanopyPanelState.CLOSING:
            self.setGeometry(self._hidden_geometry())
            self.hide()
            self._panel_state = CanopyPanelState.HIDDEN
            self._restore_foreground_context()
            self.canopyVisibilityChanged.emit(False)

    def set_voice_streaming(self, streaming: bool) -> None:
        """Update Canopy's speech state and activity visualization."""
        streaming = bool(streaming)
        self._activity_line.set_streaming(streaming)
        self._waveform_painter.set_streaming(streaming)

        if streaming:
            self.set_assistant_status("LISTENING")
        else:
            self.set_assistant_status(
                "EDITING" if self._input.text().strip() else "READY"
            )

    def set_audio_waveform_enabled(self, enabled: bool) -> None:
        """Show the waveform painter instead of the progress-line indicator."""
        self._indicator_stack.setCurrentWidget(
            self._waveform_painter
            if enabled
            else self._activity_line
        )

    def push_audio_frame(self, frame: CanopyAudioFrame) -> None:
        """Forward an audio-capture frame to the waveform renderer."""
        self._waveform_painter.push_audio_frame(frame)

    def set_transcript(self, transcript: str) -> None:
        """Place a speech transcript in the Canopy request field."""
        self._input.setText(transcript)
        self._input.setCursorPosition(len(transcript))

        if not self._activity_line.is_streaming:
            self.set_assistant_status(
                "EDITING" if transcript.strip() else "READY"
            )

    def set_assistant_status(self, status: str) -> None:
        """Set a concise, plain-text status label for Canopy integrations."""
        normalized = " ".join(str(status).split()).upper()[:24] or "READY"
        self._status_label.setText(normalized)
        self._status_label.setAccessibleDescription(
            f"Canopy assistant status: {normalized}."
        )

    def _on_input_edited(self, text: str) -> None:
        if not self._activity_line.is_streaming:
            self.set_assistant_status(
                "EDITING" if text.strip() else "READY"
            )

    def _submit_query(self) -> None:
        query = self._input.text().strip()
        if not query:
            return

        self.set_assistant_status("SENT")
        self.canopyQuerySubmitted.emit(query)

    def _set_input_focused(self, focused: bool) -> None:
        self._input_frame.setProperty("focused", focused)
        style = self._input_frame.style()
        style.unpolish(self._input_frame)
        style.polish(self._input_frame)
        self._input_frame.update()

    def _on_hotkey_error(self, message: str) -> None:
        self.set_assistant_status("HOTKEY UNAVAILABLE")
        self.setToolTip(message)
        self._status_label.setToolTip(message)

    def _on_hotkey_registered(self) -> None:
        self.setToolTip(
            f"Canopy global shortcut: "
            f"{self._hotkey_listener._binding.display_name}"
        )

    def start_global_hotkey_listener(self) -> None:
        """Start Canopy's Windows RegisterHotKey message-loop worker."""
        self._hotkey_listener.start_listener()

    def stop_global_hotkey_listener(self) -> None:
        """Request orderly shutdown of the Canopy hotkey worker."""
        self._hotkey_listener.stop()

    def shutdown(self) -> None:
        """Stop Canopy animation, audio indicators, and native hooks."""
        self._slide_animation.stop()
        self._activity_line.set_streaming(False)
        self._waveform_painter.set_streaming(False)
        self.stop_global_hotkey_listener()
        self._restore_foreground_context()
        self._panel_state = CanopyPanelState.HIDDEN

    def _quit_application(self) -> None:
        application = QApplication.instance()
        if application is not None:
            application.quit()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)

        if not self._native_backdrop_attempted:
            self._native_backdrop_attempted = True
            self._native_backdrop_applied = (
                _apply_canopy_native_backdrop(int(self.winId()))
            )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._input:
            if event.type() == QEvent.Type.FocusIn:
                self._set_input_focused(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_input_focused(False)
            elif (
                event.type() == QEvent.Type.KeyPress
                and isinstance(event, QKeyEvent)
                and event.key() == Qt.Key.Key_Escape
            ):
                self.hide_panel()
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide_panel()
            event.accept()
            return

        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.shutdown()
        event.accept()

        application = QApplication.instance()
        if application is not None:
            application.quit()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Create and run the Canopy desktop frontend."""
    application_args = list(argv) if argv is not None else sys.argv
    application = QApplication(application_args)
    application.setObjectName("CanopyApplication")
    application.setApplicationName("Canopy")
    application.setApplicationDisplayName("Canopy")
    application.setOrganizationName("Canopy")
    application.setQuitOnLastWindowClosed(False)

    window = CanopyWindow(
        enable_global_hotkey=CANOPY_ENABLE_GLOBAL_HOTKEY
    )
    application.aboutToQuit.connect(window.shutdown)
    window.show_panel()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
