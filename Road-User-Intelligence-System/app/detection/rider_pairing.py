"""
Rider pairing — tags a detected person as a 'rider' when their box
significantly overlaps a detected bicycle/motor/tricycle/awning-tricycle,
so riders are visually and logically distinct from pedestrians on foot.

Runs per-frame on raw detections, before stabilization, since it needs
the current frame's box positions to compare.
"""

from app.config import RIDEABLE_LABELS, RIDER_OVERLAP_THRESHOLD


def _overlap_ratio(person_box, vehicle_box):
    px1, py1, px2, py2 = person_box
    vx1, vy1, vx2, vy2 = vehicle_box

    inter_x1 = max(px1, vx1)
    inter_y1 = max(py1, vy1)
    inter_x2 = min(px2, vx2)
    inter_y2 = min(py2, vy2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    person_area = max(0.0, px2 - px1) * max(0.0, py2 - py1)
    if person_area <= 0:
        return 0.0
    return inter_area / person_area


def pair_riders(detections):
    vehicles = [d for d in detections if d.label in RIDEABLE_LABELS]
    people = [d for d in detections if d.track_class == "pedestrian"]

    for person in people:
        person_box = (person.x1, person.y1, person.x2, person.y2)
        for vehicle in vehicles:
            vehicle_box = (vehicle.x1, vehicle.y1, vehicle.x2, vehicle.y2)
            if _overlap_ratio(person_box, vehicle_box) >= RIDER_OVERLAP_THRESHOLD:
                person.is_rider = True
                break

    return detections