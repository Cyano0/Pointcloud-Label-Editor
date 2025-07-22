#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3‑D / 2‑D point‑cloud label editor  –  pyqtgraph ≥0.13, Open3D ≥0.17
"""
import sys, os, json, difflib, math, numpy as np
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QKeySequence  
import pyqtgraph as pg

# -------------------- back‑end deps -----------------------------------------
try:
    import pyqtgraph.opengl as gl
    import open3d as o3d
except ImportError as e:
    QtWidgets.QMessageBox.critical(None, "Missing dependency", str(e))
    sys.exit(1)

# -----sync names------------
def sync_json_pcd_filenames(json_path: str, pcd_dir: str, cutoff: float = 0.6):
    """
    If JSON‑entry count == .pcd count AND every JSON 'File' fuzzy‑matches
    a .pcd basename above `cutoff`, then:
      • rewrite rec['File'] = '<matched>.pcd'
      • sort all records by that timestamped filename
      • overwrite the original JSON in place
    Otherwise, show a warning and leave the JSON untouched.
    """
    data = json.load(open(json_path))
    pcd_files = [f for f in os.listdir(pcd_dir) if f.lower().endswith('.pcd')]

    if len(data) != len(pcd_files):
        QtWidgets.QMessageBox.warning(
            None, "Count mismatch",
            f"JSON has {len(data)} entries, but found {len(pcd_files)} .pcd files."
        )
        return

    basenames = [os.path.splitext(f)[0] for f in pcd_files]
    new_files = []
    for rec in data:
        orig = rec.get('File','')
        base = os.path.splitext(orig)[0]
        m = difflib.get_close_matches(base, basenames, n=1, cutoff=cutoff)
        if not m:
            QtWidgets.QMessageBox.warning(
                None, "No fuzzy match",
                f"Could not match “{orig}” to any .pcd in\n{pcd_dir}"
            )
            return
        new_files.append(m[0] + '.pcd')

    # All matched → rewrite and sort by timestamped basename
    for rec, new_fn in zip(data, new_files):
        rec['File'] = new_fn

    # since filenames are timestamps, lexicographic sort == chronological
    data.sort(key=lambda r: os.path.splitext(r['File'])[0])

    # overwrite original JSON
    with open(json_path, 'w') as fp:
        json.dump(data, fp, indent=2)

    QtWidgets.QMessageBox.information(
        None, "Sync complete",
        f"Filenames synced and JSON overwritten:\n{json_path}"
    )

# -------------------- helpers / constants -----------------------------------
class GLView(gl.GLViewWidget):
    def __init__(self):
        super().__init__()
        self.setBackgroundColor('k')
        grid = gl.GLGridItem(); grid.setDepthValue(10); self.addItem(grid)

# _palette = [pg.mkColor(c) for c in (
#     '#ff595e', '#ffca3a', '#8ac926', '#1982c4', '#6a4c93',
#     '#ff9f1c', '#e71d36', '#2ec4b6', '#011627')]
LABEL_COLOURS = {
    'human1': pg.mkColor('#ff595e'),    # red‑ish
    'human2': pg.mkColor('#ffca3a'),    # amber
    'human3': pg.mkColor('#8ac926'),    # green
    'human4': pg.mkColor('#1982c4'),    # blue
    'human5': pg.mkColor('#6a4c93'),    # purple
}
DEFAULT_COLOUR = pg.mkColor("#ecb1f8")  # fallback for any other class

# -------------------- main window -------------------------------------------
class Editor(QtWidgets.QMainWindow):
    # .....................................................................
    def __init__(self, json_path, pcd_dir):
        super().__init__()
        self.json_path, self.pcd_dir = json_path, pcd_dir
        self.data = json.load(open(json_path))
        self.i = 0                                          # current record

        # scene element containers
        self.roi_items, self.text_items = [], []
        self.box_items, self.hl_items   = [], []

        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        cw = QtWidgets.QWidget(); lay = QtWidgets.QGridLayout(cw)
        self.setCentralWidget(cw)

        # 3‑D
        self.v3 = GLView(); lay.addWidget(self.v3, 0, 0, 1, 4)

        # 2‑D views ------------------------------------------------------------
        self.xy = pg.PlotWidget(title="XY")
        self.xz = pg.PlotWidget(title="XZ")
        self.yz = pg.PlotWidget(title="YZ");  #self.yz.invertY(True)   # intuitive Z‑up
        for v in (self.xy, self.xz, self.yz): v.setAspectLocked(True)
        lay.addWidget(self.xy, 1, 0); lay.addWidget(self.xz, 1, 1); lay.addWidget(self.yz, 1, 2)

        # controls
        col = QtWidgets.QVBoxLayout(); lay.addLayout(col, 1, 3)
        # self.az  = self._slider(col, "Scene azimuth °",
        #                         lambda v: self.v3.opts.__setitem__('azimuth', v))
        self.rot = self._slider(col, "Rotate bbox °", self._rot_bbox)

        self.combo = QtWidgets.QComboBox(); self.combo.setEditable(True)
        self.combo.currentIndexChanged.connect(self._sync_slider)
        self.combo.lineEdit().editingFinished.connect(self._rename_label)
        col.addWidget(self.combo); col.addStretch()

        # toolbar
        tb = QtWidgets.QToolBar(); self.addToolBar(tb)
        tb.addAction("⟵", lambda: self._goto(self.i-1))
        tb.addAction("⟶", lambda: self._goto(self.i+1))
        tb.addSeparator(); tb.addAction("＋ human", self._add_label)
        tb.addAction("🗑 delete", self._delete_label)  
        tb.addAction("Rename", lambda: self._rename_label(auto_prompt=True))
        tb.addSeparator()
        tb.addAction("Save", self._save)

        lay.setRowStretch(0, 3); lay.setRowStretch(1, 1)
        for c in range(3): lay.setColumnStretch(c, 1)

        # Keyboard control
        QtWidgets.QShortcut(QKeySequence(QtCore.Qt.Key_Left),  self, activated=lambda: self._goto(self.i-1))
        QtWidgets.QShortcut(QKeySequence(QtCore.Qt.Key_Right), self, activated=lambda: self._goto(self.i+1))

    def _slider(self, parent_layout, label, cb):
        parent_layout.addWidget(QtWidgets.QLabel(label))
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal); s.setRange(0, 360); s.valueChanged.connect(cb)
        parent_layout.addWidget(s); return s
    
    # ------------------------------------------------------------------
    # camera helpers
    # ------------------------------------------------------------------
    def _set_azimuth(self, deg):
        """Update orbit azimuth and force a repaint."""
        self.v3.opts['azimuth'] = deg
        # pg.GLViewWidget does not automatically repaint on opts change
        self.v3.update()

    # ------------------------------------------------------------------
    # navigation / refresh
    # ------------------------------------------------------------------
    def _goto(self, idx):
        if 0 <= idx < len(self.data):
            self.i = idx; self._refresh()

    def _refresh(self):
        self._load_cloud(); self._draw_all()
        self.combo.blockSignals(True); self.combo.clear()
        self.combo.addItems([l['Class'] for l in self.data[self.i].get('Labels',[])])
        self.combo.blockSignals(False); self._sync_slider()

    # ------------------------------------------------------------------
    # cloud loading
    # ------------------------------------------------------------------
    def _find_pcd(self, img):
        base = os.path.splitext(img)[0]
        cands = [f for f in os.listdir(self.pcd_dir) if f.endswith('.pcd')]
        pref = f'cloud_{base}_'
        for f in cands:
            if f.startswith(pref): return f
        m = difflib.get_close_matches(base,[os.path.splitext(f)[0] for f in cands],1,0.6)
        return (m[0]+'.pcd') if m else None

    def _load_cloud(self):
        rec = self.data[self.i]; img = rec.get('File','')
        pcd = img if img.endswith('.pcd') else self._find_pcd(img)
        pts = o3d.io.read_point_cloud(os.path.join(self.pcd_dir, pcd)).points
        self.pts = np.asarray(pts)

        # 3‑D scatter
        if hasattr(self,'sc3'): self.v3.removeItem(self.sc3)
        self.sc3 = gl.GLScatterPlotItem(pos=self.pts, size=0.03,
                                        color=np.ones((len(self.pts),4))*0.8, pxMode=False)
        self.v3.addItem(self.sc3); self.v3.opts['center'] = pg.Vector(*self.pts.mean(0))

        # base scatters in 2‑D
        self._sc2d(self.xy, 'sc_xy',(0,1))
        self._sc2d(self.xz, 'sc_xz',(0,2))
        self._sc2d(self.yz, 'sc_yz',(1,2))

    def _sc2d(self, view, attr, idx):
        old = getattr(self, attr, None)
        if old: view.removeItem(old)
        sc = pg.ScatterPlotItem(pos=self.pts[:,idx], size=0.5,
                                brush=pg.mkBrush(200,200,200,120))
        setattr(self, attr, sc); view.addItem(sc)

    # ------------------------------------------------------------------
    # bbox helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _corners(cx,cy,cz,w,h,d,y):
        sx,sy,sz = w/2,h/2,d/2
        loc = np.array([[ sx, sy, sz],[ sx,-sy, sz],[-sx,-sy, sz],[-sx, sy, sz],
                        [ sx, sy,-sz],[ sx,-sy,-sz],[-sx,-sy,-sz],[-sx, sy,-sz]])
        c,s = math.cos(y), math.sin(y)
        return loc@np.array([[c,-s,0],[s,c,0],[0,0,1]]).T + np.array([cx,cy,cz])

    def _edge_item(self,c,col):
        e=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]]
        pts=np.vstack([c[k] for k in e])
        col=np.tile((*np.array(col)/255,1),(pts.shape[0],1))
        return gl.GLLinePlotItem(pos=pts,color=col,mode='lines',antialias=True,width=2)

    def _inside(self,c): from scipy.spatial import Delaunay; return Delaunay(c).find_simplex(self.pts)>=0

    # ---------- new tiny helpers --------------------------------------
    def _bbox_params(self, idx):
        return self.data[self.i]['Labels'][idx]['BoundingBoxes']

    def _set_bbox_params(self, idx, params):
        self.data[self.i]['Labels'][idx]['BoundingBoxes'] = list(params)

    # ──────────────────────────────────────────────────────────────────────
    # helper – keep exactly ONE GL‑box per label
    # ──────────────────────────────────────────────────────────────────────
    def _new_gl_box(self, label_idx: int, corners: np.ndarray, rgb):
        """
        Build/replace the GL wire‑frame box for *label_idx*.
        """
        if not hasattr(self, '_glbox_by_label'):
            self._glbox_by_label = {}

        # remove previous instance
        old = self._glbox_by_label.pop(label_idx, None)
        if old is not None:
            try:    self.v3.removeItem(old)
            except Exception:  pass

        # 12 edges → 24 vertices
        edges = [(0,1),(1,2),(2,3),(3,0),
                (4,5),(5,6),(6,7),(7,4),
                (0,4),(1,5),(2,6),(3,7)]
        pts = np.vstack([corners[list(e)] for e in edges])   # ← fixed!
        col = np.tile((*np.array(rgb)/255.0, 1.0), (pts.shape[0], 1))

        box = gl.GLLinePlotItem(pos=pts, color=col,
                                width=2, antialias=True, mode='lines')
        self._glbox_by_label[label_idx] = box
        return box

    # ──────────────────────────────────────────────────────────────────────
    # replacement _draw_all
    # ──────────────────────────────────────────────────────────────────────
    # def _draw_all(self):
    #     """Redraw 3‑D boxes, highlighted points and all 2‑D ROIs/text."""
    #     # -------- purge previous 3‑D items ---------------------------------
    #     for it in self.box_items + self.hl_items:
    #         try:
    #             self.v3.removeItem(it)
    #         except Exception:
    #             pass          # already deleted
    #     self.box_items.clear()
    #     self.hl_items.clear()

    #     # -------- purge previous 2‑D items ---------------------------------
    #     for view, roi in self.roi_items:
    #         view.removeItem(roi)
    #     for view, txt in self.text_items:
    #         view.removeItem(txt)
    #     self.roi_items.clear()
    #     self.text_items.clear()

    #     # -------------------------------------------------------------------
    #     labels = self.data[self.i].get('Labels', [])
    #     if not labels:          # nothing to draw
    #         return

    #     for j, lab in enumerate(labels):
    #         cx, cy, cz, w, h, d, yaw, *_ = lab['BoundingBoxes']
    #         colour = _palette[j % len(_palette)]

    #         # ---------- 3‑D wire‑frame box ---------------------------------
    #         corners = self._corners(cx, cy, cz, w, h, d, yaw)
    #         box = self._new_gl_box(j, corners, colour.getRgb()[:3])
    #         self.v3.addItem(box)
    #         self.box_items.append(box)

    #         # ---------- highlighted points inside bbox ---------------------
    #         # inside = self._inside(corners)
    #         # if inside.any():
    #         #     col = np.tile(np.array(colour.getRgbF()), (inside.sum(), 1))
    #         #     hl = gl.GLScatterPlotItem(pos=self.pts[inside],
    #         #                             size=0.2, color=col, pxMode=False)
    #         #     self.v3.addItem(hl)
    #         #     self.hl_items.append(hl)
    #         inside = self._inside(corners)
    #         if inside.any():
    #             hl_col = np.tile(np.array(colour.getRgbF()), (inside.sum(), 1))
    #             hl = gl.GLScatterPlotItem(pos=self.pts[inside],
    #                                     size=0.2, color=hl_col, pxMode=False)
    #             self.v3.addItem(hl)
    #             self.hl_items.append(hl)

    #         # ---------- 2‑D rectangular ROIs + captions --------------------
    #     # ----- 2‑D ROIs ----------------------------------------------------
    #     for view, axes in ((self.xy, (0, 1)), (self.xz, (0, 2)), (self.yz, (1, 2))):
    #         # project the rotated corners onto the chosen plane
    #         proj = corners[:, axes]          # 8×2
    #         (xmin, ymin), (xmax, ymax) = proj.min(0), proj.max(0)

    #         roi = pg.RectROI([xmin, ymin], [xmax - xmin, ymax - ymin],
    #                         pen=pg.mkPen(color=colour, width=2),       # ← use QColor
    #                         movable=True, resizable=True, rotatable=False)

    #         # eight handles (four corners + four edge‑midpoints)
    #         for h in ((0,0),(1,0),(1,1),(0,1),(0.5,0),(1,0.5),(0.5,1),(0,0.5)):
    #             roi.addScaleHandle(h, (1-h[0], 1-h[1]))

    #         roi.sigRegionChangeFinished.connect(
    #             lambda _, r=roi, i=j, a=axes: self._roi_moved(r, i, a))
    #         view.addItem(roi)
    #         self.roi_items.append((view, roi))

    #         txt = pg.TextItem(self.data[self.i]['Labels'][j]['Class'], color=colour)
    #         txt.setPos(xmin, ymax)
    #         view.addItem(txt)
    #         self.text_items.append((view, txt))

    def _draw_all(self):
        """Redraw 3‑D boxes, highlighted points and 2‑D ROIs."""
        # ───── clear previous items ──────────────────────────────────────
        for it in self.box_items + self.hl_items:
            try:
                self.v3.removeItem(it)
            except Exception:
                pass
        self.box_items.clear(); self.hl_items.clear()

        for view, roi in self.roi_items: view.removeItem(roi)
        for view, txt in self.text_items: view.removeItem(txt)
        self.roi_items.clear(); self.text_items.clear()

        # ───── nothing to draw? ──────────────────────────────────────────
        labels = self.data[self.i].get('Labels', [])
        if not labels:
            return

        # ───── per‑label drawing ─────────────────────────────────────────
        for j, lab in enumerate(labels):
            cx, cy, cz, w, h, d, yaw, *_ = lab['BoundingBoxes']
            # qcol   = _palette[j % len(_palette)]          # a QColor
            cls_name = lab['Class'].lower()        # case‑insensitive lookup
            qcol= LABEL_COLOURS.get(cls_name, DEFAULT_COLOUR)

            # ---------- 3‑D wire‑frame box ------------------------------
            corners = self._corners(cx, cy, cz, w, h, d, yaw)
            box = self._new_gl_box(j, corners, qcol.getRgb()[:3])
            self.v3.addItem(box);  self.box_items.append(box)

            # ---------- highlighted points ------------------------------
            inside = self._inside(corners)
            if inside.any():
                hl_col = np.tile(np.array(qcol.getRgbF()), (inside.sum(), 1))
                hl = gl.GLScatterPlotItem(pos=self.pts[inside],
                                        size=0.1, color=hl_col, pxMode=False)
                self.v3.addItem(hl);  self.hl_items.append(hl)

            # ---------- 2‑D ROIs & captions (one for each view) ---------
            for view, axes in ((self.xy, (0, 1)),
                            (self.xz, (0, 2)),
                            (self.yz, (1, 2))):

                proj = corners[:, axes]                 # 8×2 projection
                (xmin, ymin), (xmax, ymax) = proj.min(0), proj.max(0)

                roi = pg.RectROI([xmin, ymin], [xmax - xmin, ymax - ymin],
                                pen=pg.mkPen(color=qcol, width=2),
                                movable=True, resizable=True, rotatable=False)

                # 8 handles (corners + mid‑edges)
                for h in ((0,0),(1,0),(1,1),(0,1),
                        (0.5,0),(1,0.5),(0.5,1),(0,0.5)):
                    roi.addScaleHandle(h, (1-h[0], 1-h[1]))

                # capture *current* roi / label index in the lambda
                roi.sigRegionChangeFinished.connect(
                    lambda _, r=roi, i=j, a=axes: self._roi_moved(r, i, a))

                view.addItem(roi)
                self.roi_items.append((view, roi))

                txt = pg.TextItem(lab['Class'], color=qcol)
                txt.setPos(xmin, ymax)
                view.addItem(txt)
                self.text_items.append((view, txt))

    # ------------------------------------------------------------------
    # ROI moved / resized  →  update bbox & redraw
    # ------------------------------------------------------------------
# ─────────────────── patch for _roi_moved ──────────────────────────────
    def _roi_moved(self, roi, label_idx, axes):
        # current rectangle in the clicked view
        pos  = roi.pos();   size = roi.size()
        px, py = pos.x(),  pos.y()
        sx, sy = size.x(), size.y()

        # split the stored list into useful part + tail (pitch / roll / whatever)
        full             = list(self._bbox_params(label_idx))
        cx,cy,cz,w,h,d,yaw = full[:7]
        tail             = full[7:]              # 0‑2 values, keep untouched

        # overwrite the pieces that belong to the view we’re in
        if axes == (0, 1):          # XY view
            cx, cy, w, h = px+sx*0.5, py+sy*0.5, sx, sy
        elif axes == (0, 2):        # XZ view
            cx, cz, w, d = px+sx*0.5, py+sy*0.5, sx, sy
        else:                       # YZ view
            cy, cz, h, d = px+sx*0.5, py+sy*0.5, sx, sy

        # write everything back ‑ first seven we changed + untouched tail
        self._set_bbox_params(label_idx, (cx, cy, cz, w, h, d, yaw, *tail))

        # redraw – if this feels “laggy”, connect to sigRegionChangeFinished
        self._draw_all()


    # ------------------------------------------------------------------
    # rotation / renaming
    # ------------------------------------------------------------------
    def _sync_slider(self):
        """Update rotation slider when user switches label."""
        idx = self.combo.currentIndex()
        labs = self.data[self.i].get('Labels', [])
        if 0 <= idx < len(labs):
            yaw = labs[idx]['BoundingBoxes'][6]            # radians
            self.rot.blockSignals(True)
            self.rot.setValue(int(math.degrees(yaw) % 360))
            self.rot.blockSignals(False)

    def _rot_bbox(self, deg):
        """Rotate currently selected bbox in‑plane (about Z)."""
        idx = self.combo.currentIndex()
        labs = self.data[self.i].get('Labels', [])
        if 0 <= idx < len(labs):
            labs[idx]['BoundingBoxes'][6] = math.radians(deg)
            self._draw_all()                               # live redraw

    # ------------------------------------------------------------------
    # rename / delete
    # ------------------------------------------------------------------
    # def _rename_label(self):
    #     idx = self.combo.currentIndex()
    #     labs = self.data[self.i].get('Labels', [])
    #     if 0 <= idx < len(labs):
    #         new = self.combo.currentText().strip()
    #         if new and new != labs[idx]['Class']:
    #             labs[idx]['Class'] = new
    #             # update list without emitting the signal recursively
    #             self.combo.blockSignals(True)
    #             self.combo.setItemText(idx, new)
    #             self.combo.blockSignals(False)
    #             self._draw_all()
    # def _rename_label(self, auto_prompt=False):
    #     idx = self.combo.currentIndex()
    #     labs = self.data[self.i].get('Labels', [])
    #     if not (0 <= idx < len(labs)):
    #         return

    #     # plain inline edit (from combo‑box) -----------------------------
    #     if not auto_prompt:
    #         new = self.combo.currentText().strip()

    #     # dialog‑based rename -------------------------------------------
    #     else:
    #         current = labs[idx]['Class']
    #         new, ok = QtWidgets.QInputDialog.getText(
    #             self, "Rename label", "New class name:", text=current)
    #         if not ok:
    #             return
    #         new = new.strip()

    #     if new and new != labs[idx]['Class']:
    #         labs[idx]['Class'] = new
    #         self._draw_all()
    #         # keep combo in sync
    #         self.combo.blockSignals(True)
    #         self.combo.setItemText(idx, new)
    #         self.combo.blockSignals(False)
    def _rename_label(self, auto_prompt=False):
        """Inline rename (combo‑box) **or** dialog rename (toolbar)."""
        idx  = self.combo.currentIndex()
        labs = self.data[self.i].get('Labels', [])
        if not (0 <= idx < len(labs)):
            return                                    # nothing selected

        # -------- obtain new text ---------------------------------------
        if auto_prompt:                              # toolbar button
            new_txt, ok = QtWidgets.QInputDialog.getText(
                self, "Rename label", "New class name:",
                text=labs[idx]['Class'])
            if not ok:
                return
        else:                                        # combo‑box inline edit
            new_txt = self.combo.lineEdit().text()

        new_txt = new_txt.strip()
        if not new_txt or new_txt == labs[idx]['Class']:
            return                                    # no real change

        # -------- store + update UI -------------------------------------
        labs[idx]['Class'] = new_txt
        self.combo.blockSignals(True)
        self.combo.setItemText(idx, new_txt)
        self.combo.blockSignals(False)
        self._draw_all()                              # redraw captions

    def _delete_label(self):
        idx = self.combo.currentIndex()
        labs = self.data[self.i].get('Labels', [])
        if 0 <= idx < len(labs):
            if QtWidgets.QMessageBox.question(
                    self, "Delete label",
                    f"Remove “{labs[idx]['Class']}” ?",
                    QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                labs.pop(idx)
                self._refresh()         # rebuild combo + redraw
            new = self.combo.currentText().strip()
            if new and new != labs[idx]['Class']:
                labs[idx]['Class'] = new
                # update list without emitting the signal recursively
                self.combo.blockSignals(True)
                self.combo.setItemText(idx, new)
                self.combo.blockSignals(False)
                self._draw_all()

    def _delete_label(self):
        idx = self.combo.currentIndex()
        labs = self.data[self.i].get('Labels', [])
        if 0 <= idx < len(labs):
            if QtWidgets.QMessageBox.question(
                    self, "Delete label",
                    f"Remove “{labs[idx]['Class']}” ?",
                    QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                labs.pop(idx)
                self._refresh()         # rebuild combo + redraw

    # ------------------------------------------------------------------
    # add / save
    # ------------------------------------------------------------------
    def _add_label(self):
        lbls=self.data[self.i].setdefault('Labels',[])
        new_name=f"human{len(lbls)+1}"
        txt,ok=QtWidgets.QInputDialog.getText(self,"New label","Class:",text=new_name)
        if not ok or not txt.strip(): return
        cen=self.pts.mean(0) if len(self.pts) else (0,0,0)
        lbls.append({"Class":txt.strip(),"BoundingBoxes":[*cen,1,1,1,0,0,0]})
        self._refresh(); self.combo.setCurrentIndex(self.combo.count()-1)

    def _save(self):
        out=self.json_path.replace('.json','_edited.json')
        json.dump(self.data,open(out,'w'),indent=2)
        QtWidgets.QMessageBox.information(self,'Saved',out)

# -------------------- entry‑point -------------------------------------------
if __name__=='__main__':
    app=QtWidgets.QApplication(sys.argv)
    pdir=QtWidgets.QFileDialog.getExistingDirectory(None,"Select PCD folder")
    jpath,_=QtWidgets.QFileDialog.getOpenFileName(None,"Select JSON file",filter="JSON files (*.json)")
    if not pdir or not jpath: sys.exit(0)

    # overwrite the JSON in place (and sort by timestamp)
    sync_json_pcd_filenames(jpath, pdir)

    w=Editor(jpath,pdir); w.resize(1400,900); w.show()
    sys.exit(app.exec_())
