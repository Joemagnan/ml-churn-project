# Logstash avec le pipeline « fichier JSON de l'API -> Elasticsearch ».
# Le pipeline par défaut de l'image (entrée beats) est remplacé par le nôtre.
FROM docker.elastic.co/logstash/logstash:8.19.5
RUN rm -f /usr/share/logstash/pipeline/*.conf
COPY pipeline/ /usr/share/logstash/pipeline/
COPY templates/ /usr/share/logstash/templates/
