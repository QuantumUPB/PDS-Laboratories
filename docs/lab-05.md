# Lab 6 VPN

## Objective

In this lab you will set up a Nebula VPN, control access to a service, and deal with a certificate that gives its owner more access than intended. The last exercise covers a stolen private key and certificate revocation.

## Requirements and files

You need Docker with Compose and a shell that can run the supplied scripts. Use Docker Engine on Linux or a Docker Desktop installation whose Linux daemon exposes `/dev/net/tun`. If that device is unavailable, use a Linux VM with Docker Engine. Nebula needs access to a TUN device and the `NET_ADMIN` capability; the Compose file provides the container settings.

From the repository root:

```console
cd labs/lab-06/tutorial
docker compose version
```

| Path | Use |
| --- | --- |
| `compose.yaml` | Containers and the Docker underlay network |
| `configs/` | Initial Nebula configuration files; do not edit these during the exercises |
| `state/configs/` | Working configuration files created by setup; **edit these** |
| `state/peers/` | Host certificates and private keys |
| `state/authority/` | Lab certificate authority (CA) certificate and private key |
| `scripts/` | Setup, incident, certificate reissue, checks, and reset |
| `files/report.txt` | File that the employee should be able to read |

The `state/` directory is created locally and excluded from Git. It contains private keys. Do not upload it or use its credentials outside this lab.

## Network layout

All containers share a Docker network (`172.28.66.0/24`). Nebula gives each VPN peer a separate address (subnet `192.168.100.0/24`). Docker carries the encrypted UDP traffic; applications will use Nebula addresses.

| Peer | Docker address | Nebula address | Role |
| --- | --- | --- | --- |
| Lighthouse | `172.28.66.10` | `192.168.100.1` | Helps peers find one another |
| Employee | `172.28.66.11` | `192.168.100.10` | Allowed to read the report |
| Contractor | `172.28.66.12` | `192.168.100.30` | Not allowed to read the report |
| File server | `172.28.66.13` | `192.168.100.20` | Serves the report on TCP port 8080 |
| Attacker | `172.28.66.14` | Uses a stolen identity | Used in the final task only |

A lighthouse is a discovery service, not a central relay (although it can be configured to act as one) or certificate authority (as it is not recommended, typically being the sole one with an exposed public IP). The file server binds its HTTP service to `192.168.100.20`, so an HTTP request sent to its Docker address cannot bypass the VPN policy.

## Task 1: start the VPN

Run:

```console
sh scripts/setup.sh
```

This builds the image, generates a new lab CA and host certificates, and starts the lighthouse, employee, contractor, and file server. The CA private key is used by the temporary certificate tool, not mounted in the running VPN peers.

Check the container state and Nebula interface:

```console
docker compose ps
docker compose exec employee ip -4 addr show dev nebula1
docker compose exec employee ip -4 route
docker compose exec employee ping -c 2 192.168.100.20
```

You should find `192.168.100.10/24` on the employee's `nebula1` interface. The ping to the file server should work. If it fails on the first attempt, inspect `docker compose logs employee` and try again once the peers have connected.

Print the employee certificate:

```console
docker compose run --rm -T certtool print -path /state/peers/employee/host.crt
```

Find the host name, IP address, certificate group, and issuer. In `state/configs/employee.yml`, find the Docker address of the lighthouse and the Nebula address used to identify it.

Now check the starting access policy:

```console
sh scripts/check.sh network
```

The tunnel works, but HTTP access is not yet allowed. That is intentional. You will add the rule in Task 2.

## Task 2: allow the employee, not the contractor

The file server currently accepts ICMP over Nebula but has no rule allowing HTTP. Open `state/configs/fileserver.yml` and find `firewall.inbound`.

Add **one rule** with this policy:

| Field | Required value |
| --- | --- |
| Protocol | TCP |
| Port | `8080` |
| Certificate group | `employee` |

