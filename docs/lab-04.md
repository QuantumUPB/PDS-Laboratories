# Lab 4 Network storage and snapshots

## Objective

You'll learn to bring up an OpenSearch, Grafana, and an S3-compatible object store in Docker. You'll develop a small HTTP app that sends request logs to OpenSearch, inspect them in Grafana, then take and restore a snapshot.

## Required environment

You need Docker Engine or Docker Desktop with Compose, Internet access for images and plugins, and at least **4 GiB of memory available to Docker**. Commands work from a Linux, macOS, or Windows PowerShell terminal.

```console
docker version
docker compose version
```

OpenSearch requires `vm.max_map_count` of at least `262144` on the Linux machine running the Docker daemon. On native Linux, set it for this session with:

```console
sudo sysctl -w vm.max_map_count=262144
```

On Docker Desktop, follow the [OpenSearch Docker host-setting instructions](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/) for your platform if OpenSearch reports a map-count error. The stack disables OpenSearch authentication and exposes its web ports only on `127.0.0.1`. The fixed object-store credentials in the supplied files are for this isolated laboratory only.

## Open the supplied project

From the repository root:

```console
cd labs/lab-04/tutorial
docker compose config
```

On Windows PowerShell, use `Set-Location labs\lab-04\tutorial` instead of `cd` if preferred.

| File | Role |
| --- | --- |
| `compose.yaml` | Connects the app, OpenSearch, Grafana, and Silo; defines their persistent volumes |
| `opensearch/Dockerfile` | Adds the OpenSearch S3 snapshot plugin and lab credentials |
| `grafana/datasources.yaml` | Connects Grafana to the `lab-logs` index |
| `app/app.py` | HTTP app with two functions for you to finish |
| `app/load.py` | Sends six requests to the app |
| `client/lab_api.py` | Shows and sends the snapshot API requests |

The `client` service runs one-time Python commands. Compose does not start it with the main stack.

## Understand the storage layout

Read `compose.yaml` and identify these three named volumes:

| Docker volume | What it stores |
| --- | --- |
| `opensearch_data` | Live OpenSearch indexes |
| `grafana_data` | Grafana users, settings, and saved dashboards |
| `silo_data` | S3 bucket objects, including OpenSearch snapshots |

Silo provides the S3 API inside the Compose network. OpenSearch connects to `silo:9000`. You can open Silo's console at `http://localhost:9001`, OpenSearch's API at `http://localhost:9200`, and Grafana at `http://localhost:3000`.

```text
HTTP requests → app → OpenSearch ← Grafana
                         │
                         └─ snapshot → Silo bucket
```

## Task 1: build an app that sends logs to OpenSearch

The supplied app already answers web requests. Your job is to add the logging step. When someone requests `/items`, the app answers with HTTP 200. An unknown path such as `/missing` gets HTTP 404. For **both** requests, the app should create a log event and send it to OpenSearch. Grafana will read those events from OpenSearch later.

An *event* is one record describing one request. In Python it is a dictionary; over HTTP it is sent as JSON. An event for `/items` should look like this (your timestamp will differ):

```json
{
  "@timestamp": "2026-10-28T10:00:00+00:00",
  "service": "lab-app",
  "path": "/items",
  "status": 200,
  "message": "items listed"
}
```

`@timestamp` tells Grafana when the request happened. `status` is a number, while the other fields are text. OpenSearch will create the `lab-logs` index when it receives the first event; you do not need to create it by hand.

### Start the services

Build and start the stack from `labs/lab-04/tutorial`:

```console
docker compose up --build -d
docker compose ps
docker compose logs --tail=30 opensearch grafana silo app
```

The first start may take a few minutes while plugins install and OpenSearch starts. `docker compose ps` should show the four main services running. If one exits, check its logs before continuing.

### Complete the app

Open `app/app.py` in a text editor. Find `build_event` and `send_event`. They currently end with `raise NotImplementedError(...)`, which means “this part is still missing.” Replace each `raise` with your code. The imports you need are already at the top of the file; leave the supplied `Handler` class alone.

#### Step 1: create an event

In `build_event(path, status)`, return a Python dictionary with the five fields shown above. Use the `path` and `status` arguments you receive, rather than fixed values. For the time, use `datetime.now(timezone.utc).isoformat()`. Set `message` to `"items listed"` when `status == 200`, and `"route missing"` otherwise. Start with:

```python
message = "items listed" if status == 200 else "route missing"
return {
    "@timestamp": datetime.now(timezone.utc).isoformat(),
    # Add service, path, status, and message here.
}
```

Replace the comment with four dictionary entries. Each entry has the form `"field": value,`. Use `"lab-app"` for `service`, and the variables `path`, `status`, and `message` for the others.

#### Step 2: send the event

In `send_event(event)`, turn the dictionary into JSON bytes and send it to OpenSearch. The request must use HTTP `POST`, the path `/lab-logs/_doc?refresh=wait_for`, and the `Content-Type: application/json` header. Place this code inside the function:

```python
payload = json.dumps(event).encode("utf-8")
request = Request(
    OPENSEARCH_URL + "/lab-logs/_doc?refresh=wait_for",
    data=payload,
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urlopen(request, timeout=5):
    pass
```

