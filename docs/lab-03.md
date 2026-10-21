# Lab 3 DHCP and DNS services

## Purpose

In this lab you will configure a DHCP server, request an IPv4 lease from a real DHCP client, run a caching DNS resolver using Unbound, and observe the effect of cached DNS responses. In the final task you will connect these services to a web application: DHCP will tell the client which DNS server to use, and DNS will translate the application's hostname into its IP address.

At the end of the laboratory you should be able to explain the DHCP exchange, distinguish Docker's IPAM from DHCP, identify the DHCP option used to advertise DNS servers, configure a forwarding DNS cache, and verify a locally defined DNS record.

## Required environment

You need Docker Engine or Docker Desktop with the Docker Compose plugin. The examples use a Linux container network and work from the terminal on Linux, macOS, or Windows PowerShell. Docker Desktop runs Linux containers in a virtual machine on Windows and macOS. You do not need to configure DHCP on the host network.

```console
docker version
docker compose version
```

The laboratory requires Internet access to download container images and Alpine packages.

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

The Alpine image includes the BusyBox DHCP client, `udhcpc`. Its event script is responsible for applying the received IP address, route, and DNS settings. We supply a small script, `client/udhcpc-lab.sh`, because the ordinary Docker interface is initially configured by Docker.

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
docker compose run --rm --no-deps --entrypoint unbound-checkconf resolver
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
docker compose exec resolver unbound-control -c /etc/unbound/unbound.conf stats_noreset | grep -E '^total\.num\.(cachehits|cachemiss)='
```

Find `total.num.cachehits` and `total.num.cachemiss`, or the corresponding `thread0.*` counters if the total fields are not present. The counters are cumulative during the resolver's current runtime.

Now execute the same query twice in quick succession, from the host terminal:

```console
docker compose run --rm --no-deps client dig @172.30.88.11 example.org A +noall +answer +stats
docker compose run --rm --no-deps client dig @172.30.88.11 example.org A +noall +answer +stats
docker compose exec resolver unbound-control -c /etc/unbound/unbound.conf stats_noreset | grep -E '^total\.num\.(cachehits|cachemiss)='
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

In the previous exercises, you obtained an address from a DHCP server and queried an Unbound DNS resolver. Now connect these services. Your client should receive the DNS server address through DHCP and use that server to resolve a local web application name.

At the end of the task, the following process must work:

```text
                 DHCPDISCOVER / DHCPREQUEST
Client ------------------------------------------> dnsmasq (172.30.88.10)
       <------------------------------------------
                  Lease + DNS option 6
                  (DNS server: 172.30.88.11)

Client ---------- DNS: web.lab.test? ------------> Unbound (172.30.88.11)
       <------------------------------------------
                     A: 172.30.88.12

Client --------- HTTP: web.lab.test -------------> Nginx (172.30.88.12)
       <------------------------------------------
                       Web page
```

Work in the existing `labs/lab-03/tutorial` directory. You will edit **three files**: `compose.yaml`, `resolver/unbound.conf`, and `dhcp/dnsmasq.conf`. The supplied client image and DHCP event script do not need changes.

All `docker compose` commands below run in a **host terminal** in `labs/lab-03/tutorial`. Commands shown after opening the interactive client shell run **inside that client container**. Keep the host terminal available to start and stop services.

### Part 1: add and test an HTTP service

Add a service named `web` under the existing `services:` section of `compose.yaml`. Use the `nginx:alpine` image and give the service a fixed IP address of `172.30.88.12` on `labnet`.

The service definition has the following form:

```yaml
services:
  # Existing dhcp, resolver, and client services remain here.
  web:
    image: nginx:alpine
    networks:
      labnet:
        ipv4_address: 172.30.88.12
```

**Do not add a second `services:` section.** Insert only the `web:` block into the existing one, using the same indentation level as `dhcp:` and `resolver:`. Do not remove the existing services or network definition. You do not need a `ports:` entry: the web server is accessed by another container on the same Docker network, not through a host port.

