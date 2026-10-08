from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.dataset import Dataset
from app.models.user import User
from app.services import datasets as dataset_service


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, int | Path], None, None]:
    Base.metadata.create_all(TEST_ENGINE)
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        dataset_service,
        "get_settings",
        lambda: SimpleNamespace(max_dataset_size_mb=1, upload_directory=str(tmp_path)),
    )
    with TestSessionLocal() as db:
        first_user = User(name="First User", email="first@example.com", password_hash=hash_password("password123"))
        second_user = User(name="Second User", email="second@example.com", password_hash=hash_password("password123"))
        db.add_all([first_user, second_user])
        db.commit()
        db.refresh(first_user)
        db.refresh(second_user)
        context = {"first_user_id": first_user.id, "second_user_id": second_user.id, "upload_dir": tmp_path}
    yield context
    app.dependency_overrides.clear()
    Base.metadata.drop_all(TEST_ENGINE)


@asynccontextmanager
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


def auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.mark.anyio
async def test_unauthenticated_upload_returns_401() -> None:
    async with client() as test_client:
        response = await test_client.post("/api/v1/datasets/upload", files={"file": ("data.csv", b"a,b\n1,2")})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_csv_upload_stores_metadata_and_file(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("sales.csv", b"month,total\nJanuary,10\n", "text/csv")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "sales.csv"
    assert body["file_type"] == ".csv"
    assert body["file_size"] > 0
    with TestSessionLocal() as db:
        dataset = db.get(Dataset, body["id"])
        assert dataset is not None
        assert dataset.user_id == isolated_database["first_user_id"]
        assert dataset.stored_filename != "sales.csv"
        assert Path(dataset.file_path).exists()


@pytest.mark.anyio
async def test_xlsx_upload_is_allowed(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("report.xlsx", b"xlsx bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 201
    assert response.json()["file_type"] == ".xlsx"


@pytest.mark.anyio
async def test_txt_upload_is_allowed(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("people.txt", b"Name;Age\nAbel;20\nHana;21\n", "text/plain")},
        )
    assert response.status_code == 201
    assert response.json()["file_type"] == ".txt"


@pytest.mark.anyio
async def test_unsupported_extension_is_rejected(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("notes.md", b"not supported", "text/markdown")},
        )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_oversized_file_is_rejected(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("large.csv", b"x" * (1024 * 1024 + 1), "text/csv")},
        )
    assert response.status_code == 413
    assert list(Path(isolated_database["upload_dir"]).iterdir()) == []


@pytest.mark.anyio
async def test_list_is_scoped_to_authenticated_user(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("owned.csv", b"a,b\n1,2")},
        )
        first_response = await test_client.get("/api/v1/datasets", headers=auth_headers(int(isolated_database["first_user_id"])))
        second_response = await test_client.get("/api/v1/datasets", headers=auth_headers(int(isolated_database["second_user_id"])))

    assert len(first_response.json()) == 1
    assert second_response.json() == []


@pytest.mark.anyio
async def test_user_can_delete_own_dataset_and_file(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        upload = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("remove.csv", b"a,b\n1,2")},
        )
        dataset_id = upload.json()["id"]
        with TestSessionLocal() as db:
            file_path = db.get(Dataset, dataset_id).file_path
        response = await test_client.delete(
            f"/api/v1/datasets/{dataset_id}",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 204
    assert not Path(file_path).exists()
    with TestSessionLocal() as db:
        assert db.get(Dataset, dataset_id) is None


@pytest.mark.anyio
async def test_user_cannot_delete_another_users_dataset(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        upload = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("private.csv", b"a,b\n1,2")},
        )
        dataset_id = upload.json()["id"]
        forbidden = await test_client.delete(
            f"/api/v1/datasets/{dataset_id}",
            headers=auth_headers(int(isolated_database["second_user_id"])),
        )
        owner_delete = await test_client.delete(
            f"/api/v1/datasets/{dataset_id}",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert forbidden.status_code == 404
    assert owner_delete.status_code == 204


@pytest.mark.anyio
async def test_exploration_route_returns_safe_capabilities_and_results(isolated_database: dict[str, int | Path]) -> None:
    async with client() as test_client:
        upload = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            files={"file": ("sales.csv", b"region,sales,order_date\nNorth,10,2024-01-01\nSouth,20,2024-01-02\nNorth,30,2024-01-03\n", "text/csv")},
        )
        dataset_id = upload.json()["id"]

        capabilities = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/explore/capabilities",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
        response = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            json={"dimension": "region", "measure": "sales", "aggregation": "mean", "limit": 5},
        )
        trend = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(int(isolated_database["first_user_id"])),
            json={"exploration_type": "time_trend", "date_field": "order_date", "measure": "sales", "aggregation": "sum", "date_from": "2024-01-02", "date_to": "2024-01-02", "filters": [{"field": "sales", "operator": "between", "value": 19, "value_2": 21}]},
        )

    assert capabilities.status_code == 200
    assert set(capabilities.json()) >= {"dimensions", "measures", "time_fields", "filter_fields"}
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == dataset_id
    assert body["visualization"] in {"bar", "line"}
    assert body["points"]
    assert body["points"][0]["label"] in {"North", "South"}
    assert trend.status_code == 200
    assert trend.json()["visualization"] == "line"
    assert trend.json()["points"] == [{"label": "2024-01-02T00:00:00+00:00", "value": 20.0, "count": None, "x": None, "y": None, "series": None}]
    assert len(trend.json()["filters"]) == 3


