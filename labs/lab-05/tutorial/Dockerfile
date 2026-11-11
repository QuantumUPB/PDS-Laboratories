FROM alpine:3.24

# Nebula is supplied by Alpine's community package repository.
# The same image is used for VPN peers and the certificate utility.
RUN apk add --no-cache nebula iproute2 curl python3 tcpdump bind-tools
COPY app/entrypoint.sh /usr/local/bin/lab-entrypoint.sh
RUN chmod 755 /usr/local/bin/lab-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/lab-entrypoint.sh"]
CMD ["nebula"]
