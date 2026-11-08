"""Génère ml-churn-kibana.ndjson : vue de données, recherches enregistrées,
visualisations et dashboard Kibana pour les logs de l'API.

    python docker/kibana/build_saved_objects.py

Le fichier est importé automatiquement par le service « kibana-setup » du
docker-compose (setup-kibana.sh).
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name("ml-churn-kibana.ndjson")
DATA_VIEW_ID = "ml-churn-logs"
INDEX_REF = "kibanaSavedObjectMeta.searchSourceJSON.index"


def search_source(query: str) -> str:
    return json.dumps({"query": {"query": query, "language": "kuery"}, "filter": [],
                       "indexRefName": INDEX_REF})


def refs():
    return [{"name": INDEX_REF, "type": "index-pattern", "id": DATA_VIEW_ID}]


def saved_search(obj_id, title, query, columns):
    return {"id": obj_id, "type": "search", "references": refs(), "attributes": {
        "title": title, "description": "", "columns": columns,
        "sort": [["@timestamp", "desc"]],
        "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}}}


def visualization(obj_id, title, query, vis_state):
    vis_state = {"title": title, **vis_state}
    return {"id": obj_id, "type": "visualization", "references": refs(), "attributes": {
        "title": title, "description": "", "version": 1, "uiStateJSON": "{}",
        "visState": json.dumps(vis_state),
        "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}}}


COUNT = {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}


def metric_vis(label):
    return {"type": "metric", "aggs": [{**COUNT, "params": {"customLabel": label}}], "params": {
        "type": "metric", "addTooltip": True, "addLegend": False,
        "metric": {"percentageMode": False, "useRanges": False, "colorSchema": "Green to Red",
                   "metricColorMode": "None", "colorsRange": [{"from": 0, "to": 10000}],
                   "labels": {"show": True}, "invertColors": False,
                   "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "",
                             "fontSize": 48}}}}


def axes(value_title):
    return {
        "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom", "show": True,
                          "scale": {"type": "linear"}, "labels": {"show": True, "filter": True, "truncate": 100},
                          "title": {}}],
        "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left",
                       "show": True, "scale": {"type": "linear", "mode": "normal"},
                       "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": value_title}}],
        "addTooltip": True, "legendPosition": "right", "times": [], "addTimeMarker": False,
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
        "labels": {}, "palette": {"type": "palette", "name": "default"},
    }


def series(agg_id, label, kind="line", mode="normal"):
    return {"show": True, "type": kind, "mode": mode, "data": {"label": label, "id": agg_id},
            "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True, "lineWidth": 2,
            "showCircles": True, "interpolate": "linear"}


DATE_HIST = {"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
             "params": {"field": "@timestamp", "interval": "auto", "min_doc_count": 1,
                        "extended_bounds": {}, "useNormalizedEsInterval": True}}

objects = [
    {"id": DATA_VIEW_ID, "type": "index-pattern", "references": [], "attributes": {
        "title": "ml-churn-logs-*", "name": "ML Churn – logs de l'API", "timeFieldName": "@timestamp"}},

    saved_search("search-predictions", "Prédictions de churn", "operation : \"predict\"",
                 ["prediction", "probability", "response_time_ms", "model_time_ms", "model_version",
                  "client_id", "request_id"]),
    saved_search("search-errors", "Erreurs de l'API", "level : \"ERROR\" or status_code >= 500",
                 ["message", "error", "endpoint", "status_code", "model_version", "client_id", "request_id"]),
    saved_search("search-http", "Requêtes HTTP", "endpoint : *",
                 ["method", "endpoint", "status_code", "response_time_ms", "client_id", "client_ip"]),

    visualization("vis-predictions-count", "Nombre de prédictions", "operation : \"predict\"",
                  metric_vis("Prédictions")),
    visualization("vis-errors-count", "Nombre d'erreurs (level ERROR)", "level : \"ERROR\"",
                  metric_vis("Erreurs")),
    visualization("vis-predictions-pie", "Répartition des prédictions", "operation : \"predict\"", {
        "type": "pie",
        "aggs": [COUNT, {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
                         "params": {"field": "prediction", "orderBy": "1", "order": "desc", "size": 5,
                                    "otherBucket": False, "missingBucket": False}}],
        "params": {"type": "pie", "addTooltip": True, "legendDisplay": "show", "legendPosition": "right",
                   "isDonut": True, "distinctColors": True,
                   "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}}}),
    visualization("vis-response-time", "Temps de réponse de /predict (ms)",
                  "endpoint : \"/predict\"", {
                      "type": "line",
                      "aggs": [{"id": "1", "enabled": True, "type": "avg", "schema": "metric",
                                "params": {"field": "response_time_ms", "customLabel": "Moyenne"}},
                               {"id": "3", "enabled": True, "type": "max", "schema": "metric",
                                "params": {"field": "response_time_ms", "customLabel": "Maximum"}},
                               DATE_HIST],
                      "params": {"type": "line", **axes("ms"),
                                 "seriesParams": [series("1", "Moyenne"), series("3", "Maximum")]}}),
    visualization("vis-requests-endpoint", "Requêtes par endpoint", "endpoint : *", {
        "type": "histogram",
        "aggs": [COUNT, DATE_HIST,
                 {"id": "3", "enabled": True, "type": "terms", "schema": "group",
                  "params": {"field": "endpoint", "orderBy": "1", "order": "desc", "size": 10,
                             "otherBucket": False, "missingBucket": False}}],
        "params": {"type": "histogram", **axes("requêtes"),
                   "seriesParams": [series("1", "Requêtes", kind="histogram", mode="stacked")]}}),
    visualization("vis-model-version", "Prédictions par version du modèle", "operation : \"predict\"", {
        "type": "table",
        "aggs": [COUNT, {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
                         "params": {"field": "model_version", "orderBy": "1", "order": "desc", "size": 10,
                                    "otherBucket": False, "missingBucket": False,
                                    "customLabel": "Version"}},
                 {"id": "3", "enabled": True, "type": "avg", "schema": "metric",
                  "params": {"field": "probability", "customLabel": "Probabilité moyenne"}}],
        "params": {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False,
                   "showTotal": False, "totalFunc": "sum", "percentageCol": ""}}),
]

panels = [  # (id, type, x, y, w, h) sur la grille Kibana de 48 colonnes
    ("vis-predictions-count", "visualization", 0, 0, 24, 8),
    ("vis-errors-count", "visualization", 24, 0, 24, 8),
    ("vis-predictions-pie", "visualization", 0, 8, 16, 14),
    ("vis-model-version", "visualization", 16, 8, 32, 14),
    ("vis-response-time", "visualization", 0, 22, 24, 15),
    ("vis-requests-endpoint", "visualization", 24, 22, 24, 15),
    ("search-errors", "search", 0, 37, 48, 15),
    ("search-predictions", "search", 0, 52, 48, 15),
]
panels_json, references = [], []
for i, (obj_id, kind, x, y, w, h) in enumerate(panels, start=1):
    panels_json.append({"type": kind, "panelIndex": str(i), "panelRefName": f"panel_{i}",
                        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
                        "embeddableConfig": {}})
    references.append({"name": f"{i}:panel_{i}", "type": kind, "id": obj_id})

objects.append({"id": "dashboard-ml-churn", "type": "dashboard", "references": references, "attributes": {
    "title": "ML Churn API – Logs", "description": "Prédictions, erreurs et temps de réponse (logs FastAPI via Logstash)",
    "panelsJSON": json.dumps(panels_json),
    "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
    "timeRestore": True, "timeFrom": "now-1h", "timeTo": "now",
    "refreshInterval": {"pause": False, "value": 10000},
    "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"},
                                                              "filter": []})}}})

with OUT.open("w", encoding="utf-8", newline="\n") as fh:
    for obj in objects:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
print(f"{len(objects)} objets écrits dans {OUT.name}")
