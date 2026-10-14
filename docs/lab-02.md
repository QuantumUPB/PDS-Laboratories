# Lab 2 Docker volumes and Compose

## Purpose

In Lab 1 you built an image and started a container. In this laboratory you will keep data outside a container, connect two containers, and describe an application with Docker Compose.

## Required environment

You will need to use Docker with the Docker Compose plugin. Docker Desktop should come with it pre-installed, on some Linux distribution you may need to install it manually.

```console
docker version
docker compose version
```

Both commands must succeed. Use the `docker compose` command shown here. Run commands from the directory stated in each section. Commands on one line work in Bash and PowerShell unless separate versions are given.

## Observe the container filesystem

A file written inside a container normally belongs to that container's writable layer. Stopping and starting the same container preserves this layer. Removing the container removes the layer.

Create a file without a mount. The Python process exits after writing it, leaving a stopped container.

```console
docker run --name pds-lab02-temporary python:3.13-slim python -c "from pathlib import Path; Path('/note.txt').write_text('container data'); print('File created')"
docker cp pds-lab02-temporary:/note.txt ./container-note.txt
docker rm pds-lab02-temporary
```

The copied file on the host remains. Now check a new container created from the same image.

```console
docker run --rm python:3.13-slim python -c "from pathlib import Path; print(Path('/note.txt').exists())"
```

The result should be `False`. Writing a file in one container did not change the image.

## Create and use a named volume

A named volume is storage managed by Docker. Mount it at a path inside a container to keep data after that container is removed.

```console
docker volume create pds-lab02-notes
docker volume ls
docker volume inspect pds-lab02-notes
```

Write to the volume from a temporary container.

```console
docker run --rm --mount type=volume,source=pds-lab02-notes,target=/data python:3.13-slim python -c "from pathlib import Path; Path('/data/note.txt').write_text('persistent data')"
```

Here `source` names the volume and `target` is its mount path inside the container. `--rm` removes this container when its process exits. It does not remove this named volume.

Read the data from a different container. Mount the volume read-only for this operation.

```console
docker run --rm --mount type=volume,source=pds-lab02-notes,target=/data,readonly python:3.13-slim python -c "from pathlib import Path; print(Path('/data/note.txt').read_text())"
```

The output should be `persistent data`. The two containers used the same storage, even though the first container no longer exists. Inspect the data through a container; the mount location reported by Docker may be inside the Docker Desktop virtual machine.

Before continuing, predict the result of reading `/data/note.txt` in a container without this mount. Test your prediction.

## Mount a host directory

A bind mount makes a specific host file or directory available inside a container. This is useful when you want to edit input on the host and let a container read it.

From the repository root, move to the supplied final-task input directory.

On Linux and macOS:

```bash
cd labs/lab-02/final-app/input
docker run --rm --mount "type=bind,source=$(pwd),target=/input,readonly" python:3.13-slim python -c "from pathlib import Path; print(Path('/input/sample.txt').read_text())"
```

On Windows PowerShell:

```powershell
Set-Location labs\lab-02\final-app\input
docker run --rm --mount "type=bind,source=$($PWD.Path),target=/input,readonly" python:3.13-slim python -c "from pathlib import Path; print(Path('/input/sample.txt').read_text())"
```

Edit `sample.txt` on the host and repeat the Docker command. The new text should appear without rebuilding an image. `readonly` prevents writes through this mount from the container. It does not prevent you from editing the file on the host.

| Storage | Where the data comes from | Survives container removal? | Use in this lab |
| --- | --- | --- | --- |
| Container writable layer | Files written inside that container | No | Temporary data |
| Named volume | Storage managed by Docker | Yes, until the volume is removed | Received data |
| Bind mount | A selected host path | Yes, until the host data is removed | Input files |

`COPY` in a Dockerfile stores files in the image at build time. A mount is attached when a container is created. A bind mount over a populated container directory hides the image files at that path while mounted. Use `/app` for program files, `/input` for input, and `/data` for saved output in this lab.

## Pass an environment variable

An environment variable is a name and a string value available to a process. Applications can read it to select behavior without changing source code.

```console
docker run --rm -e MESSAGE=Hello python:3.13-slim python -c "import os; print(os.getenv('MESSAGE', 'Default message'))"
docker run --rm python:3.13-slim python -c "import os; print(os.getenv('MESSAGE', 'Default message'))"
```

The first command prints `Hello`. The second uses the default. Python receives strings, so a port number normally needs conversion, for example `int(os.getenv("PORT", "8000"))`.

