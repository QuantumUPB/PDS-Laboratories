FROM alpine:3.22
RUN apk add --no-cache dnsmasq && mkdir -p /var/lib/misc
COPY dnsmasq.conf /etc/dnsmasq.conf
CMD ["sh", "-c", "chown -R nobody:nobody /var/lib/misc && exec dnsmasq --no-daemon --conf-file=/etc/dnsmasq.conf"]
