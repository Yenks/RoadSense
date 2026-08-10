from app.database.db import get_session
from app.database.models import SessionSummary

s = get_session()
for sess in s.query(SessionSummary).all():
    print(sess.video_name, sess.total_vehicles, sess.avg_speed_kmh, sess.peak_speed_kmh, sess.total_violations)