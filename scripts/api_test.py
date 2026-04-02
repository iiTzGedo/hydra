#!/usr/bin/env python3
"""Simple API endpoint test script using requests."""

import json
import os
import urllib.request
import urllib.error

API_BASE = os.environ.get("HYDRA_API_BASE", "http://localhost:8080/api/v1")

def make_request(method, path, headers=None, body=None):
    """Make an HTTP request."""
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers or {}
    )
    if body:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}

def test_endpoints():
    """Test all new API endpoints."""

    # Check health first
    print("=== Health Check ===")
    status, data = make_request("GET", "/health")
    print(f"Status: {status}")
    print(json.dumps(data, indent=2)[:500])

    if status != 200:
        print("API not healthy, exiting")
        return

    # Try to login
    print("\n=== Login ===")
    login_data = {
        "username": os.environ.get("HYDRA_TEST_USER", "system_admin"),
        "password": os.environ.get("HYDRA_TEST_PASSWORD", "system12345"),
    }
    status, data = make_request("POST", "/auth/login", body=login_data)
    print(f"Status: {status}")

    if status != 200:
        print(f"Login failed")
        return

    token = data.get("accessToken")
    if not token:
        print("No token received")
        return

    headers = {"Authorization": f"Bearer {token}"}
    print(f"Got token: {token[:20]}...")

    # Test endpoints
    endpoints = [
        ("GET", "/ai/models"),
        ("GET", "/mcp/servers"),
        ("GET", "/chat/projects"),
        ("GET", "/chat/sessions"),
        ("GET", "/search?q=test"),
        ("GET", "/settings"),
    ]

    for method, path in endpoints:
        print(f"\n=== {method} {path} ===")
        try:
            status, data = make_request(method, path, headers=headers)
            print(f"Status: {status}")
            data_str = json.dumps(data, indent=2, default=str)
            if len(data_str) > 500:
                data_str = data_str[:500] + "..."
            print(data_str)
        except Exception as e:
            print(f"Error: {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    test_endpoints()
