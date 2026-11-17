"""Batch dataflow example for Lab 6."""

import argparse
import csv

import apache_beam as beam
from apache_beam import pvalue
from apache_beam.options.pipeline_options import PipelineOptions


class ParseTrip(beam.DoFn):
    def process(self, line):
        row = next(csv.reader([line]))
        if row and row[0] == "trip_id":
            return
        if len(row) != 4:
            yield pvalue.TaggedOutput("rejected", f"wrong column count|{line}")
            return
        trip_id, start, end, duration_text = row
        try:
            duration = int(duration_text)
        except ValueError:
            yield pvalue.TaggedOutput("rejected", f"invalid duration|{line}")
            return
        if not trip_id or not start or not end or duration <= 0:
            yield pvalue.TaggedOutput("rejected", f"missing field or nonpositive duration|{line}")
            return
        yield (start, duration)


def parse_station(line):
    row = next(csv.reader([line]))
    if row and row[0] != "station_id":
        yield (row[0], row[1])


def format_report(pair):
    station_id, groups = pair
    name = groups["stations"][0]
    count = groups["counts"][0]
    average = groups["averages"][0]
    return f"{station_id},{name},{count},{average:.2f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trips", default="input/trips.csv")
    parser.add_argument("--stations", default="input/stations.csv")
    parser.add_argument("--output", default="output")
    args = parser.parse_args()

    with beam.Pipeline(options=PipelineOptions(["--runner=DirectRunner"])) as pipeline:
        parsed = (
            pipeline
            | "Read trips" >> beam.io.ReadFromText(args.trips)
            | "Parse trips" >> beam.ParDo(ParseTrip()).with_outputs("rejected", main="valid")
        )

        durations = parsed.valid | "Key durations" >> beam.Map(
            lambda trip: (trip[0], trip[1])
        )
        counts = durations | "Count departures" >> beam.combiners.Count.PerKey()
        averages = durations | "Mean duration" >> beam.combiners.Mean.PerKey()
        stations = (
            pipeline
            | "Read stations" >> beam.io.ReadFromText(args.stations)
            | "Parse stations" >> beam.FlatMap(parse_station)
        )
        report = (
            {"counts": counts, "averages": averages, "stations": stations}
            | "Join station data" >> beam.CoGroupByKey()
            | "Format report" >> beam.Map(format_report)
        )

        report | "Write report" >> beam.io.WriteToText(
            f"{args.output}/station-summary", num_shards=1, shard_name_template=""
        )
        parsed.rejected | "Write rejected" >> beam.io.WriteToText(
            f"{args.output}/rejected", num_shards=1, shard_name_template=""
        )


if __name__ == "__main__":
    main()
