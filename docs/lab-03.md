# Lab 3 DHCP and DNS services

## Purpose

In Lab 2 you connected containers using a Docker network and accessed a service by its Compose service name. In this laboratory you will examine two network services that computers use outside Docker: the Dynamic Host Configuration Protocol (DHCP) and the Domain Name System (DNS).

You will configure a DHCP server, request an IPv4 lease from a real DHCP client, run a caching DNS resolver using Unbound, and observe the effect of cached DNS responses. In the final task you will connect these services to a web application: DHCP will tell the client which DNS server to use, and DNS will translate the application's hostname into its IP address.

At the end of the laboratory you should be able to explain the DHCP exchange, distinguish Docker IPAM from DHCP, identify the DHCP option used to advertise DNS servers, configure a forwarding DNS cache, and verify a locally defined DNS record.

## Required environment

You need Docker Engine or Docker Desktop with the Docker Compose plugin. The examples use a Linux container network and work from the terminal on Linux, macOS, or Windows PowerShell. Docker Desktop runs Linux containers in a virtual machine on Windows and macOS. You do not need to configure DHCP on the host network.

```console
docker version
docker compose version
```

The laboratory requires Internet access to download container images and Alpine packages. The DNS cache example also needs outbound DNS access to the configured forwarding resolvers. A campus or corporate network may restrict outbound UDP/TCP port 53; ask your instructor about an approved upstream resolver if queries fail.

**Network safety:** All DHCP traffic in this laboratory must remain on the isolated, user-defined Docker bridge network. Do not use `network_mode: host`, a macvlan network connected to the campus LAN, or publish DHCP port 67 on the host. Running a DHCP server on a shared physical network can disrupt other computers.

**Docker limitation:** Docker normally assigns container IP addresses through its own IP address management (IPAM) system, not through DHCP. We will deliberately replace the address in an experimental client container and use a separate, nonoverlapping range for DHCP leases. Afterward, Docker's inspection data may still show the address originally assigned by Docker. Do not interpret that address as the DHCP lease.

## Open the laboratory files

From the repository root, enter the tutorial directory. On Linux and macOS:

```bash
cd labs/lab-03/tutorial
```

On Windows PowerShell:

```powershell
Set-Location labs\lab-03\tutorial
```

The supplied directory contains the following files. The configuration files are editable; the Dockerfiles install the required programs.

| Path relative to `tutorial` | Role |
| --- | --- |
| `compose.yaml` | Defines the network and three container services |
| `dhcp/Dockerfile` | Installs dnsmasq |
| `dhcp/dnsmasq.conf` | DHCP address pool and options |
| `resolver/Dockerfile` | Installs Unbound |
| `resolver/unbound.conf` | Forwarding DNS cache configuration |
| `client/Dockerfile` | Installs `ip`, `dig`, and `tcpdump` |
| `client/udhcpc-lab.sh` | Applies the DHCP lease inside the client |

Keep a host terminal in this directory for all Compose commands. Build the images and check the resolved Compose configuration.

```console
docker compose config
docker compose build
```

This laboratory uses a project named `pds-lab03` and a Docker bridge named `pds-lab03_labnet`.

## Understand the laboratory network

Read the `networks` section of `compose.yaml` before starting the services.

```yaml
networks:
  labnet:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.88.0/24
          gateway: 172.30.88.1
          ip_range: 172.30.88.192/27
```

The subnet is `172.30.88.0/24`. Docker's automatic assignments are restricted to `172.30.88.192/27`, while the DHCP server will offer addresses between `172.30.88.100` and `172.30.88.150`. The services use fixed addresses outside both dynamically assigned ranges.

| Component | IP address or range | Who configures it? |
| --- | --- | --- |
| Bridge gateway | `172.30.88.1` | Docker |
| dnsmasq | `172.30.88.10` | Compose static address |
| Unbound | `172.30.88.11` | Compose static address |
| Web server (final task) | `172.30.88.12` | You, in Compose |
| DHCP clients | `172.30.88.100–150` | dnsmasq |
| Temporary container addresses | `172.30.88.192/27` | Docker IPAM |

