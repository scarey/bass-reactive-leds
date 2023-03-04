# MIT License (MIT)
# Copyright (c) 2023 Stephen Carey
# https://opensource.org/licenses/MIT

# Micropython code for bass reactive NeoPixel strips with an ESP32.

import json
import time

from neopixel import NeoPixel
from machine import Pin
from ulab import numpy as np

from audio_handler import AudioHandler
from button_handler import ButtonHandler
from rotary_irq_esp import RotaryIRQ

RIGHT_STRIP_PIN = 25
LEFT_STRIP_PIN = 26

ROTARY_DT_PIN_NUM = 19
ROTARY_CLK_PIN_NUM = 18
BUTTON_PIN_NUM = 21
MIC_PIN = 27

NUM_LEDS_PER = 18
AMPLITUDE_PEAK = 5000  # >= this amplitude will be 100% brightness

OFF = (0, 0, 0)
PURPLE = (180, 0, 255)


# for the reactive part we'll average the last few brightness values to smooth the changes
brightness_list = [100 for _ in range(6)]
brightness_index: int = 0
avg_brightness = 100

color_index: int = 0
# increase to slow down the color change for reactive mode
REACTIVE_COLOR_CHANGE_SPEED = 3
COLOR_INDEX_MAX = 256 * REACTIVE_COLOR_CHANGE_SPEED

# When adjusted for low brightness some colors returned by wheel() may be OFF.  In that case
# we'll use the previous color to prevent a flicker
last_non_zero_color = None

np_left: NeoPixel = NeoPixel(Pin(LEFT_STRIP_PIN), NUM_LEDS_PER)
np_right: NeoPixel = NeoPixel(Pin(RIGHT_STRIP_PIN), NUM_LEDS_PER)

# encoder clicks will cycle the LED modes
# rotation control the color change speed in some modes and adjusts the
# amplitude that's considered 100% brightness in the reactive one
# TODO: maybe persist the selected mode and rotary value so it'll remember across boots
click_detected: bool = False

# https://github.com/miketeachman/micropython-rotary
encoder: RotaryIRQ = RotaryIRQ(pin_num_clk=ROTARY_CLK_PIN_NUM,
                               pin_num_dt=ROTARY_DT_PIN_NUM,
                               min_val=0,
                               max_val=50,
                               reverse=False,
                               range_mode=RotaryIRQ.RANGE_BOUNDED,
                               pull_up=True)

audio_handler: AudioHandler = AudioHandler(MIC_PIN)


def button_pressed():
    global click_detected, click_index, avg_brightness
    click_index = (click_index + 1) % len(click_functions)
    avg_brightness = 100
    click_detected = True


button_pin: Pin = Pin(BUTTON_PIN_NUM, Pin.IN, Pin.PULL_UP)
button_handler: ButtonHandler = ButtonHandler(BUTTON_PIN_NUM, button_pin, button_pressed)
button_pin.irq(handler=button_handler)


def mode_switched():
    global click_detected
    if click_detected:
        click_detected = False
        return True
    return False


def one_color(wait, color):
    """Fills all strips with a single color"""
    global click_detected
    np_left.fill(color)
    np_right.fill(color)
    np_left.write()
    np_right.write()
    if mode_switched():
        return
    time.sleep_ms(50)


def rainbow_cycle(wait):
    """Different colors on each pixel with color sliding across over time."""
    global click_detected
    for j in range(255):
        color = wheel(j)
        if on_off == 0:
            color = OFF
        for i in range(NUM_LEDS_PER):
            np_left[i] = color
            np_right[i] = color
        if mode_switched():
            return
        time.sleep_ms(wait - encoder.value() * 2)
        np_left.write()
        np_right.write()


def rainbow(wait):
    """Same color on every pixel with color change over time."""
    global click_detected
    for j in range(255):
        for i in range(NUM_LEDS_PER):
            np_left[i] = wheel((i * 5 + j) & 255)
        for i in range(NUM_LEDS_PER):
            np_right[i] = wheel(((i + NUM_LEDS_PER) * 5 + j) & 255)
        np_left.write()
        np_right.write()
        if mode_switched():
            return
        time.sleep_ms(wait - encoder.value() * 2)


def on_off(wait):
    one_color(wait, OFF)


def all_purple(wait):
    """Wife's favorite color goes here."""
    one_color(wait, PURPLE)


def map_value(x, in_min, in_max, out_min, out_max):
    """Scales the input value that's in the in range to the out range."""
    return max(min(out_max, (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min), out_min)


def apply_brightness(color_value):
    """Adjust the input color based on the current average brightness."""
    adjusted = int(color_value * avg_brightness / 100.0)
    return adjusted


def wheel(pos):
    if pos < 0 or pos > 255:
        return 0, 0, 0
    if pos < 85:
        return apply_brightness(255 - pos * 3), apply_brightness(pos * 3), 0
    if pos < 170:
        pos -= 85
        return 0, apply_brightness(255 - pos * 3), apply_brightness(pos * 3)
    pos -= 170
    return apply_brightness(pos * 3), 0, apply_brightness(255 - pos * 3)


def average_brightness(new_value):
    """Write a new brightness value over the oldest and return the new average."""
    # probably a more clever way to do this
    global brightness_index
    brightness_list[brightness_index] = new_value
    brightness_index += 1
    if brightness_index == len(brightness_list):
        brightness_index = 0
    return int(np.mean(brightness_list))


def reactive(wait):
    fundamental_freq, low_freq_amp = audio_handler.sample()

    # the encoder will reduce the amplitude needed to reach full brightness, useful for low volume, etc.
    brightness = map_value(low_freq_amp, 0, AMPLITUDE_PEAK - (encoder.value() * 50), 20, 100)
    global avg_brightness, color_index, last_non_zero_color
    avg_brightness = average_brightness(brightness)
    color = wheel(color_index / REACTIVE_COLOR_CHANGE_SPEED)
    if last_non_zero_color is None or color != OFF:
        last_non_zero_color = color
    if color == OFF:
        color = last_non_zero_color
    if brightness == 100.0:
        print("Fund freq: {}, Low Freq Amp: {}, bright: {}, color: {}".format(fundamental_freq,
                                                                              low_freq_amp, brightness,
                                                                              color))
    color_index = color_index + 1 if color_index != COLOR_INDEX_MAX else 0
    np_left.fill(color)
    np_right.fill(color)
    np_left.write()
    np_right.write()


# A config file defines which lighting modes to cycle through and the order
with open("config.json") as config_file:
    config = json.load(config_file)
    click_functions = [locals()[mode] for mode in config['modes']]
    click_index: int = 0

while True:
    click_functions[click_index](100)
