# Lab 1 Docker fundamentals

## Purpose

This laboratory introduces the basic Docker workflow. You will run existing container images, observe container state, publish a network port, create a Dockerfile, build a custom image, and run your own image locally.

At the end of the laboratory you should be able to take a small application, describe its container image with a Dockerfile, build that image, and start a container from it.

The laboratory uses a small Python HTTP server. The application has no external Python packages. Python does not need to be installed on your host computer for the application exercise because Python will be provided by the container image.

## Required environment

Docker must be installed before the laboratory starts. On Windows, Docker Desktop is the expected environment. On Linux, Docker Engine or Docker Desktop can be used. On macOS, Docker Desktop can be used.

All Docker commands in this laboratory use the same syntax on Linux, macOS, and Windows PowerShell. Commands that work with local directories are shown separately when the syntax differs.

Open a terminal and run the following command.

```console
docker version
```

The command should show information about both the Docker client and the Docker server. If the client is present but the server cannot be reached, start Docker Desktop or the Docker service before you continue.

On some Linux systems the local Docker configuration requires `sudo`. Follow the configuration used in your laboratory environment. Do not add `sudo` on Windows or macOS.

## Images and containers

Docker uses images and containers for different purposes. An image is a stored filesystem and configuration that can be used to create containers. A container is an instance created from an image. A container can be running or stopped.

A Dockerfile is a text file that contains build instructions. Docker reads the Dockerfile when it creates an image.

```text
Dockerfile
    |
    | docker build
    v
  Image
    |
    | docker run
    v
 Container
```

One image can be used to create many containers. Removing a container does not normally remove the image from which it was created.

## Run the first container

Run the Docker `hello-world` image.

```console
docker run --rm hello-world
```

Docker first checks whether the image is available locally. If it is not available, Docker downloads it from a registry. Docker then creates a container from the image and starts the process defined by the image.

The `hello-world` process prints a message and exits. The container therefore stops almost immediately. The `--rm` option tells Docker to remove the container after the process exits.

Run the command again and compare the output with the first run. The image should already exist locally, so Docker normally does not need to download it again.

## Run a long lived container

The next container runs an Nginx web server. Start it in detached mode.

```console
docker run --name lab-nginx -d nginx:alpine
```

The `--name` option gives the container a stable name. The `-d` option starts the container in detached mode and returns control to the terminal.

Show the running containers.

```console
docker ps
```

The output should contain a container named `lab-nginx`.

Show all containers, including stopped containers.

```console
docker ps -a
```

Read the container log.

```console
docker logs lab-nginx
```

Stop the container.

```console
docker stop lab-nginx
```

Run `docker ps` and `docker ps -a` again. The first command should no longer show the container. The second command should show it with a stopped state.

Start the same container again.

```console
docker start lab-nginx
```

Check its state.

```console
docker ps
```

Stop and remove the container before the next section.

```console
docker stop lab-nginx
docker rm lab-nginx
```

The image remains on the computer after the container is removed.

## Publish a container port

Start Nginx again and publish its HTTP port.

```console
docker run --name lab-nginx -d -p 8080:80 nginx:alpine
```

Open `http://localhost:8080` in a browser. The Nginx page should be visible.

The value `8080:80` maps TCP port 8080 on the host to TCP port 80 in the container. Nginx listens on port 80 inside the container. The browser connects to port 8080 on the host.

```text
browser
   |
   | localhost 8080
   v
Docker host
   |
   | published port
   v
container port 80
```

Show the port mapping reported by Docker.

```console
docker port lab-nginx
```

Stop and remove the container.

```console
docker stop lab-nginx
docker rm lab-nginx
```

A published port is a runtime property of the container. It is created with `docker run`. Later in the laboratory you will also use the Dockerfile instruction `EXPOSE`. `EXPOSE` documents the port used by the application in the image. It does not create the host port mapping by itself.

## Inspect local images

Show the images that are stored locally.

```console
docker image ls
```

You should see images that were used in the previous sections. The exact set depends on images that were already present on your computer.

An image name can include a tag. The value `nginx:alpine` uses `nginx` as the image name and `alpine` as the tag. Tags are commonly used to distinguish image variants or versions.

## Open the laboratory application

The repository contains a small application in `labs/lab-01/app`.

On Linux and macOS run the following commands from the repository root.

```bash
cd labs/lab-01/app
ls
```

On Windows PowerShell run the following commands from the repository root.

```powershell
Set-Location labs\lab-01\app
Get-ChildItem
```

The directory contains `server.py` and `index.html`. The Python program starts an HTTP server on port 8000 and serves files from its current working directory.

Do not create the Dockerfile by changing `server.py`. The purpose of the Dockerfile is to describe the environment that will run the existing application.

## Create the Dockerfile

Create a new text file named `Dockerfile` in the same directory as `server.py`. The file name has no extension.

Add the following first instruction.

```dockerfile
FROM python:3.13-slim
```

`FROM` selects the base image. This image provides a small Linux userspace and Python 3.13. The application can therefore run even when Python is not installed on the host computer.