The network address, gateway, service addresses, lease pool, and Docker IPAM range must not overlap inappropriately. The fixed service addresses are outside the Docker IPAM pool. If your Docker host already uses this subnet, choose another unused private `/24` and update **all** matching settings consistently.

## Exercise 1: obtain a DHCP lease

DHCP allows a client to learn its network settings without entering each value manually. The basic IPv4 exchange is commonly called DORA:

```text
Client                           DHCP server
  |                                   |
  | -------- DHCPDISCOVER ----------> |
  | <--------- DHCPOFFER -----------  |
  | -------- DHCPREQUEST ---------->  |
  | <--------- DHCPACK ------------  |
  |                                   |
```

The initial client typically sends a broadcast because it does not yet have an IPv4 address. The server responds with a proposed configuration; the client requests the offered address; the server acknowledges the lease. DHCP normally uses UDP port 67 on the server and port 68 on the client.

### Start the DHCP server

Open `dhcp/dnsmasq.conf`. The main settings are:

```ini
port=0
interface=eth0
bind-interfaces
dhcp-authoritative
log-dhcp
dhcp-range=172.30.88.100,172.30.88.150,255.255.255.0,10m
dhcp-option=option:router,172.30.88.1
```

The `port=0` setting disables dnsmasq's DNS service; here it acts only as a DHCP server. `dhcp-range` defines the address pool, subnet mask, and lease duration. The `router` option advertises the Docker bridge gateway. The configuration also saves leases in a named volume mounted at `/var/lib/misc`. The DHCP image gives the unprivileged dnsmasq user permission to write in that volume before starting the service.

Start only dnsmasq. Other services do not need to be running yet.

```console
docker compose up -d dhcp
docker compose ps
docker compose logs dhcp
```

Inspect the Compose network:

```console
docker network inspect pds-lab03_labnet
```

Find the address assigned to the dnsmasq container. It should be `172.30.88.10`.

### Start a client and inspect its original address

Open a client shell. The `client` service is under a manual profile, so Compose does not automatically start it with the server.

```console
docker compose run --rm --no-deps client
```

Inside this shell, first inspect the network interface and routing table.

```sh
ip -4 address show dev eth0
ip -4 route
cat /etc/resolv.conf
```

The client initially has an address from Docker's IPAM range. That address was **not** obtained from dnsmasq. The resolver configuration may also point to Docker's embedded DNS server (`127.0.0.11`).

### Request an actual DHCP lease

The Alpine image includes the BusyBox DHCP client, `udhcpc`. Its event script is responsible for applying the received IP address, route, and DNS settings. We supply a small script, `client/udhcpc-lab.sh`, because the ordinary Docker interface is initially configured by Docker. Read that script before running it.

Inside the client shell:

```sh
udhcpc -i eth0 -n -q -s /usr/local/bin/udhcpc-lab.sh
ip -4 address show dev eth0
ip -4 route
cat /tmp/dhcp-dns-servers
```

The DHCP client calls the script first with a `deconfig` event, which clears Docker's temporary IPv4 address, and then with `bound` after receiving a lease. The script applies the new address on the known `/24` lab network. The output should report an address in `172.30.88.100–150`. Exact addresses may differ.

The `-n` option makes `udhcpc` fail if it cannot obtain a lease, and `-q` exits after acquiring one. Thus this example demonstrates the initial allocation, **not an ongoing renewal daemon**.

From a second **host terminal** in `labs/lab-03/tutorial`, show the server's messages and lease file.

```console
docker compose logs dhcp
docker compose exec dhcp cat /var/lib/misc/dnsmasq.leases
```

Inspect the lease duration, client MAC address, and assigned IP address. Contrast the result with the Docker address recorded by `docker inspect` or `docker network inspect`.

### Capture the DHCP packets

The first request has already completed. Create another disposable client by opening a second shell from the host:

```console
docker compose run --rm --no-deps client
```

Inside this new client shell, start a capture in the background **before** requesting a lease.

