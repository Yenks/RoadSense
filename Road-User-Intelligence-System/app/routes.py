"""
Dashboard routes — Week 9 (v3, Supabase Auth).
"""

import csv
import io
import os

from flask import render_template, request, redirect, url_for, flash, Response, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user

from app.config import VIOLATIONS_DIR
from app.database.db import get_session
from app.database.models import Vehicle, Violation, SessionSummary
from app.auth import authenticate


def _violation_type_counts(db):
    counts = {"Speeding": 0, "Failed to Yield": 0}
    for v in db.query(Violation).all():
        label = "Speeding" if v.violation_type == "speeding" else "Failed to Yield"
        counts[label] += 1
    return counts


def _violations_by_video(db):
    counts = {}
    for s in db.query(SessionSummary).all():
        counts[s.video_name] = s.total_violations
    return counts


def _vehicle_class_counts(db):
    counts = {}
    for v in db.query(Vehicle).all():
        counts[v.vehicle_class] = counts.get(v.vehicle_class, 0) + 1
    return counts


def _compliance_rate(db, video_name=None):
    vquery = db.query(Vehicle)
    if video_name:
        vquery = vquery.filter(Vehicle.video_name == video_name)
    total = vquery.count()
    if total == 0:
        return 100

    all_track_ids = {r[0] for r in (
        db.query(Vehicle.track_id).filter(Vehicle.video_name == video_name) if video_name
        else db.query(Vehicle.track_id)
    ).all()}

    vio_query = db.query(Violation.track_id)
    if video_name:
        vio_query = vio_query.filter(Violation.video_name == video_name)
    violating_ids = {r[0] for r in vio_query.all() if r[0] in all_track_ids}

    return round(((total - len(violating_ids)) / total) * 100, 1)


def register_routes(app):

    @app.route("/")
    def landing():
        return render_template("landing.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            try:
                supabase_user = authenticate(email, password)
                login_user(supabase_user)
                return redirect(url_for("dashboard_home"))
            except Exception:
                flash("Invalid email or password.")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard_home():
        db = get_session()
        sessions = db.query(SessionSummary).order_by(SessionSummary.processed_at.desc()).all()
        total_vehicles = db.query(Vehicle).count()
        total_violations = db.query(Violation).count()
        violation_type_counts = _violation_type_counts(db)
        violations_by_video = _violations_by_video(db)
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
        db = get_session()
        sessions = db.query(SessionSummary).order_by(SessionSummary.processed_at.desc()).all()
        db.close()
        return render_template("videos.html", sessions=sessions)

    @app.route("/video/<video_name>")
    @login_required
    def video_detail(video_name):
        db = get_session()
        summary = db.query(SessionSummary).filter(SessionSummary.video_name == video_name).first()
        vehicles = db.query(Vehicle).filter(Vehicle.video_name == video_name).all()
        violations = db.query(Violation).filter(Violation.video_name == video_name).all()
        compliance_rate = _compliance_rate(db, video_name)
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
        db = get_session()
        violations = db.query(Violation).order_by(Violation.timestamp_sec.desc()).all()
        type_counts = _violation_type_counts(db)
        db.close()
        return render_template("violations.html", violations=violations, type_counts=type_counts)

    @app.route("/export/violations")
    @login_required
    def export_violations():
        db = get_session()
        violations = db.query(Violation).all()
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
        directory = os.path.join(VIOLATIONS_DIR, video_name)
        return send_from_directory(directory, filename)