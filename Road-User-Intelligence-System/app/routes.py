"""
Dashboard routes — Week 9 (v3, Supabase Auth + Data Isolation).
"""

import csv
import io
import os
import re

from flask import render_template, request, redirect, url_for, flash, Response, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user

from app.config import VIOLATIONS_DIR
from app.database.db import get_session
from app.database.models import Vehicle, Violation, SessionSummary
from app.auth import authenticate, sign_up_user


def _violation_type_counts(db, user_id=None):
    counts = {"Speeding": 0, "Failed to Yield": 0}
    query = db.query(Violation)
    if user_id is not None:
        query = query.filter(Violation.user_id == user_id)
    else:
        # If unauthenticated/no user_id, return zero counts
        return counts

    for v in query.all():
        label = "Speeding" if v.violation_type == "speeding" else "Failed to Yield"
        counts[label] += 1
    return counts


def _violations_by_video(db, user_id=None):
    counts = {}
    query = db.query(SessionSummary)
    if user_id is not None:
        query = query.filter(SessionSummary.user_id == user_id)
    else:
        return counts

    for s in query.all():
        counts[s.video_name] = s.total_violations
    return counts


def _vehicle_class_counts(db, user_id=None):
    counts = {}
    query = db.query(Vehicle)
    if user_id is not None:
        query = query.filter(Vehicle.user_id == user_id)
    else:
        return counts

    for v in query.all():
        counts[v.vehicle_class] = counts.get(v.vehicle_class, 0) + 1
    return counts


def _compliance_rate(db, video_name=None, user_id=None):
    if user_id is None:
        return 100

    vquery = db.query(Vehicle).filter(Vehicle.user_id == user_id)
    if video_name:
        vquery = vquery.filter(Vehicle.video_name == video_name)
    total = vquery.count()
    if total == 0:
        return 100

    all_track_query = db.query(Vehicle.track_id).filter(Vehicle.user_id == user_id)
    if video_name:
        all_track_query = all_track_query.filter(Vehicle.video_name == video_name)
    all_track_ids = {r[0] for r in all_track_query.all()}

    vio_query = db.query(Violation.track_id).filter(Violation.user_id == user_id)
    if video_name:
        vio_query = vio_query.filter(Violation.video_name == video_name)
    violating_ids = {r[0] for r in vio_query.all() if r[0] in all_track_ids}

    return round(((total - len(violating_ids)) / total) * 100, 1)


EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def register_routes(app):

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.route("/")
    def landing():
        return render_template("landing.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard_home"))

        if request.method == "POST":
            email = (request.form.get("email") or request.form.get("username") or "").strip()
            password = request.form.get("password", "")

            if not email or not password:
                flash("Please enter both email address and password.")
            else:
                try:
                    supabase_user = authenticate(email, password)
                    login_user(supabase_user)
                    return redirect(url_for("dashboard_home"))
                except Exception as ex:
                    err_msg = str(ex)
                    if "Invalid login credentials" in err_msg or "invalid" in err_msg.lower():
                        flash("Invalid email address or password.")
                    elif "Email not confirmed" in err_msg:
                        flash("Please confirm your email address before logging in.")
                    else:
                        flash("Invalid email address or password.")
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard_home"))

        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            # Validation
            if not email or not password or not confirm_password:
                flash("All fields are required.")
                return render_template("signup.html", email=email)

            if not EMAIL_REGEX.match(email):
                flash("Please enter a valid email address.")
                return render_template("signup.html", email=email)

            if len(password) < 6:
                flash("Password must be at least 6 characters long.")
                return render_template("signup.html", email=email)

            if password != confirm_password:
                flash("Passwords do not match. Please re-enter your password.")
                return render_template("signup.html", email=email)

            try:
                result = sign_up_user(email, password)
                # Success state: tell user to check their email
                return render_template("signup.html", success=True, email=email)
            except Exception as ex:
                err_msg = str(ex)
                if "already registered" in err_msg.lower() or "already exists" in err_msg.lower():
                    flash("An account with this email address already exists. Please log in.")
                elif "weak password" in err_msg.lower():
                    flash("Password is too weak. Please choose a stronger password.")
                else:
                    flash(f"Registration error: {err_msg}")
                return render_template("signup.html", email=email)

        return render_template("signup.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard_home():
        uid = getattr(current_user, "user_id", None)
        db = get_session()

        sessions = (
            db.query(SessionSummary)
            .filter(SessionSummary.user_id == uid)
            .order_by(SessionSummary.processed_at.desc())
            .all()
        )
        total_vehicles = db.query(Vehicle).filter(Vehicle.user_id == uid).count()
        total_violations = db.query(Violation).filter(Violation.user_id == uid).count()
        violation_type_counts = _violation_type_counts(db, user_id=uid)
        violations_by_video = _violations_by_video(db, user_id=uid)
        latest_processed = sessions[0].processed_at if sessions else None
        db.close()

        return render_template(
            "index.html",
            sessions=sessions,
            total_vehicles=total_vehicles,
            total_violations=total_violations,
            violation_type_counts=violation_type_counts,
            violations_by_video=violations_by_video,
            latest_processed=latest_processed,
        )

    @app.route("/videos")
    @login_required
    def videos_page():
        uid = getattr(current_user, "user_id", None)
        db = get_session()
        sessions = (
            db.query(SessionSummary)
            .filter(SessionSummary.user_id == uid)
            .order_by(SessionSummary.processed_at.desc())
            .all()
        )
        db.close()
        return render_template("videos.html", sessions=sessions)

    @app.route("/video/<video_name>")
    @login_required
    def video_detail(video_name):
        uid = getattr(current_user, "user_id", None)
        db = get_session()
        summary = (
            db.query(SessionSummary)
            .filter(SessionSummary.video_name == video_name, SessionSummary.user_id == uid)
            .first()
        )
        if not summary:
            db.close()
            return render_template("404.html"), 404

        vehicles = (
            db.query(Vehicle)
            .filter(Vehicle.video_name == video_name, Vehicle.user_id == uid)
            .all()
        )
        violations = (
            db.query(Violation)
            .filter(Violation.video_name == video_name, Violation.user_id == uid)
            .all()
        )
        compliance_rate = _compliance_rate(db, video_name=video_name, user_id=uid)
        db.close()

        return render_template(
            "video_detail.html",
            video_name=video_name,
            summary=summary,
            vehicles=vehicles,
            violations=violations,
            compliance_rate=compliance_rate,
        )

    @app.route("/violations")
    @login_required
    def violations_page():
        uid = getattr(current_user, "user_id", None)
        db = get_session()
        violations = (
            db.query(Violation)
            .filter(Violation.user_id == uid)
            .order_by(Violation.timestamp_sec.desc())
            .all()
        )
        type_counts = _violation_type_counts(db, user_id=uid)
        db.close()
        return render_template("violations.html", violations=violations, type_counts=type_counts)

    @app.route("/export/violations")
    @login_required
    def export_violations():
        uid = getattr(current_user, "user_id", None)
        db = get_session()
        violations = db.query(Violation).filter(Violation.user_id == uid).all()
        db.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["video_name", "track_id", "vehicle_class", "violation_type",
                          "timestamp_sec", "speed_kmh", "threshold_kmh", "snapshot_path"])
        for v in violations:
            writer.writerow([v.video_name, v.track_id, v.vehicle_class, v.violation_type,
                              v.timestamp_sec, v.speed_kmh, v.threshold_kmh, v.snapshot_path])

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=violations_export.csv"},
        )

    @app.route("/snapshot/<video_name>/<filename>")
    @login_required
    def serve_snapshot(video_name, filename):
        safe_video_name = os.path.basename(video_name)
        safe_filename = os.path.basename(filename)
        uid = getattr(current_user, "user_id", None)

        db = get_session()
        violation = (
            db.query(Violation)
            .filter(Violation.video_name == safe_video_name, Violation.user_id == uid)
            .first()
        )
        db.close()

        if not violation:
            return render_template("404.html"), 404

        directory = os.path.join(VIOLATIONS_DIR, safe_video_name)
        return send_from_directory(directory, safe_filename)

    @app.route("/privacy")
    def privacy_page():
        return render_template("privacy.html")

    @app.route("/faq")
    def faq_page():
        return render_template("faq.html")

    @app.route("/robots.txt")
    def robots_txt():
        content = (
            "User-agent: *\n"
            "Allow: /\n"
            "Allow: /login\n"
            "Allow: /signup\n"
            "Allow: /privacy\n"
            "Allow: /faq\n"
            "Disallow: /dashboard\n"
            "Disallow: /videos\n"
            "Disallow: /video/\n"
            "Disallow: /violations\n"
            "Disallow: /export/\n"
            "Disallow: /snapshot/\n"
            "\n"
            "Sitemap: " + request.url_root.rstrip('/') + "/sitemap.xml\n"
        )
        return Response(content, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        base_url = request.url_root.rstrip('/')
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'  <url><loc>{base_url}/</loc><priority>1.0</priority></url>\n'
            f'  <url><loc>{base_url}/faq</loc><priority>0.8</priority></url>\n'
            f'  <url><loc>{base_url}/privacy</loc><priority>0.5</priority></url>\n'
            '</urlset>\n'
        )
        return Response(content, mimetype="application/xml")