These values are runtime configuration. Changing them requires a new container configuration, but does not require a new image. Dockerfile `ARG` values configure a build and do not automatically become runtime environment variables.

## Open the Compose tutorial

Docker Compose describes services, networks, and volumes in a YAML file. A service describes how to build or select an image and how to run it. For this lab, each service runs one container.

Move from `labs/lab-02/final-app/input` to the tutorial directory.

Keep this terminal in `labs/lab-02/tutorial` for the tutorial. This is the application's main directory. The supplied files have the following roles.

| Path relative to the main directory | Role |
| --- | --- |
| `compose.yaml` | Defines the complete application |
| `.env.example` | Example values to copy to `.env` |
| `server/Dockerfile` | Builds the server image |
| `server/server.py` | Returns a message over HTTP |
| `client/Dockerfile` | Builds the client image |
| `client/client.py` | Requests the message and appends it to a file |

Open both Python files. The server reads `PORT` and `MESSAGE` from its environment. It listens on `0.0.0.0`, so it can accept connections through its container's network interface. The client reads `SERVER_HOST`, `SERVER_PORT`, and `OUTPUT_FILE`.

The client makes one HTTP request, saves the reply, and exits. The server continues to run. A successful client exit is expected.

## Build each service from its own directory

Open `server/Dockerfile`.

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY server.py .
CMD ["python", "-u", "server.py"]
```

The client Dockerfile has the same structure but copies and starts `client.py`. The `-u` option makes Python output appear promptly in container logs. Both programs use only the Python standard library.

The Compose entry `build: ./server` selects the server directory as its build context. `COPY server.py .` therefore reads `server/server.py` on the host. The client uses `build: ./client`. Each service has an independent image; neither build context includes the other service or the main directory's `.env` file.

## Read the Compose file

The supplied `compose.yaml` contains:

```yaml
name: pds-lab02-tutorial

services:
  server:
    build: ./server
    environment:
      PORT: "${SERVICE_PORT:-8000}"
      MESSAGE: "${MESSAGE:-Hello from Compose}"
    networks:
      - labnet
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/', timeout=2).close()"
      interval: 2s
      timeout: 3s
      retries: 10
      start_period: 2s

  client:
    build: ./client
    environment:
      SERVER_HOST: server
      SERVER_PORT: "${SERVICE_PORT:-8000}"
      OUTPUT_FILE: /data/messages.txt
    volumes:
      - messages:/data
    networks:
      - labnet
    depends_on:
      server:
        condition: service_healthy

networks:
  labnet:
    driver: bridge

volumes:
  messages:
```

Use spaces for YAML indentation. Keys at the same indentation level belong to the same mapping. This file uses the current Compose specification and does not need a top-level `version` key.

The top-level `networks` and `volumes` entries declare resources. The entries under each service attach those resources to that service. Declaring a volume alone does not mount it.

`messages:/data` mounts the named volume in the client. The server has no mount of that volume. Compose prefixes resource names with the project name, so this configuration creates `pds-lab02-tutorial_messages` and `pds-lab02-tutorial_labnet`.

## Understand the Docker network

Both services join `labnet`, a user-defined bridge network on this Docker host. Docker provides name resolution on this network. The client connects to `http://server:8000/`, using the service name rather than an IP address.

Inside the client container, `localhost` means the client itself. It does not mean the server or the host computer. The server listens on `0.0.0.0`, while the client uses the destination name `server`.

There is no `ports` entry. Containers on this network can communicate using the application port directly. A host port mapping is needed only if you also want to reach the service from the host. `EXPOSE` is not required to enable this connection.

Compose normally creates a default network if none is specified. We declare `labnet` explicitly so you can see which services join it. A bridge network here connects containers on one Docker host; this lab does not configure networking between separate computers.

## Configure Compose with .env

Copy the example configuration.

On Linux and macOS:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

The file contains:

```dotenv
SERVICE_PORT=8000
MESSAGE=Hello from the PDS laboratory
```

In `${SERVICE_PORT:-8000}`, Compose substitutes the variable value, or `8000` if it is unset or empty. Running from this main directory lets Compose read the local `.env` file. A variable already set in the terminal environment takes precedence over the same name in `.env`.

There are two separate steps: Compose substitutes values into the YAML; the service's `environment` section passes selected values into the container. A `.env` entry alone does not automatically reach Python. Here `SERVICE_PORT` becomes `PORT` in the server and `SERVER_PORT` in the client. A service-level `env_file` is another way to supply container variables; we use explicit `environment` mappings in this lab.

Inspect the resolved configuration before starting.

```console
docker compose config
```

