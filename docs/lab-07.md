# Lab 7 Event time with Apache Beam

Allow about 30 minutes. You will run a finished event-time pipeline, compare its panes, then add two events. This lab has its own files and does not need Lab 6.

## Run the stream

You need Docker with Compose and Internet access for the first build. From the repository root:

```console
cd labs/lab-07/tutorial
docker compose build
docker compose run --rm beam
```

`stream.py` uses `TestStream` to give a short, repeatable arrival sequence. Its timestamps are **event times**; the order of the `add_elements` calls is **arrival order**. The stream is finite for the exercise but uses Beam's streaming mode. No message broker is needed.

Read `make_events()`. The first two `S1` records have event times 10 and 20. An `S2` record has time 70. The watermark then passes the end of the first one-minute window, and another `S1` record arrives with time 30. Work out which window contains each event before reading the output. Windows are half-open: `[0, 60)` and `[60, 120)`.

## Compare the panes

Run the same stream with two late-data policies:

```console
docker compose run --rm beam
docker compose run --rm beam python stream.py --lateness 120
docker compose run --rm beam python stream.py --lateness 120 --mode discarding
```

Look for these `S1` results in `window=0-60` (line order can vary):

| Setting | On-time pane | Late pane |
| --- | ---: | ---: |
| Default: no allowed lateness | 2 | none |
| 120 seconds, accumulating | 2 | 3 |
| 120 seconds, discarding | 2 | 1 |

The watermark says earlier event times are unlikely, but the late-data limit decides whether the time-30 event can still update its window. An accumulating pane gives the new total; a discarding pane gives only the new contribution. `S2` remains in `window=60-120` with count 1.

In `stream.py`, find `FixedWindows(60)`, `AfterWatermark`, `allowed_lateness`, and the accumulation mode. `CombinePerKey` groups by both station and window. An endless stream cannot wait for one global count to finish.

## Your task: find the cleanup boundary

Keep the existing events. In `make_events()`, after the time-30 event:

1. Add another `S1` event with event time **40**.
2. Advance the watermark to **181**.
3. Add one more `S1` event with event time **50**, before `advance_watermark_to_infinity()`.

Follow the existing `TimestampedValue(("S1", 1), ...)` pattern. The first window ends at 60; with 120 seconds of allowed lateness, its allowance expires after 180. Predict which of the new events will count, then rebuild and run:

```console
docker compose build
docker compose run --rm beam python stream.py --lateness 120
docker compose run --rm beam
```

With accumulating panes, `S1` should show counts 2 (on time), 3 (late), and 4 (late). It must not reach 5. With no allowed lateness, only the on-time count of 2 remains. Explain why the events at times 40 and 50 have different outcomes even though both belong to `[0, 60)`.

## Cleanup and references

Run `docker compose down` to remove the service network. Beam's Python Direct Runner has limited streaming support; this lab uses a small, controlled `TestStream` for that reason.

- [Beam windowing and triggers](https://beam.apache.org/documentation/programming-guide/)
- [TestStream](https://beam.apache.org/blog/test-stream/)
- [Direct Runner](https://beam.apache.org/documentation/runners/direct/)
