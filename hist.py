#!/usr/bin/env python3

import numpy as np
import argparse
from threading import Timer, Event
import sys

parser = argparse.ArgumentParser(
    description='Print the histogram of numbers read numbers from stdin into a circular buffer.')
parser.add_argument('--size', type=int, help='Size of the circular buffer, default=%(default)s', default=1000)
parser.add_argument('--bins', type=int, help='Number of bins, default=%(default)s', default=10)
parser.add_argument('--truncate', help="Truncate histogram range at +-3 sigma values", action='store_true')
parser.add_argument('--range', type=int, nargs=2, metavar=("LOW", "HIGH"),
                    help='Range of the histogram, defaults to the min/max values', default=[None, None])
parser.add_argument('--interval', type=float, help='Refersh interval (in seconds) default=%(default)s', default=2)
parser.add_argument('--width', type=int, help='Width of the bins, default=%(default)s', default=70)

args = parser.parse_args()


def updatehist(a, bins, truncate, low, high, interval, stopevent):
    """
    Timer callback function, restarts the timer and prints the histogram.
    """
    if not stopevent.isSet():
        # start a new timer
        timerobject = Timer(interval, updatehist, args=[a, bins, truncate, low, high, interval, stopevent])
        timerobject.start()

        # statistics
        mu = np.mean(a)
        sigma = np.std(a)
        minimum = np.min(a)
        maximum = np.max(a)

        # range of the histogram:
        #   - values in argument
        #   - min/max of numbers
        #   - mu +-3sigma of numbers, if truncated
        histrange = (low if low is not None else (max(minimum, mu - 3 * sigma) if truncate else minimum),
                     high if high is not None else (min(maximum, mu + 3 * sigma) if truncate else maximum))

        # calculate histogram
        hist = np.histogram(a, bins, range=histrange)

        # max value for normalization
        freqmax = np.max(hist[0])

        # padding of values to align bars
        padding = int(np.log10(hist[1].max()) + 1)

        # print header
        print("%s___mu=%.2f___sigma=%.2f___min=%.0f___max=%.0f_" % (("_" * (padding + 2)), mu, sigma, minimum, maximum))

        # print histogram
        for value, freq in zip(hist[1], hist[0]):
            # index
            sys.stdout.write(("%%%dd: " % padding) % value)

            # bulks
            sys.stdout.write("=" * (freq * 20 // freqmax))

            # newline
            sys.stdout.write('\n')


if __name__ == '__main__':
    numbers = np.zeros(args.size)
    stop = Event()

    # start a timer
    t = Timer(args.interval, updatehist,
              args=[numbers, args.bins, args.truncate, args.range[0], args.range[1], args.interval, stop])
    t.start()

    # current write pointer in the circular buffer of numbers
    ptr = 0
    try:
        # read inputs from stdin
        for line in sys.stdin:
            try:
                numbers[ptr] = float(line)
                ptr = (ptr + 1) % args.size
            except ValueError:
                sys.stderr.write("Warning: non float value received: '%s'\n" % line.rstrip())

    except KeyboardInterrupt:
        stop.set()

    # wait for the timer thread to end (worst case: timer have been just started)
    t.join(timeout=args.interval + 1)