Find the server's `PORT` and the client's `SERVER_PORT`. They must match. The `.env` file is ignored by Git in this project; keep `.env.example` as the reproducible example. Environment variables are not a secret-storage mechanism.

## Wait for the server to be ready

Starting a container is not the same as having a server ready to accept requests. Plain `depends_on` controls startup order. This example also uses `condition: service_healthy`.

The health check runs inside the server container. It makes a request to the server's loopback address using the configured port. The client starts after that request succeeds. Loopback is correct here because the check and the server run in the same container.

A health check does not guarantee that the server will remain available later. The client still reports a failed request with a nonzero exit status. In the final task you will also implement bounded readiness retries in the sender.

## Start and inspect the application

Build and start the application.

```console
docker compose up --build -d
docker compose ps -a
docker compose logs server client
```

After the request completes, the server should be running and healthy. The client should show `Exited (0)`. The logs should include the configured message and the path `/data/messages.txt`. If the client is still running, repeat the status check after it finishes.

Inspect the network and volume.

```console
docker network ls
docker network inspect pds-lab02-tutorial_labnet
docker volume inspect pds-lab02-tutorial_messages
```

The network inspection lists attached active endpoints; a client that has already exited may no longer appear there. Test DNS from a temporary client container.

```console
docker compose run --rm --no-deps client python -c "import socket; print(socket.gethostbyname('server'))"
```

The IP can change when a container is recreated. Keep `server` in the configuration rather than copying this IP.

Read the saved messages with a temporary container that uses the client's volume configuration.

```console
docker compose run --rm --no-deps client python -c "from pathlib import Path; print(Path('/data/messages.txt').read_text())"
```

`run` creates a new container for a one-time command. The command after `client` replaces its usual command. `--no-deps` avoids starting dependencies for this inspection. By comparison, `exec` runs a command in an already-running service container, so `exec client` will not work after this client exits.

## Change behavior without rebuilding

Edit `.env`: change the message and change `SERVICE_PORT` to `9000`. Inspect the configuration and recreate the server with the new environment.

```console
docker compose config
docker compose up -d server
docker compose run --rm client
```

The one-time client waits for the configured healthy dependency and requests the new port. Read `/data/messages.txt` again with the inspection command above. It should contain both the old and new messages.

No source file changed, so no image rebuild was needed. `docker compose restart` alone does not apply changed environment values. Use `up` to apply the new service configuration. If you change a Python source file that is copied into an image, use `docker compose up --build -d` instead.

For one request, override only the client's output path.

```console
docker compose run --rm -e OUTPUT_FILE=/data/another.txt client
docker compose run --rm --no-deps client python -c "from pathlib import Path; print(Path('/data/another.txt').read_text())"
```

Explain why this command changes the output file without editing the Dockerfile.

## Verify persistence after removal

Remove the tutorial containers and network, keeping the named volume.

```console
docker compose down
docker volume inspect pds-lab02-tutorial_messages
docker compose run --rm --no-deps client python -c "from pathlib import Path; print(Path('/data/messages.txt').read_text())"
docker compose down
```

The message file should still exist. The inspection command temporarily recreates the resources it needs. The final `down` removes the recreated network.

`docker compose down --volumes` also deletes the project's declared named volumes and their data. Use that command only when you intend to reset the lab. Bind-mounted host files are not deleted by `down --volumes`.

## Final task: transfer a file between containers

Write a small file-transfer application. The sender must read a file from its mounted input directory and send its bytes over HTTP. The receiver must accept the upload and write those bytes into its own named volume.

Use Python's standard library. `urllib.request.Request` and `urlopen` can send the request. `BaseHTTPRequestHandler` and `HTTPServer` can implement the receiver. A single-request-at-a-time server is sufficient.

Move from `labs/lab-02/tutorial` to `labs/lab-02/final-app`.

On Linux and macOS:

```bash
cd ../final-app
```

On Windows PowerShell:

```powershell
Set-Location ..\final-app
```

### Create the project structure

Use `final-app` as the main directory. The input file and service directories are supplied. Create the remaining files yourself.

| Path relative to final-app | What you must provide |
| --- | --- |
| `compose.yaml` | Two services, one network, and the receiver volume |
| `.env.example` | Example configuration values |
| `.env` | Your local copy of the configuration |
| `sender/sender.py` | Reads and uploads the file |
| `sender/Dockerfile` | Builds and starts the sender |
| `receiver/receiver.py` | Receives and saves the file |
| `receiver/Dockerfile` | Builds and starts the receiver |
| `input/sample.txt` | Supplied input; you may edit it |