```sh
tcpdump -ni eth0 -vv 'udp port 67 or udp port 68' &
CAPTURE_PID=$!
udhcpc -i eth0 -n -q -s /usr/local/bin/udhcpc-lab.sh
kill "$CAPTURE_PID"
```

The capture should show the four DHCP messages, including the offered IPv4 address and DHCP options. `tcpdump` may display protocol names instead of the four message names; look for the DHCP message-type options. The capture can include additional traffic.

**Questions:** Which message contains the offered address? Which message confirms the lease? Why can the client initially send DHCP traffic without an IPv4 address? Why is the advertised router `.1` rather than the dnsmasq server `.10`? Why does Docker still report a different address from the one shown inside the client?

Exit both experimental client shells before continuing. This prevents the modified client network configuration from affecting later tasks.

## Exercise 2: configure a caching DNS resolver

DNS translates names into records such as IPv4 `A` addresses. A recursive resolver finds or requests the necessary DNS information on behalf of a client. A caching resolver stores responses for a limited time and may answer repeated questions without contacting an upstream server again.

In this exercise Unbound will operate as a **forwarding caching resolver**: it will accept questions from the lab network and forward cache misses to upstream recursive resolvers. It will not contact the DNS root servers directly. DNS records have a time-to-live (TTL), which limits how long an answer can remain valid in a cache.

### Read the Unbound configuration

Open `resolver/unbound.conf`. It contains these settings:

```yaml
server:
    interface: 0.0.0.0
    port: 53
    do-ip6: no
    access-control: 172.30.88.0/24 allow
    extended-statistics: yes
    prefetch: no
    cache-min-ttl: 0
    cache-max-ttl: 3600

remote-control:
    control-enable: yes
    control-interface: 127.0.0.1
    control-use-cert: no

forward-zone:
    name: "."
    forward-addr: 1.1.1.1
    forward-addr: 9.9.9.9
```

This excerpt omits a few settings present in the complete supplied file. The `interface` option makes Unbound listen for requests from other containers, while `access-control` permits recursive queries only from the isolated lab subnet. `forward-zone` names the upstream recursive DNS servers. `control-interface` limits the administrative interface to Unbound's own loopback interface; it must not be exposed outside the container.

The resolver container also sets `username` and `chroot` to empty values for simplicity in this isolated teaching setup. This is not a recommended production deployment.

### Start and verify Unbound

From the **host terminal**, check the configuration and start Unbound:

```console
docker compose run --rm --no-deps --entrypoint unbound-checkconf resolver -c /etc/unbound/unbound.conf
docker compose up -d resolver
docker compose ps
docker compose logs resolver
```

The configuration check should report no errors. Query the server from a temporary client, without using the host machine's DNS configuration:

```console
docker compose run --rm --no-deps client dig @172.30.88.11 example.org A +noall +answer +stats
```

`@172.30.88.11` explicitly identifies Unbound as the DNS server. The `A` record type requests IPv4 addresses. The `+stats` option includes query time and server information.

Do not infer caching from response time alone. Network conditions and upstream caches can affect the first response. Unbound's own cache counters provide stronger evidence.

### Measure cache hits and misses

Flush any existing entry for `example.org` and inspect the initial counters:

```console
docker compose exec resolver unbound-control -c /etc/unbound/unbound.conf flush example.org
docker compose exec resolver unbound-control -c /etc/unbound/unbound.conf stats_noreset
```

Find `total.num.cachehits` and `total.num.cachemiss`, or the corresponding `thread0.*` counters if the total fields are not present. The counters are cumulative during the resolver's current runtime.

Now execute the same query twice in quick succession, from the host terminal:

```console
docker compose run --rm --no-deps client dig @172.30.88.11 example.org A +noall +answer +stats
docker compose run --rm --no-deps client dig @172.30.88.11 example.org A +noall +answer +stats
docker compose exec resolver unbound-control -c /etc/unbound/unbound.conf stats_noreset
```

Compare the before and after counters. The first lookup after flushing should need recursive processing, while a repeated lookup made before the entry expires should normally produce a cache hit. Other DNS activity can also change the counters, so compare the **differences** rather than assuming the counters start at zero.

