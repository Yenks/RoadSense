import json

with open('data/processed/DJI_0567_720p_week5_speed.json') as f:
    records = json.load(f)

near_limit = [r for r in records if r.get('speed_kmh') and 25 <= r['speed_kmh'] < 30]
print(f"DJI_0567: {len(near_limit)} readings in the 25-30 km/h band")

with open('data/processed/DJI_0538_720p_week5_speed.json') as f:
    records2 = json.load(f)

near_limit2 = [r for r in records2 if r.get('speed_kmh') and 25 <= r['speed_kmh'] < 30]
print(f"DJI_0538: {len(near_limit2)} readings in the 25-30 km/h band")