Use service names `sender` and `receiver`, project name `pds-lab02-final`, and build contexts `./sender` and `./receiver`. Use `python:3.13-slim` as the base image for both services.

Attach both services to a declared bridge network named `transfernet`. Bind-mount `./input` at `/input` in the sender with read-only access. Declare a named volume `received_data` and mount it at `/data` in the receiver. The resulting Docker volume name will be `pds-lab02-final_received_data`.

The sender must not mount the receiver's output volume. The receiver must not mount the sender's input directory. Transfer the bytes over the network. Do not bake input files into either image. No published host ports are needed.

### Configure the programs through environment variables

Use the following variable names and initial values inside the containers. Values in the final column are strings until your program converts them.

| Service | Environment variable | Initial value |
| --- | --- | --- |
| Sender | `INPUT_FILE` | `/input/sample.txt` |
| Sender | `RECEIVER_HOST` | `receiver` |
| Sender | `RECEIVER_PORT` | `8000` |
| Sender | `MAX_ATTEMPTS` | `10` |
| Sender | `RETRY_DELAY` | `1` |
| Receiver | `PORT` | `8000` |
| Receiver | `OUTPUT_FILE` | `/data/received.bin` |

Put a common `TRANSFER_PORT=8000` in `.env.example` and map it to both the receiver's `PORT` and the sender's `RECEIVER_PORT` in Compose. Put the input path, output path, retry count, and retry delay in the example file too, then map them through `environment`. The destination hostname can stay `receiver` in Compose.

The receiver must bind to `0.0.0.0`. The sender must use the service name, not `localhost` or a fixed IP. `MAX_ATTEMPTS` must be a positive integer; `RETRY_DELAY` is a positive number of seconds. Reject invalid numeric configuration with a useful error.

### Define a small HTTP interface

Use this interface so the two programs agree on the transfer format.

| Request | Receiver behavior |
| --- | --- |
| `GET /health` | Respond `200 OK` without writing a file |
| `POST /upload` | Read the raw request body and save it at `OUTPUT_FILE`; respond `201 Created` only after a successful write |

The sender must open `INPUT_FILE` in binary mode, send the bytes as the request body, and set `Content-Type: application/octet-stream`. Send the byte count as `Content-Length`. Do not use a text encoding, JSON, Base64, or multipart form data. Use small test files of at most 1 MiB so reading one whole file into memory is sufficient for this exercise.

The receiver must read the declared body length and verify that it received that many bytes before writing the file. Create the output parent directory if needed and use binary mode. A repeated successful upload overwrites the configured output file. The output path comes from the receiver's environment, not from a path supplied by the sender.

Use a request timeout, for example five seconds. Handle a missing input file, an unavailable receiver, and a failed upload with a clear message and a nonzero sender exit status. Print the transferred byte count on success. Do not report success merely because a connection was established: check for the `201` response.

### Handle startup

Add a receiver health check that requests `/health` using its configured `PORT`. Configure the sender to depend on a healthy receiver.

The sender must also try `/health` up to `MAX_ATTEMPTS` times, waiting `RETRY_DELAY` seconds between failed attempts. Exit with an error after the last failed attempt. After readiness succeeds, upload the file once and exit. The receiver must stay running to accept later transfers.

Keep readiness checks separate from uploads: a readiness probe must not write or overwrite the output file. Automatic retries of a partially completed upload are outside the required task.

### Run and verify

Run these commands from `final-app` after creating the files and copying `.env.example` to `.env`.

```console
docker compose config
docker compose up --build -d
docker compose ps -a
docker compose logs sender receiver
```

Wait for the sender to exit. Expect `Exited (0)` for the sender and a healthy running receiver. Copy the saved output from the receiver to the host for verification.

On Linux and macOS:

```bash
mkdir -p verified
docker compose cp receiver:/data/received.bin ./verified/received.bin
cmp input/sample.txt verified/received.bin
```

