"""Tests for /.well-known/ deep link configuration files."""

import json


class TestAppleAppSiteAssociation:
    def test_returns_200(self, client):
        response = client.get("/.well-known/apple-app-site-association")
        assert response.status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/.well-known/apple-app-site-association")
        assert "application/json" in response["Content-Type"]

    def test_contains_applinks_key(self, client):
        response = client.get("/.well-known/apple-app-site-association")
        data = json.loads(response.content)
        assert "applinks" in data

    def test_contains_trainer_path(self, client):
        response = client.get("/.well-known/apple-app-site-association")
        data = json.loads(response.content)
        paths = data["applinks"]["details"][0]["paths"]
        assert "/trainer/*" in paths

    def test_contains_gym_path(self, client):
        response = client.get("/.well-known/apple-app-site-association")
        data = json.loads(response.content)
        paths = data["applinks"]["details"][0]["paths"]
        assert "/gym/*" in paths

    def test_contains_fittrybe_app_id(self, client):
        response = client.get("/.well-known/apple-app-site-association")
        data = json.loads(response.content)
        app_id = data["applinks"]["details"][0]["appID"]
        assert "com.fittrybe.app" in app_id


class TestAssetLinks:
    def test_returns_200(self, client):
        response = client.get("/.well-known/assetlinks.json")
        assert response.status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/.well-known/assetlinks.json")
        assert "application/json" in response["Content-Type"]

    def test_returns_json_array(self, client):
        response = client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)
        assert isinstance(data, list)

    def test_contains_fittrybe_package_name(self, client):
        response = client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)
        package_name = data[0]["target"]["package_name"]
        assert package_name == "com.fittrybe.app"

    def test_contains_handle_all_urls_relation(self, client):
        response = client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)
        assert "delegate_permission/common.handle_all_urls" in data[0]["relation"]
