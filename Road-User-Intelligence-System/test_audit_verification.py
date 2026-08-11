"""
Verification test script for CivicShield production audit & enhancements.
"""

import sys
import os

# Add app folder to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import create_app
from app.auth import supabase_client, sign_up_user

def run_tests():
    print("=== CivicShield Verification Tests ===")
    
    # 1. Environment and Security check
    assert "SUPABASE_SERVICE_KEY" not in os.environ, "SUPABASE_SERVICE_KEY should not be in os.environ"
    assert "SUPABASE_URL" in os.environ, "SUPABASE_URL missing"
    assert "SUPABASE_ANON_KEY" in os.environ, "SUPABASE_ANON_KEY missing"
    print("[PASS] Security & Environment variables check")

    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    # 2. Test GET / (Landing page)
    res = client.get("/")
    assert res.status_code == 200, f"Landing page status {res.status_code}"
    html = res.get_data(as_text=True)
    assert "<title>CivicShield | School Zone Safety Intelligence</title>" in html
    assert "og:title" in html
    assert 'rel="canonical"' in html
    print("[PASS] GET / (Landing Page)")

    # 3. Test GET /login
    res = client.get("/login")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'for="email"' in html
    assert 'type="email"' in html
    assert "New here? Create an account" in html
    print("[PASS] GET /login")

    # 4. Test GET /signup
    res = client.get("/signup")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'autocomplete="new-password"' in html
    assert "Create Account" in html
    print("[PASS] GET /signup")

    # 5. Test POST /signup validation (password mismatch)
    res = client.post("/signup", data={
        "email": "testuser@example.com",
        "password": "Password123!",
        "confirm_password": "Password456!"
    }, follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Passwords do not match" in html
    print("[PASS] POST /signup password mismatch validation")

    # 6. Test POST /signup validation (short password)
    res = client.post("/signup", data={
        "email": "testuser@example.com",
        "password": "123",
        "confirm_password": "123"
    }, follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "at least 6 characters" in html
    print("[PASS] POST /signup short password validation")

    # 7. Test GET /privacy
    res = client.get("/privacy")
    assert res.status_code == 200
    assert "Privacy Policy — CivicShield" in res.get_data(as_text=True)
    print("[PASS] GET /privacy")

    # 8. Test GET /faq
    res = client.get("/faq")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Frequently Asked Questions" in html
    assert "Ghana Road Traffic Regulations 2012" in html
    print("[PASS] GET /faq")

    # 9. Test GET /robots.txt
    res = client.get("/robots.txt")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "Disallow: /dashboard" in text
    assert "Sitemap:" in text
    print("[PASS] GET /robots.txt")

    # 10. Test GET /sitemap.xml
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    xml = res.get_data(as_text=True)
    assert "<loc>" in xml
    assert "/faq" in xml
    print("[PASS] GET /sitemap.xml")

    # 11. Test 404 handler (GET /nonexistent-route-xyz)
    res = client.get("/nonexistent-route-xyz")
    assert res.status_code == 404
    html = res.get_data(as_text=True)
    assert "Page Not Found" in html
    assert "Error 404" in html
    print("[PASS] Custom 404 Error Handler")

    # 12. Test authenticated routes redirect to /login when unauthenticated
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    print("[PASS] Auth gating on /dashboard")

    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