`OPENSEARCH_URL` comes from Compose and points to the OpenSearch container. `refresh=wait_for` makes the new event searchable before the request finishes. The `with` block sends the request and closes the response; this task does not need the response body.

Save `app/app.py`. Python uses indentation to mark which lines belong to a function: keep the new lines indented by four spaces, as in the examples.

### Try it and inspect the logs

Restart the app to load your edits. `load.py` then sends six requests to it, and `lab_api.py search` asks OpenSearch for the saved events:

```console
docker compose restart app
docker compose exec app python load.py
docker compose run --rm --no-deps client python lab_api.py search
```

Expect four HTTP 200 responses and two HTTP 404 responses. In the search output, look for `hits.total.value` (six on your first run) and the `path` and `status` fields under `hits.hits` → `_source`. Each time you run `load.py`, it adds six more events.

HTTP 404 is expected for `/missing`: the app received the request and logged it. HTTP 503 means the app could not send a log. If you see 503, run `docker compose logs --tail=30 app`. A `NotImplementedError` means a function is still unfinished; a connection error may mean OpenSearch is still starting. Fix the cause, restart the app if you edited it, and run `load.py` again.

Open `http://localhost:3000`. Sign in with `admin` / `admin` and change the password when prompted. In **Explore**, choose **OpenSearch** and a time range covering the last few minutes. Find the events, including a 404. The data source uses `http://opensearch:9200`; from inside Grafana, `localhost` would mean the Grafana container.

## Task 2: prepare S3 snapshot storage

The object store needs a bucket before OpenSearch can save snapshots. Run the Silo client inside its container:

```console
docker compose exec silo mcli alias set local http://127.0.0.1:9000 labadmin labsecret123
docker compose exec silo mcli mb local/lab-snapshots
docker compose exec silo mcli ls local
```

The first command names the Silo server `local` for its command-line client; `mb` makes a bucket. If the bucket already exists, confirm it with `mcli ls`.

Read `opensearch/Dockerfile` and the `opensearch` environment in Compose. Find the S3 plugin, lab credentials, endpoint, and path-style setting.

Register and verify a snapshot repository:

```console
docker compose run --rm --no-deps client python lab_api.py register
docker compose run --rm --no-deps client python lab_api.py verify
```

Read the method, URL, and body printed by each command. `register` tells OpenSearch which bucket to use; `verify` checks that it can reach the bucket.

**Questions:** Why does the endpoint use `silo` instead of `localhost`? Has OpenSearch written a snapshot yet?

## Final task: take and restore a snapshot

Take a snapshot containing only the app's `lab-logs` index:

```console
docker compose run --rm --no-deps client python lab_api.py snapshot
docker compose run --rm --no-deps client python lab_api.py snapshots
docker compose exec silo mcli ls --recursive local/lab-snapshots
```

Check for `SUCCESS` and zero failed shards. The Silo listing should now contain objects. Their names belong to OpenSearch's snapshot format.

After confirming `SUCCESS`, remove **only the `lab-logs` index** and restore it:

```console
docker compose run --rm --no-deps client python lab_api.py delete-sample
docker compose run --rm --no-deps client python lab_api.py search
docker compose run --rm --no-deps client python lab_api.py restore
docker compose run --rm --no-deps client python lab_api.py search
```

The first search should report that `lab-logs` is missing; the second should return the same events you had when you took the snapshot (six if you ran `load.py` once). Do not send new app requests between deletion and restoration, as they would recreate the index. Refresh Grafana Explore and find the events again. Widen the time range if needed: restoring a record does not change its timestamp.

## Troubleshooting and cleanup

| Symptom | Check |
| --- | --- |
| OpenSearch exits early | `docker compose logs opensearch`, Docker memory, `vm.max_map_count` |
| App requests return 503 | `docker compose logs app`; check the two functions and OpenSearch readiness |
| Grafana has no OpenSearch data source | `docker compose logs grafana`; plugin installation needs network access |
| No events in Grafana | OpenSearch API search, selected time range, `lab-logs` data source |
| Repository registration fails | S3 plugin build, Silo status, bucket name, endpoint and credentials |
| Snapshot name already exists | This exercise uses the fixed name `checkpoint-1`; reset the lab volumes or choose a new name in `client/lab_api.py` |
| Restore says index already exists | Delete only `lab-logs` before restoring, or restore under a new index name |

Stop containers while retaining all three named volumes:

```console
docker compose down
```

`docker compose down --volumes` deletes the live index, Grafana settings, and S3 bucket objects. Use it only to reset the lab. Events added after `checkpoint-1` will not be in that snapshot. Grafana's settings are outside the OpenSearch snapshot.

## References

- [OpenSearch Docker installation](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/), [S3 snapshot repositories](https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/snapshot-restore/), and [restore API](https://docs.opensearch.org/latest/api-reference/snapshots/restore-snapshot/)
- [Grafana OpenSearch data source](https://grafana.com/docs/plugins/grafana-opensearch-datasource/latest/configure/) and [Docker plugin installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/)
- [Silo container quick start](https://github.com/pgsty/silo#quick-start)
