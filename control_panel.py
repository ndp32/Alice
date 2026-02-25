"""Floating NSPanel control panel for Kokoro Reader."""

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSBlockOperation,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSMakeRect,
    NSNonactivatingPanelMask,
    NSObject,
    NSOperationQueue,
    NSPanel,
    NSPopUpButton,
    NSScreen,
    NSSlider,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)


class _PanelDelegate(NSObject):
    """Objective-C delegate that forwards button/window events to Python callbacks."""

    def init(self):
        self = objc.super(_PanelDelegate, self).init()
        if self is None:
            return None
        self._on_prev = None
        self._on_toggle = None
        self._on_next = None
        self._on_seek = None
        self._on_speed_change = None
        self._on_voice_change = None
        self._on_close = None
        self._suppress_actions = False
        return self

    def prevClicked_(self, sender):
        if self._on_prev:
            self._on_prev()

    def toggleClicked_(self, sender):
        if self._on_toggle:
            self._on_toggle()

    def nextClicked_(self, sender):
        if self._on_next:
            self._on_next()

    def seekChanged_(self, sender):
        if self._suppress_actions or not self._on_seek:
            return
        self._on_seek(int(sender.intValue()))

    def speedChanged_(self, sender):
        if self._suppress_actions or not self._on_speed_change:
            return
        raw = float(sender.doubleValue())
        speed = round(raw / ControlPanel.SPEED_STEP) * ControlPanel.SPEED_STEP
        self._on_speed_change(round(speed, 2))

    def voiceChanged_(self, sender):
        if self._suppress_actions or not self._on_voice_change:
            return
        title = sender.titleOfSelectedItem()
        if title:
            self._on_voice_change(title)

    def windowWillClose_(self, notification):
        if self._on_close:
            self._on_close()


