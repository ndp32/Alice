"""Floating NSPanel control panel for Kokoro Reader."""

from AppKit import (
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSObject,
    NSPanel,
    NSScreen,
    NSTextField,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSFloatingWindowLevel,
    NSNonactivatingPanelMask,
    NSBezelStyleRounded,
    NSOperationQueue,
    NSBlockOperation,
    NSTextAlignmentCenter,
)


class _PanelDelegate(NSObject):
    """Objective-C delegate that forwards button/window events to Python callbacks."""

    def init(self):
        self = super().init()
        if self is None:
            return None
        self._on_prev = None
        self._on_toggle = None
        self._on_next = None
        self._on_close = None
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

    def windowWillClose_(self, notification):
        if self._on_close:
            self._on_close()


class ControlPanel:
    PANEL_WIDTH = 280
    PANEL_HEIGHT = 80

    def __init__(self):
        self._panel = None
        self._label = None
        self._play_btn = None
        self._delegate = _PanelDelegate.alloc().init()
        self._build_panel()

    def _build_panel(self):
        screen = NSScreen.mainScreen().frame()
        x = (screen.size.width - self.PANEL_WIDTH) / 2
        y = 80  # 80pt from bottom

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

        # Dark background
        self._panel.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.15, 0.15, 1.0)
        )

        content = self._panel.contentView()
        content_h = self.PANEL_HEIGHT - 22  # account for title bar

        # Progress label — top area
        self._label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(10, content_h - 28, self.PANEL_WIDTH - 20, 20)
        )
        self._label.setStringValue_("Ready")
        self._label.setEditable_(False)
        self._label.setBezeled_(False)
        self._label.setDrawsBackground_(False)
        self._label.setTextColor_(NSColor.whiteColor())
        self._label.setFont_(NSFont.systemFontOfSize_(12))
        self._label.setAlignment_(NSTextAlignmentCenter)
        content.addSubview_(self._label)

        # Buttons — bottom area, centered
        btn_w = 50
        btn_h = 30
        spacing = 8
        total_w = btn_w * 3 + spacing * 2
        start_x = (self.PANEL_WIDTH - total_w) / 2
        btn_y = 4

        prev_btn = self._make_button(
            "⏮", NSMakeRect(start_x, btn_y, btn_w, btn_h), "prevClicked:"
        )
        self._play_btn = self._make_button(
            "⏯", NSMakeRect(start_x + btn_w + spacing, btn_y, btn_w, btn_h), "toggleClicked:"
        )
        next_btn = self._make_button(
            "⏭", NSMakeRect(start_x + 2 * (btn_w + spacing), btn_y, btn_w, btn_h), "nextClicked:"
        )

        content.addSubview_(prev_btn)
        content.addSubview_(self._play_btn)
        content.addSubview_(next_btn)

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
            self._label.setStringValue_(f"Sentence {current + 1} of {total}")
        self._run_on_main(_update)

    def set_playing(self, is_playing: bool):
        def _update():
            self._play_btn.setTitle_("⏸" if is_playing else "▶")
        self._run_on_main(_update)

    def set_callbacks(self, on_prev, on_toggle, on_next, on_close):
        self._delegate._on_prev = on_prev
        self._delegate._on_toggle = on_toggle
        self._delegate._on_next = on_next
        self._delegate._on_close = on_close

    def _run_on_main(self, block):
        """Dispatch a block to the main thread."""
        op = NSBlockOperation.blockOperationWithBlock_(block)
        NSOperationQueue.mainQueue().addOperation_(op)