Use the format of the existing firewall rules or the [Nebula firewall reference](https://nebula.defined.net/docs/config/firewall/). Do not allow `host: any` for TCP port 8080, and do not change the certificate groups.

Restart the file server to apply the edited configuration:

```console
docker compose restart fileserver
```

Test the employee and contractor separately:

```console
docker compose exec employee curl -fsS --max-time 5 http://192.168.100.20:8080/report.txt
docker compose exec contractor curl --connect-timeout 2 --max-time 5 http://192.168.100.20:8080/report.txt
```

The employee should receive the report. The contractor should not. Run the checker:

```console
sh scripts/check.sh baseline
```

The checker also tries the file server's Docker address to ensure there is no direct HTTP path around Nebula.

### Observe the traffic

Open two terminals. In the first, capture UDP traffic on the employee's Docker interface:

```console
docker compose exec employee tcpdump -ni eth0 udp port 4242
```

In the second, request the report again:

```console
docker compose exec employee curl -fsS http://192.168.100.20:8080/report.txt
```

Stop `tcpdump` with Ctrl+C. You should see Nebula UDP packets, not the HTTP request body. If you capture on `nebula1` instead, you inspect the inner packets after decryption. A packet capture does not, by itself, prove that an encryption algorithm is secure.

## Task 3: an incorrectly issued certificate

A contractor reports that they can now open the employee-only report. An administrator recently issued a replacement contractor certificate.

Introduce the incident:

```console
sh scripts/introduce-incident.sh
sh scripts/check.sh incident
```

The checker should confirm that the contractor now reaches the report. Investigate **before** changing the file server firewall.

Print the current contractor certificate and compare its groups with the access rule from Task 2:

```console
docker compose run --rm -T certtool print -path /state/peers/contractor/host.crt
```

Write down what is wrong and why Nebula accepted the connection. A certificate can have a valid signature and still carry incorrect permissions.

Issue a replacement certificate using the correct group. The helper takes the group name as its argument:

```console
sh scripts/reissue-contractor.sh GROUP_NAME
```

Replace `GROUP_NAME` with the group the contractor should have. The script generates a new keypair and restarts the contractor. It does **not** revoke the previous certificate.

Check your repair:

```console
sh scripts/check.sh reissued
```

The employee should still read the report and the contractor should be denied. If the checker fails, inspect the new certificate and the file server's firewall rule.

## Final task: stolen credentials

During the previous incident, someone copied the contractor's **old certificate and private key**. The files are in `state/incident/stolen/`. They are still signed by the lab CA. The replacement issued in Task 3 did not invalidate them.

Print the stolen certificate and record its **fingerprint**:

```console
docker compose run --rm -T certtool print -path /state/incident/stolen/host.crt
```

The copied identity uses the same Nebula IP as the contractor. Stop the legitimate contractor before starting the attacker container:

```console
docker compose stop contractor
docker compose --profile incident up -d attacker
sh scripts/check.sh stolen
```

The attacker should be able to read the report. The attacker has the old `employee` group claim, even though it is not the legitimate employee.

### Part A: try blocking the certificate at the lighthouse

Open `state/configs/lighthouse.yml` and add the stolen certificate fingerprint to `pki.blocklist`. Keep the existing PKI paths. The format is a YAML list:

```yaml
blocklist:
  - YOUR_FINGERPRINT_HERE
```

Restart the lighthouse and attacker, then repeat the test:

```console
docker compose --profile incident restart lighthouse attacker
sh scripts/check.sh stolen
```

The attacker should still reach the report. The attacker has a static mapping to the file server, so it can contact that peer without using the lighthouse for discovery. More importantly, a lighthouse does **not** distribute its certificate blocklist to other peers.

### Part B: revoke the certificate at the file server

Add the same fingerprint to `pki.blocklist` in `state/configs/fileserver.yml`. Restart the protected peer and the attacker:

```console
docker compose --profile incident restart fileserver attacker
sh scripts/check.sh revoked
```

The attacker should now be denied, while the employee still works. In an actual deployment, revocation data needs to reach **every peer that must reject that credential**. Blocking it only at the lighthouse is not a network-wide revocation mechanism.

**Final questions:** Why did certificate reissuance not fix the compromised identity? Why is stealing a certificate without its private key different from stealing both? What would you have to distribute to every peer after a real credential compromise?

## Cleanup

Stop the containers while keeping the generated keys:

```console
docker compose --profile incident down
```

To start again from scratch, remove the generated **lab** credentials and configurations:

```console
sh scripts/reset.sh
sh scripts/setup.sh
```

`reset.sh` deletes only `labs/lab-06/tutorial/state/`. Do not use the lab CA or its private key on real systems.

## References

- [Nebula quick start](https://nebula.defined.net/docs/guides/quick-start/)
- [Nebula firewall configuration](https://nebula.defined.net/docs/config/firewall/)
- [Nebula PKI and certificate blocklist](https://nebula.defined.net/docs/config/pki/)
- [Nebula host discovery](https://nebula.defined.net/docs/guides/host-discovery/)
- [strongSwan IKEv2/IPsec documentation](https://docs.strongswan.org/)
