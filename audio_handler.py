# MIT License (MIT)
# Copyright (c) 2023 Stephen Carey
# https://opensource.org/licenses/MIT

# Handler for audio sampling.

import time

from machine import Pin, ADC
from ulab import numpy as np
from ulab import utils as utils

# Adapted from: https://medium.com/swlh/how-to-perform-fft-onboard-esp32-and-get-both-frequency-and-amplitude-45ec5712d7da
NUM_SAMPLES = 256
REACT_CROSSOVER = 400


class AudioHandler:
    def __init__(self, pin_num: int, num_samples: int = NUM_SAMPLES, crossover: int = REACT_CROSSOVER):
        self.pin_num = pin_num
        self.num_samples = num_samples
        self.crossover = crossover
        self.sound_pin = ADC(Pin(self.pin_num))
        self.sound_pin.atten(ADC.ATTN_11DB)
        self.samples = []

    def sample(self):
        """Samples the desired number of times from the mic and returns the fundamental frequency and the max amplitude
         of the frequencies below the configured crossover."""
        sample_start = time.ticks_us()
        for _ in range(self.num_samples):
            self.samples.append(self.sound_pin.read_u16())
        sample_secs = time.ticks_diff(time.ticks_us(), sample_start) / 1_000_000
        # print("Sample secs: {}".format(sample_secs))

        array = np.array(self.samples)
        self.samples.clear()

        # this splits the sound into frequency buckets with magnitude as the value
        output = utils.spectrogram(array)
        max_magnitude = 0
        max_low_freq_mag = 0
        fundamental_freq = 0

        for i in range(1, int(self.num_samples / 2) + 1):
            mag = output[i]
            freq = i * 1.0 / sample_secs

            if mag > max_magnitude:
                fundamental_freq = freq
                max_magnitude = mag
            if freq < self.crossover and mag > max_low_freq_mag:
                max_low_freq_mag = mag

            # print("Freq: {}, Low Mag: {}".format(freq, max_low_freq_mag))

        low_freq_amp = max_low_freq_mag * 2 / self.num_samples

        return fundamental_freq, low_freq_amp