Inspect the TTL in the answer section. If the same record is returned from the cache, the remaining TTL should normally decrease with elapsed time. Do not use a permanently changing public name as a test of cache behavior without inspecting its response and TTL.

### Study other DNS records

Use `dig` to request different record types from the same resolver:

```console
docker compose run --rm --no-deps client dig @172.30.88.11 example.org NS +noall +answer
docker compose run --rm --no-deps client dig @172.30.88.11 example.org MX +noall +answer
```

An `A` record maps a name to an IPv4 address; an `NS` record identifies authoritative name servers for a DNS zone; an `MX` record describes mail exchange destinations. A domain is not required to have every record type. If a query produces no answer, inspect its response status before claiming a network failure.

**Questions:** What is the difference between a cache hit and a cache miss? Why does DNS caching reduce work for a resolver? Can two names resolve to the same IP address? Why is the cache lifetime not necessarily equal to the time that the container stays running? How does querying `@172.30.88.11` differ from using the resolver written in `/etc/resolv.conf`?

## Final task: DHCP-configured service discovery

In Lab 2 a client could access a server through its Compose service name. In this task you will create an additional HTTP service and access it by a DNS name announced through your own network configuration rather than through Docker's embedded DNS service.

Your goal is to make the following chain work:

```text
DHCP client -- DHCP option 6 --> dnsmasq
     |
     | DNS server address = 172.30.88.11
     v
  Unbound -- local A record --> web.lab.test = 172.30.88.12
     |
     v
  Nginx web server at 172.30.88.12:80
```

Use the existing `tutorial` project and edit its configuration; you do not need to create another application from scratch. This final task combines networking, Compose, HTTP, DHCP, and DNS.

### Step 1: add a web service

Extend `compose.yaml` with a service named `web` that runs the `nginx:alpine` image and joins `labnet` using the **static IPv4 address** `172.30.88.12`. The server must be reachable by other containers on this network. You do not need to publish an HTTP port on the Docker host.

Start the web server and confirm that it runs. From a fresh client, first access `http://172.30.88.12` by IP address using `wget` (available in Alpine). This proves that the HTTP service works before DNS is involved.

### Step 2: define a local DNS name

Edit `resolver/unbound.conf` to define the local zone `lab.test.` and an `A` record named `web.lab.test.` pointing to `172.30.88.12`, with a TTL of 60 seconds. The `.test` top-level domain is reserved for testing; it is not intended for public DNS delegation.

Read about the Unbound `local-zone` and `local-data` options, then add suitable settings under `server:`. Use a `static` local zone so that names not defined in this zone do not get forwarded to public resolvers.

Check the configuration, recreate Unbound using Compose, and verify the answer from a client using `dig @172.30.88.11 web.lab.test A`. Show the answer's address and TTL. Confirm that another name in the local zone without a record does not resolve to your web server.

### Step 3: advertise the DNS resolver using DHCP

Edit `dhcp/dnsmasq.conf` to advertise `172.30.88.11` as the DNS server using **DHCP option 6**. Keep the existing lease pool and router option unchanged.

Rebuild and recreate the DHCP service:

```console
docker compose up -d --build dhcp
```

Start a **new client container** with a shell. Inspect its initial IPv4 address and `/etc/resolv.conf` before requesting a DHCP lease. Then run:

```sh
udhcpc -i eth0 -n -q -s /usr/local/bin/udhcpc-lab.sh
cat /tmp/dhcp-dns-servers
cat /etc/resolv.conf
ip -4 address show dev eth0
```

The supplied `udhcpc-lab.sh` reads the DNS addresses received through DHCP and installs them in the client's `/etc/resolv.conf` file. It does not consult Docker Compose service names. **Confirm that the DNS server came from the DHCP exchange**, not from Docker's original resolver settings. If necessary, repeat the DHCP packet capture from Exercise 1 and examine the DHCP option list in the OFFER or ACK.

### Step 4: access the web service by name

With the same DHCP-configured client, test both DNS and HTTP:

```sh
nslookup web.lab.test
wget -qO- http://web.lab.test/
```

