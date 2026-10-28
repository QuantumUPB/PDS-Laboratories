# Lab 4 Object storage and recovery

## Objective

In this lab you will run one S3-compatible object store in Docker, upload a file, overwrite it, and recover an earlier version after deleting it. You will use Silo, a maintained fork of MinIO. Its bundled `mcli` command lets you work with the store without installing another program.

An object store is different from Network File Systems (NFS): clients address objects by **bucket and key** through an API, rather than mounting a shared directory. This lab focuses on object storage.

## Requirements and files

You need Docker Engine or Docker Desktop with Compose and Internet access to download the Silo image. From the repository root, go to the lab directory:

```console
cd labs/lab-04/tutorial
docker compose config
```

On Windows PowerShell, `Set-Location labs\lab-04\tutorial` also works. Run the remaining commands from this directory.

| File | Purpose |
| --- | --- |
| `compose.yaml` | Runs Silo and mounts its data volume |
| `files/report-v1.txt` | Original report |
| `files/report-v2.txt` | Corrected report |

Read `compose.yaml`. The named volume `silo_data` is mounted at `/data`, where Silo stores its buckets and objects. The two reports are mounted read-only at `/lab-files` so you can upload them with `mcli`. The credentials in Compose are for this local lab only. Ports 9000 (S3 API) and 9001 (web console) are available only on your own computer.

## Task 1: create a bucket and upload a file

Start the object store:

```console
docker compose up -d
docker compose ps
```

Wait until the `silo` service is running. Configure the client bundled in the container:

```console
docker compose exec silo mcli alias set local http://127.0.0.1:9000 labadmin labsecret123
```

An **alias** is a short name for the server and its login details. `local` refers to Silo's API inside the container. Create a bucket named `lab-files`, then turn on versioning **before** the first upload:

```console
docker compose exec silo mcli mb local/lab-files
docker compose exec silo mcli version enable local/lab-files
docker compose exec silo mcli version info local/lab-files
```

A bucket groups objects. Versioning keeps older copies when an object is replaced or deleted. Upload the original report under the key `report.txt`:

```console
docker compose exec silo mcli cp /lab-files/report-v1.txt local/lab-files/report.txt
docker compose exec silo mcli ls local/lab-files
docker compose exec silo mcli cat local/lab-files/report.txt
```

The last command should print `3 disks passed inspection`. The source is a file inside the container; `local/lab-files/report.txt` means **server alias / bucket / object key**. Open `http://localhost:9001` and sign in with `labadmin` / `labsecret123`. Find the bucket and its object in the web console.

## Task 2: replace the object and inspect its versions

Upload the corrected report to the **same key**. This creates another version of `report.txt`:

```console
docker compose exec silo mcli cp /lab-files/report-v2.txt local/lab-files/report.txt
docker compose exec silo mcli cat local/lab-files/report.txt
docker compose exec silo mcli ls --versions local/lab-files/report.txt
```

The current report should say `2 disks passed inspection`. The versions listing should show two entries with different version IDs. Record the ID of the **original** version, the one uploaded first. You will need it in the final task. A normal `mcli cat` reads the current version, while `--version-id` can select an older one.

**Check:** Why did the second upload create a new version instead of an object with a second name? Which Docker volume holds the versions?

## Final task: recover a deleted report

Delete `report.txt` without specifying a version ID:

```console
docker compose exec silo mcli rm local/lab-files/report.txt
docker compose exec silo mcli ls local/lab-files
docker compose exec silo mcli ls --versions local/lab-files/report.txt
```

The normal listing no longer shows the report. In a versioned bucket, this deletion adds a **delete marker**; the earlier contents remain available. The versions listing should now show the marker and both report versions.

Recover the **original** report. Replace `VERSION_ID_HERE` below with the ID you recorded in Task 2:

```console
docker compose exec silo mcli cp --version-id=VERSION_ID_HERE local/lab-files/report.txt /tmp/recovered-report.txt
docker compose exec silo cat /tmp/recovered-report.txt
docker compose exec silo mcli cp /tmp/recovered-report.txt local/lab-files/report.txt
docker compose exec silo mcli cat local/lab-files/report.txt
```

The recovered file should say `3 disks passed inspection`. Uploading it creates a new current version; it does not erase the corrected version or the delete marker. Check with `mcli ls --versions` again.

Now recreate the container while keeping its named volume:

```console
docker compose down
docker compose up -d
docker compose exec silo mcli alias set local http://127.0.0.1:9000 labadmin labsecret123
docker compose exec silo mcli cat local/lab-files/report.txt
```

The recovered report should still be present. The client alias had to be set again because it lived in the old container; the bucket and its objects survived in `silo_data`.

**Show the instructor:** the original and corrected report versions, the delete marker, the recovered current report, and the report still present after container recreation. Explain the difference between the Docker volume, the S3 bucket, and the object key.

## Troubleshooting and cleanup

| Symptom | Check |
| --- | --- |
| `mcli` cannot connect | `docker compose ps`, `docker compose logs silo`, and the alias command |
| Bucket already exists | Continue with `mcli version info local/lab-files` |
| No older version appears | Check that versioning was enabled before the first upload |
| `cat` says the object does not exist after deletion | This is expected until you upload a recovered version |
| Recovery returns the corrected report | Choose the version ID from the first upload, not the second |

To stop Silo and keep its data, run `docker compose down`. To reset this lab completely, run `docker compose down --volumes`; this deletes the lab's bucket and all its object versions.

## References

- [Silo quick start](https://github.com/pgsty/silo#quick-start)
- [Silo client commands](https://silo.pgsty.com/reference/minio-mc/) and [bucket versioning](https://silo.pgsty.com/administration/object-management/object-versioning/)

