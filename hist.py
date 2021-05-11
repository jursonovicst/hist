#!/usr/bin/env python3

import numpy as np
import argparse
from threading import Timer, Event
import sys

parser = argparse.ArgumentParser(description='Print the histogram of numbers read over stdin.')
parser.add_argument('--size', type=int, help='Size of the circular buffer, default=%(default)s', default=1000)
parser.add_argument('--bins', type=int, help='Number of bins, default=%(default)s', default=10)
parser.add_argument('--truncate', help="Truncate histogram range at +-3 sigma values", action='store_true')
parser.add_argument('--range', type=float, nargs=2, metavar=("LOW", "HIGH"),
                    help='Range of the histogram, defaults to the min/max values', default=[None, None])
parser.add_argument('--interval', type=float, help='Refresh interval (in seconds) default=%(default)s', default=2)
parser.add_argument('--percentiles', type=float,
                    help='Percentiles to compute, which must be between 0 and 100 inclusive.', nargs='*')
parser.add_argument('--width', type=int, help='Width of the bars, default=%(default)s', default=70)

args = parser.parse_args()


def updatehist(buffer, bins, truncate, low, high, percentiles, interval, stopevent, width):
    """
    Timer callback function, restarts the timer and prints the histogram.
    """
    if not stopevent.isSet():
        # start a new timer
        timerobject = Timer(interval, updatehist,
                            args=[buffer, bins, truncate, low, high, percentiles, interval, stopevent, width])
        timerobject.start()

        # statistics
        mu = np.mean(buffer)
        sigma = np.std(buffer)
        minimum = np.min(buffer)
        maximum = np.max(buffer)

        # range of the histogram:
        #   - values in argument
        #   - mu +-3sigma of numbers, if truncated
        #   - min/max of numbers
        histrange = (low if low is not None else (max(minimum, mu - 3 * sigma) if truncate else minimum),
                     high if high is not None else (min(maximum, mu + 3 * sigma) if truncate else maximum))

        # calculate histogram
        hist = np.histogram(buffer, bins, range=histrange)

        # max value for normalization
        freqmax = np.max(hist[0])

        # calculate percentiles
        values = hist[1][:-1]
        freqs = hist[0]
        if percentiles is not None:
            perc = np.percentile(buffer, percentiles)
            assert len(perc) == len(percentiles), "Len mismatch after creating percentiles: %s %s" % (perc, percentiles)

            # append percentiles, use negative sign for marking mark
            values = np.concatenate([values, perc])
            freqs = np.concatenate([freqs, np.multiply(percentiles, -1)])

        assert len(values) == len(freqs), "Len mismatch: %s %s %s %s" % (hist[1], values, hist[0], freqs)

        # padding of values to align bars
        padding = int(np.log10(hist[1].max()) + 1)

        # print header
        print(f"{' ' * (padding + 2)}   mu={mu:.2f}   sigma={sigma:.2f}   min={minimum:.0f}   max={maximum:.0f}")

        # print histogram

        # get argsort
        p = values.argsort()

        for value, freq in zip(values[p], freqs[p]):
            if freq >= 0:
                # index
                sys.stdout.write(("%%%dd: " % padding) % value)

                # bulks
                barwidth = int(freq * width // freqmax)
                sys.stdout.write("▄" * barwidth + " " * (width-barwidth))
            else:
                # percentile
                sys.stdout.write(
                    (" " * (padding + 2)) + ("." * ((width - 4) // 2)) + ("%gth" % (freq * -1)) + ("." * ((width - 4) // 2)))

            # newline
            sys.stdout.write('\n')

        # move cursor back

        print(f"\033[{len(values) + 2}A")


if __name__ == '__main__':
    buffer = np.zeros(args.size)
    stop = Event()

    # start a timer
    t = Timer(args.interval, updatehist,
              args=[buffer, args.bins, args.truncate, args.range[0], args.range[1], args.percentiles, args.interval,
                    stop, args.width])
    t.start()

    # current write pointer in the circular buffer of numbers
    ptr = 0
    try:
        # read inputs from stdin
        for line in sys.stdin:
            try:
                buffer[ptr] = float(line)
                ptr = (ptr + 1) % args.size
            except ValueError:
                sys.stderr.write("Warning: non float value received: '%s'\n" % line.rstrip())

    except KeyboardInterrupt:
        stop.set()

    # wait for the timer thread to end (worst case: timer have been just started)
    t.join(timeout=args.interval + 1)
