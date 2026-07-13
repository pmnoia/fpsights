"""
FPSights Professional Gaming UI
Responsive PySide6 prototype for senior project demo.
"""
import sys
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QFileDialog, QProgressBar, QTableWidget,
    QTableWidgetItem, QSizePolicy, QScrollArea, QComboBox, QLineEdit
)

BG = "#070d14"
PANEL = "#0d1722"
PANEL2 = "#111e2c"
BORDER = "#22384e"
TEXT = "#f4f7fb"
MUTED = "#9fb3c8"
RED = "#ff375f"
GREEN = "#20e080"
YELLOW = "#ffd166"

STYLE = f"""
QMainWindow {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-family: Arial; font-size: 14px; }}
QFrame#Sidebar {{ background: #08111b; border-right: 1px solid {BORDER}; }}
QFrame#Card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#CardHot {{ background: #120d16; border: 1px solid {RED}; border-radius: 10px; }}
QPushButton {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 10px 14px; font-weight: bold; }}
QPushButton:hover {{ border: 1px solid {RED}; background: #172538; }}
QPushButton#ActiveNav {{ background: #3b1220; color: {RED}; border-left: 4px solid {RED}; border-radius: 7px; text-align: left; }}
QPushButton#Nav {{ text-align: left; border: none; background: transparent; padding-left: 18px; }}
QPushButton#Nav:hover {{ background: #111e2c; color: {RED}; }}
QPushButton#Primary {{ background: {RED}; color: white; border: none; }}
QPushButton#Primary:hover {{ background: #ff5575; }}
QProgressBar {{ background: #0a111a; border: 1px solid {BORDER}; border-radius: 6px; height: 12px; text-align: center; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 6px; }}
QTableWidget {{ background: #08111b; gridline-color: #1e3145; border: 1px solid {BORDER}; border-radius: 8px; }}
QHeaderView::section {{ background: {PANEL2}; color: {TEXT}; padding: 8px; border: none; font-weight: bold; }}
QLineEdit, QComboBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px; color: {TEXT}; }}
"""

class MiniChart(QFrame):
    def __init__(self, kind="radar"):
        super().__init__(); self.kind = kind; self.setMinimumHeight(190); self.setObjectName("Card")
    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h = self.width(), self.height(); cx,cy = w//2, h//2+12
        p.setPen(QPen(QColor("#46617c"),1))
        for r in [35,60,85]:
            pts=[]
            for i in range(5):
                import math
                a = -math.pi/2 + i*2*math.pi/5
                pts.append((cx+int(math.cos(a)*r), cy+int(math.sin(a)*r)))
            for i in range(5): p.drawLine(*pts[i], *pts[(i+1)%5])
        p.setPen(QPen(QColor(RED),3)); p.setBrush(QColor(255,55,95,70))
        vals=[70,82,75,45,68]; pts=[]
        import math
        for i,v in enumerate(vals):
            r=v/100*85; a=-math.pi/2+i*2*math.pi/5
            pts.append((cx+int(math.cos(a)*r), cy+int(math.sin(a)*r)))
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        p.drawPolygon(QPolygon([QPoint(x,y) for x,y in pts]))
        p.setPen(QColor(TEXT)); p.setFont(QFont("Arial",9, QFont.Bold)); p.drawText(16,28,"ANALYSIS SUMMARY")

