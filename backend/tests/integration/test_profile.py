import pytest

# Status — before upload
@pytest.mark.asyncio
async def test_profile_status_no_profile_returns_false(authed_client):
    resp = await authed_client.get("/api/profile/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_profile" in data

@pytest.mark.asyncio
async def test_profile_status_requires_auth(client):
    resp = await client.get("/api/profile/status")
    assert resp.status_code == 401

# Upload — using the real resume file
@pytest.mark.asyncio
async def test_upload_profile_pdf_success(authed_client, resume_path):
    with open(resume_path, "rb") as f:
        file_data = f.read()

    resp = await authed_client.post(
        "/api/profile",
        files={"file": ("resume.pdf", file_data, "application/pdf")},
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    data = resp.json()
    assert data["message"] == "Profile uploaded and indexed successfully."
    assert data["chunks_indexed"] > 0
    assert data["indexed_at"] is not None

@pytest.mark.asyncio
async def test_upload_profile_sets_has_profile_true(authed_client, resume_path):
    with open(resume_path, "rb") as f:
        file_data = f.read()

    await authed_client.post(
        "/api/profile",
        files={"file": ("resume.pdf", file_data, "application/pdf")},
    )

    status_resp = await authed_client.get("/api/profile/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["has_profile"] is True
    assert data["file_name"] == "resume.pdf"
    assert data["file_type"] == "pdf"
    assert data["indexed_at"] is not None

@pytest.mark.asyncio
async def test_upload_profile_chunks_indexed_count_is_reasonable(authed_client, resume_path):
    with open(resume_path, "rb") as f:
        file_data = f.read()

    resp = await authed_client.post(
        "/api/profile",
        files={"file": ("resume.pdf", file_data, "application/pdf")},
    )
    data = resp.json()
    assert data["chunks_indexed"] >= 3, (
        f"Expected at least 3 chunks (identity + skill + experience), "
        f"got {data['chunks_indexed']}"
    )

@pytest.mark.asyncio
async def test_reupload_succeeds_and_refreshes_chunks(authed_client, resume_path):
    with open(resume_path, "rb") as f:
        file_data = f.read()

    first = await authed_client.post(
        "/api/profile",
        files={"file": ("resume.pdf", file_data, "application/pdf")},
    )
    assert first.status_code == 200
    first_chunks = first.json()["chunks_indexed"]

    second = await authed_client.post(
        "/api/profile",
        files={"file": ("resume.pdf", file_data, "application/pdf")},
    )
    assert second.status_code == 200
    second_chunks = second.json()["chunks_indexed"]

    assert second_chunks == first_chunks

@pytest.mark.asyncio
async def test_upload_unsupported_file_type_returns_error(authed_client):
    resp = await authed_client.post(
        "/api/profile",
        files={"file": ("resume.txt", b"just some text", "text/plain")},
    )
    assert resp.status_code in (400, 422, 500)

@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    resp = await client.post(
        "/api/profile",
        files={"file": ("resume.pdf", b"%PDF fake", "application/pdf")},
    )
    assert resp.status_code == 401

# Status — field presence after upload
@pytest.mark.asyncio
async def test_profile_status_returns_created_at_after_upload(authed_client, resume_path):
    with open(resume_path, "rb") as f:
        file_data = f.read()

    await authed_client.post(
        "/api/profile",
        files={"file": ("resume.pdf", file_data, "application/pdf")},
    )

    resp = await authed_client.get("/api/profile/status")
    data = resp.json()
    assert data["created_at"] is not None