@pytest.mark.anyio
async def test_exploration_top_n_and_field_validation(isolated_database: dict[str, int | Path]) -> None:
    groups = [("Alpha", 8, 100), ("Beta", 6, 50), ("Gamma", 4, 25), ("Delta", 2, 1)]
    rows = [f"{group},{value + offset}" for group, count, value in groups for offset in range(count)]
    csv_bytes = ("unfamiliar group,numeric value\n" + "\n".join(rows) + "\n").encode()
    owner_id = int(isolated_database["first_user_id"])
    other_id = int(isolated_database["second_user_id"])

    async with client() as test_client:
        upload = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(owner_id),
            files={"file": ("unknown-domain.csv", csv_bytes, "text/csv")},
        )
        dataset_id = upload.json()["id"]
        top_n = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(owner_id),
            json={"exploration_type": "group_comparison", "dimension": "unfamiliar group", "measure": "numeric value", "aggregation": "mean", "limit": 2},
        )
        bad_field = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(owner_id),
            json={"dimension": "unknown column"},
        )
        bad_filter = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(owner_id),
            json={"dimension": "unfamiliar group", "filters": [{"field": "unfamiliar group", "operator": "gt", "value": "Beta"}]},
        )
        forbidden = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/explore/capabilities",
            headers=auth_headers(other_id),
        )

    assert top_n.status_code == 200
    result = top_n.json()
    assert result["total_count"] == 4
    assert result["showing_limited"] is True
    assert len(result["points"]) == 2
    assert result["points"][0]["label"] == "Alpha"
    assert any("top 2 of 4" in limitation for limitation in result["limitations"])
    assert bad_field.status_code == 422
    assert bad_filter.status_code == 422
    assert forbidden.status_code == 404


@pytest.mark.anyio
async def test_exploration_supports_bounded_multi_measure_series(isolated_database: dict[str, int | Path]) -> None:
    rows = [f"{group},{value},{value * 2}" for group, start in (("A", 2), ("B", 4), ("C", 6), ("D", 8)) for value in range(start, start + 4)]
    csv_bytes = ("group,measure_one,measure_two\n" + "\n".join(rows) + "\n").encode()
    user_id = int(isolated_database["first_user_id"])

    async with client() as test_client:
        upload = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(user_id),
            files={"file": ("multi-series.csv", csv_bytes, "text/csv")},
        )
        dataset_id = upload.json()["id"]
        capabilities = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/explore/capabilities",
            headers=auth_headers(user_id),
        )
        response = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(user_id),
            json={"exploration_type": "multi_measure_comparison", "dimension": "group", "measure": "measure_one", "secondary_measure": "measure_two", "aggregation": "mean", "limit": 4},
        )
        relationship = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(user_id),
            json={"exploration_type": "numeric_relationship", "x_field": "measure_one", "y_field": "measure_two", "limit": 4},
        )

    assert capabilities.status_code == 200
    assert any(item["type"] == "multi_measure_comparison" for item in capabilities.json()["recommended_explorations"])
    assert response.status_code == 200
    points = response.json()["points"]
    assert points
    assert set(points[0]["series"]) == {"measure_one", "measure_two"}
    assert response.json()["chart_config"]["series_names"] == ["measure_one", "measure_two"]
    assert relationship.status_code == 200
    assert relationship.json()["summary_detail"]["correlation"] == pytest.approx(1.0)
    assert "does not establish causation" in relationship.json()["summary_detail"]["key_observation"]


@pytest.mark.anyio
async def test_duplicate_review_uses_deterministic_row_profile(isolated_database: dict[str, int | Path]) -> None:
    user_id = int(isolated_database["first_user_id"])
    async with client() as test_client:
        upload = await test_client.post(
            "/api/v1/datasets/upload",
            headers=auth_headers(user_id),
            files={"file": ("duplicate-profile.csv", b"unfamiliar field,value\nalpha,1\nalpha,1\nbeta,2\n", "text/csv")},
        )
        dataset_id = upload.json()["id"]
        capabilities = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/explore/capabilities",
            headers=auth_headers(user_id),
        )
        response = await test_client.post(
            f"/api/v1/datasets/{dataset_id}/explore",
            headers=auth_headers(user_id),
            json={"exploration_type": "duplicate_review"},
        )

    assert any(item["type"] == "duplicate_review" for item in capabilities.json()["recommended_explorations"])
    assert response.status_code == 200
    counts = {point["label"]: point["count"] for point in response.json()["points"]}
    assert counts == {"Duplicate rows": 1, "Distinct rows": 2}
