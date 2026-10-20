FROM alpine:3.22
RUN apk add --no-cache unbound
COPY unbound.conf /etc/unbound/unbound.conf
CMD ["unbound", "-d", "-c", "/etc/unbound/unbound.conf"]
