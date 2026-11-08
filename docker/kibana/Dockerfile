# Image ponctuelle qui importe la vue de données et le dashboard dans Kibana.
FROM docker.elastic.co/kibana/kibana:8.19.5
COPY setup-kibana.sh ml-churn-kibana.ndjson /setup/
ENTRYPOINT ["/bin/bash", "/setup/setup-kibana.sh"]