class ControlPanel:
    PANEL_WIDTH = 420
    PANEL_HEIGHT = 150
    SPEED_MIN = 0.6
    SPEED_MAX = 2.0
    SPEED_STEP = 0.05

    def __init__(self, voices: list[str], speeds: list[float]):
        self._panel = None
        self._label = None
        self._play_btn = None
        self._seek_slider = None
        self._speed_slider = None
        self._speed_value_label = None
        self._voice_popup = None
        self._voices = voices
        self._speeds = speeds
        self._delegate = _PanelDelegate.alloc().init()
        self._build_panel()

    def _build_panel(self):
        screen = NSScreen.mainScreen().frame()
        x = (screen.size.width - self.PANEL_WIDTH) / 2
        y = 80

        frame = NSMakeRect(x, y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSNonactivatingPanelMask
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setTitle_("")
        self._panel.setIsVisible_(False)
        self._panel.setAlphaValue_(0.92)
        self._panel.setDelegate_(self._delegate)
        self._panel.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.15, 0.15, 1.0)
        )

        content = self._panel.contentView()
        content_h = self.PANEL_HEIGHT - 22

        self._label = self._make_label(NSMakeRect(12, content_h - 22, self.PANEL_WIDTH - 24, 18), "Sentence 1 of 1")
        content.addSubview_(self._label)

        self._seek_slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(14, content_h - 48, self.PANEL_WIDTH - 28, 18)
        )
        self._seek_slider.setMinValue_(0)
        self._seek_slider.setMaxValue_(0)
        self._seek_slider.setIntValue_(0)
        self._seek_slider.setNumberOfTickMarks_(1)
        self._seek_slider.setAllowsTickMarkValuesOnly_(True)
        self._seek_slider.setTarget_(self._delegate)
        self._seek_slider.setAction_("seekChanged:")
        content.addSubview_(self._seek_slider)

        btn_w = 50
        btn_h = 28
        spacing = 10
        total_w = btn_w * 3 + spacing * 2
        start_x = (self.PANEL_WIDTH - total_w) / 2
        btn_y = 40

        prev_btn = self._make_button("⏮", NSMakeRect(start_x, btn_y, btn_w, btn_h), "prevClicked:")
        self._play_btn = self._make_button(
            "⏯", NSMakeRect(start_x + btn_w + spacing, btn_y, btn_w, btn_h), "toggleClicked:"
        )
        next_btn = self._make_button(
            "⏭", NSMakeRect(start_x + 2 * (btn_w + spacing), btn_y, btn_w, btn_h), "nextClicked:"
        )
        content.addSubview_(prev_btn)
        content.addSubview_(self._play_btn)
        content.addSubview_(next_btn)

        speed_label = self._make_label(NSMakeRect(12, 16, 56, 18), "Speed")
        content.addSubview_(speed_label)

        self._speed_slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(68, 12, 140, 24)
        )
        self._speed_slider.setMinValue_(self.SPEED_MIN)
        self._speed_slider.setMaxValue_(self.SPEED_MAX)
        self._speed_slider.setNumberOfTickMarks_(0)
        self._speed_slider.setAllowsTickMarkValuesOnly_(False)
        self._speed_slider.setContinuous_(True)
        self._speed_slider.setTarget_(self._delegate)
        self._speed_slider.setAction_("speedChanged:")
        content.addSubview_(self._speed_slider)

        self._speed_value_label = self._make_label(NSMakeRect(210, 16, 40, 18), "1.0x")
        content.addSubview_(self._speed_value_label)

        voice_label = self._make_label(NSMakeRect(258, 16, 44, 18), "Voice")
        content.addSubview_(voice_label)

        self._voice_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(302, 12, 108, 24), False
        )
        for voice in self._voices:
            self._voice_popup.addItemWithTitle_(voice)
        self._voice_popup.setTarget_(self._delegate)
        self._voice_popup.setAction_("voiceChanged:")
        content.addSubview_(self._voice_popup)

    def _make_label(self, frame, text):
        from AppKit import NSTextAlignmentCenter, NSTextField

        label = NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setEditable_(False)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(NSFont.systemFontOfSize_(12))
        label.setAlignment_(NSTextAlignmentCenter)
        return label

    def _make_button(self, title, frame, action_sel):
        btn = NSButton.alloc().initWithFrame_(frame)
        btn.setTitle_(title)
        btn.setBezelStyle_(NSBezelStyleRounded)
        btn.setFont_(NSFont.systemFontOfSize_(16))
        btn.setTarget_(self._delegate)
        btn.setAction_(action_sel)
        return btn

    def show(self):
        self._run_on_main(lambda: self._panel.orderFront_(None))

    def hide(self):
        self._run_on_main(lambda: self._panel.orderOut_(None))

    def update_progress(self, current: int, total: int):
        def _update():
            safe_total = max(total, 1)
            safe_current = max(0, min(current, safe_total - 1))
            self._delegate._suppress_actions = True
            self._label.setStringValue_(f"Sentence {safe_current + 1} of {safe_total}")
            self._seek_slider.setMaxValue_(safe_total - 1)
            self._seek_slider.setNumberOfTickMarks_(safe_total)
            self._seek_slider.setEnabled_(safe_total > 1)
            self._seek_slider.setIntValue_(safe_current)
            self._delegate._suppress_actions = False

        self._run_on_main(_update)

    def set_playing(self, is_playing: bool):
        def _update():
            self._play_btn.setTitle_("⏸" if is_playing else "▶")

        self._run_on_main(_update)

    def set_speed(self, speed: float):
        def _update():
            self._delegate._suppress_actions = True
            safe_speed = min(max(speed, self.SPEED_MIN), self.SPEED_MAX)
            self._speed_slider.setDoubleValue_(safe_speed)
            self._speed_value_label.setStringValue_(f"{safe_speed:.2f}x")
            self._delegate._suppress_actions = False

        self._run_on_main(_update)

    def set_voice(self, voice: str):
        def _update():
            self._delegate._suppress_actions = True
            self._voice_popup.selectItemWithTitle_(voice)
            self._delegate._suppress_actions = False

        self._run_on_main(_update)

    def set_callbacks(
        self,
        on_prev,
        on_toggle,
        on_next,
        on_seek,
        on_speed_change,
        on_voice_change,
        on_close,
    ):
        self._delegate._on_prev = on_prev
        self._delegate._on_toggle = on_toggle
        self._delegate._on_next = on_next
        self._delegate._on_seek = on_seek
        self._delegate._on_speed_change = on_speed_change
        self._delegate._on_voice_change = on_voice_change
        self._delegate._on_close = on_close

    def _run_on_main(self, block):
        """Dispatch a block to the main thread."""
        op = NSBlockOperation.blockOperationWithBlock_(block)
        NSOperationQueue.mainQueue().addOperation_(op)
