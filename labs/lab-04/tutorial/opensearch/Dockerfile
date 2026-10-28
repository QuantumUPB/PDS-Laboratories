FROM opensearchproject/opensearch:3.9.0

RUN /usr/share/opensearch/bin/opensearch-plugin install --batch repository-s3

# Fixed credentials are for this isolated teaching project only.
RUN /usr/share/opensearch/bin/opensearch-keystore create && \
    printf '%s' 'labadmin' | /usr/share/opensearch/bin/opensearch-keystore add --stdin s3.client.default.access_key && \
    printf '%s' 'labsecret123' | /usr/share/opensearch/bin/opensearch-keystore add --stdin s3.client.default.secret_key