class VideoMock(QFrame):
    def __init__(self):
        super().__init__(); self.setMinimumHeight(330); self.setObjectName("Card")
    def paintEvent(self,e):
        super().paintEvent(e); p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        grad=QLinearGradient(0,0,w,h); grad.setColorAt(0,QColor("#1a0f13")); grad.setColorAt(1,QColor("#07101a")); p.fillRect(12,12,w-24,h-24,grad)
        p.setPen(QPen(QColor("#5f6670"),2))
        for x in range(80,w-40,110): p.drawLine(x,60,x+40,h-90)
        for y in range(75,h-110,55): p.drawLine(55,y,w-65,y-10)
        p.setPen(QPen(QColor(RED),3)); p.setBrush(QColor(255,55,95,35))
        p.drawRect(w//2+20,h//2-40,64,90); p.drawRect(w//2+175,h//2-35,60,85)
        p.drawLine(w//2+52,h//2-10,w//2+52,h//2+25); p.drawLine(w//2+38,h//2+5,w//2+66,h//2+5)
        p.setPen(QPen(QColor("#e8edf5"),2)); p.setFont(QFont("Arial",12,QFont.Bold)); p.drawText(w//2-40,42,"8      1:12      6")
        p.setPen(QPen(QColor(RED),5)); p.drawLine(45,h-64,w//2-20,h-64); p.setPen(QPen(QColor("#7d8794"),4)); p.drawLine(w//2-20,h-64,w-50,h-64)
        p.setPen(QColor(TEXT)); p.setFont(QFont("Arial",11,QFont.Bold)); p.drawText(45,h-35,"▶  ▌▌     00:12 / 25:43                                      1.0x  ⚙  ⛶")

class HeatmapMock(QFrame):
    def __init__(self): super().__init__(); self.setMinimumHeight(230); self.setObjectName("Card")
    def paintEvent(self,e):
        super().paintEvent(e); p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(TEXT)); p.setFont(QFont("Arial",9,QFont.Bold)); p.drawText(16,28,"HEATMAP")
        p.setPen(QPen(QColor("#36506b"),1)); p.drawRect(35,50,self.width()-70,self.height()-85)
        centers=[(110,140,55),(230,128,45),(345,145,50),(470,95,60)]
        for x,y,r in centers:
            for rr,c in [(r,QColor(0,210,255,45)),(int(r*.65),QColor(255,210,0,80)),(int(r*.35),QColor(255,55,95,140))]:
                p.setBrush(c); p.setPen(Qt.NoPen); p.drawEllipse(x-rr,y-rr,rr*2,rr*2)
        p.setPen(QColor(MUTED)); p.drawText(55,145,"A Site"); p.drawText(self.width()-115,125,"B Site")

class StatCard(QFrame):
    def __init__(self, title, value, sub, icon="◇"):
        super().__init__(); self.setObjectName("Card"); self.setMinimumHeight(100)
        lay=QHBoxLayout(self); lay.setContentsMargins(18,12,18,12)
        ic=QLabel(icon); ic.setStyleSheet(f"color:{RED}; font-size:28px;"); lay.addWidget(ic)
        box=QVBoxLayout(); box.addWidget(label(title,10,MUTED,True)); box.addWidget(label(value,24,TEXT,True)); box.addWidget(label(sub,11,GREEN,True)); lay.addLayout(box); lay.addStretch()

def label(text, size=12, color=TEXT, bold=False):
    l=QLabel(text); l.setStyleSheet(f"color:{color}; font-size:{size}px;" + ("font-weight:bold;" if bold else "")); l.setWordWrap(True); return l

def card_title(t): return label(t,13,TEXT,True)

class FPSightsPro(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("FPSights Pro Gaming UI"); self.resize(1440, 920); self.setMinimumSize(1100,720); self.setStyleSheet(STYLE)
        root=QWidget(); self.setCentralWidget(root); main=QHBoxLayout(root); main.setContentsMargins(0,0,0,0); main.setSpacing(0)
        self.sidebar=QFrame(); self.sidebar.setObjectName("Sidebar"); self.sidebar.setFixedWidth(245); main.addWidget(self.sidebar)
        self.build_sidebar()
        self.stack=QStackedWidget(); main.addWidget(self.stack,1)
        self.pages=[]
        self.add_page("Dashboard", self.dashboard_page())
        self.add_page("Analyze VOD", self.analyze_page())
        self.add_page("Report", self.report_page())
        self.add_page("Heatmap", self.heatmap_page())
        self.add_page("Compare", self.compare_page())
        self.add_page("Settings", self.settings_page())
        self.set_active(1)
    def build_sidebar(self):
        lay=QVBoxLayout(self.sidebar); lay.setContentsMargins(22,26,0,22); lay.setSpacing(14)
        lay.addWidget(label("◢  FPSights",26,TEXT,True)); lay.addWidget(label("     AI Gameplay Coach",13,MUTED)); lay.addSpacing(30)
        self.nav=[]
        for name, icon in [("Dashboard","⌂"),("Analyze VOD","▣"),("Report","▤"),("Heatmap","◎"),("Compare","⇄"),("Settings","⚙")]:
            b=QPushButton(f"{icon}  {name.upper()}"); b.setObjectName("Nav"); b.setFixedHeight(46); b.clicked.connect(lambda _,i=len(self.nav): self.set_active(i)); lay.addWidget(b); self.nav.append(b)
        lay.addStretch(); rank=QFrame(); rank.setObjectName("Card"); rank.setFixedHeight(125); r=QVBoxLayout(rank); r.addWidget(label("CURRENT RANK",11,MUTED,True)); r.addWidget(label("◆ Immortal 3",20,TEXT,True)); r.addWidget(label("324 RR     Win 52%",12,MUTED)); lay.addWidget(rank)
    def add_page(self, name, widget): self.pages.append(name); self.stack.addWidget(widget)
    def set_active(self, idx):
        self.stack.setCurrentIndex(idx)
        for i,b in enumerate(self.nav): b.setObjectName("ActiveNav" if i==idx else "Nav"); b.style().unpolish(b); b.style().polish(b)
    def wrap(self, content):
        area=QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QFrame.NoFrame); area.setWidget(content); return area
    def header(self, title):
        row=QHBoxLayout(); left=QVBoxLayout(); left.addWidget(label(title,24,TEXT,True)); left.addWidget(label("Ascent  •  Competitive  •  25:43  •  5/12/2026 10:48 PM",13,MUTED)); row.addLayout(left); row.addStretch()
        up=QPushButton("Upload VOD"); ex=QPushButton("↓  Export Report"); ex.setObjectName("Primary"); row.addWidget(up); row.addWidget(ex); return row
    def dashboard_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Dashboard"))
        grid=QGridLayout(); grid.setSpacing(12)
        stats=[("AVG REACTION TIME","420 ms","Good (under 350ms)","⚡"),("CROSSHAIR SCORE","82%","Great","⌖"),("POSITIONING SCORE","75%","Good","🛡"),("ACCURACY","68%","Good","◎"),("K/D RATIO","1.79","15 Kills / 7 Deaths","⚔")]
        for i,s in enumerate(stats): grid.addWidget(StatCard(*s),0,i)
        lay.addLayout(grid); lay.addWidget(VideoMock()); lay.addWidget(self.event_timeline()); return self.wrap(w)
    def analyze_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("valorant_round_01.mp4  ✎"))
        grid=QGridLayout(); grid.setSpacing(12)
        for i,s in enumerate([("AVG REACTION TIME","420 ms","Good (under 350ms)","⚡"),("CROSSHAIR SCORE","82%","Great","⌖"),("POSITIONING SCORE","75%","Good","🛡"),("ACCURACY","68%","Good","◎"),("K/D RATIO","1.79","15 Kills / 7 Deaths","⚔")]): grid.addWidget(StatCard(*s),0,i)
        lay.addLayout(grid)
        mid=QHBoxLayout(); left=QVBoxLayout(); left.addWidget(VideoMock(),3); left.addWidget(self.event_timeline(),1); mid.addLayout(left,2)
        right=QVBoxLayout(); right.addWidget(MiniChart()); right.addWidget(self.coach_card()); mid.addLayout(right,1); lay.addLayout(mid)
        bottom=QHBoxLayout(); bottom.addWidget(self.event_table(),3); bottom.addWidget(HeatmapMock(),2); lay.addLayout(bottom); return self.wrap(w)
    def event_timeline(self):
        c=QFrame(); c.setObjectName("Card"); c.setMinimumHeight(95); l=QVBoxLayout(c); l.addWidget(label("Event Markers   ◇ Enemy Visible    ⚠ Aim Correction    ✹ Shot Fired    ☠ Enemy Killed    💀 Player Died",12,TEXT))
        pb=QProgressBar(); pb.setValue(48); l.addWidget(pb); l.addWidget(label("00:00        05:00        10:00        15:00        20:00        25:43",11,MUTED)); return c
    def coach_card(self):
        c=QFrame(); c.setObjectName("CardHot"); c.setMinimumHeight(250); l=QVBoxLayout(c)
        l.addWidget(label("AI COACH FEEDBACK",13,RED,True));
        tips=["⬆ Great reaction time! You react faster than average players.","⬆ Crosshair placement is strong. Keep head-level angles.","⚠ Avoid wide peeking in Mid. You died 3 times in same spot.","⚠ Improve first bullet accuracy. Try burst fire instead of spraying."]
        for t in tips: l.addWidget(label(t,12,TEXT)); l.addStretch()
        b=QPushButton("View Full Report  ›"); b.setObjectName("Primary"); l.addWidget(b); return c
    def event_table(self):
        t=QTableWidget(6,6); t.setHorizontalHeaderLabels(["#","TIME","EVENT","DETAILS","REGION","VIDEO"]); t.verticalHeader().setVisible(False)
        rows=[("1","00:12.400","◇ Enemy Visible","1 enemy spotted","Mid","▶"),("2","00:12.610","⚠ Aim Correction","Moving crosshair","Mid","▶"),("3","00:12.920","✹ Shot Fired","First bullet fired","Mid","▶"),("4","00:13.100","☠ Enemy Killed","Kill confirmed","Mid","▶"),("5","00:25.800","◇ Enemy Visible","2 enemies spotted","A Site","▶"),("6","00:26.150","💀 Player Died","Killed by enemy","A Site","▶")]
        for r,row in enumerate(rows):
            for c,val in enumerate(row): t.setItem(r,c,QTableWidgetItem(val))
        t.setMinimumHeight(230); t.horizontalHeader().setStretchLastSection(True); return t
    def report_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Performance Report"));
        g=QGridLayout(); g.setSpacing(12)
        for i,s in enumerate([("OVERALL SCORE","78/100","Good performance","★"),("BEST SKILL","Crosshair","Strong head level","⌖"),("WEAK AREA","Positioning","Avoid Mid overpeek","⚠"),("EXPORT","PDF Ready","Report available","↓")]): g.addWidget(StatCard(*s),0,i)
        lay.addLayout(g); lay.addWidget(self.coach_card()); lay.addWidget(self.event_table()); return self.wrap(w)
    def heatmap_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Heatmap")); lay.addWidget(HeatmapMock()); lay.addWidget(label("Red zones show high activity / danger positions. Use this to explain positioning mistakes in your demo.",14,MUTED)); return self.wrap(w)
    def compare_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Compare Matches")); lay.addWidget(label("Compare current match with previous VOD performance.",14,MUTED)); lay.addWidget(self.event_table()); return self.wrap(w)
    def setting_row(self, title, widget, hint=""):
        row = QFrame(); row.setObjectName("Card"); row.setMinimumHeight(82)
        lay = QHBoxLayout(row); lay.setContentsMargins(18, 12, 18, 12); lay.setSpacing(18)
        left = QVBoxLayout(); left.addWidget(label(title, 13, TEXT, True))
        if hint:
            left.addWidget(label(hint, 11, MUTED))
        lay.addLayout(left, 1)
        widget.setMinimumWidth(260); widget.setMaximumWidth(420)
        lay.addWidget(widget, 1)
        return row

    def combo(self, items, current=0):
        c = QComboBox(); c.addItems(items); c.setCurrentIndex(current); return c

    def settings_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(26, 24, 26, 24)
        lay.setSpacing(14)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(label("Settings", 24, TEXT, True))
        title_box.addWidget(label("Customize FPSights for the senior project demo.", 14, MUTED))
        top.addLayout(title_box)
        top.addStretch()
        save_top = QPushButton("Save Settings")
        save_top.setObjectName("Primary")
        top.addWidget(save_top)
        lay.addLayout(top)

        profile = QFrame(); profile.setObjectName("CardHot")
        p_lay = QVBoxLayout(profile); p_lay.setContentsMargins(18, 14, 18, 14)
        p_lay.addWidget(label("PLAYER PROFILE", 13, RED, True))
        p_lay.addWidget(label("These settings are used for match records, reports, and dashboard display.", 12, MUTED))
        lay.addWidget(profile)

        grid = QGridLayout(); grid.setSpacing(12)

        player = QLineEdit("Bryan")
        game = self.combo(["Valorant", "Counter-Strike 2 / CS2"], 0)
        rank = self.combo(["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal 1", "Immortal 2", "Immortal 3", "Radiant"], 9)
        agent = self.combo(["Raze", "Jett", "Reyna", "Phoenix", "Sova", "Killjoy", "Cypher", "Omen", "Sage", "Other"], 0)
        default_map = self.combo(["Ascent", "Bind", "Haven", "Split", "Lotus", "Sunset", "Icebox", "Breeze", "Mirage", "Dust II", "Inferno"], 0)
        theme = self.combo(["Dark Valorant", "Midnight Blue", "Minimal Dark"], 0)
        accent = self.combo(["Valorant Red", "Neon Cyan", "Electric Purple", "Gold"], 0)
        target = self.combo(["250 ms", "300 ms", "350 ms", "400 ms", "450 ms"], 2)
        export_fmt = self.combo(["PDF Report", "CSV Data", "PDF + CSV", "Screenshot Summary"], 0)

        grid.addWidget(self.setting_row("Player Name", player, "Name shown on report and dashboard"), 0, 0)
        grid.addWidget(self.setting_row("Game", game, "Choose target FPS game"), 0, 1)
        grid.addWidget(self.setting_row("Rank", rank, "Player rank for profile card"), 1, 0)
        grid.addWidget(self.setting_row("Main Agent", agent, "Used for Valorant-style profile"), 1, 1)
        grid.addWidget(self.setting_row("Default Map", default_map, "Default map for demo analysis"), 2, 0)
        grid.addWidget(self.setting_row("Theme Mode", theme, "Visual style of the application"), 2, 1)
        grid.addWidget(self.setting_row("Accent Color", accent, "Highlight color for buttons and charts"), 3, 0)
        grid.addWidget(self.setting_row("Target Reaction Time", target, "Benchmark for good reaction time"), 3, 1)
        grid.addWidget(self.setting_row("Export Report Format", export_fmt, "Output format for final report"), 4, 0)

        save = QPushButton("Save Settings")
        save.setObjectName("Primary")
        save.setMinimumHeight(46)
        grid.addWidget(save, 4, 1)

        lay.addLayout(grid)

        note = QFrame(); note.setObjectName("Card")
        n = QVBoxLayout(note); n.setContentsMargins(18, 14, 18, 14)
        n.addWidget(label("WEEK 3 UI CONNECTION", 13, RED, True))
        n.addWidget(label("Next step: connect these settings to SQLite, so player profile and default options can be saved and loaded.", 12, MUTED))
        lay.addWidget(note)
        lay.addStretch()
        return self.wrap(w)

if __name__ == "__main__":
    app=QApplication(sys.argv); app.setStyleSheet(STYLE); win=FPSightsPro(); win.show(); sys.exit(app.exec())