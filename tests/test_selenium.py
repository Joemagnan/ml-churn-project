"""Tests de bout en bout avec Selenium (PARTIE 17).

Correction du sujet : le titre de la page /docs est « Churn Prediction API -
Swagger UI » (FastAPI y met le titre de l'application) : l'assertion
« "FastAPI" in driver.title » du sujet échoue donc toujours.

Prérequis : l'API doit tourner et Chrome doit être installé
(Selenium Manager télécharge le chromedriver adapté).

    uvicorn api.main:app                  # terminal 1
    pytest -m e2e tests/test_selenium.py  # terminal 2

Variables : API_URL (défaut http://localhost:8000), UI_URL (défaut
$API_URL/ui/ ; http://localhost:8080 pour l'interface Nginx du docker-compose),
HEADLESS=0 pour voir le navigateur.
"""
import os

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.e2e

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
UI_URL = os.getenv("UI_URL", f"{API_URL}/ui/")
TIMEOUT = 15


@pytest.fixture(scope="module")
def driver():
    options = webdriver.ChromeOptions()
    if os.getenv("HEADLESS", "1") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    browser = webdriver.Chrome(options=options)
    yield browser
    browser.quit()


def fill_form(driver, values):
    for field, value in values.items():
        element = driver.find_element(By.ID, field)
        element.clear()
        element.send_keys(str(value))


def test_application(driver):
    """Test du sujet, corrigé : la documentation Swagger s'ouvre."""
    driver.get(f"{API_URL}/docs")
    WebDriverWait(driver, TIMEOUT).until(lambda d: "Swagger UI" in d.title)
    assert "Churn Prediction API" in driver.title


def test_interface_shows_api_status(driver):
    driver.get(UI_URL)
    badge = WebDriverWait(driver, TIMEOUT).until(
        EC.text_to_be_present_in_element((By.ID, "api-status"), "UP"))
    assert badge
    assert "Modèle" in driver.find_element(By.ID, "model-info").text


def test_prediction_scenario(driver, payload):
    """Ouverture → saisie des données client → clic sur « Prédire » → appel API
    → affichage du résultat → vérification du résultat."""
    driver.get(UI_URL)
    fill_form(driver, payload)
    driver.find_element(By.ID, "predict-btn").click()

    WebDriverWait(driver, TIMEOUT).until(EC.visibility_of_element_located((By.ID, "result")))
    label = driver.find_element(By.ID, "result-label").text
    proba = driver.find_element(By.ID, "result-proba").text
    assert label in {"CHURN", "NO_CHURN"}
    assert proba.endswith("%")
    assert 0 <= float(proba.replace("%", "").strip()) <= 100
    assert driver.find_element(By.ID, "result-version").text != ""


def test_invalid_input_displays_error(driver, payload):
    driver.get(UI_URL)
    payload["age"] = 10  # âge refusé par l'API (minimum 18)
    fill_form(driver, payload)
    driver.find_element(By.ID, "predict-btn").click()

    error = WebDriverWait(driver, TIMEOUT).until(
        EC.visibility_of_element_located((By.ID, "error")))
    assert "422" in error.text
    assert not driver.find_element(By.ID, "result").is_displayed()