Validate the file and start Nginx from the host terminal:

```console
docker compose config
docker compose up -d web
docker compose ps
```

Now test HTTP without involving DNS. From the host terminal, open a disposable client shell:

```console
docker compose run --rm --no-deps client
```

Inside that client, run:

```sh
wget -qO- http://172.30.88.12/
```

**Checkpoint:** You should see the default Nginx HTML page. If this request fails, do not continue to DNS configuration. Verify the `web` service's status, static IP address, and membership in `labnet`.

Exit the client shell with `exit`. You will start a new client later when testing DHCP.

### Part 2: create the DNS record in Unbound

Open `resolver/unbound.conf`. Unbound already forwards public DNS queries upstream. Keep that configuration and add a **local zone** for the laboratory application.

You need two directives in the existing `server:` section:

- `local-zone` declares which DNS names Unbound handles locally. The type `static` means that an unknown name in this zone will not be forwarded to the public DNS servers.
- `local-data` adds a DNS record. An `A` record associates a hostname with an IPv4 address. Its syntax is `"<hostname>. <TTL> IN A <IPv4-address>"`.

For example, an unrelated local record could be defined as follows:

```yaml
server:
    # Other existing server options remain unchanged.
    local-zone: "example.test." static
    local-data: "host.example.test. 120 IN A 172.30.88.20"
```

**Your task:** Adapt these directives to define the zone `lab.test.` and the record `web.lab.test.` with address `172.30.88.12` and TTL **60 seconds**. Add them under the existing `server:` heading. Do not put them under `forward-zone:` and do not add another `server:` heading. Keep the final dot in the complete DNS names.

Check the file and rebuild the resolver image because the Dockerfile copies `unbound.conf` into that image:

```console
docker compose run --rm --no-deps --entrypoint unbound-checkconf resolver
docker compose up -d --build resolver
```

Verify the record from the host terminal with a disposable client:

```console
docker compose run --rm --no-deps client dig @172.30.88.11 web.lab.test A +noall +answer +comments
docker compose run --rm --no-deps client dig @172.30.88.11 missing.lab.test A +noall +answer +comments
```

The first response should include an `A` record for `172.30.88.12`. The second request should not return an address for `missing.lab.test`; with the `static` zone it should normally return `NXDOMAIN`. Inspect the response status rather than treating an empty answer as proof of failure.

**Checkpoint:** Unbound resolves the local name correctly when the client explicitly specifies the resolver address. DHCP is not involved in these two tests.

### Part 3: send the DNS server address through DHCP

Open `dhcp/dnsmasq.conf`. In Exercise 1, dnsmasq advertised an address from its lease pool and a default gateway. DHCP can also send a list of DNS resolvers in **option 6**.

In dnsmasq, the directive has this form:

```ini
dhcp-option=option:dns-server,<DNS_SERVER_IP>
```

Replace `<DNS_SERVER_IP>` with the fixed IP address of your Unbound container. Keep the existing `dhcp-range` and `option:router` settings unchanged. The `dns-server` option is different from the router option: it tells clients where to send DNS queries, not where to forward general IP traffic.

Rebuild and recreate dnsmasq to apply the edited file:

```console
docker compose up -d --build dhcp
docker compose logs dhcp
```

Start a **new** client shell from the host:

```console
docker compose run --rm --no-deps client
```

Before starting DHCP, inspect Docker's original client configuration:

```sh
ip -4 address show dev eth0
cat /etc/resolv.conf
```

Now request a lease using the supplied event script:

```sh
udhcpc -i eth0 -n -q -s /usr/local/bin/udhcpc-lab.sh
ip -4 address show dev eth0
cat /tmp/dhcp-dns-servers
cat /etc/resolv.conf
```

The script removes the temporary address assigned by Docker, applies the leased address, and writes the DNS servers received from DHCP to `/etc/resolv.conf`.