Add the working directory instruction.

```dockerfile
WORKDIR /app
```

`WORKDIR` sets `/app` as the working directory for later build instructions and for the default application process.

Add the copy instruction.

```dockerfile
COPY . .
```

The first dot refers to the current directory in the build context. The second dot refers to the current working directory inside the image, which is `/app` because of the previous `WORKDIR` instruction.

Add the port documentation.

```dockerfile
EXPOSE 8000
```

The application listens on port 8000. `EXPOSE` records this information in the image. It does not publish the port on the host.

Add the default command.

```dockerfile
CMD ["python", "server.py"]
```

`CMD` defines the default process that Docker starts when a container is created from the image.

The completed Dockerfile should now contain the following instructions.

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["python", "server.py"]
```

Dockerfiles can also use `RUN` to execute commands while an image is being built. This application has no external packages, so no build step is required here. Later laboratories can use `RUN` to install dependencies or prepare application files.

## Build the custom image

Make sure the terminal is still in `labs/lab-01/app` and build the image.

```console
docker build -t docker-lab-web:1.0 .
```

The `-t` option assigns the name `docker-lab-web` and the tag `1.0` to the image.

The final dot selects the current directory as the build context. Docker can access files in this context during the build. The `COPY . .` instruction therefore copies files from this directory into the image.

Show the new image.

```console
docker image ls docker-lab-web
```

The image is now stored locally. No container has been created from it yet.

## Run the custom image

Create a container from the image.

```console
docker run --name docker-lab-web -d -p 8080:8000 docker-lab-web:1.0
```

Open `http://localhost:8080` in a browser. The page from `index.html` should be visible.

Show the running container.

```console
docker ps
```

Read its log.

```console
docker logs docker-lab-web
```

The log should contain the message printed by `server.py` and HTTP request messages created when the browser accesses the page.

Run a command inside the running container.

```console
docker exec docker-lab-web python --version
```

This command starts an additional process inside the existing container. It should report the Python version provided by the base image.

## Change the application and rebuild the image

Keep the container running. Open `index.html` in a text editor and change the text inside the first `h1` element. Save the file on the host computer.

Refresh `http://localhost:8080`.

The page in the running container should not change. The file that you edited is outside the container. The container still uses the copy of `index.html` that was stored in the image when the image was built.

Build a new image tag from the modified application.

```console
docker build -t docker-lab-web:1.1 .
```

Show both image tags.

```console
docker image ls docker-lab-web
```

Stop and remove the old container.

```console
docker stop docker-lab-web
docker rm docker-lab-web
```

Start a new container from version 1.1.

```console
docker run --name docker-lab-web -d -p 8080:8000 docker-lab-web:1.1
```

Refresh the browser. The modified page should now be visible.

This build and run cycle is central to the basic Docker workflow. Source files are changed on the host. A new image is built. A new container is then created from that image.

## Final task

Move to `labs/lab-01/final-app`. Do not copy the Dockerfile from the previous directory. Create a new Dockerfile from memory and from the concepts used in this laboratory.

On Linux and macOS, if the terminal is still in `labs/lab-01/app`, run the following command.

```bash
cd ../final-app
```

On Windows PowerShell run the following command.

```powershell
Set-Location ..\final-app
```

The application again runs `server.py` and listens on port 8000. Create a Dockerfile that uses `python:3.13-slim`, uses `/app` as its working directory, copies the application files into the image, records port 8000, and starts `server.py` with Python.

Build an image named `docker-lab-final` with tag `1.0`. Start a detached container named `docker-lab-final`. Publish host port 8081 to container port 8000. Confirm that `http://localhost:8081` shows the final task page.

Use `docker ps`, `docker logs docker-lab-final`, and `docker image ls docker-lab-final` to verify the result.

The task is complete when the page is reachable from the host and the image can be used to create a new container after the original container is removed.

## Cleanup

Stop and remove the containers created from the custom images.

```console
docker rm -f docker-lab-web
docker rm -f docker-lab-final
```

The `-f` option stops a running container before Docker removes it.

The custom images can also be removed when they are no longer needed.

```console
docker image rm docker-lab-web:1.0
docker image rm docker-lab-web:1.1
docker image rm docker-lab-final:1.0
```

Do not use broad cleanup commands such as `docker system prune` on a shared or important Docker environment unless you understand which objects they will remove.

## Questions

### Question 1

Explain the difference between a Docker image and a Docker container. State which command in this laboratory created an image and which command created a container from that image.

### Question 2

Explain why changing `index.html` on the host did not change the page served by the running `docker-lab-web` container.

### Question 3

Explain the difference between `EXPOSE 8000` in the Dockerfile and `-p 8080:8000` in the `docker run` command.

### Question 4

Explain the meaning of the final dot in the following command.

```console
docker build -t docker-lab-web:1.0 .
```

### Question 5

Explain what happens when the process started by `CMD` exits.

## Completion

You have completed the laboratory when you can create a Dockerfile for the supplied final application, build a named image from it, start a container from that image, publish the application port, verify the running container, and remove the container without removing the source files.
