# Lab 6 Batch dataflow with Apache Beam

Allow about 30 minutes. You will run a finished pipeline, follow its data through the graph, then add one small branch. This lab uses only its own files.

## Run the pipeline

You need Docker with Compose and Internet access for the first build. From the repository root:

```console
cd labs/lab-06/tutorial
docker compose build
docker compose run --rm beam
cat output/station-summary
cat output/rejected
docker compose run --rm --entrypoint python beam check.py
```

The input is a small bike-trip file. Each valid row gives a start station and duration. The report counts departures and averages their durations. Its three rows may appear in any order:

```text
S1,Central,3,11.33
S2,Riverside,3,15.33
S3,North Park,2,12.50
```

The checker also expects two rejected trips: `t09` has a negative duration and `t10` has text where a number belongs. The output files are on the host in `output/`.

## Follow the data

Open `batch.py` beside `input/trips.csv` and `input/stations.csv`. Read the named transforms in order:

1. `Read trips` creates a bounded `PCollection` from the file. `ParseTrip` sends good rows to `valid` and bad rows to `rejected`.
2. `Key durations` produces `(station_id, duration)` pairs. The same collection feeds `Count departures` and `Mean duration`.
3. `Read stations` supplies `(station_id, station_name)` pairs. `CoGroupByKey` joins the three keyed collections. `Format report` writes the four-column result.

Draw these branches as arrows. Mark the transforms that can handle one row independently. Mark `Count`, `Mean`, and `CoGroupByKey` as points where records with the same key must meet. On a distributed runner, that meeting can require data to move between workers. The supplied pipeline uses Beam's local Direct Runner.

Try one input change: set `t08`'s duration from `7` to `0`, rerun the pipeline, and compare both output files. `S3` should then have one valid departure, averaging `18.00`; there should be three rejected rows. Restore `7` before the next section. Input is mounted into the container, so this change needs no rebuild.

## Your task: count longer trips

Add a branch from `parsed.valid` in `batch.py`. Keep trips whose duration is **at least 12 minutes**, count them by **start station**, and write two-column rows to `output/long-trips` without a header. Follow the existing `counts` and `Write report` code. The branch needs `Filter`, `Map` to `(station_id, 1)`, `CombinePerKey(sum)`, `Map` to CSV text, and `WriteToText` with one shard and an empty shard-name template.

Expected rows, in any order:

```text
S1,1
S2,2
S3,1
```

Rebuild after editing Python, then run the extended check:

```console
docker compose build
docker compose run --rm beam
docker compose run --rm --entrypoint python beam check.py --extension
```

Explain why filtering before the count changes only this new branch, while `station-summary` stays the same.

## Cleanup and references

`docker compose down` removes the service network. The files in `output/` remain until you remove them. Beam may print a warning about optional BigQuery libraries; this lab does not use BigQuery.

- [Beam programming guide](https://beam.apache.org/documentation/programming-guide/)
- [Direct Runner](https://beam.apache.org/documentation/runners/direct/)
