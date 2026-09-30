from fastapi.testclient import TestClient

from api.app.main import app
from api.app.services import get_measurements
from api.app import services


def test_predict_rejects_target_columns():
    with TestClient(app) as client:
        response = client.post("/predict", json={"features": {"Age": 58, "LAD": "Stenotic"}})
    assert response.status_code == 422


def test_predict_rejects_unknown_features():
    with TestClient(app) as client:
        response = client.post("/predict", json={"features": {"Age": 58, "made_up": 1}})
    assert response.status_code == 422


def test_predict_rejects_implausible_and_invalid_binary_values():
    with TestClient(app) as client:
        age = client.post("/predict", json={"features": {"Age": 999}})
        sex = client.post("/predict", json={"features": {"Sex": 2}})
    assert age.status_code == 422
    assert sex.status_code == 422


def test_samples_use_labeled_dataset():
    with TestClient(app) as client:
        response = client.get("/samples")
    assert response.status_code == 200
    samples = response.json()["samples"]
    assert len(samples) == 3
    assert all(not {"Cath", "LAD", "LCX", "RCA"} & set(s["features"]) for s in samples)


def test_prediction_has_four_real_explanations():
    with TestClient(app) as client:
        sample = client.get("/samples").json()["samples"][0]
        response = client.post("/predict", json={"features": sample["features"]})

    assert response.status_code == 200
    result = response.json()
    assert set(result["predictions"]) == {"CAD", "LAD", "LCX", "RCA"}
    for target in result["predictions"]:
        contributions = result["explanations"][target]["contributions"]
        assert contributions, target
        assert any(abs(c["shap"]) > 1e-9 for c in contributions), target


def test_metrics_endpoint_reports_held_out_results_for_every_target():
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    evaluation = response.json()["evaluation"]
    assert set(evaluation) == {"CAD", "LAD", "LCX", "RCA"}
    assert all(item["metrics"]["source"] == "held_out" for item in evaluation.values())
    assert set(response.json()["feature_importance"]) == {"CAD", "LAD", "LCX", "RCA"}


def test_measurements_do_not_invent_reference_ranges():
    measurements = get_measurements({"Region RWMA": 4, "BP": 150})

    assert [item["feature"] for item in measurements] == ["BP"]
    assert measurements[0]["status"] == "high"


def test_measurement_units_match_raw_dataset_scale():
    measurements = {item["feature"]: item for item in get_measurements({"WBC": 5700, "CR": 0.7})}

    assert measurements["WBC"]["status"] == "normal"
    assert measurements["CR"]["unit"] == "mg/dL"


def test_cors_does_not_allow_arbitrary_websites():
    with TestClient(app) as client:
        response = client.options("/predict", headers={
            "Origin": "https://unrelated.example",
            "Access-Control-Request-Method": "POST",
        })

    assert response.headers.get("access-control-allow-origin") is None


def test_missing_vessel_model_prevents_partial_prediction():
    with TestClient(app) as client:
        saved = services.models.pop("RCA")
        try:
            assert client.get("/health").json()["status"] == "degraded"
            response = client.post("/predict", json={"features": {"Age": 58}})
            assert response.status_code == 503
        finally:
            services.models["RCA"] = saved
