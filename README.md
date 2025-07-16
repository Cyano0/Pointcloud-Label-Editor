# Point‑Cloud Label Checker / Editor

Interactive tool for inspecting and fixing 3‑D LIDAR / RGB‑D point‑cloud
annotations written in **Python 3 + PyQtGraph + Open3D**.

---

## ✨  Key features
| ✔ | Description |
|---|-------------|
| **3‑D + 3 × 2‑D views** | 3‑D scene with ground grid + linked XY / XZ / YZ orthographic projections. |
| **Multiple humans** | Up to **human1‑human5** get fixed colours (red, yellow, green, blue, purple); any extra classes share a common grey. |
| **Live editing** | • Drag / resize bboxes in any 2‑D view → updates everywhere.<br>• Rotate a selected box with a slider.<br>• Scene azimuth slider. |
| **Label management** | Rename class in the combo‑box *(press Enter)*, delete label, or add **＋ human** (opens name prompt). |
| **Highlight points** | Points inside the currently drawn bboxes are recoloured in 3‑D. |
| **Mismatch helper** | Detects PNG → PCD filename mismatches and logs the fixes. |
| **Safe‑save** | Writes `*_edited.json`, never overwrites your original labels. |

---

## 📂  Directory layout expected

```
<project>/
├─ pointclouds/            # *.pcd files
└─ labels.json             # annotation file in the format shown below
```

`labels.json` (excerpt):

```json
{
  "Timestamp": 1.7303671180519698e9,
  "File": "1730367118.051969.png",
  "Labels": [
    {
      "Class": "human1",
      "BoundingBoxes": [cx, cy, cz, w, h, d, yaw, 0, 0]
    },
    …
  ]
}
```
- `cx,cy,cz` = centre; `w,h,d` = size; `yaw` = rotation (rad)

---

## 🛠  Installation

```bash
# 1. create & activate a venv if you want
python3 -m venv .venv
source .venv/bin/activate

# 2. install dependencies
pip install pyqt5 pyqtgraph PyOpenGL PyOpenGL_accelerate open3d scipy numpy
```

> **Tested versions**  
> • Python 3.9‑3.11 • pyqtgraph ≥ 0.13 • Open3D ≥ 0.17

---

## ▶️  Running

```bash
python pcd_check_json.py
```

A file‑dialog first asks for the **PCD folder**, then the
**labels.json**.  
The window opens at 1400 × 900 px.

---

## 🖱  Controls & hot‑keys

| Action | How |
|--------|-----|
| Next / previous record | Toolbar arrows ⟵ ⟶ |
| Rotate scene | “Scene azimuth °” slider |
| Select label | Combo‑box (drop‑down) |
| Rotate selected bbox | “Rotate bbox °” slider |
| Move / resize bbox | Drag handles in any 2‑D view |
| Rename class | Click drop‑down text → type → **Enter** |
| Delete label | Select in drop‑down → **Delete** key |
| Add label | Toolbar **＋ human** |
| Save | Toolbar **Save** (writes `*_edited.json`) |

---

## ⚙️  Tweaking point size / colours

Open **`pcd_check_json.py`** and look for these constants near the top:

```python
BASE_POINT_SIZE      = 0.05   # grey cloud
HIGHLIGHT_POINT_SIZE = 0.20   # points inside bbox

_PALETTE = {           # fixed colours
    "human1": pg.mkColor('#ff595e'),
    "human2": pg.mkColor('#ffca3a'),
    "human3": pg.mkColor('#8ac926'),
    "human4": pg.mkColor('#1982c4'),
    "human5": pg.mkColor('#6a4c93'),
    "other" : pg.mkColor('#aaaaaa')   # fallback
}
```

Adjust and restart.

---

## 🧩  Common issues

| Message / symptom | Fix |
|-------------------|-----|
| `Missing dependency PyOpenGL` | `pip install PyOpenGL PyOpenGL_accelerate` |
| Black 3‑D view | Check your GPU supports OpenGL ≥ 2.0, update drivers. |
| “Could not find PCD for …” | Ensure PCD names start with `cloud_<pngBase>_` or are similar enough for fuzzy match. |
| Colours wrong / too few | You have more than 5 “human” classes → they fall back to grey. Add more colours in `_PALETTE`. |

---

## 📝  License

MIT – do whatever you like, no warranty.

Enjoy fast point‑cloud label fixing!
