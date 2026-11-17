"""A finite test stream with the timing rules of an unbounded source."""

import argparse

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.testing.test_stream import TestStream
from apache_beam.transforms import trigger, window
from apache_beam.transforms.window import TimestampedValue
from apache_beam.utils.windowed_value import PaneInfoTiming


def make_events():
    # Timestamps are seconds since an arbitrary origin. The records are
    # (station, count); the calls below define their arrival order.
    return (
        TestStream()
        .add_elements([TimestampedValue(("S1", 1), 10), TimestampedValue(("S1", 1), 20)])
        .add_elements([TimestampedValue(("S2", 1), 70)])
        .advance_watermark_to(61)
        .add_elements([TimestampedValue(("S1", 1), 30)])
        .advance_watermark_to_infinity()
    )


def describe(element, window=beam.DoFn.WindowParam, pane=beam.DoFn.PaneInfoParam):
    station, count = element
    timing = PaneInfoTiming.to_string(pane.timing)
    return f"{station},window={int(window.start)}-{int(window.end)},count={count},pane={timing}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lateness", type=int, default=0, help="allowed lateness in seconds")
    parser.add_argument("--mode", choices=("accumulating", "discarding"), default="accumulating")
    args = parser.parse_args()

    mode = (
        trigger.AccumulationMode.ACCUMULATING
        if args.mode == "accumulating"
        else trigger.AccumulationMode.DISCARDING
    )

    options = PipelineOptions(["--streaming", "--runner=DirectRunner"])
    with beam.Pipeline(options=options) as pipeline:
        (
            pipeline
            | "Events" >> make_events()
            | "One-minute windows" >> beam.WindowInto(
                window.FixedWindows(60),
                trigger=trigger.AfterWatermark(late=trigger.AfterCount(1)),
                accumulation_mode=mode,
                allowed_lateness=args.lateness,
            )
            | "Count by station" >> beam.CombinePerKey(sum)
            | "Describe panes" >> beam.Map(describe)
            | "Print panes" >> beam.Map(print)
        )


if __name__ == "__main__":
    main()
