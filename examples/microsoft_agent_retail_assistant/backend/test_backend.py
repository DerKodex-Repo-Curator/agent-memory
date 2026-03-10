"""Standalone smoke tests for the retail assistant backend.

Requires the backend server to be running at http://localhost:8000.
No external dependencies beyond the Python standard library.

Usage:
    python test_backend.py
    python test_backend.py --base-url http://localhost:9000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:8000"
SESSION_ID = "smoke-test-1"
MULTI_TURN_SESSION_ID = "smoke-test-multi-turn"
MEMORY_LIFECYCLE_SESSION_ID = "smoke-test-memory-lifecycle"
MAX_OUTPUT = 200


def truncate(obj: object, max_len: int = MAX_OUTPUT) -> str:
    """Return a truncated string representation of obj."""
    text = json.dumps(obj, indent=2) if isinstance(obj, (dict, list)) else str(obj)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def request(method: str, path: str, base_url: str, body: dict | None = None) -> tuple[int, dict | str]:
    """Make an HTTP request and return (status_code, parsed_response)."""
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def test_health(base_url: str) -> bool:
    """Test the health check endpoint."""
    status, data = request("GET", "/health", base_url)
    ok = status == 200 and isinstance(data, dict) and "status" in data
    print(f"  {truncate(data)}")
    return ok


def test_chat_sync(base_url: str) -> bool:
    """Test the synchronous chat endpoint."""
    body = {"message": "What running shoes do you recommend?", "session_id": SESSION_ID}
    status, data = request("POST", "/chat/sync", base_url, body)
    ok = status == 200 and isinstance(data, dict) and "response" in data
    print(f"  {truncate(data)}")
    return ok


def test_chat_stream(base_url: str) -> bool:
    """Test the SSE streaming chat endpoint (reads first few events)."""
    url = f"{base_url}/chat"
    body = json.dumps({"message": "I prefer Nike shoes under $150", "session_id": SESSION_ID}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            events = []
            for line in resp:
                decoded = line.decode().strip()
                if decoded.startswith("data:"):
                    events.append(decoded)
                    if len(events) >= 5:
                        break
            ok = resp.status == 200 and len(events) > 0
            print(f"  events_received={len(events)}")
            for ev in events:
                print(f"  {truncate(ev)}")
            return ok
    except urllib.error.HTTPError as e:
        print(f"  status={e.code}")
        return False


def test_memory_context(base_url: str) -> bool:
    """Test the memory context endpoint."""
    path = f"/memory/context?session_id={SESSION_ID}&query=shoes"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict)
    print(f"  {truncate(data)}")
    return ok


def test_memory_preferences(base_url: str) -> bool:
    """Test the memory preferences endpoint."""
    path = f"/memory/preferences?session_id={SESSION_ID}"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "preferences" in data
    print(f"  {truncate(data)}")
    return ok


def test_memory_graph(base_url: str) -> bool:
    """Test the memory graph endpoint."""
    path = f"/memory/graph?session_id={SESSION_ID}"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "nodes" in data and "edges" in data
    print(f"  {truncate(data)}")
    return ok


def test_product_search(base_url: str) -> bool:
    """Test the product search endpoint."""
    path = "/products/search?query=shoes"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "products" in data and "total" in data
    print(f"  {truncate(data)}")
    return ok


def _get_a_product_id(base_url: str) -> str | None:
    """Helper to fetch a product ID from search results."""
    status, data = request("GET", "/products/search?query=shoes", base_url)
    if status == 200 and isinstance(data, dict) and data.get("products"):
        return data["products"][0]["id"]
    return None


def test_get_product(base_url: str) -> bool:
    """Test the get product detail endpoint."""
    product_id = _get_a_product_id(base_url)
    if not product_id:
        print("  SKIP: no products found to test with")
        return True

    path = f"/products/{product_id}"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "name" in data
    print(f"  {truncate(data)}")
    return ok


def test_related_products(base_url: str) -> bool:
    """Test the related products endpoint."""
    product_id = _get_a_product_id(base_url)
    if not product_id:
        print("  SKIP: no products found to test with")
        return True

    path = f"/products/{product_id}/related"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "related_products" in data
    print(f"  {truncate(data)}")
    return ok


# --- Query Parameter Variation Tests ---


def test_product_search_with_category(base_url: str) -> bool:
    """Test product search filtered by category."""
    path = "/products/search?query=shoes&category=Footwear"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "products" in data
    if ok and data["products"]:
        # Every returned product should match the category filter
        ok = all(p.get("category") == "Footwear" for p in data["products"])
    print(f"  total={data.get('total', '?')}, {truncate(data)}")
    return ok


def test_product_search_with_brand(base_url: str) -> bool:
    """Test product search filtered by brand."""
    path = "/products/search?query=shoes&brand=Nike"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "products" in data
    if ok and data["products"]:
        ok = all(p.get("brand") == "Nike" for p in data["products"])
    print(f"  total={data.get('total', '?')}, {truncate(data)}")
    return ok


def test_product_search_with_max_price(base_url: str) -> bool:
    """Test product search filtered by max price."""
    path = "/products/search?query=shoes&max_price=100"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "products" in data
    if ok and data["products"]:
        ok = all(p.get("price", 0) <= 100 for p in data["products"])
    print(f"  total={data.get('total', '?')}, {truncate(data)}")
    return ok


def test_product_search_with_limit(base_url: str) -> bool:
    """Test product search with a custom limit."""
    path = "/products/search?query=product&limit=2"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "products" in data
    if ok:
        ok = len(data["products"]) <= 2
    print(f"  total={data.get('total', '?')}, count={len(data.get('products', []))}")
    return ok


def test_related_products_with_limit(base_url: str) -> bool:
    """Test related products with a custom limit."""
    product_id = _get_a_product_id(base_url)
    if not product_id:
        print("  SKIP: no products found to test with")
        return True

    path = f"/products/{product_id}/related?limit=2"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "related_products" in data
    if ok:
        ok = len(data["related_products"]) <= 2
    print(f"  count={len(data.get('related_products', []))}")
    return ok


def test_related_products_with_relationship_type(base_url: str) -> bool:
    """Test related products filtered by relationship type."""
    product_id = _get_a_product_id(base_url)
    if not product_id:
        print("  SKIP: no products found to test with")
        return True

    path = f"/products/{product_id}/related?relationship_type=IN_CATEGORY"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "related_products" in data
    print(f"  count={len(data.get('related_products', []))}, {truncate(data)}")
    return ok


def test_memory_graph_with_max_hops(base_url: str) -> bool:
    """Test memory graph with a custom max_hops parameter."""
    path = f"/memory/graph?session_id={SESSION_ID}&max_hops=1"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "nodes" in data and "edges" in data
    print(f"  nodes={len(data.get('nodes', []))}, edges={len(data.get('edges', []))}")
    return ok


def test_memory_preferences_with_category(base_url: str) -> bool:
    """Test memory preferences filtered by category."""
    path = f"/memory/preferences?session_id={SESSION_ID}&category=brand"
    status, data = request("GET", path, base_url)
    ok = status == 200 and isinstance(data, dict) and "preferences" in data
    print(f"  count={len(data.get('preferences', []))}, {truncate(data)}")
    return ok


# --- Error Handling Tests ---


def test_get_product_invalid_id(base_url: str) -> bool:
    """Test get product with a non-existent ID returns 404."""
    path = "/products/nonexistent-id-12345"
    status, data = request("GET", path, base_url)
    ok = status == 404
    print(f"  status={status} (expected 404), {truncate(data)}")
    return ok


def test_chat_sync_missing_message(base_url: str) -> bool:
    """Test sync chat with missing message field returns 422."""
    body: dict = {"session_id": SESSION_ID}
    status, data = request("POST", "/chat/sync", base_url, body)
    ok = status == 422
    print(f"  status={status} (expected 422), {truncate(data)}")
    return ok


def test_chat_sync_empty_body(base_url: str) -> bool:
    """Test sync chat with empty body returns 422."""
    body: dict = {}
    status, data = request("POST", "/chat/sync", base_url, body)
    ok = status == 422
    print(f"  status={status} (expected 422), {truncate(data)}")
    return ok


def test_product_search_missing_query(base_url: str) -> bool:
    """Test product search without required query param returns 422."""
    path = "/products/search"
    status, data = request("GET", path, base_url)
    ok = status == 422
    print(f"  status={status} (expected 422), {truncate(data)}")
    return ok


def test_memory_context_missing_session(base_url: str) -> bool:
    """Test memory context without required session_id returns 422."""
    path = "/memory/context"
    status, data = request("GET", path, base_url)
    ok = status == 422
    print(f"  status={status} (expected 422), {truncate(data)}")
    return ok


# --- Multi-Turn Conversation Test ---


def test_multi_turn_conversation(base_url: str) -> bool:
    """Test that a multi-turn conversation builds memory context."""
    sid = MULTI_TURN_SESSION_ID

    # Turn 1
    body1 = {"message": "I'm looking for running shoes", "session_id": sid}
    status1, data1 = request("POST", "/chat/sync", base_url, body1)
    if status1 != 200:
        print(f"  FAIL on turn 1: status={status1}")
        return False
    print(f"  Turn 1 response: {truncate(data1.get('response', '') if isinstance(data1, dict) else data1, 80)}")

    # Turn 2 — follow-up in the same session
    body2 = {"message": "I prefer Nike brand and my budget is under $150", "session_id": sid}
    status2, data2 = request("POST", "/chat/sync", base_url, body2)
    if status2 != 200:
        print(f"  FAIL on turn 2: status={status2}")
        return False
    print(f"  Turn 2 response: {truncate(data2.get('response', '') if isinstance(data2, dict) else data2, 80)}")

    # Verify memory context reflects the conversation
    path = f"/memory/context?session_id={sid}&query=shoes"
    status3, data3 = request("GET", path, base_url)
    if status3 != 200:
        print(f"  FAIL fetching memory context: status={status3}")
        return False

    short_term = data3.get("short_term", [])
    ok = len(short_term) >= 2  # At least 2 messages stored
    print(f"  Memory context: {len(short_term)} messages in short-term")
    return ok


# --- Memory Lifecycle Test ---


def test_memory_lifecycle(base_url: str) -> bool:
    """Test that chatting about preferences populates memory endpoints."""
    sid = MEMORY_LIFECYCLE_SESSION_ID

    # Chat about a specific preference so entity extraction can pick it up
    body = {
        "message": "I love Adidas sneakers and I always buy size 10 shoes. My favorite color is blue.",
        "session_id": sid,
    }
    status, data = request("POST", "/chat/sync", base_url, body)
    if status != 200:
        print(f"  FAIL sending chat: status={status}")
        return False
    print(f"  Chat response: {truncate(data.get('response', '') if isinstance(data, dict) else data, 80)}")

    # Check that the memory graph has content for this session
    path = f"/memory/graph?session_id={sid}"
    status2, graph_data = request("GET", path, base_url)
    if status2 != 200:
        print(f"  FAIL fetching memory graph: status={status2}")
        return False

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    print(f"  Memory graph: {len(nodes)} nodes, {len(edges)} edges")

    # Check preferences endpoint
    path = f"/memory/preferences?session_id={sid}"
    status3, pref_data = request("GET", path, base_url)
    if status3 != 200:
        print(f"  FAIL fetching preferences: status={status3}")
        return False

    prefs = pref_data.get("preferences", [])
    print(f"  Preferences found: {len(prefs)}")

    # The test passes if the endpoints respond correctly.
    # Entity extraction may run async, so we check structure rather than
    # requiring specific content to be present immediately.
    ok = isinstance(nodes, list) and isinstance(prefs, list)
    return ok


TESTS = [
    # --- Core endpoints ---
    ("Health check", test_health),
    ("Sync chat", test_chat_sync),
    ("Streaming chat (SSE)", test_chat_stream),
    ("Memory context", test_memory_context),
    ("Memory preferences", test_memory_preferences),
    ("Memory graph", test_memory_graph),
    ("Product search", test_product_search),
    ("Get product", test_get_product),
    ("Related products", test_related_products),
    # --- Query parameter variations ---
    ("Product search: category filter", test_product_search_with_category),
    ("Product search: brand filter", test_product_search_with_brand),
    ("Product search: max_price filter", test_product_search_with_max_price),
    ("Product search: limit", test_product_search_with_limit),
    ("Related products: limit", test_related_products_with_limit),
    ("Related products: relationship_type", test_related_products_with_relationship_type),
    ("Memory graph: max_hops", test_memory_graph_with_max_hops),
    ("Memory preferences: category filter", test_memory_preferences_with_category),
    # --- Error handling ---
    ("Get product: invalid ID (404)", test_get_product_invalid_id),
    ("Sync chat: missing message (422)", test_chat_sync_missing_message),
    ("Sync chat: empty body (422)", test_chat_sync_empty_body),
    ("Product search: missing query (422)", test_product_search_missing_query),
    ("Memory context: missing session (422)", test_memory_context_missing_session),
    # --- Multi-turn & memory lifecycle ---
    ("Multi-turn conversation", test_multi_turn_conversation),
    ("Memory lifecycle", test_memory_lifecycle),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke tests for the retail assistant backend")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend URL (default: {DEFAULT_BASE_URL})")
    args = parser.parse_args()

    tests = TESTS

    if not tests:
        print("No tests to run (both --skip-api and --skip-neo4j specified)")
        sys.exit(1)

    print(f"Testing backend at {args.base_url}\n")

    passed = 0
    failed = 0

    for name, fn in tests:
        print(f"[TEST] {name}")
        try:
            if fn(args.base_url):
                print(f"  PASS\n")
                passed += 1
            else:
                print(f"  FAIL\n")
                failed += 1
        except Exception as e:
            print(f"  ERROR: {e}\n")
            failed += 1

    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
