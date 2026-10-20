FROM alpine:3.22
RUN apk add --no-cache iproute2 bind-tools tcpdump
COPY udhcpc-lab.sh /usr/local/bin/udhcpc-lab.sh
RUN chmod +x /usr/local/bin/udhcpc-lab.sh
CMD ["sh"]
