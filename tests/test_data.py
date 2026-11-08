"""Tests unitaires du dataset généré (PARTIE 4)."""
import pandas as pd

from src.generate_data import generate
from src.train import DATA_PATH, FEATURES, TARGET

EXPECTED_COLUMNS = FEATURES + [TARGET]


def test_generated_shape_and_columns():
    df = generate()
    assert df.shape == (2000, 7)
    assert list(df.columns) == EXPECTED_COLUMNS


def test_generated_values_are_valid():
    df = generate()
    assert df.isnull().sum().sum() == 0
    assert set(df[TARGET].unique()) == {0, 1}
    assert df["age"].between(18, 69).all()
    assert df["anciennete"].between(1, 119).all()
    assert (df[["nb_reclamations", "retards_paiement"]] >= 0).all().all()


def test_generation_is_reproducible():
    pd.testing.assert_frame_equal(generate(), generate())


def test_dataset_file_matches_generator():
    """Le CSV versionné dans data/raw est bien celui produit par le générateur."""
    on_disk = pd.read_csv(DATA_PATH)
    pd.testing.assert_frame_equal(on_disk, generate(), check_dtype=False)


def test_churn_signal_direction():
    """Sanity check métier : les clients récents résilient plus que les anciens."""
    df = generate()
    recent = df[df["anciennete"] <= 24]["churn"].mean()
    old = df[df["anciennete"] > 72]["churn"].mean()
    assert recent > old