`cmp` should produce no output and exit successfully.

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force verified
docker compose cp receiver:/data/received.bin ./verified/received.bin
(Get-FileHash input/sample.txt -Algorithm SHA256).Hash -eq (Get-FileHash verified/received.bin -Algorithm SHA256).Hash
```

The comparison should return `True`. These paths assume the initial `OUTPUT_FILE`; adjust the copy source when you change it.

Demonstrate each of the following checks to the laboratory instructor.

| Check | Required result |
| --- | --- |
| Transfer `sample.txt` | Saved file matches the input |
| Transfer a binary file containing zero bytes and non-text bytes | Saved bytes match exactly |
| Transfer an empty file | An empty output file is created successfully |
| Change `INPUT_FILE` and `OUTPUT_FILE` in `.env`, then use `up -d receiver` and `run --rm sender` | New paths take effect without an image rebuild |
| Change `TRANSFER_PORT` to `9000`, then use `up -d receiver` and `run --rm sender` | Both programs communicate using the new port |
| Set `INPUT_FILE` to a nonexistent path for a one-time sender run | Sender exits with an error |
| Remove and recreate the receiver | Previously saved output is still present |

To create binary and empty test files without host Python, run these commands from `final-app`. This setup step intentionally uses a writable host mount; the application's sender mount must remain read-only.

On Linux and macOS:

```bash
docker run --rm --mount "type=bind,source=$(pwd)/input,target=/input" python:3.13-slim python -c "from pathlib import Path; Path('/input/binary.bin').write_bytes(bytes(range(256)) * 1024); Path('/input/empty.bin').write_bytes(b'')"
```

On Windows PowerShell:

```powershell
docker run --rm --mount "type=bind,source=$($PWD.Path)/input,target=/input" python:3.13-slim python -c "from pathlib import Path; Path('/input/binary.bin').write_bytes(bytes(range(256)) * 1024); Path('/input/empty.bin').write_bytes(b'')"
```

Use `docker compose run --rm -e INPUT_FILE=/input/binary.bin sender` for a one-time input override, and repeat for `/input/empty.bin`. Verify each output before the next upload overwrites it.

Test the sender's readiness failure path independently of Compose's healthy-dependency check.

```console
docker compose stop receiver
docker compose run --rm --no-deps -e MAX_ATTEMPTS=3 sender
docker compose up -d receiver
```

The sender must exit with an error after its bounded attempts. `--no-deps` prevents Compose from starting the receiver for this test. Confirm the exit status with `echo $?` in Bash or `$LASTEXITCODE` in PowerShell immediately after the sender command.

Finally, copy the current received file to `verified/before.bin`. Then recreate only the receiver, so a new sender cannot hide data loss by uploading again.

```console
docker compose down
docker compose up -d receiver
```

Copy the same output path to `verified/after.bin` and compare the two files. The data must survive. Show the instructor the Compose configuration, both scripts, and the verification results. Explain which mechanism carries the bytes between containers and which mechanism preserves them after container removal.

### Optional extensions

Reject uploads with missing or invalid lengths and enforce a configurable maximum size. Save to a temporary file and replace the final file only after a complete write. Return a SHA-256 digest and have the sender verify it. Keep these extensions separate from the required Docker behavior.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot resolve `server` or `receiver` | The service name and shared network membership |
| Connection refused | The listening port, bind address, and readiness logs |
| Client tries its own container | Replace destination `localhost` with the other service name |
| Changed `.env` has no effect | Check terminal variable overrides, `compose config`, and recreate the service with `up` |
| Old Python code runs | Rebuild the affected image |
| Input file not found | Compare the host mount source with the container's `/input` path |
| Saved file disappears after recreation | Confirm the output path is inside the mounted `/data` directory |
| Receiver never becomes healthy | Run `docker compose logs receiver`; check the health-check URL and configured port |

## Cleanup

From `final-app`, use `docker compose down` to keep received files, or the following command to delete this project's containers, network, and named volume data.

```console
docker compose down --volumes
```

Move to `../tutorial` and run the same command to delete the tutorial resources. Remove the standalone volume created at the start when its data is no longer needed.

```console
docker volume rm pds-lab02-notes
```

Host files in `input`, `verified`, and the earlier `container-note.txt` are not removed by these commands. Keep submitted work and delete test files manually when no longer needed.

## References

The examples use the current Compose specification. See the official documentation for further details.

| Topic | Documentation |
| --- | --- |
| Persistent storage | [Docker volumes](https://docs.docker.com/engine/storage/volumes/) and [bind mounts](https://docs.docker.com/engine/storage/bind-mounts/) |
| Build directories | [Compose build specification](https://docs.docker.com/reference/compose-file/build/) |
| Container communication | [Networking in Compose](https://docs.docker.com/compose/how-tos/networking/) |
| Configuration | [Compose variable interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) and [service definitions](https://docs.docker.com/reference/compose-file/services/) |
| Readiness | [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/) |
| One-time commands and cleanup | [compose run](https://docs.docker.com/reference/cli/docker/compose/run/) and [compose down](https://docs.docker.com/reference/cli/docker/compose/down/) |
| Python HTTP | [http.server](https://docs.python.org/3.13/library/http.server.html) and [urllib.request](https://docs.python.org/3.13/library/urllib.request.html) |
