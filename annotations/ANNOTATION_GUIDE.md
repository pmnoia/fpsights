# FPSights Annotation Guide
## Ground-truth labeling schema

Use this schema when manually labeling event frames from VODs for validation.

## Required columns
1. `frame_number` (int) — frame index in video
2. `timestamp_ms` (int) — elapsed milliseconds
3. `event_type` (text) — one of:
   - `round_start`
   - `enemy_visible`
   - `aim_correction_start`
   - `shot_fired`
   - `enemy_killed`
   - `player_died`
4. `crosshair_x` (int) — crosshair center x
5. `crosshair_y` (int) — crosshair center y
6. `enemy_bbox_x` (int, nullable)
7. `enemy_bbox_y` (int, nullable)
8. `enemy_bbox_w` (int, nullable)
9. `enemy_bbox_h` (int, nullable)
10. `enemy_head_y` (int, nullable)
11. `map_region` (text, nullable)
12. `notes` (text, nullable)

## Annotation rules
- One event per row
- If two events happen on the same frame, create two rows
- Keep `crosshair_x` and `crosshair_y` filled on every row
- Use empty value for non-applicable bbox/head/map fields
- Annotate at least:
  - 2 rounds
  - 10 enemy encounters
  - 5 kills
  - 3 deaths

## Event definitions
- `enemy_visible`: first frame enemy appears
- `aim_correction_start`: first frame crosshair starts moving toward target
- `shot_fired`: muzzle flash/recoil start/ammo count decrease
- `enemy_killed`: kill confirmation frame
- `player_died`: death confirmation frame