**Checkpoint:** Verify both of the following before continuing:

1. `eth0` has an IPv4 address in `172.30.88.100–150`.
2. `/tmp/dhcp-dns-servers` and `/etc/resolv.conf` identify `172.30.88.11` as the DNS server, rather than Docker's initial `127.0.0.11` resolver.

If these conditions do not hold, inspect `docker compose logs dhcp` in the host terminal. You can also repeat the packet capture from Exercise 1 and find the DNS server option in the DHCP OFFER or ACK. Do not use `docker inspect` to verify the DHCP lease: Docker still tracks the temporary IP address it allocated when creating the container.

**Keep this client shell open for the remaining steps.** It now represents a client configured by your DHCP server.

### Part 4: resolve the hostname and access the web server

Inside the **same DHCP-configured client**, run the following commands:

```sh
dig web.lab.test A +noall +answer +stats
nslookup web.lab.test
wget -qO- http://web.lab.test/
```

Notice that the first two commands do **not** include `@172.30.88.11` or another explicit resolver argument. They use the DNS configuration installed by the DHCP event script. The HTTP command also uses the hostname instead of the server's IP address.

**Checkpoint:** The DNS response identifies `172.30.88.12` and the HTTP request displays the Nginx page.

Explain why each of these values has a different role: the client's leased address, the DNS server's address (`172.30.88.11`), and the address returned for `web.lab.test` (`172.30.88.12`).

### Part 5: investigate a DNS failure

Keep the DHCP-configured client shell open. From the **host terminal**, stop only the resolver:

```console
docker compose stop resolver
```

Now return to the **existing client shell** and repeat a DNS query, followed by a direct HTTP request:

```sh
dig +time=2 +tries=1 web.lab.test A
wget -qO- http://172.30.88.12/
```

The DNS query should time out or fail while Unbound is stopped. The HTTP request by IP address should still succeed because Nginx is running independently of the resolver. These commands also avoid relying on a previously resolved hostname or another DNS server.

Restore Unbound from the host terminal:

```console
docker compose start resolver
```

In the client shell, check that name resolution and access by hostname work again:

```sh
dig web.lab.test A +noall +answer
wget -qO- http://web.lab.test/
```

**Checkpoint:** You can explain which part of the network stopped working, why direct HTTP by IP continued to work, and why restarting Unbound restored hostname-based access.

### Required verification

Demonstrate these checks to the laboratory instructor:

| Check | Required result |
| --- | --- |
| Web service | `wget` reaches `172.30.88.12` before DNS is configured |
| Local DNS | An explicit query to `172.30.88.11` returns the `web.lab.test` A record with TTL 60 |
| DHCP configuration | Client receives a lease in `172.30.88.100–150` and DNS server `172.30.88.11` in option 6 |
| DNS through DHCP | `dig web.lab.test A` succeeds **without** an explicit `@server` argument |
| Service discovery | `wget -qO- http://web.lab.test/` returns the Nginx page |
| Failure test | DNS fails while Unbound is stopped, but HTTP by IP still works |

The cache-hit and cache-miss observations from **Exercise 2** remain part of the laboratory. Do not try to demonstrate a recursive-cache hit using only `web.lab.test`: Unbound serves that name from its local configuration.

### Questions

1. Which DHCP option identifies the DNS server? Does it contain the address of Nginx or of Unbound?
2. Why could the client reach Nginx by IP address before you configured the local DNS record?
3. Why do the commands without `@172.30.88.11` demonstrate more than a manually directed DNS query?
4. If the Nginx container changed its address, which configuration would you need to update? Would the DHCP option also need to change?

### Optional extension

Add another hostname, `portal.lab.test`, pointing to the same Nginx IP address, with a TTL of 120 seconds. Query both records and compare the returned TTLs. Explain why changing the DNS name does not require changing the Nginx container's address.

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
