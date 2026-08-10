import json

with open('data/processed/DJI_0538_720p_week5_speed.json') as f:
    records = json.load(f)

top = sorted([r for r in records if r.get('speed_kmh')], key=lambda r: r['speed_kmh'], reverse=True)[:5]
for r in top:
    print(f"track_id={r['track_id']} speed={r['speed_kmh']} pos=({r['cx']},{r['cy']}) frame={r['frame_index']}")