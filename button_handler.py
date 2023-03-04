# MIT License (MIT)
# Copyright (c) 2023 Stephen Carey
# https://opensource.org/licenses/MIT

# Handler for a button click.

from machine import Pin, Timer


# Tweaked version of https://forum.micropython.org/viewtopic.php?t=4641&start=10#p32492

class ButtonHandler:
    def __init__(self, pin_num, pin, callback, debounce_ms=10):
        self.pin_num = pin_num
        self.pin = pin
        self.debounce_ms = debounce_ms
        self.callback = callback
        self.timer = Timer(pin_num)
        self._tmp = None

    def on_timer_end(self, _):
        if self.pin.value() == self._tmp:
            # print("pressed!")
            self.callback()
        self._tmp = None

    def __call__(self, _):
        if self._tmp is not None:
            return
        value = self.pin.value()
        if not value:  # no need for debounce on a button release
            pass  # print("released!")
        else:
            self._tmp = value
            self.timer.init(
                mode=Timer.ONE_SHOT,
                period=self.debounce_ms,
                callback=self.on_timer_end,
            )