A successful result resolves `web.lab.test` to `172.30.88.12` and returns the default Nginx page. The commands do not specify the DNS server explicitly. Name resolution should use the server announced by DHCP and written into `/etc/resolv.conf`.

Test the effect of stopping the resolver, while keeping the web server running. Try the hostname again from a fresh client. Does connecting to the web server's IP address still work? Explain the difference between a DNS failure and a web-server failure. Restart the resolver afterward.

### Required verification

Demonstrate the following checks to the laboratory instructor:

| Check | Required evidence |
| --- | --- |
| DHCP lease | Address in `172.30.88.100–150` shown inside client |
| DHCP exchange | Discover, Offer, Request, ACK visible in capture or server log |
| DHCP DNS configuration | Option 6 advertises `172.30.88.11` |
| DNS caching | Unbound counters show cache misses and subsequent hits |
| Local DNS record | `web.lab.test` resolves to `172.30.88.12` |
| HTTP by hostname | `wget http://web.lab.test/` returns the Nginx page |
| Failure diagnosis | Explain results with DNS unavailable but web server still running |

Explain the difference between the automatically assigned Docker IP address, the DHCP lease, the Unbound DNS address, and the address returned by the `web.lab.test` DNS record. These four values have different roles.

### Optional extension

Create a second local DNS name for the same Nginx container, but give it a different TTL. Verify both names and compare their answer TTLs. Explain whether the records must be cached, whether the web server is aware of these DNS names, and what might change if the web server requires virtual-host configuration.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| DHCP client receives no offer | dnsmasq status, same Docker network, subnet, UDP 67/68, server logs |
| Client still has Docker's original IP | Use the supplied `udhcpc` script and inspect `ip -4 address` inside the client |
| `docker inspect` reports a different client IP | Docker IPAM tracks the original endpoint address; use the in-container IP for this exercise |
| DNS query times out | Unbound logs, `172.30.88.11`, access control, outbound access to forwarders |
| `unbound-control` fails | Confirm resolver is running, control config is loaded, and command executes **inside** resolver |
| Cache counter does not change as expected | Flush the name, check TTL, avoid other queries, compare before/after counter values |
| `web.lab.test` returns NXDOMAIN | Local-zone/local-data spelling, trailing dots, resolver rebuild/recreation |
| `nslookup` uses `127.0.0.11` | The new client has not applied DHCP option 6; inspect the script output and `/etc/resolv.conf` |
| IP-based HTTP works but hostname fails | DNS configuration or local DNS record, not the web server itself |
| Host networking acts unexpectedly | Do not use host mode; inspect the Compose bridge and check for overlapping host/VPN subnets |

## Cleanup

Exit any client shells and return to `labs/lab-03/tutorial` on the host. Remove the project containers and network:

```console
docker compose down
```

The DHCP lease volume remains. To delete the volume and its lease history as well, use:

```console
docker compose down --volumes
```

This command does not delete the Compose file or source configurations. It only affects the resources belonging to this Compose project. Do not use broad commands such as `docker system prune` for routine laboratory cleanup.

## References

| Topic | Documentation |
| --- | --- |
| Docker IPAM and static addresses | [Docker network connect](https://docs.docker.com/reference/cli/docker/network/connect/) and [Compose network IPAM](https://docs.docker.com/reference/compose-file/networks/) |
| DHCP basics | [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131) and [DHCP options, RFC 2132](https://www.rfc-editor.org/rfc/rfc2132) |
| dnsmasq configuration | [dnsmasq manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html) |
| BusyBox DHCP client | [udhcpc event scripts](https://git.busybox.net/busybox/tree/examples/udhcp) |
| Unbound configuration | [Unbound configuration reference](https://unbound.docs.nlnetlabs.nl/en/latest/manpages/unbound.conf.html) |
| Unbound cache statistics | [unbound-control manual](https://unbound.docs.nlnetlabs.nl/en/latest/manpages/unbound-control.html) |
| Domain reserved for tests | [RFC 6761](https://www.rfc-editor.org/rfc/rfc6761) |
