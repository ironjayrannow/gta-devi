#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GTA 5 - Top Down Klon  (Pygame, tek dosya)
==========================================
v2 - Yenilikler
  * Telefon (T) düzeltildi, tam ekran arayüzlü iFruit + rehber
  * Harita 3200 -> 6400 px, yollar 160 -> 280 px (geniş caddeler)
  * Girilebilir dükkanlar: berber, market, espor arenası, Ammu-Nation,
    giyim, eczane, spor salonu, modifiye, tattoo, fast-food
  * Görev sistemi: kurye, suikast, araç kaçırma, kaçış (para + itibar)
  * Yeni araç fiziği: gerçek yanal kayma (drift), motor/fren/vites, hasar
  * Yol ağı üzerinde çalışan trafik AI
  * F1 yardım ekranı, bildirim paneli, görev/waypoint oku

Kontroller
  WASD / Yön tuşları : yürü  |  araçta: W gaz, S fren/geri, A-D direksiyon
  Mouse              : 360 derece nişan
  Sol tık            : ateş et
  Sağ tık (basılı)   : nişan modu (zoom + lazer)
  E                  : araca bin / in, dükkan kapısı, görev al, eşya satın al
  Q                  : dükkandan çık
  T veya P           : telefon aç / kapat
  R                  : şarjör doldur
  SPACE              : el freni (drift)
  H                  : korna
  F1                 : kontrol listesi
  ESC                : kapat / geri
"""

try:
    import pygame
except ImportError:  # pygame kurulu değilse yol göster
    raise SystemExit("pygame bulunamadı. Kurulum:  pip install pygame")

import math
import random
import sys
import datetime

pygame.init()
pygame.font.init()

# ============================================================
#  AYARLAR
# ============================================================
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

MAP_W = MAP_H = 6400
ROAD_W = 280                       # cadde genişliği (eski 160)
ROAD_STEP = 1000
ROAD_START = 400
ROAD_XS = [ROAD_START + i * ROAD_STEP for i in range(6)]
ROAD_YS = [ROAD_START + i * ROAD_STEP for i in range(6)]

C = {
    "grass":      (34, 92, 42),
    "grass2":     (42, 108, 50),
    "road":       (44, 45, 50),
    "road_edge":  (58, 59, 64),
    "line":       (232, 205, 70),
    "line_white": (225, 225, 228),
    "walk":       (150, 150, 152),
    "walk2":      (128, 128, 132),
    "walk_line":  (112, 112, 116),
    "skin":       (232, 190, 140),
    "shirt":      (26, 34, 56),
    "pants":      (44, 60, 96),
    "shoe":       (22, 22, 24),
    "hud_bg":     (14, 15, 18),
    "green":      (46, 204, 64),
    "blue":       (52, 152, 219),
    "gold":       (241, 196, 15),
    "red":        (231, 76, 60),
    "phone":      (16, 17, 22),
    "neon":       (0, 220, 255),
}


# ============================================================
#  YARDIMCI FONKSİYONLAR
# ============================================================
def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, mn, mx):
    return mn if v < mn else (mx if v > mx else v)


def dist(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def angle_to(ax, ay, bx, by):
    return math.degrees(math.atan2(by - ay, bx - ax))


def norm_angle(a):
    while a > 180:
        a -= 360
    while a < -180:
        a += 360
    return a


def world_to_screen(wx, wy, cam):
    return (wx - cam.x) * cam.zoom + SCREEN_W / 2, (wy - cam.y) * cam.zoom + SCREEN_H / 2


_FONTS = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = pygame.font.SysFont("dejavusans,segoeui,arial", size, bold=bold)
    return _FONTS[key]


def text(surf, s, x, y, size=14, bold=False, color=(255, 255, 255),
         center=False, shadow=True, alpha=255):
    f = font(size, bold)
    img = f.render(str(s), True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    px = x - img.get_width() // 2 if center else x
    if shadow:
        sh = f.render(str(s), True, (0, 0, 0))
        sh.set_alpha(min(alpha, 150))
        surf.blit(sh, (px + 1, y + 1))
    surf.blit(img, (px, y))
    return img.get_width()


def wrap_text(s, size, max_w, bold=False):
    f = font(size, bold)
    words, lines, cur = s.split(), [], ""
    for w in words:
        test = (cur + " " + w) if cur else w
        if f.size(test)[0] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def rounded(surf, color, rect, radius=8, width=0):
    pygame.draw.rect(surf, color, rect, width, border_radius=radius)


def panel(surf, rect, bg=(18, 19, 24), border=(70, 74, 86), radius=12, alpha=235):
    x, y, w, h = rect
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*bg, alpha), (0, 0, w, h), border_radius=radius)
    pygame.draw.rect(s, (*border, 255), (0, 0, w, h), 1, border_radius=radius)
    surf.blit(s, (x, y))


def star_points(cx, cy, r_out, r_in, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        a = math.radians(rot + i * 180 / n)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


# ============================================================
#  İNSAN ÇİZİMİ (top-down, sprite yukarı bakar)
# ============================================================
def draw_person(surface, sx, sy, angle, skin, shirt, pants, hair,
                step=0.0, moving=False, weapon=None, aiming=False,
                scale=1.0, vest=None):
    w, h = 42, 50
    spr = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2 + 3

    swing = math.sin(step) * 5.0 if moving else 0.0
    bob = math.sin(step * 2) * 1.2 if moving else 0.0

    # bacaklar
    pygame.draw.rect(spr, pants, (cx - 8, cy + 3 + swing * 0.45 + bob, 7, 15), border_radius=4)
    pygame.draw.rect(spr, pants, (cx + 1, cy + 3 - swing * 0.45 + bob, 7, 15), border_radius=4)
    # ayakkabı
    pygame.draw.rect(spr, C["shoe"], (cx - 8, cy + 15 + swing * 0.45 + bob, 7, 5), border_radius=2)
    pygame.draw.rect(spr, C["shoe"], (cx + 1, cy + 15 - swing * 0.45 + bob, 7, 5), border_radius=2)

    # gövde
    pygame.draw.rect(spr, shirt, (cx - 10, cy - 9 + bob, 20, 19), border_radius=6)
    pygame.draw.rect(spr, tuple(max(0, c - 30) for c in shirt), (cx - 10, cy + 3 + bob, 20, 5), border_radius=3)
    if vest:
        pygame.draw.rect(spr, vest, (cx - 8, cy - 6 + bob, 16, 14), border_radius=4)
        pygame.draw.rect(spr, (30, 32, 38), (cx - 8, cy + 1 + bob, 16, 2))
    # yaka
    pygame.draw.rect(spr, (14, 15, 22), (cx - 6, cy - 9 + bob, 12, 5), border_radius=2)

    # kollar + silah (yukarı bakıyor)
    if weapon:
        pygame.draw.line(spr, skin, (cx - 9, cy - 4 + bob), (cx - 3, cy - 15 + bob), 5)
        pygame.draw.line(spr, skin, (cx + 9, cy - 4 + bob), (cx + 3, cy - 15 + bob), 5)
        pygame.draw.circle(spr, skin, (cx - 3, cy - 15 + bob), 3)
        pygame.draw.circle(spr, skin, (cx + 3, cy - 15 + bob), 3)
        if weapon == "Pistol":
            pygame.draw.rect(spr, (30, 30, 34), (cx - 2, cy - 25 + bob, 4, 11), border_radius=1)
            pygame.draw.rect(spr, (78, 78, 86), (cx - 3, cy - 26 + bob, 6, 4), border_radius=1)
            pygame.draw.rect(spr, (22, 22, 26), (cx - 2, cy - 17 + bob, 6, 3))
        else:  # Rifle
            pygame.draw.rect(spr, (34, 34, 38), (cx - 2, cy - 32 + bob, 4, 20), border_radius=1)
            pygame.draw.rect(spr, (70, 56, 32), (cx - 4, cy - 22 + bob, 8, 5), border_radius=1)
            pygame.draw.rect(spr, (90, 90, 98), (cx - 1, cy - 34 + bob, 2, 4))
    else:
        pygame.draw.line(spr, skin, (cx - 10, cy - 5 + bob), (cx - 12 - swing * 0.3, cy + 4 + bob), 5)
        pygame.draw.line(spr, skin, (cx + 10, cy - 5 + bob), (cx + 12 + swing * 0.3, cy + 4 + bob), 5)
        pygame.draw.circle(spr, skin, (int(cx - 12 - swing * 0.3), int(cy + 4 + bob)), 3)
        pygame.draw.circle(spr, skin, (int(cx + 12 + swing * 0.3), int(cy + 4 + bob)), 3)

    # kafa
    hx, hy = cx, cy - 14 + bob
    pygame.draw.circle(spr, hair, (hx, hy - 1), 9)
    pygame.draw.circle(spr, skin, (hx, hy), 8)
    # saç üst
    pygame.draw.rect(spr, hair, (hx - 8, hy - 9, 16, 6), border_radius=3)
    pygame.draw.circle(spr, hair, (hx, hy - 7), 5)
    # yüz (yukarı baktığı için üstte)
    pygame.draw.circle(spr, (28, 22, 20), (hx - 3, hy - 3), 1)
    pygame.draw.circle(spr, (28, 22, 20), (hx + 3, hy - 3), 1)
    pygame.draw.line(spr, (196, 150, 110), (hx, hy - 2), (hx, hy + 2), 1)

    if scale != 1.0:
        spr = pygame.transform.smoothscale(spr, (int(w * scale), int(h * scale)))
    rot = pygame.transform.rotate(spr, -angle - 90)
    surface.blit(rot, rot.get_rect(center=(sx, sy)))


# ============================================================
#  KAMERA
# ============================================================
class Camera:
    def __init__(self):
        self.x = MAP_W / 2
        self.y = MAP_H / 2
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.shake = 0.0

    def follow(self, tx, ty, aiming=False, snap=False):
        self.target_zoom = 1.0
        self.zoom = lerp(self.zoom, self.target_zoom, 0.07)
        t = 1.0 if snap else 0.11
        self.x = lerp(self.x, tx, t)
        self.y = lerp(self.y, ty, t)
        hw = SCREEN_W / (2 * self.zoom)
        hh = SCREEN_H / (2 * self.zoom)
        self.x = clamp(self.x, hw, MAP_W - hw)
        self.y = clamp(self.y, hh, MAP_H - hh)
        if self.shake > 0.1:
            self.x += random.uniform(-self.shake, self.shake)
            self.y += random.uniform(-self.shake, self.shake)
            self.shake = lerp(self.shake, 0, 0.16)
        else:
            self.shake = 0.0

    def visible_rect(self, pad=200):
        hw = SCREEN_W / (2 * self.zoom) + pad
        hh = SCREEN_H / (2 * self.zoom) + pad
        return pygame.Rect(int(self.x - hw), int(self.y - hh), int(hw * 2), int(hh * 2))


# ============================================================
#  DÜKKAN TANIMLARI
# ============================================================
SHOPS = {
    "barber": {
        "name": "Berber Boğa", "sign": "BERBER", "color": (58, 78, 132),
        "wall": (60, 66, 92), "floor": (222, 214, 198), "floor2": (204, 196, 180),
        "accent": (230, 90, 70), "prop": "barber",
        "items": [
            {"name": "Saç Kesimi", "price": 150, "desc": "Yeni stil", "effect": "hair", "value": 0},
            {"name": "Sakal Tıraşı", "price": 90, "desc": "Temiz görünüm", "effect": "hair", "value": 1},
            {"name": "Saç Boyası", "price": 220, "desc": "Renk değiştir", "effect": "hair", "value": 2},
        ],
    },
    "market": {
        "name": "24/7 Market", "sign": "24/7", "color": (200, 150, 40),
        "wall": (76, 62, 46), "floor": (226, 226, 220), "floor2": (208, 208, 202),
        "accent": (46, 190, 120), "prop": "shelf",
        "items": [
            {"name": "Sandviç", "price": 25, "desc": "+25 can", "effect": "health", "value": 25},
            {"name": "Enerji İçeceği", "price": 40, "desc": "+45 can", "effect": "health", "value": 45},
            {"name": "İlk Yardım", "price": 90, "desc": "+80 can", "effect": "health", "value": 80},
            {"name": "Çelik Yelek", "price": 300, "desc": "+50 zırh", "effect": "armor", "value": 50},
        ],
    },
    "ammunation": {
        "name": "Ammu-Nation", "sign": "AMMU-NATION", "color": (120, 40, 40),
        "wall": (62, 52, 48), "floor": (208, 200, 186), "floor2": (190, 182, 168),
        "accent": (220, 60, 50), "prop": "guns",
        "items": [
            {"name": "Tabanca Mermisi", "price": 60, "desc": "+40 mermi", "effect": "ammo", "value": 40},
            {"name": "Tüfek (Rifle)", "price": 900, "desc": "Yeni silah", "effect": "rifle", "value": 0},
            {"name": "Tüfek Mermisi", "price": 120, "desc": "+90 mermi", "effect": "ammo", "value": 90},
            {"name": "Ağır Zırh", "price": 420, "desc": "+80 zırh", "effect": "armor", "value": 80},
        ],
    },
    "esports": {
        "name": "ESPOR ARENA", "sign": "ESPOR", "color": (60, 40, 120),
        "wall": (34, 30, 58), "floor": (26, 24, 40), "floor2": (32, 30, 50),
        "accent": (0, 220, 255), "prop": "pc",
        "items": [
            {"name": "1 Saat PC", "price": 100, "desc": "Turnuva kazan", "effect": "gamble", "value": 0},
            {"name": "Turnuva Girişi", "price": 250, "desc": "Büyük ödül", "effect": "gamble", "value": 1},
            {"name": "Kafe & Dinlenme", "price": 80, "desc": "+30 can", "effect": "health", "value": 30},
        ],
    },
    "clothes": {
        "name": "Binco Giyim", "sign": "BINCO", "color": (40, 110, 80),
        "wall": (58, 74, 68), "floor": (218, 214, 206), "floor2": (200, 196, 188),
        "accent": (52, 200, 130), "prop": "clothes",
        "items": [
            {"name": "T-Shirt", "price": 120, "desc": "Renk değiştir", "effect": "shirt", "value": 0},
            {"name": "Kıyafet Seti", "price": 260, "desc": "Yeni kombin", "effect": "shirt", "value": 1},
            {"name": "Zırh Yelek", "price": 350, "desc": "+60 zırh", "effect": "armor", "value": 60},
        ],
    },
    "pharmacy": {
        "name": "Eczane", "sign": "ECZANE", "color": (40, 130, 120),
        "wall": (54, 86, 82), "floor": (232, 238, 236), "floor2": (214, 222, 220),
        "accent": (60, 210, 180), "prop": "shelf",
        "items": [
            {"name": "Ağrı Kesici", "price": 70, "desc": "+40 can", "effect": "health", "value": 40},
            {"name": "Medkit", "price": 180, "desc": "Canı fulle", "effect": "healmax", "value": 0},
            {"name": "Vitamin", "price": 500, "desc": "+25 maks can", "effect": "maxhealth", "value": 25},
        ],
    },
    "gym": {
        "name": "Spor Salonu", "sign": "GYM", "color": (70, 70, 80),
        "wall": (48, 52, 60), "floor": (60, 62, 70), "floor2": (52, 54, 62),
        "accent": (240, 180, 40), "prop": "gym",
        "items": [
            {"name": "Antrenman", "price": 150, "desc": "+15 maks can", "effect": "maxhealth", "value": 15},
            {"name": "Protein", "price": 90, "desc": "+40 can", "effect": "health", "value": 40},
            {"name": "Boks Dersi", "price": 220, "desc": "+25 zırh", "effect": "armor", "value": 25},
        ],
    },
    "customs": {
        "name": "Los Santos Customs", "sign": "CUSTOMS", "color": (130, 90, 40),
        "wall": (58, 54, 46), "floor": (86, 86, 90), "floor2": (74, 74, 78),
        "accent": (250, 150, 40), "prop": "garage",
        "items": [
            {"name": "Onarım", "price": 300, "desc": "Aracı tamir et", "effect": "repair", "value": 0},
            {"name": "Nitro", "price": 450, "desc": "Araç hızlandır", "effect": "nitro", "value": 0},
            {"name": "Boya", "price": 250, "desc": "Rastgele renk", "effect": "paint", "value": 0},
        ],
    },
    "tattoo": {
        "name": "Dövme Stüdyosu", "sign": "TATTOO", "color": (90, 40, 70),
        "wall": (56, 40, 52), "floor": (208, 198, 196), "floor2": (190, 180, 178),
        "accent": (230, 80, 160), "prop": "barber",
        "items": [
            {"name": "Kol Dövmesi", "price": 250, "desc": "Kozmetik", "effect": "tattoo", "value": 0},
            {"name": "Boyun Dövmesi", "price": 380, "desc": "Kozmetik", "effect": "tattoo", "value": 1},
        ],
    },
    "burger": {
        "name": "Cluckin' Bell", "sign": "CLUCKIN", "color": (190, 70, 40),
        "wall": (74, 52, 40), "floor": (230, 220, 206), "floor2": (212, 202, 188),
        "accent": (250, 200, 60), "prop": "fastfood",
        "items": [
            {"name": "Tavuk Menü", "price": 30, "desc": "+30 can", "effect": "health", "value": 30},
            {"name": "Mega Menü", "price": 55, "desc": "+60 can", "effect": "health", "value": 60},
            {"name": "Kahve", "price": 15, "desc": "+10 can", "effect": "health", "value": 10},
        ],
    },
}

SHOP_KEYS = list(SHOPS.keys())


# ============================================================
#  BİNA & HARİTA
# ============================================================
class Building:
    """Çatıdan görünüm: parapet duvar + çatı detayları (klima, havalandırma,
    su deposu, çatı penceresi, iniş kapağı)."""

    def __init__(self, x, y, w, h, color):
        self.rect = pygame.Rect(int(x), int(y), int(w), int(h))
        self.color = color
        self.kind = "block"
        self.shop_key = None
        self.door = None
        self.sign_dir = "bottom"
        self.roof = []
        self._make_roof()

    def _make_roof(self):
        W, H = self.rect.width, self.rect.height
        rnd = random.Random((self.rect.x * 7919 + self.rect.y * 104729) & 0xFFFF)
        n = 2 if W < 200 else rnd.randint(3, 6)
        for _ in range(n):
            kind = rnd.choice(["ac", "ac", "vent", "skylight", "tank", "hatch", "duct"])
            if kind == "ac":
                bw, bh = rnd.randint(34, 58), rnd.randint(26, 44)
            elif kind == "vent":
                bw = bh = rnd.randint(16, 26)
            elif kind == "skylight":
                bw, bh = rnd.randint(44, 76), rnd.randint(32, 52)
            elif kind == "tank":
                bw = bh = rnd.randint(34, 48)
            elif kind == "duct":
                bw, bh = rnd.randint(70, 150), rnd.randint(14, 20)
            else:
                bw = bh = rnd.randint(20, 30)
            if W - 56 - bw < 10 or H - 56 - bh < 10:
                continue
            self.roof.append((kind, rnd.randint(28, W - 28 - bw), rnd.randint(28, H - 28 - bh), bw, bh))


class GameMap:
    def __init__(self):
        self.buildings = []
        self.colliders = []
        self.blocks = []
        self.decor = []
        self.roads_v = []
        self.roads_h = []
        self.intersections = []
        self.mission_spots = []
        self.generate()
        self.mini = self._render_minimap()

    # ---------- üretim ----------
    @staticmethod
    def _spans(road_centers, total):
        spans, prev = [], 0
        for c in road_centers:
            s = c - ROAD_W // 2
            if s - prev > 60:
                spans.append((prev, s))
            prev = c + ROAD_W // 2
        if total - prev > 60:
            spans.append((prev, total))
        return spans

    def generate(self):
        for x in ROAD_XS:
            self.roads_v.append(pygame.Rect(x - ROAD_W // 2, 0, ROAD_W, MAP_H))
        for y in ROAD_YS:
            self.roads_h.append(pygame.Rect(0, y - ROAD_W // 2, MAP_W, ROAD_W))
        for x in ROAD_XS:
            for y in ROAD_YS:
                self.intersections.append((x, y))

        xs = self._spans(ROAD_XS, MAP_W)
        ys = self._spans(ROAD_YS, MAP_H)

        # bloklar
        for (x0, x1) in xs:
            for (y0, y1) in ys:
                self.blocks.append({
                    "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                    "x1": x1, "y1": y1, "park": False, "shops": [],
                })

        # park blokları
        random.seed(7)
        parks = random.sample(range(len(self.blocks)), 6)
        for i in parks:
            self.blocks[i]["park"] = True

        # dükkan blokları -> her dükkan tipi en az bir kez
        shop_blocks = [i for i in range(len(self.blocks)) if not self.blocks[i]["park"]]
        random.shuffle(shop_blocks)
        assignments = []
        for k in SHOP_KEYS:
            assignments.append(k)
        # 2. tur birkaç dükkan daha
        for k in random.sample(SHOP_KEYS, 4):
            assignments.append(k)
        for idx, key in zip(shop_blocks, assignments):
            self.blocks[idx]["shops"].append(key)

        for blk in self.blocks:
            if blk["park"]:
                self._make_park(blk)
            elif blk["shops"]:
                self._make_shop_block(blk)
            else:
                self._make_buildings(blk)

        # görev noktaları (sokak köşelerinde sarı ? işaretleri)
        spots = random.sample(self.intersections, 6)
        for (ix, iy) in spots:
            self.mission_spots.append((ix + 150, iy + 150))

        random.seed()

    def _add_building(self, b):
        self.buildings.append(b)
        self.colliders.append(b.rect)

    def _make_park(self, blk):
        x, y, w, h = blk["x"], blk["y"], blk["w"], blk["h"]
        for _ in range(int(w * h / 24000)):
            self.decor.append(("tree", x + random.randint(40, w - 40), y + random.randint(40, h - 40)))

    def _make_buildings(self, blk):
        x, y, w, h = blk["x"] + 26, blk["y"] + 26, blk["w"] - 52, blk["h"] - 52
        if w < 120 or h < 120:
            return
        palette = [(178, 158, 132), (162, 142, 118), (196, 178, 152), (150, 138, 128),
                   (176, 132, 108), (136, 148, 156), (188, 168, 120), (128, 118, 112),
                   (160, 108, 96), (108, 126, 130), (198, 190, 172), (146, 122, 104)]
        # şehir dokusu: küçük parseller
        choice = random.choices(
            ["one", "two_v", "two_h", "four", "six", "three_v"],
            weights=[0.08, 0.16, 0.14, 0.32, 0.20, 0.10])[0]
        gap = random.choice([12, 16, 20])
        if choice == "one":
            self._add_building(Building(x, y, w, h, random.choice(palette)))
        elif choice == "two_v":
            bw = (w - gap) // 2
            self._add_building(Building(x, y, bw, h, random.choice(palette)))
            self._add_building(Building(x + bw + gap, y, w - bw - gap, h, random.choice(palette)))
        elif choice == "three_v":
            bw = (w - gap * 2) // 3
            for i in range(3):
                self._add_building(Building(x + i * (bw + gap), y, bw, h, random.choice(palette)))
        elif choice == "two_h":
            bh = (h - gap) // 2
            self._add_building(Building(x, y, w, bh, random.choice(palette)))
            self._add_building(Building(x, y + bh + gap, w, h - bh - gap, random.choice(palette)))
        elif choice == "four":
            bw, bh = (w - gap) // 2, (h - gap) // 2
            for ix in range(2):
                for iy in range(2):
                    if random.random() < 0.06:
                        continue
                    self._add_building(Building(x + ix * (bw + gap), y + iy * (bh + gap),
                                                bw, bh, random.choice(palette)))
        else:  # six (3x2)
            bw, bh = (w - gap * 2) // 3, (h - gap) // 2
            for ix in range(3):
                for iy in range(2):
                    if random.random() < 0.08:
                        continue
                    self._add_building(Building(x + ix * (bw + gap), y + iy * (bh + gap),
                                                bw, bh, random.choice(palette)))
        # ara sokak çöp konteyneri / çalı
        for _ in range(random.randint(0, 2)):
            cx_ = x + random.randint(30, max(31, w - 30))
            cy_ = y + random.randint(30, max(31, h - 30))
            if not self.blocked_point(cx_, cy_):
                self.decor.append(("bin" if random.random() < 0.5 else "bush", cx_, cy_))

    def _make_shop_block(self, blk):
        x, y, w, h = blk["x"], blk["y"], blk["w"], blk["h"]
        key = blk["shops"][0]
        sd = SHOPS[key]
        # dükkanlar her zaman caddeye bakan tarafta olsun (erişim + tabela)
        side = random.choice(["top", "bottom"])
        m = 46
        bw = w - 2 * m
        bh = min(300, int(h * 0.52))
        bx = x + m
        by = y + m if side == "top" else y + h - bh - m
        # kapı noktası kaldırımda, bina duvarının hemen dışında
        door = (bx + bw // 2, by - 24 if side == "top" else by + bh + 24)

        b = Building(bx, by, bw, bh, sd["color"])
        b.kind = "shop"
        b.shop_key = key
        b.door = door
        b.sign_dir = side
        self._add_building(b)
        blk["shops"] = [key]

        # kalan alana normal bina
        rest_y = by + bh + 26 if side == "top" else y + m
        rest_h = (y + h - m) - rest_y if side == "top" else by - 26 - rest_y
        if rest_h > 130:
            self._add_building(Building(x + m, rest_y, w - 2 * m, rest_h,
                                        random.choice([(70, 62, 56), (86, 78, 72), (80, 66, 60)])))

    def _render_minimap(self):
        size = 230
        s = pygame.Surface((size, size))
        s.fill(C["grass"])
        sc = size / MAP_W
        for r in self.roads_v + self.roads_h:
            pygame.draw.rect(s, (56, 57, 62),
                             (int(r.x * sc), int(r.y * sc), max(1, int(r.width * sc)), max(1, int(r.height * sc))))
        for b in self.buildings:
            pygame.draw.rect(s, (120, 114, 106),
                             (int(b.rect.x * sc), int(b.rect.y * sc),
                              max(1, int(b.rect.width * sc)), max(1, int(b.rect.height * sc))))
        for b in self.buildings:
            if b.kind == "shop":
                pygame.draw.rect(s, SHOPS[b.shop_key]["accent"],
                                 (int(b.rect.x * sc), int(b.rect.y * sc),
                                  max(2, int(b.rect.width * sc)), max(2, int(b.rect.height * sc))))
        return s

    # ---------- sorgular ----------
    def blocked(self, rect):
        return rect.collidelist(self.colliders) != -1

    def blocked_point(self, x, y):
        return self.blocked(pygame.Rect(int(x) - 2, int(y) - 2, 4, 4))

    def nearest_shop(self, x, y):
        best, bd = None, 1e9
        for b in self.buildings:
            if b.kind == "shop":
                d = dist(x, y, b.door[0], b.door[1])
                if d < bd:
                    bd, best = d, b
        return best

    def shop_at_door(self, x, y, radius=64):
        for b in self.buildings:
            if b.kind == "shop" and dist(x, y, b.door[0], b.door[1]) < radius:
                return b
        return None

    def road_point_near(self, x, y, min_d=300, max_d=1800):
        for _ in range(40):
            a = random.uniform(0, math.tau)
            d = random.uniform(min_d, max_d)
            px = clamp(x + math.cos(a) * d, 100, MAP_W - 100)
            py = clamp(y + math.sin(a) * d, 100, MAP_H - 100)
            if self.on_road(px, py) and not self.blocked_point(px, py):
                return px, py
        return clamp(x + 300, 100, MAP_W - 100), y

    def on_road(self, x, y):
        for r in self.roads_v:
            if r.left <= x <= r.right and 0 <= y <= MAP_H:
                if any(abs(x - c) < ROAD_W / 2 for c in ROAD_XS):
                    return True
        for c in ROAD_YS:
            if abs(y - c) < ROAD_W / 2:
                return True
        return False

    def sidewalk_point(self, cx, cy):
        for _ in range(30):
            px = random.uniform(60, MAP_W - 60)
            py = random.uniform(60, MAP_H - 60)
            if dist(px, py, cx, cy) < 500:
                continue
            if self.blocked_point(px, py):
                continue
            if not self.on_road(px, py):
                return px, py
        return cx + random.uniform(-300, 300), cy + 200

    # ---------- çizim ----------
    def draw(self, screen, cam):
        vis = cam.visible_rect()
        screen.fill(C["grass"])
        z = cam.zoom

        # çim dokusu
        step = 70
        sx0 = int((cam.x - SCREEN_W / 2 / z) // step * step)
        sy0 = int((cam.y - SCREEN_H / 2 / z) // step * step)
        for gx in range(sx0, sx0 + int(SCREEN_W / z) + step * 2, step):
            for gy in range(sy0, sy0 + int(SCREEN_H / z) + step * 2, step):
                if 0 <= gx < MAP_W and 0 <= gy < MAP_H and not self.on_road(gx, gy):
                    px, py = world_to_screen(gx + 17, gy + 23, cam)
                    pygame.draw.circle(screen, C["grass2"], (int(px), int(py)), 3)

        # bloklar (kaldırım)
        for blk in self.blocks:
            r = pygame.Rect(blk["x"], blk["y"], blk["w"], blk["h"])
            if not vis.colliderect(r):
                continue
            if blk["park"]:
                continue
            x, y = world_to_screen(r.x, r.y, cam)
            pygame.draw.rect(screen, C["walk"], (x, y, r.width * z, r.height * z))
            # kaldırım döşeme çizgileri
            pygame.draw.rect(screen, C["walk_line"], (x, y, r.width * z, r.height * z), 2)

        # yollar
        for r in self.roads_v + self.roads_h:
            if not vis.colliderect(r):
                continue
            x, y = world_to_screen(r.x, r.y, cam)
            pygame.draw.rect(screen, C["road_edge"], (x, y, r.width * z, r.height * z))
            pygame.draw.rect(screen, C["road"], (x + 12, y + 12, (r.width - 24) * z, (r.height - 24) * z))

        # şerit çizgileri
        for r in self.roads_v:
            if not vis.colliderect(r):
                continue
            cx, _ = world_to_screen(r.centerx, r.y, cam)
            y0 = max(r.y, vis.y)
            y1 = min(r.bottom, vis.bottom)
            for y in range(int(y0) // 60 * 60, int(y1) + 60, 60):
                sy = world_to_screen(0, y, cam)[1]
                pygame.draw.rect(screen, C["line"], (cx - 2 * z, sy, 4 * z, 30 * z))
            lx, _ = world_to_screen(r.x + 30, 0, cam)
            rx, _ = world_to_screen(r.right - 30, 0, cam)
            top = world_to_screen(0, r.y + 14, cam)[1]
            pygame.draw.rect(screen, C["line_white"], (lx, top, 2, r.height * z - 28 * z))
            pygame.draw.rect(screen, C["line_white"], (rx, top, 2, r.height * z - 28 * z))
        for r in self.roads_h:
            if not vis.colliderect(r):
                continue
            _, cy = world_to_screen(r.x, r.centery, cam)
            x0 = max(r.x, vis.x)
            x1 = min(r.right, vis.right)
            for x in range(int(x0) // 60 * 60, int(x1) + 60, 60):
                sx = world_to_screen(x, 0, cam)[0]
                pygame.draw.rect(screen, C["line"], (sx, cy - 2 * z, 30 * z, 4 * z))
            ty = world_to_screen(0, r.y + 30, cam)[1]
            by = world_to_screen(0, r.bottom - 30, cam)[1]
            left = world_to_screen(r.x + 14, 0, cam)[0]
            pygame.draw.rect(screen, C["line_white"], (left, ty, r.width * z - 28 * z, 2))
            pygame.draw.rect(screen, C["line_white"], (left, by, r.width * z - 28 * z, 2))

        # kavşak zebra
        for (ix, iy) in self.intersections:
            inter = pygame.Rect(ix - ROAD_W // 2, iy - ROAD_W // 2, ROAD_W, ROAD_W)
            if not vis.colliderect(inter):
                continue
            x, y = world_to_screen(inter.x, inter.y, cam)
            for i in range(7):
                pygame.draw.rect(screen, (235, 235, 235),
                                 (x + (14 + i * 36) * z, y + 8 * z, 18 * z, 34 * z))
                pygame.draw.rect(screen, (235, 235, 235),
                                 (x + (14 + i * 36) * z, y + (ROAD_W - 42) * z, 18 * z, 34 * z))
                pygame.draw.rect(screen, (235, 235, 235),
                                 (x + 8 * z, y + (14 + i * 36) * z, 34 * z, 18 * z))
                pygame.draw.rect(screen, (235, 235, 235),
                                 (x + (ROAD_W - 42) * z, y + (14 + i * 36) * z, 34 * z, 18 * z))

        # dekor (çalı / ağaç)
        for kind, dx, dy in self.decor:
            if not vis.collidepoint(dx, dy):
                continue
            px, py = world_to_screen(dx, dy, cam)
            if kind == "tree":
                pygame.draw.circle(screen, (0, 0, 0), (int(px + 4 * z), int(py + 5 * z)), int(19 * z))
                pygame.draw.circle(screen, (26, 74, 32), (int(px), int(py)), int(19 * z))
                pygame.draw.circle(screen, (38, 104, 44), (int(px - 5 * z), int(py - 5 * z)), int(13 * z))
                pygame.draw.circle(screen, (56, 132, 58), (int(px - 7 * z), int(py - 8 * z)), int(7 * z))
            elif kind == "bin":
                pygame.draw.rect(screen, (0, 0, 0), (int(px - 12 * z + 3), int(py - 8 * z + 3),
                                                     int(24 * z), int(17 * z)), border_radius=3)
                pygame.draw.rect(screen, (46, 96, 62), (int(px - 12 * z), int(py - 8 * z),
                                                        int(24 * z), int(17 * z)), border_radius=3)
                pygame.draw.rect(screen, (66, 122, 82), (int(px - 12 * z), int(py - 8 * z),
                                                         int(24 * z), int(6 * z)), border_radius=2)
                pygame.draw.rect(screen, (26, 60, 38), (int(px - 12 * z), int(py - 8 * z),
                                                        int(24 * z), int(17 * z)), 1, border_radius=3)
            else:
                pygame.draw.circle(screen, (26, 74, 32), (int(px), int(py)), int(9 * z))
                pygame.draw.circle(screen, (40, 104, 44), (int(px - 3 * z), int(py - 2 * z)), int(6 * z))

        # binalar
        for b in self.buildings:
            if not vis.colliderect(b.rect):
                continue
            self._draw_building(screen, cam, b, z)

        # dükkan kapı işaretleri (parlayan halka)
        t = pygame.time.get_ticks() * 0.003
        for b in self.buildings:
            if b.kind != "shop":
                continue
            if not vis.collidepoint(b.door):
                continue
            px, py = world_to_screen(b.door[0], b.door[1], cam)
            acc = SHOPS[b.shop_key]["accent"]
            pulse = 0.6 + 0.4 * math.sin(t * 2)
            glow = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*acc, int(70 * pulse)), (40, 40), 26)
            screen.blit(glow, (px - 40, py - 40))
            pygame.draw.circle(screen, acc, (int(px), int(py)), int(13 * z), 2)
            pygame.draw.circle(screen, (255, 255, 255), (int(px), int(py)), int(4 * z))

    def _draw_building(self, screen, cam, b, z):
        x, y = world_to_screen(b.rect.x, b.rect.y, cam)
        w, h = b.rect.width * z, b.rect.height * z
        base = b.color
        dark = tuple(max(0, int(c * 0.62)) for c in base)
        edge = tuple(min(255, int(c * 1.22)) for c in base)

        # gölge
        sh = pygame.Surface((int(w) + 22, int(h) + 22), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 105), (12, 14, int(w), int(h)), border_radius=9)
        screen.blit(sh, (x - 12, y - 14))

        # çatı gövdesi
        rounded(screen, base, (x, y, w, h), radius=7)
        # parapet (çatı kenarı) — içe doğru koyu şerit
        inset = max(3, int(7 * z))
        rounded(screen, dark, (x + inset, y + inset, w - inset * 2, h - inset * 2), radius=5)
        # iç çatı zemini
        rounded(screen, tuple(min(255, int(c * 0.94)) for c in base),
                (x + inset * 2, y + inset * 2, w - inset * 4, h - inset * 4), radius=4)
        # üst kenar ışığı (güneş)
        pygame.draw.line(screen, edge, (x + 6, y + 3), (x + w - 6, y + 3), 2)
        # çatı dokusu: katran dikişleri + çakıl
        step = max(28, int(46 * z))
        seam = tuple(max(0, int(c * 0.72)) for c in base)
        grit = tuple(min(255, int(c * 1.10)) for c in base)
        yy = y + inset * 2 + step
        while yy < y + h - inset * 2:
            pygame.draw.line(screen, seam, (x + inset * 2, yy), (x + w - inset * 2, yy), 1)
            yy += step
        for i in range(int(max(0, (w * h) / 2600))):
            gx = x + inset * 2 + ((i * 37) % max(1, int(w - inset * 4)))
            gy = y + inset * 2 + ((i * 61) % max(1, int(h - inset * 4)))
            pygame.draw.circle(screen, grit if i % 3 else seam, (int(gx), int(gy)), 1)
        pygame.draw.rect(screen, (14, 14, 18), (x, y, w, h), 2, border_radius=7)

        # çatı detayları
        for (kind, rx, ry, rw, rh) in b.roof:
            px, py = world_to_screen(b.rect.x + rx, b.rect.y + ry, cam)
            pw, ph = rw * z, rh * z
            if pw < 4 or ph < 4:
                continue
            if kind == "ac":
                pygame.draw.rect(screen, (0, 0, 0), (px + 2, py + 3, pw, ph), border_radius=3)
                pygame.draw.rect(screen, (168, 170, 176), (px, py, pw, ph), border_radius=3)
                pygame.draw.rect(screen, (120, 122, 128), (px, py, pw, ph), 1, border_radius=3)
                pygame.draw.circle(screen, (86, 88, 94), (int(px + pw / 2), int(py + ph / 2)),
                                   max(2, int(min(pw, ph) * 0.30)))
                pygame.draw.circle(screen, (56, 58, 64), (int(px + pw / 2), int(py + ph / 2)),
                                   max(1, int(min(pw, ph) * 0.16)))
            elif kind == "vent":
                pygame.draw.rect(screen, (0, 0, 0), (px + 2, py + 2, pw, ph), border_radius=2)
                pygame.draw.rect(screen, (150, 152, 158), (px, py, pw, ph), border_radius=2)
                for i in range(3):
                    yy = py + ph * (0.25 + i * 0.25)
                    pygame.draw.line(screen, (96, 98, 104), (px + 2, yy), (px + pw - 2, yy), 1)
            elif kind == "skylight":
                pygame.draw.rect(screen, (0, 0, 0), (px + 2, py + 3, pw, ph), border_radius=2)
                pygame.draw.rect(screen, (96, 150, 186), (px, py, pw, ph), border_radius=2)
                pygame.draw.rect(screen, (150, 205, 232), (px + 2, py + 2, pw - 4, ph * 0.4), border_radius=1)
                pygame.draw.rect(screen, (48, 62, 74), (px, py, pw, ph), 1, border_radius=2)
            elif kind == "tank":
                cx2, cy2 = px + pw / 2, py + ph / 2
                pygame.draw.circle(screen, (0, 0, 0), (int(cx2 + 2), int(cy2 + 3)), int(pw / 2))
                pygame.draw.circle(screen, (128, 108, 82), (int(cx2), int(cy2)), int(pw / 2))
                pygame.draw.circle(screen, (154, 132, 100), (int(cx2), int(cy2)), int(pw / 2.8))
                pygame.draw.circle(screen, (86, 72, 56), (int(cx2), int(cy2)), int(pw / 2), 1)
            elif kind == "duct":
                pygame.draw.rect(screen, (0, 0, 0), (px + 2, py + 3, pw, ph), border_radius=3)
                pygame.draw.rect(screen, (152, 154, 160), (px, py, pw, ph), border_radius=3)
                pygame.draw.rect(screen, (110, 112, 118), (px, py, pw, ph), 1, border_radius=3)
                nseg = max(2, int(pw / (20 * z)))
                for i in range(1, nseg):
                    lx = px + pw * i / nseg
                    pygame.draw.line(screen, (110, 112, 118), (lx, py + 1), (lx, py + ph - 1), 1)
            else:  # hatch
                pygame.draw.rect(screen, (0, 0, 0), (px + 2, py + 2, pw, ph), border_radius=2)
                pygame.draw.rect(screen, (108, 100, 92), (px, py, pw, ph), border_radius=2)
                pygame.draw.line(screen, (72, 66, 60), (px + 2, py + ph - 2), (px + pw - 2, py + 2), 1)

        # korkuluk köşeleri
        for cx3, cy3 in ((x + inset, y + inset), (x + w - inset, y + inset),
                         (x + inset, y + h - inset), (x + w - inset, y + h - inset)):
            pygame.draw.circle(screen, edge, (int(cx3), int(cy3)), max(2, int(3 * z)))
        # sol/üst kenar gölgesi (hacim hissi)
        shadow_strip = pygame.Surface((int(max(6, 10 * z)), int(h)), pygame.SRCALPHA)
        pygame.draw.rect(shadow_strip, (0, 0, 0, 65), (0, 0, int(max(6, 10 * z)), int(h)))
        screen.blit(shadow_strip, (x + 1, y))

        if b.kind == "shop":
            self._draw_shop_front(screen, cam, b, z)

    def _draw_shop_front(self, screen, cam, b, z):
        """Vitrin: tente şeridi, cam vitrin, kapı ve tabela (kapıyla çakışmaz)."""
        sd = SHOPS[b.shop_key]
        acc = sd["accent"]
        x, y = world_to_screen(b.rect.x, b.rect.y, cam)
        w, h = b.rect.width * z, b.rect.height * z
        side = b.sign_dir
        dx, dy = world_to_screen(b.door[0], b.door[1], cam)
        wall_y = y if side == "top" else y + h          # duvar hattı (ekran)
        inward = 1 if side == "top" else -1

        # tente: duvar boyunca renkli şerit
        band_h = 26 * z
        band_y = wall_y + (4 * z if side == "top" else -band_h - 4 * z)
        pygame.draw.rect(screen, tuple(int(c * 0.35) for c in acc), (x + 4, band_y, w - 8, band_h))
        n_stripe = max(4, int(b.rect.width // 34))
        for i in range(n_stripe):
            sx = x + 4 + i * (w - 8) / n_stripe
            if i % 2 == 0:
                pygame.draw.rect(screen, acc, (sx, band_y, (w - 8) / n_stripe, band_h))
        pygame.draw.rect(screen, (12, 12, 16), (x + 4, band_y, w - 8, band_h), 1)

        # cam vitrin (tentenin iç tarafında)
        gx = x + 12
        gw = w - 24
        gh = 16 * z
        gy = band_y + (band_h + 3 * z) * inward if side == "top" else band_y - gh - 3 * z
        if gh > 3:
            pygame.draw.rect(screen, (150, 200, 226), (gx, gy, gw, gh))
            pygame.draw.rect(screen, (206, 236, 252), (gx, gy, gw, gh * 0.4))
            pygame.draw.rect(screen, (40, 56, 68), (gx, gy, gw, gh), 1)

        # kapı boşluğu
        door_w = 64 * z
        door_h = 30 * z
        ddy = wall_y + (0 if side == "top" else -door_h)
        pygame.draw.rect(screen, (26, 24, 28), (dx - door_w / 2, ddy, door_w, door_h))
        pygame.draw.rect(screen, acc, (dx - door_w / 2, ddy, door_w, door_h), 2)
        pygame.draw.line(screen, (70, 74, 84), (dx, ddy + 2), (dx, ddy + door_h - 2), 1)
        pygame.draw.rect(screen, (240, 240, 200), (dx + door_w / 2 - 8 * z, ddy + door_h * 0.45, 4 * z, 4 * z))

        # Tabela: duvar boyunca, sol tarafa hizalı (kapıyla çakışmaz)
        label = sd["sign"]
        f = font(max(10, int(13 * z)), True)
        tw = f.size(label)[0]
        sw = tw + 18
        sh_ = max(16, int(22 * z))
        sx = x + 12
        if sx + sw > dx - door_w / 2 - 6:
            sx = max(x + 8, dx - door_w / 2 - 6 - sw)
        sy = (band_y + band_h + 4 * z) if side == "top" else (band_y - sh_ - 4 * z)
        pygame.draw.rect(screen, (14, 14, 18), (sx, sy, sw, sh_), border_radius=4)
        pygame.draw.rect(screen, acc, (sx, sy, sw, sh_), 2, border_radius=4)
        img = f.render(label, True, acc)
        screen.blit(img, (sx + 9, sy + (sh_ - img.get_height()) // 2))


# ============================================================
#  PARTİKÜL & MERMİ
# ============================================================
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "grav")

    def __init__(self, x, y, vx, vy, life, color, size, grav=0.1):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.grav = grav

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.grav
        self.vx *= 0.97
        self.vy *= 0.97
        self.life -= 1
        return self.life > 0

    def draw(self, screen, cam):
        p = self.life / self.max_life
        s = max(1, self.size * p)
        px, py = world_to_screen(self.x, self.y, cam)
        surf = pygame.Surface((int(s * 2) + 2, int(s * 2) + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.color, int(230 * p)), (int(s) + 1, int(s) + 1), int(s))
        screen.blit(surf, (px - s, py - s))


class Bullet:
    def __init__(self, x, y, angle, speed=20, damage=25, owner="player"):
        self.x, self.y = x, y
        self.ang = angle
        self.vx = math.cos(math.radians(angle)) * speed
        self.vy = math.sin(math.radians(angle)) * speed
        self.damage = damage
        self.owner = owner
        self.life = 60
        self.trail = []

    def update(self, gmap):
        self.x += self.vx
        self.y += self.vy
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.life -= 1
        if gmap.blocked_point(self.x, self.y):
            return False
        if not (0 < self.x < MAP_W and 0 < self.y < MAP_H):
            return False
        return self.life > 0

    def draw(self, screen, cam):
        for i in range(len(self.trail) - 1):
            a = i / len(self.trail)
            p1 = world_to_screen(*self.trail[i], cam)
            p2 = world_to_screen(*self.trail[i + 1], cam)
            pygame.draw.line(screen, (255, int(200 + 40 * a), int(80 + 120 * a)), p1, p2, 2)
        px, py = world_to_screen(self.x, self.y, cam)
        pygame.draw.circle(screen, (255, 235, 150), (int(px), int(py)), 4)
        pygame.draw.circle(screen, (255, 255, 255), (int(px), int(py)), 2)


# ============================================================
#  ARAÇLAR
# ============================================================
VEHICLE_TYPES = [
    {"name": "Sultan", "color": (196, 34, 44), "color2": (120, 18, 24), "max_speed": 9.6, "accel": 0.20,
     "handling": 3.4, "grip": 0.86, "drag": 0.988, "brake": 0.34, "w": 46, "h": 84},
    {"name": "Adder", "color": (24, 24, 30), "color2": (230, 180, 20), "max_speed": 12.4, "accel": 0.26,
     "handling": 2.9, "grip": 0.90, "drag": 0.992, "brake": 0.40, "w": 46, "h": 92},
    {"name": "Blista", "color": (52, 132, 220), "color2": (240, 240, 245), "max_speed": 8.2, "accel": 0.18,
     "handling": 3.8, "grip": 0.84, "drag": 0.986, "brake": 0.36, "w": 44, "h": 78},
    {"name": "Mesa", "color": (66, 72, 58), "color2": (40, 44, 36), "max_speed": 7.4, "accel": 0.17,
     "handling": 2.6, "grip": 0.88, "drag": 0.984, "brake": 0.30, "w": 50, "h": 88, "suv": True},
    {"name": "Taxi", "color": (252, 206, 12), "color2": (30, 30, 30), "max_speed": 8.6, "accel": 0.19,
     "handling": 3.2, "grip": 0.85, "drag": 0.987, "brake": 0.34, "w": 46, "h": 84, "taxi": True},
    {"name": "Bati", "color": (150, 30, 160), "color2": (60, 20, 80), "max_speed": 11.0, "accel": 0.24,
     "handling": 2.6, "grip": 0.91, "drag": 0.990, "brake": 0.38, "w": 40, "h": 80, "sport": True},
]

POLICE_TYPE = {"name": "Polis", "color": (240, 240, 245), "color2": (20, 30, 70), "max_speed": 10.6,
               "accel": 0.24, "handling": 3.4, "grip": 0.88, "drag": 0.989, "brake": 0.38,
               "w": 46, "h": 86, "police": True}


class Vehicle:
    def __init__(self, x, y, vtype, angle=None):
        self.x, self.y = float(x), float(y)
        self.type = dict(vtype)
        self.w, self.h = vtype["w"], vtype["h"]
        self.angle = random.uniform(0, 360) if angle is None else angle
        self.vx = self.vy = 0.0
        self.health = 100.0
        self.occupied = False
        self.nitro = 0
        self.horn = 0
        self.marks = []
        self.is_mission_car = False
        self.ai = None          # "traffic" / "police" / None
        self.target_angle = self.angle
        self.road_i = self.road_j = 0
        self.dir = (0, 1)

    # --- fizik ---
    def physics(self, gmap, throttle=0.0, steer=0.0, handbrake=False, dt=1.0):
        a = math.radians(self.angle)
        fx, fy = math.cos(a), math.sin(a)
        rx, ry = -math.sin(a), math.cos(a)

        vf = self.vx * fx + self.vy * fy
        vl = self.vx * rx + self.vy * ry

        maxs = self.type["max_speed"] * (1.25 if self.nitro > 0 else 1.0)
        if self.nitro > 0:
            throttle = max(throttle, 1.0)

        if throttle > 0:
            vf += self.type["accel"] * (1.6 if self.nitro > 0 else 1.0) * throttle
        elif throttle < 0:
            if vf > 0.4:
                vf -= self.type["brake"]          # fren
            else:
                vf += self.type["accel"] * 0.55 * throttle   # geri vites
        else:
            vf *= 0.988 if abs(vf) > 0.05 else 0.90

        vf = clamp(vf, -maxs * 0.42, maxs)
        vf *= self.type["drag"]

        # yanal tutuş (grip düşükse kayar)
        grip = self.type["grip"]
        if handbrake:
            grip = min(0.985, grip + 0.13)
            vf *= 0.982
        vl *= grip

        # direksiyon: hıza bağlı
        spd_ratio = clamp(abs(vf) / self.type["max_speed"], 0.0, 1.0)
        turn_rate = self.type["handling"] * (0.30 + 0.70 * min(1.0, spd_ratio * 2.4))
        turn_rate *= (1.0 - 0.30 * spd_ratio)
        if abs(vf) < 0.15:
            turn_rate *= 0.15
        if vf < -0.3:
            turn_rate = -turn_rate
        # el freniyle dönüş artar
        if handbrake:
            turn_rate *= 1.35
        self.angle += steer * turn_rate

        if handbrake and abs(vf) > 3 and random.random() < 0.6:
            self.marks.append((self.x, self.y, self.angle, 26))
        elif abs(vl) > 2.0 and random.random() < 0.25:
            self.marks.append((self.x, self.y, self.angle, 16))

        # yeni yön vektörleri
        a = math.radians(self.angle)
        fx, fy = math.cos(a), math.sin(a)
        rx, ry = -math.sin(a), math.cos(a)
        self.vx = fx * vf + rx * vl
        self.vy = fy * vf + ry * vl

        self._move(gmap)
        if self.nitro > 0:
            self.nitro -= 1
        if self.horn > 0:
            self.horn -= 1

        # lastik izleri ömrü
        if self.marks:
            self.marks = [(mx, my, ma, ml - 1) for (mx, my, ma, ml) in self.marks if ml > 1]

    def _move(self, gmap):
        nx, ny = self.x + self.vx, self.y + self.vy
        box = pygame.Rect(0, 0, self.w - 8, self.h - 8)
        box.center = (nx, ny)
        if not gmap.blocked(box):
            self.x, self.y = nx, ny
        else:
            box.center = (nx, self.y)
            if not gmap.blocked(box):
                self.x = nx
                self.vy *= -0.28
                self._crash()
            else:
                box.center = (self.x, ny)
                if not gmap.blocked(box):
                    self.y = ny
                    self.vx *= -0.28
                    self._crash()
                else:
                    self.vx *= -0.30
                    self.vy *= -0.30
                    self._crash()
        self.x = clamp(self.x, 40, MAP_W - 40)
        self.y = clamp(self.y, 40, MAP_H - 40)

    def _crash(self):
        sp = math.hypot(self.vx, self.vy)
        if sp > 4:
            self.health -= sp * 0.6

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    def forward_speed(self):
        a = math.radians(self.angle)
        return self.vx * math.cos(a) + self.vy * math.sin(a)

    def get_rect(self):
        r = pygame.Rect(0, 0, self.w, self.h)
        r.center = (int(self.x), int(self.y))
        return r

    # --- AI ---
    def update_traffic(self, gmap):
        if not self.ai:
            return
        if self.ai == "police":
            return
        # hedef kavşak
        ti, tj = self.road_i, self.road_j
        tx = ROAD_XS[ti] + self.dir[0] * 0
        ty = ROAD_YS[tj] + self.dir[1] * 0
        # sağ şerit ofseti
        a = math.radians(self.angle)
        right = (-math.sin(a), math.cos(a))
        lane = 62
        px = tx + right[0] * lane * 0.5 + self.dir[0] * 0
        py = ty + right[1] * lane * 0.5 + self.dir[1] * 0
        desired = angle_to(self.x, self.y, px, py)
        diff = norm_angle(desired - self.angle)
        throttle = 1.0 if abs(diff) < 55 else 0.25
        steer = clamp(diff / 28.0, -1.0, 1.0)
        if self.speed > 6.5:
            throttle = 0.2
        self.physics(gmap, throttle, steer, False)
        if dist(self.x, self.y, tx, ty) < 190:
            self._next_road_node()

    def _next_road_node(self):
        di, dj = self.dir
        ni, nj = self.road_i + di, self.road_j + dj
        # sınır veya rastgele dönüş
        if not (0 <= ni < len(ROAD_XS)) or not (0 <= nj < len(ROAD_YS)) or random.random() < 0.30:
            options = []
            for (di2, dj2) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (di2, dj2) == (-di, -dj):
                    continue
                if 0 <= self.road_i + di2 < len(ROAD_XS) and 0 <= self.road_j + dj2 < len(ROAD_YS):
                    options.append((di2, dj2))
            if options:
                self.dir = random.choice(options)
            ni, nj = self.road_i + self.dir[0], self.road_j + self.dir[1]
        self.road_i = clamp(ni, 0, len(ROAD_XS) - 1)
        self.road_j = clamp(nj, 0, len(ROAD_YS) - 1)

    # --- çizim ---
    def draw(self, screen, cam, highlight=False):
        z = cam.zoom
        px, py = world_to_screen(self.x, self.y, cam)

        for (mx, my, ma, ml) in self.marks:
            sx, sy = world_to_screen(mx, my, cam)
            a = int(90 * (ml / 26))
            s = pygame.Surface((14, 14), pygame.SRCALPHA)
            pygame.draw.circle(s, (10, 10, 10, a), (7, 7), 4)
            screen.blit(s, (sx - 7, sy - 7))

        w, h = self.w, self.h
        base, dark = self.type["color"], self.type["color2"]
        spr = pygame.Surface((w + 18, h + 18), pygame.SRCALPHA)
        ox, oy = 9, 9

        # gölge
        pygame.draw.ellipse(spr, (0, 0, 0, 90), (ox - 2, oy + 4, w + 4, h))

        # gövde
        rounded(spr, dark, (ox, oy, w, h), radius=12)
        rounded(spr, base, (ox + 2, oy + 2, w - 4, h - 4), radius=11)
        # kaput/çatı tonu
        rounded(spr, tuple(min(255, c + 18) for c in base), (ox + 4, oy + 6, w - 8, 18), radius=8)
        rounded(spr, tuple(max(0, c - 26) for c in base), (ox + 4, oy + h - 26, w - 8, 20), radius=8)
        # orta hat
        pygame.draw.line(spr, (0, 0, 0, 70), (ox + 6, oy + 26), (ox + w - 6, oy + 26), 1)
        pygame.draw.line(spr, (0, 0, 0, 70), (ox + 6, oy + h - 28), (ox + w - 6, oy + h - 28), 1)

        # ön cam
        rounded(spr, (150, 205, 240), (ox + 6, oy + 20, w - 12, 16), radius=5)
        rounded(spr, (205, 235, 255), (ox + 8, oy + 22, w - 16, 6), radius=3)
        # arka cam
        rounded(spr, (110, 165, 210), (ox + 6, oy + h - 34, w - 12, 13), radius=4)
        # yan camlar
        rounded(spr, (128, 186, 226), (ox + 2, oy + 40, 5, 16), radius=2)
        rounded(spr, (128, 186, 226), (ox + w - 7, oy + 40, 5, 16), radius=2)
        # kapı çizgileri
        pygame.draw.line(spr, (0, 0, 0, 60), (ox + 3, oy + 40), (ox + 3, oy + 58), 1)
        pygame.draw.line(spr, (0, 0, 0, 60), (ox + w - 3, oy + 40), (ox + w - 3, oy + 58), 1)
        # aynalar
        pygame.draw.rect(spr, tuple(max(0, c - 40) for c in base), (ox - 3, oy + 22, 4, 6), border_radius=2)
        pygame.draw.rect(spr, tuple(max(0, c - 40) for c in base), (ox + w - 1, oy + 22, 4, 6), border_radius=2)

        # farlar / stoplar
        pygame.draw.ellipse(spr, (255, 250, 200), (ox + 5, oy + 2, 9, 7))
        pygame.draw.ellipse(spr, (255, 250, 200), (ox + w - 14, oy + 2, 9, 7))
        pygame.draw.rect(spr, (215, 40, 40), (ox + 5, oy + h - 6, 9, 5), border_radius=2)
        pygame.draw.rect(spr, (215, 40, 40), (ox + w - 14, oy + h - 6, 9, 5), border_radius=2)

        # tekerler
        for wx, wy in ((ox - 3, oy + 14), (ox + w - 7, oy + 14), (ox - 3, oy + h - 32), (ox + w - 7, oy + h - 32)):
            pygame.draw.rect(spr, (16, 16, 18), (wx, wy, 10, 18), border_radius=4)
            pygame.draw.rect(spr, (64, 64, 70), (wx + 2, wy + 3, 6, 12), border_radius=3)
            pygame.draw.line(spr, (30, 30, 34), (wx + 2, wy + 9), (wx + 8, wy + 9), 1)

        t = self.type
        if t.get("taxi"):
            pygame.draw.rect(spr, (250, 250, 250), (ox + w // 2 - 13, oy + 6, 26, 9), border_radius=2)
            for i in range(0, w - 12, 7):
                col = (0, 0, 0) if (i // 7) % 2 == 0 else (250, 250, 250)
                pygame.draw.rect(spr, col, (ox + 6 + i, oy + h - 14, 7, 7))
        elif t.get("police"):
            pygame.draw.rect(spr, (20, 26, 60), (ox + 4, oy + 34, w - 8, 14), border_radius=3)
            blink = (pygame.time.get_ticks() // 150) % 2 == 0
            c1 = (255, 40, 40) if blink else (90, 20, 20)
            c2 = (40, 60, 255) if not blink else (20, 24, 90)
            rounded(spr, (24, 24, 28), (ox + w // 2 - 15, oy + h // 2 - 19, 30, 8), radius=3)
            pygame.draw.circle(spr, c1, (ox + w // 2 - 7, oy + h // 2 - 15), 4)
            pygame.draw.circle(spr, c2, (ox + w // 2 + 7, oy + h // 2 - 15), 4)
            if blink:
                glow = pygame.Surface((44, 26), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 60, 60, 70), (10, 12), 10)
                spr.blit(glow, (ox + w // 2 - 22, oy + h // 2 - 28))
        elif t.get("sport"):
            pygame.draw.rect(spr, dark, (ox + w // 2 - 14, oy + h - 12, 28, 6), border_radius=2)
            pygame.draw.rect(spr, (200, 200, 210), (ox + 6, oy + 44, w - 12, 2))
        else:
            pygame.draw.rect(spr, (255, 255, 255, 60), (ox + w // 2 - 1, oy + 8, 2, h - 20), border_radius=1)

        rot = pygame.transform.rotate(spr, -self.angle - 90)
        screen.blit(rot, rot.get_rect(center=(int(px), int(py))))

        if highlight:
            pygame.draw.circle(screen, C["gold"], (int(px), int(py)), int(40 * z), 2)

        if self.horn > 0:
            text(screen, "BEEP!", px + 26, py - 34, 12, True, (255, 255, 255))
        # hasar dumanı
        if self.health < 45:
            if random.random() < 0.35:
                pygame.draw.circle(screen, (90, 90, 95), (int(px + random.randint(-8, 8)), int(py - 6)), 6)


# ============================================================
#  YAYA
# ============================================================
class Pedestrian:
    def __init__(self, x, y, gmap):
        self.x, self.y = float(x), float(y)
        self.gmap = gmap
        self.angle = random.uniform(0, 360)
        self.state = "walk"           # walk / flee / dead
        self.health = 40
        self.speed = random.uniform(0.9, 1.7)
        self.step = random.random() * 6
        self.timer = random.randint(60, 200)
        self.panic = 0
        self.skin = random.choice([(232, 190, 140), (208, 152, 118), (150, 104, 74), (110, 74, 52), (242, 214, 184)])
        self.shirt = random.choice([(200, 44, 48), (48, 112, 210), (48, 152, 74), (238, 190, 42),
                                    (84, 84, 90), (124, 62, 164), (232, 232, 236), (30, 32, 40)])
        self.pants = random.choice([(32, 42, 82), (44, 44, 48), (88, 58, 36), (24, 24, 28), (60, 64, 74)])
        self.hair = random.choice([(30, 25, 22), (18, 16, 14), (92, 62, 34), (140, 110, 60), (200, 200, 205)])
        self.has_bag = random.random() < 0.3
        self.target_ped = False

    def take_damage(self, dmg, dx=0, dy=0):
        self.health -= dmg
        if self.health <= 0:
            self.state = "dead"
            return True
        self.state = "flee"
        self.panic = 260
        self.speed = random.uniform(2.6, 3.6)
        self.angle = angle_to(0, 0, -dx, -dy) + random.uniform(-25, 25) if (dx or dy) else random.uniform(0, 360)
        return False

    def update(self, player, bullets, gmap):
        if self.state == "dead":
            return
        moving = False
        self.step += 0.25
        for b in bullets:
            if dist(self.x, self.y, b.x, b.y) < 70:
                self.state = "flee"
                self.panic = max(self.panic, 120)
                self.angle = angle_to(b.x, b.y, self.x, self.y) + random.uniform(-20, 20)
                self.speed = max(self.speed, 2.8)

        if self.state == "flee":
            self.panic -= 1
            spd = self.speed
            if dist(self.x, self.y, player.x, player.y) < 260:
                away = angle_to(player.x, player.y, self.x, self.y)
                self.angle = lerp(self.angle, away, 0.12)
            nx = self.x + math.cos(math.radians(self.angle)) * spd
            ny = self.y + math.sin(math.radians(self.angle)) * spd
            if gmap.blocked(pygame.Rect(nx - 9, ny - 9, 18, 18)):
                self.angle += random.choice([55, -55, 100, -100])
            else:
                self.x, self.y = nx, ny
                moving = True
            self.angle += random.uniform(-4, 4)
            if self.panic <= 0:
                self.state = "walk"
                self.speed = random.uniform(0.9, 1.7)
        else:
            self.timer -= 1
            if self.timer <= 0 or random.random() < 0.01:
                self.angle += random.uniform(-80, 80)
                self.timer = random.randint(80, 240)
                self.speed = random.uniform(0.9, 1.7)
            nx = self.x + math.cos(math.radians(self.angle)) * self.speed
            ny = self.y + math.sin(math.radians(self.angle)) * self.speed
            if gmap.blocked(pygame.Rect(nx - 9, ny - 9, 18, 18)) or not (30 < nx < MAP_W - 30 and 30 < ny < MAP_H - 30):
                self.angle += random.choice([60, -60, 130, -130])
            else:
                self.x, self.y = nx, ny
                moving = True

        self.x = clamp(self.x, 24, MAP_W - 24)
        self.y = clamp(self.y, 24, MAP_H - 24)

    def draw(self, screen, cam):
        px, py = world_to_screen(self.x, self.y, cam)
        if not (-80 < px < SCREEN_W + 80 and -80 < py < SCREEN_H + 80):
            return
        if self.state == "dead":
            pygame.draw.ellipse(screen, (120, 16, 16), (px - 20, py - 8, 40, 22))
            pygame.draw.ellipse(screen, (60, 8, 8), (px - 14, py - 5, 26, 15))
            pygame.draw.circle(screen, self.skin, (int(px + 12), int(py + 2)), 7)
            pygame.draw.circle(screen, self.shirt, (int(px - 6), int(py + 1)), 8)
            return
        pygame.draw.ellipse(screen, (0, 0, 0, 60), (px - 12, py + 9, 24, 10))
        draw_person(screen, px, py, self.angle, self.skin, self.shirt, self.pants, self.hair,
                    step=self.step, moving=self.state != "dead")
        if self.has_bag:
            pygame.draw.rect(screen, (58, 40, 26), (px + 8, py - 2, 7, 9), border_radius=2)
        if self.state == "flee":
            pygame.draw.circle(screen, (255, 216, 0), (int(px + 13), int(py - 24)), 8)
            text(screen, "!", px + 13, py - 31, 12, True, (0, 0, 0), center=True, shadow=False)
        if self.target_ped:
            bob = math.sin(pygame.time.get_ticks() * 0.006) * 3
            pygame.draw.polygon(screen, C["red"], [(px, py - 40 + bob), (px - 8, py - 54 + bob), (px + 8, py - 54 + bob)])
            pygame.draw.polygon(screen, (255, 255, 255), [(px, py - 40 + bob), (px - 8, py - 54 + bob), (px + 8, py - 54 + bob)], 1)


# ============================================================
#  POLİS
# ============================================================
class PoliceUnit:
    def __init__(self, x, y, is_car=True):
        self.is_car = is_car
        if is_car:
            self.vehicle = Vehicle(x, y, POLICE_TYPE,
                                   angle=random.uniform(0, 360))
            self.vehicle.ai = "police"
            self.vehicle.health = 140
            self.x, self.y = x, y
        else:
            self.vehicle = None
            self.x, self.y = x, y
            self.angle = random.uniform(0, 360)
            self.health = 60
            self.step = random.random() * 6
        self.shoot_cd = random.randint(30, 70)
        self.target_offset = (random.uniform(-40, 40), random.uniform(-40, 40))

    def update(self, player, gmap, bullets):
        px, py = player.x, player.y
        d = dist(self.x, self.y, px, py)
        if self.is_car:
            v = self.vehicle
            tx, ty = px + self.target_offset[0], py + self.target_offset[1]
            desired = angle_to(v.x, v.y, tx, ty)
            diff = norm_angle(desired - v.angle)
            steer = clamp(diff / 26.0, -1.0, 1.0)
            throttle = 1.0 if abs(diff) < 70 else 0.35
            if d < 120:
                throttle = -1.0 if abs(diff) < 55 else 0.35
            elif d < 300:
                throttle = 0.75
            v.physics(gmap, throttle, steer, False)
            self.x, self.y = v.x, v.y
            if d < 60:
                if player.in_vehicle:
                    ang = angle_to(v.x, v.y, px, py)
                    v.vx += math.cos(math.radians(ang)) * 1.6
                    v.vy += math.sin(math.radians(ang)) * 1.6
                    if random.random() < 0.06:
                        player.take_damage(5)
                else:
                    player.take_damage(0.9)
            self.shoot_cd -= 1
            if self.shoot_cd <= 0 and d < 560 and random.random() < 0.5:
                a = angle_to(v.x, v.y, px, py) + random.uniform(-4, 4)
                bullets.append(Bullet(v.x + math.cos(math.radians(a)) * 34,
                                      v.y + math.sin(math.radians(a)) * 34,
                                      a, 17, 10, "police"))
                self.shoot_cd = random.randint(26, 52)
        else:
            self.step += 0.24
            self.angle = angle_to(self.x, self.y, px, py)
            spd = 2.4 if d > 60 else 1.2
            nx = self.x + math.cos(math.radians(self.angle)) * spd
            ny = self.y + math.sin(math.radians(self.angle)) * spd
            if not gmap.blocked(pygame.Rect(nx - 8, ny - 8, 16, 16)):
                self.x, self.y = nx, ny
            else:
                self.angle += 45
            if d < 26 and not player.in_vehicle:
                player.take_damage(0.8)
            self.shoot_cd -= 1
            if self.shoot_cd <= 0 and d < 480:
                a = angle_to(self.x, self.y, px, py) + random.uniform(-3, 3)
                bullets.append(Bullet(self.x + math.cos(math.radians(a)) * 16,
                                      self.y + math.sin(math.radians(a)) * 16,
                                      a, 17, 12, "police"))
                self.shoot_cd = random.randint(30, 58)

    def draw(self, screen, cam):
        if self.is_car:
            self.vehicle.draw(screen, cam)
        else:
            px, py = world_to_screen(self.x, self.y, cam)
            pygame.draw.ellipse(screen, (0, 0, 0, 60), (px - 12, py + 9, 24, 10))
            draw_person(screen, px, py, self.angle, (232, 190, 140), (26, 44, 120), (20, 26, 60),
                        (16, 18, 40), step=self.step, moving=True, weapon="Pistol")
            pygame.draw.circle(screen, C["gold"], (px, py - 2), 3)


# ============================================================
#  OYUNCU
# ============================================================
class Player:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.angle = -90
        self.speed = 4.4
        self.health = 100
        self.max_health = 100
        self.armor = 25
        self.money = 2500
        self.ammo = 120
        self.mag = 12
        self.mag_max = 12
        self.weapon = "Pistol"
        self.shoot_cd = 0
        self.reload_t = 0
        self.is_aiming = False
        self.in_vehicle = None
        self.wanted = 0
        self.wanted_timer = 0
        self.step = 0.0
        self.moving = False
        self.invul = 0
        self.skin = C["skin"]
        self.shirt = (32, 44, 78)
        self.pants = (42, 48, 66)
        self.hair = (34, 26, 20)
        self.tattoo = 0
        self.stamina = 100

    def get_rect(self):
        r = pygame.Rect(0, 0, 22, 22)
        r.center = (int(self.x), int(self.y))
        return r

    def update(self, keys, mouse_pos, cam, gmap):
        if self.shoot_cd > 0:
            self.shoot_cd -= 1
        if self.invul > 0:
            self.invul -= 1
        if self.reload_t > 0:
            self.reload_t -= 1
            if self.reload_t == 0:
                need = self.mag_max - self.mag
                take = min(need, self.ammo)
                self.mag += take
                self.ammo -= take

        if self.in_vehicle:
            self.x, self.y = self.in_vehicle.x, self.in_vehicle.y
            self.is_aiming = pygame.mouse.get_pressed()[2]
            return

        mx, my = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            my -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            my += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            mx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            mx += 1

        self.is_aiming = pygame.mouse.get_pressed()[2]
        self.moving = (mx != 0 or my != 0)
        if self.moving:
            l = math.hypot(mx, my)
            mx, my = mx / l, my / l
            self.step += 0.30
            spd = self.speed * (0.58 if self.is_aiming else 1.0)
            nx, ny = self.x + mx * spd, self.y + my * spd
            box = pygame.Rect(0, 0, 20, 20)
            box.center = (nx, ny)
            if not gmap.blocked(box):
                self.x, self.y = nx, ny
            else:
                box.center = (nx, self.y)
                if not gmap.blocked(box):
                    self.x = nx
                box.center = (self.x, ny)
                if not gmap.blocked(box):
                    self.y = ny
        else:
            self.step += 0.05

        self.x = clamp(self.x, 24, MAP_W - 24)
        self.y = clamp(self.y, 24, MAP_H - 24)

        wmx = (mouse_pos[0] - SCREEN_W / 2) / cam.zoom + cam.x
        wmy = (mouse_pos[1] - SCREEN_H / 2) / cam.zoom + cam.y
        self.angle = math.degrees(math.atan2(wmy - self.y, wmx - self.x))

        if self.wanted > 0:
            self.wanted_timer += 1
            if self.wanted_timer > 900 and random.random() < 0.01:
                self.wanted = max(0, self.wanted - 1)
                self.wanted_timer = 300

    def try_shoot(self):
        if self.reload_t > 0 or self.shoot_cd > 0:
            return None
        if self.mag <= 0:
            if self.ammo > 0:
                self.reload_t = 45
            return None
        spread = 1.0 if self.is_aiming else 3.4
        ang = self.angle + random.uniform(-spread, spread)
        if self.weapon == "Pistol":
            speed, dmg, cd = 20, 26, 11
        else:
            speed, dmg, cd = 23, 19, 5
            spread = spread + 1.2
            ang = self.angle + random.uniform(-spread, spread)
        self.shoot_cd = cd
        self.mag -= 1
        muzzle = 26
        return Bullet(self.x + math.cos(math.radians(ang)) * muzzle,
                      self.y + math.sin(math.radians(ang)) * muzzle,
                      ang, speed, dmg, "player")

    def reload(self):
        if self.reload_t == 0 and self.mag < self.mag_max and self.ammo > 0:
            self.reload_t = 45

    def take_damage(self, dmg):
        if self.invul > 0:
            return
        if self.armor > 0:
            absorb = min(self.armor, dmg * 0.7)
            self.armor -= absorb
            dmg -= absorb
        self.health = max(0, self.health - dmg)
        self.invul = 12

    def add_wanted(self, n):
        self.wanted = clamp(self.wanted + n, 0, 5)
        self.wanted_timer = 0

    def draw(self, screen, cam):
        if self.in_vehicle:
            return
        px, py = world_to_screen(self.x, self.y, cam)
        pygame.draw.ellipse(screen, (0, 0, 0, 80), (px - 14, py + 10, 28, 12))
        if self.invul > 0 and (self.invul // 3) % 2 == 0:
            return
        draw_person(screen, px, py, self.angle, self.skin, self.shirt, self.pants, self.hair,
                    step=self.step, moving=self.moving, weapon=self.weapon,
                    aiming=self.is_aiming, scale=1.16)
        if self.tattoo:
            pygame.draw.circle(screen, (40, 30, 60), (int(px), int(py + 2)), 3)
        # sağlık barı
        if self.health < self.max_health:
            w = 40
            pygame.draw.rect(screen, (0, 0, 0), (px - w / 2 - 1, py - 34, w + 2, 6), border_radius=3)
            pct = self.health / self.max_health
            col = C["green"] if pct > 0.5 else (C["gold"] if pct > 0.25 else C["red"])
            pygame.draw.rect(screen, col, (px - w / 2, py - 33, w * pct, 4), border_radius=2)


# ============================================================
#  TELEFON (iFruit)
# ============================================================
class Phone:
    W, H = 400, 560

    def __init__(self, player):
        self.player = player
        self.open = False
        self.anim = 0.0
        self.selected = 0
        self.dialog = ""
        self.dialog_timer = 0
        self.dialog_name = ""
        self.contacts = [
            {"name": "Franklin", "role": "İş Veren", "initials": "F",
             "desc": "Görev al, para kazan", "action": "mission", "col": (60, 160, 90)},
            {"name": "Lester Crest", "role": "Kirli İşler", "initials": "L",
             "desc": "Wanted temizle ($500)", "action": "lester", "col": (120, 90, 190)},
            {"name": "Michael De Santa", "role": "Aile Babası", "initials": "M",
             "desc": "Para + sağlık", "action": "michael", "col": (200, 150, 40)},
            {"name": "Downtown Cab", "role": "Taksi", "initials": "T",
             "desc": "Taksi çağır ($80)", "action": "taxi", "col": (230, 190, 20)},
            {"name": "Rüşvet Polisi", "role": "Yolsuz Memur", "initials": "P",
             "desc": "1 yıldız sil ($800)", "action": "bribe", "col": (50, 70, 160)},
            {"name": "Ammu-Nation", "role": "Silah Dükkanı", "initials": "A",
             "desc": "En yakın şubeyi bul", "action": "find_ammo", "col": (180, 50, 40)},
            {"name": "Mors Mutual", "role": "Sigorta", "initials": "M",
             "desc": "Araç getir", "action": "car", "col": (60, 130, 200)},
            {"name": "Los Santos Doktor", "role": "Sağlık", "initials": "D",
             "desc": "Canı fulle ($250)", "action": "heal", "col": (200, 60, 80)},
        ]

    # --- girdi ---
    def open_phone(self):
        self.open = True

    def close_phone(self):
        self.open = False

    def move_selection(self, d):
        self.selected = (self.selected + d) % len(self.contacts)

    def click(self, pos):
        r = self.rect()
        idx = (pos[1] - (r.y + 132)) // 52
        if 0 <= idx < len(self.contacts) and r.collidepoint(pos):
            self.selected = int(idx)
            return True
        return False

    def rect(self):
        y = SCREEN_H - self.H - 18 + int((1 - self.anim) * 120)
        return pygame.Rect(SCREEN_W - self.W - 20, y, self.W, self.H)

    # --- arama ---
    def call_selected(self, game):
        c = self.contacts[self.selected]
        p = self.player
        self.dialog_name = c["name"]
        act = c["action"]
        msg = ""
        if act == "mission":
            msg = game.missions.start_random()
        elif act == "lester":
            if p.money >= 500:
                p.money -= 500
                p.wanted = 0
                msg = "Lester: Kameralara girdim, kayıtları sildim. Temizsin. Bir dahakine $1000."
            else:
                msg = "Lester: $500 yoksa iş yok evlat."
        elif act == "michael":
            if p.money >= 200:
                p.money -= 200
                p.health = min(p.max_health, p.health + 40)
                msg = "Michael: Bu $200'ü al, kendine bir şey ısmarla. Kanepemde uyumak yasak ama."
            else:
                msg = "Michael: Johnny, biraz para lazım... bende de yok gerçi."
        elif act == "taxi":
            if p.money >= 80:
                p.money -= 80
                game.spawn_taxi()
                msg = "Downtown Cab: Taksi yola çıktı, sarı aracı ara. $80 çekildi."
            else:
                msg = "Downtown Cab: $80 yoksa yürürsün dostum."
        elif act == "bribe":
            if p.wanted <= 0:
                msg = "Memur: Temizsin zaten, rüşvete gerek yok."
            elif p.money >= 800:
                p.money -= 800
                p.wanted = max(0, p.wanted - 1)
                msg = "Memur: Bir yıldız düştü. Görüşmeyi unut."
            else:
                msg = "Memur: $800 olmadan rozet yok."
        elif act == "find_ammo":
            b = None
            for bd in game.map.buildings:
                if bd.kind == "shop" and bd.shop_key == "ammunation":
                    if b is None or dist(p.x, p.y, bd.door[0], bd.door[1]) < dist(p.x, p.y, b.door[0], b.door[1]):
                        b = bd
            if b:
                game.set_waypoint(b.door[0], b.door[1], "Ammu-Nation")
                msg = f"Ammu-Nation: En yakın şube {int(dist(p.x, p.y, b.door[0], b.door[1]))}m ileride, haritada işaretledim."
            else:
                msg = "Ammu-Nation: Şube bulunamadı."
        elif act == "car":
            game.spawn_vehicle_near(random.choice(VEHICLE_TYPES))
            msg = "Mors Mutual: Aracınız konumunuza bırakıldı. İyi günler."
        elif act == "heal":
            if p.money >= 250:
                p.money -= 250
                p.health = p.max_health
                msg = "Doktor: Dikişler atıldı, tam sağlıksın. $250."
            else:
                msg = "Doktor: Önce ödeme, $250."
        self.dialog = msg
        self.dialog_timer = 420
        game.toast("📞 " + c["name"], c["col"])

    def notify(self, name, msg):
        self.dialog_name = name
        self.dialog = msg
        self.dialog_timer = 400

    def update(self):
        target = 1.0 if self.open else 0.0
        self.anim = lerp(self.anim, target, 0.22)
        if self.dialog_timer > 0:
            self.dialog_timer -= 1

    # --- çizim ---
    def draw(self, screen):
        if self.anim < 0.02:
            self._draw_dialog(screen)
            return
        r = self.rect()
        x, y = r.x, r.y
        W, H = self.W, self.H

        # gölge
        sh = pygame.Surface((W + 24, H + 24), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 120), (8, 8, W + 8, H + 8), border_radius=26)
        screen.blit(sh, (x - 8, y - 8))

        P = pygame.Surface((W, H), pygame.SRCALPHA)
        # kasa
        rounded(P, (22, 23, 28), (0, 0, W, H), radius=24)
        pygame.draw.rect(P, (86, 90, 100), (0, 0, W, H), 2, border_radius=24)

        # durum çubuğu
        rounded(P, (10, 11, 14), (0, 0, W, 34), radius=24)
        pygame.draw.rect(P, (10, 11, 14), (0, 20, W, 16))
        text(P, datetime.datetime.now().strftime("%H:%M"), 16, 9, 12, True, (235, 235, 240), shadow=False)
        text(P, "5G  ▮▮▮", W - 74, 9, 12, True, (235, 235, 240), shadow=False)
        pygame.draw.circle(P, (40, 42, 50), (W // 2, 20), 3)

        # başlık
        rounded(P, (26, 30, 44), (0, 34, W, 74), radius=0)
        text(P, "iFruit", 18, 44, 20, True, (255, 255, 255), shadow=False)
        text(P, "Los Santos  •  Rehber", 18, 70, 11, False, (150, 170, 200), shadow=False)
        money = self.player.money
        text(P, f"${money:,}".replace(",", "."), W - 18 - font(14, True).size(f"${money:,}".replace(",", "."))[0],
             48, 14, True, C["green"], shadow=False)
        want = "★" * self.player.wanted + "☆" * (5 - self.player.wanted)
        text(P, want, W - 18 - font(13).size(want)[0], 74, 13, False, C["gold"], shadow=False)

        # liste
        rounded(P, (244, 245, 248), (10, 114, W - 20, H - 178), radius=14)
        vis = 7
        start = clamp(self.selected - 3, 0, max(0, len(self.contacts) - vis))
        for i in range(vis):
            idx = start + i
            if idx >= len(self.contacts):
                break
            c = self.contacts[idx]
            sel = idx == self.selected
            ry = 124 + i * 52
            if sel:
                rounded(P, (28, 34, 52), (18, ry, W - 36, 46), radius=10)
            else:
                rounded(P, (255, 255, 255), (18, ry, W - 36, 46), radius=10)
                pygame.draw.rect(P, (226, 228, 234), (18, ry, W - 36, 46), 1, border_radius=10)
            pygame.draw.circle(P, c["col"], (44, ry + 23), 16)
            text(P, c["initials"], 44, ry + 15, 15, True, (255, 255, 255), center=True, shadow=False)
            text(P, c["name"], 68, ry + 6, 13, True, (255, 255, 255) if sel else (24, 26, 32), shadow=False)
            text(P, c["desc"], 68, ry + 25, 10, False, (170, 190, 215) if sel else (120, 124, 132), shadow=False)
            if sel:
                pygame.draw.circle(P, C["green"], (W - 44, ry + 23), 9)
                text(P, "►", W - 44, ry + 15, 11, True, (0, 0, 0), center=True, shadow=False)

        # alt butonlar
        rounded(P, (18, 20, 26), (10, H - 56, W - 20, 46), radius=12)
        text(P, "↑ ↓  Seç      ENTER  Ara      T  Kapat", W // 2, H - 42, 11, True,
             (200, 205, 215), center=True, shadow=False)

        # animasyon alpha
        if self.anim < 0.99:
            P.set_alpha(int(255 * self.anim))
        screen.blit(P, (x, y))
        self._draw_dialog(screen)

    def _draw_dialog(self, screen):
        if self.dialog_timer <= 0 or not self.dialog:
            return
        fade = min(1.0, self.dialog_timer / 40.0)
        w, h = 660, 92
        x, y = SCREEN_W // 2 - w // 2, 78
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(box, (16, 18, 24, 242), (0, 0, w, h), border_radius=14)
        pygame.draw.rect(box, (0, 200, 255, 200), (0, 0, w, h), 2, border_radius=14)
        pygame.draw.circle(box, (0, 140, 190), (40, 40), 22)
        text(box, self.dialog_name[:1].upper(), 40, 28, 20, True, (255, 255, 255), center=True, shadow=False)
        text(box, self.dialog_name, 74, 12, 15, True, (0, 220, 255), shadow=False)
        lines = wrap_text(self.dialog, 12, w - 100)
        for i, line in enumerate(lines[:3]):
            text(box, line, 74, 34 + i * 17, 12, False, (235, 238, 244), shadow=False)
        box.set_alpha(int(255 * fade))
        screen.blit(box, (x, y))


# ============================================================
#  DÜKKAN İÇİ (INTERIOR)
# ============================================================
class Interior:
    def __init__(self, key, defn, game):
        self.key = key
        self.d = defn
        self.game = game
        self.room = pygame.Rect(SCREEN_W // 2 - 460, 132, 920, 470)
        self.px = self.room.centerx
        self.py = self.room.bottom - 60
        self.angle = -90
        self.step = 0.0
        self.msg = ""
        self.msg_t = 0
        self.flash = 0
        self.near = -1
        self.items = []
        n = len(defn["items"])
        for i, it in enumerate(defn["items"]):
            if n == 1:
                sx = self.room.centerx
            else:
                sx = self.room.x + 170 + i * (self.room.width - 340) / (n - 1)
            self.items.append({"def": it, "x": sx, "y": self.room.y + 150})
        self.door = pygame.Rect(self.room.centerx - 60, self.room.bottom - 26, 120, 30)
        self.t = 0

    def update(self, keys, mouse):
        self.t += 1
        mx = (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0) - \
             (1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0)
        my = (1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0) - \
             (1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0)
        if mx or my:
            l = math.hypot(mx, my)
            self.step += 0.3
            self.px = clamp(self.px + mx / l * 4.0, self.room.x + 30, self.room.right - 30)
            self.py = clamp(self.py + my / l * 4.0, self.room.y + 110, self.room.bottom - 20)
        else:
            self.step += 0.05
        self.angle = math.degrees(math.atan2(mouse[1] - self.py, mouse[0] - self.px))

        self.near = -1
        for i, it in enumerate(self.items):
            if dist(self.px, self.py, it["x"], it["y"] + 60) < 85:
                self.near = i
                break
        if self.msg_t > 0:
            self.msg_t -= 1
        if self.flash > 0:
            self.flash -= 1

    def buy(self):
        if self.near < 0:
            self.msg = "Bir ürüne yaklaş (E)"
            self.msg_t = 120
            return
        item = self.items[self.near]["def"]
        p = self.game.player
        if p.money < item["price"]:
            self.msg = f"Paran yetmiyor: ${item['price']} gerekli"
            self.msg_t = 160
            return
        p.money -= item["price"]
        msg = self.game.apply_effect(item["effect"], item.get("value", 0), self.key)
        self.msg = msg
        self.msg_t = 200
        self.flash = 12

    def can_exit(self):
        return (self.door.collidepoint(self.px, self.py + 8) or
                dist(self.px, self.py, self.door.centerx, self.door.centery) < 70)

    # --- çizim ---
    def draw(self, screen):
        d = self.d
        # arka plan
        screen.fill((8, 9, 12))
        for i in range(0, SCREEN_H, 4):
            pass
        # zemin
        r = self.room
        pygame.draw.rect(screen, d["floor"], r)
        tile = 46
        for ty in range(r.y, r.bottom, tile):
            for tx in range(r.x, r.right, tile):
                if ((tx - r.x) // tile + (ty - r.y) // tile) % 2 == 0:
                    pygame.draw.rect(screen, d["floor2"], (tx, ty, min(tile, r.right - tx), min(tile, r.bottom - ty)))
        # duvarlar
        pygame.draw.rect(screen, d["wall"], (r.x - 22, r.y - 22, r.width + 44, 26))
        pygame.draw.rect(screen, d["wall"], (r.x - 22, r.y - 22, 26, r.height + 44))
        pygame.draw.rect(screen, d["wall"], (r.right - 4, r.y - 22, 26, r.height + 44))
        pygame.draw.rect(screen, d["wall"], (r.x - 22, r.bottom - 4, r.width + 44, 26))
        pygame.draw.rect(screen, d["accent"], (r.x - 22, r.y - 22, r.width + 44, 5))
        pygame.draw.rect(screen, (0, 0, 0), (r.x - 22, r.y - 22, r.width + 44, r.height + 44), 3)

        # dekor / raflar
        self._draw_props(screen)

        # ürün noktaları
        for i, it in enumerate(self.items):
            self._draw_item(screen, i, it)

        # çıkış kapısı
        pygame.draw.rect(screen, (18, 20, 24), self.door)
        pygame.draw.rect(screen, d["accent"], self.door, 2)
        text(screen, "ÇIKIŞ [Q]", self.door.centerx, self.door.y + 8, 12, True, (255, 255, 255),
             center=True, shadow=False)

        # oyuncu
        p = self.game.player
        draw_person(screen, self.px, self.py, self.angle, p.skin, p.shirt, p.pants, p.hair,
                    step=self.step, moving=True, weapon=None)

        # tezgah + arkasında görevli
        cx = r.right - 190
        cy = r.y + 118
        draw_person(screen, cx, cy - 46, 90, (216, 176, 132), (40, 60, 110), (30, 34, 48), (26, 20, 16))
        pygame.draw.rect(screen, (150, 120, 90), (cx - 120, cy, 240, 48), border_radius=8)
        pygame.draw.rect(screen, (176, 144, 108), (cx - 120, cy, 240, 12), border_radius=5)
        pygame.draw.rect(screen, (110, 88, 66), (cx - 120, cy + 40, 240, 8), border_radius=4)
        pygame.draw.rect(screen, (30, 30, 34), (cx - 40, cy + 14, 80, 22), border_radius=4)
        pygame.draw.rect(screen, (90, 200, 140), (cx - 30, cy + 20, 60, 10), border_radius=2)
        text(screen, "Görevli", cx, cy + 56, 11, False, (230, 230, 235), center=True)

        # üst bar
        pygame.draw.rect(screen, (14, 15, 20), (0, 0, SCREEN_W, 96))
        pygame.draw.rect(screen, d["accent"], (0, 94, SCREEN_W, 3))
        text(screen, d["name"].upper(), 30, 22, 26, True, (255, 255, 255))
        text(screen, "Dükkan içi  •  WASD yürü  •  E satın al  •  Q çık", 30, 58, 13, False, (180, 186, 198))
        text(screen, f"${p.money:,}".replace(",", "."), SCREEN_W - 30 - font(22, True).size(
            f"${p.money:,}".replace(",", "."))[0], 26, 22, True, C["green"])
        text(screen, f"CAN {int(p.health)}   ZIRH {int(p.armor)}", SCREEN_W - 30 - font(13, True).size(
            f"CAN {int(p.health)}   ZIRH {int(p.armor)}")[0], 60, 13, True, (200, 210, 226))

        # satın alma ipucu
        if self.near >= 0:
            it = self.items[self.near]["def"]
            bw, bh = 460, 54
            bx, by = SCREEN_W // 2 - bw // 2, SCREEN_H - 96
            panel(screen, (bx, by, bw, bh), (16, 18, 24), d["accent"], 12)
            text(screen, f"[E]  {it['name']}  —  ${it['price']}", bx + 20, by + 8, 15, True, (255, 255, 255))
            text(screen, it["desc"], bx + 20, by + 30, 12, False, (175, 182, 196))
        else:
            text(screen, "Ürünlerin yanına git", SCREEN_W // 2, SCREEN_H - 80, 13, False,
                 (150, 156, 168), center=True)

        if self.msg_t > 0:
            lines = wrap_text(self.msg, 13, 640)
            bh = 30 + len(lines) * 18
            bx, by = SCREEN_W // 2 - 330, SCREEN_H - 170
            panel(screen, (bx, by, 660, bh), (18, 20, 26), d["accent"], 12)
            for i, ln in enumerate(lines[:2]):
                text(screen, ln, bx + 16, by + 10 + i * 18, 13, False, (240, 242, 248))

        if self.flash > 0:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((*d["accent"], int(40 * self.flash / 12)))
            screen.blit(ov, (0, 0))

    def _draw_props(self, screen):
        d, r = self.d, self.room
        prop = d["prop"]
        acc = d["accent"]
        if prop == "shelf":
            shelf_w = r.width - 420
            for row in range(2):
                y = r.y + 130 + row * 120
                pygame.draw.rect(screen, (150, 148, 140), (r.x + 40, y + 60, shelf_w, 18), border_radius=4)
                for i in range(int((shelf_w - 20) / 34)):
                    x = r.x + 56 + i * 34
                    col = random.Random(i * 7 + row).choice([(220, 70, 60), (60, 160, 90), (240, 200, 60),
                                                             (70, 130, 210), (230, 130, 40)])
                    pygame.draw.rect(screen, col, (x, y + 32, 22, 30), border_radius=3)
                    pygame.draw.rect(screen, (255, 255, 255), (x + 3, y + 38, 16, 6), border_radius=2)
        elif prop == "guns":
            for i in range(6):
                x = r.x + 60 + i * 46
                pygame.draw.rect(screen, (120, 110, 96), (x, r.y + 150, 12, 40), border_radius=3)
                pygame.draw.rect(screen, (40, 40, 44), (x - 4, r.y + 180, 20, 8), border_radius=2)
            pygame.draw.rect(screen, (140, 40, 36), (r.x + 60, r.y + 210, r.width - 120, 16), border_radius=4)
        elif prop == "pc":
            for i in range(4):
                x = r.x + 90 + i * 190
                pygame.draw.rect(screen, (18, 20, 28), (x, r.y + 150, 120, 8), border_radius=3)
                glow = pygame.Surface((120, 74), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*acc, 90), (0, 0, 120, 74), border_radius=4)
                screen.blit(glow, (x, r.y + 74))
                pygame.draw.rect(screen, (10, 12, 18), (x, r.y + 74, 120, 74), 2, border_radius=4)
                for k in range(4):
                    pygame.draw.rect(screen, (*acc, 255), (x + 10, r.y + 86 + k * 14, 100 - k * 15, 5), border_radius=2)
                pygame.draw.rect(screen, (30, 32, 40), (x + 40, r.y + 158, 40, 16), border_radius=3)
                pygame.draw.rect(screen, (60, 62, 72), (x + 10, r.y + 196, 100, 14), border_radius=3)
        elif prop == "clothes":
            for i, col in enumerate([(220, 70, 60), (60, 160, 90), (240, 200, 60), (70, 130, 210), (200, 120, 220)]):
                x = r.x + 90 + i * 150
                pygame.draw.rect(screen, (60, 60, 66), (x, r.y + 130, 6, 90))
                pygame.draw.polygon(screen, col, [(x - 24, r.y + 140), (x + 30, r.y + 140),
                                                  (x + 34, r.y + 200), (x - 28, r.y + 200)])
                pygame.draw.polygon(screen, (0, 0, 0, 80), [(x - 24, r.y + 140), (x + 30, r.y + 140),
                                                            (x + 34, r.y + 200), (x - 28, r.y + 200)], 1)
        elif prop == "gym":
            for i in range(3):
                x = r.x + 110 + i * 210
                pygame.draw.rect(screen, (40, 42, 50), (x, r.y + 140, 140, 16), border_radius=6)
                pygame.draw.circle(screen, (24, 24, 28), (x + 14, r.y + 178), 22)
                pygame.draw.circle(screen, (24, 24, 28), (x + 126, r.y + 178), 22)
                pygame.draw.rect(screen, (70, 72, 80), (x + 30, r.y + 172, 80, 12), border_radius=4)
            pygame.draw.rect(screen, acc, (r.x + 40, r.y + 250, r.width - 80, 8), border_radius=4)
        elif prop == "garage":
            pygame.draw.rect(screen, (52, 52, 58), (r.x + 120, r.y + 130, 320, 170), border_radius=10)
            pygame.draw.rect(screen, acc, (r.x + 120, r.y + 130, 320, 170), 3, border_radius=10)
            pygame.draw.line(screen, (90, 90, 96), (r.x + 280, r.y + 130), (r.x + 280, r.y + 300), 2)
            for i in range(8):
                pygame.draw.rect(screen, (30, 30, 34), (r.x + 140, r.y + 150 + i * 18, 260, 6))
        elif prop == "fastfood":
            pygame.draw.rect(screen, (200, 190, 170), (r.x + 200, r.y + 160, 520, 60), border_radius=8)
            for i in range(5):
                pygame.draw.rect(screen, (220, 60, 40), (r.x + 240 + i * 100, r.y + 120, 60, 36), border_radius=4)
                pygame.draw.circle(screen, (250, 220, 120), (r.x + 270 + i * 100, r.y + 138), 12)
            pygame.draw.rect(screen, (150, 110, 70), (r.x + 180, r.y + 220, 560, 12), border_radius=6)
        else:  # barber
            for i in range(2):
                x = r.x + 210 + i * 300
                pygame.draw.rect(screen, (40, 42, 50), (x - 26, r.y + 160, 60, 20), border_radius=6)
                pygame.draw.rect(screen, (40, 42, 50), (x - 30, r.y + 178, 68, 46), border_radius=8)
                pygame.draw.rect(screen, (200, 200, 210), (x - 30, r.y + 178, 68, 8), border_radius=4)
                pygame.draw.circle(screen, (200, 210, 230), (x + 4, r.y + 120), 26)
                pygame.draw.circle(screen, (160, 170, 200), (x + 4, r.y + 120), 26, 2)
                pygame.draw.rect(screen, (120, 120, 130), (x + 26, r.y + 140, 6, 26))
            pygame.draw.rect(screen, acc, (r.x + 40, r.y + 300, r.width - 80, 14), border_radius=6)

    def _draw_item(self, screen, i, it):
        d = self.d
        x, y = it["x"], it["y"]
        hover = (i == self.near)
        pulse = 0.6 + 0.4 * math.sin(self.t * 0.08 + i)
        glow = pygame.Surface((110, 110), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*d["accent"], int((90 if hover else 45) * pulse)), (55, 55), 44)
        screen.blit(glow, (x - 55, y + 60 - 55))
        pygame.draw.circle(screen, d["accent"], (x, y + 60), 30, 2)
        # ürün ikonu (basit vektörel)
        pygame.draw.rect(screen, (245, 245, 250), (x - 12, y + 48, 24, 24), border_radius=5)
        pygame.draw.rect(screen, d["accent"], (x - 12, y + 48, 24, 24), 2, border_radius=5)
        pygame.draw.circle(screen, d["accent"], (x, y + 60), 6)
        # isim + fiyat
        name = it["def"]["name"]
        price = f"${it['def']['price']}"
        wname = font(12, True).size(name)[0]
        rounded(screen, (14, 15, 20), (x - wname / 2 - 8, y + 100, wname + 16, 20), radius=6)
        text(screen, name, x, y + 103, 12, True, (255, 255, 255), center=True, shadow=False)
        wp = font(13, True).size(price)[0]
        rounded(screen, C["green"] if not hover else C["gold"], (x - wp / 2 - 8, y + 122, wp + 16, 22), radius=6)
        text(screen, price, x, y + 125, 13, True, (10, 14, 10), center=True, shadow=False)


# ============================================================
#  GÖREV SİSTEMİ
# ============================================================
class MissionManager:
    KINDS = ["courier", "hit", "boost", "escape"]

    def __init__(self, game):
        self.game = game
        self.active = None
        self.done = 0
        self.cooldown = 0

    def start_random(self):
        if self.active:
            return f"Franklin: Zaten '{self.active['title']}' görevindesin. Bitir önce."
        kind = random.choice(self.KINDS)
        return self.start(kind)

    def start(self, kind):
        g = self.game
        p = g.player
        if kind == "courier":
            a = g.map.road_point_near(p.x, p.y, 900, 2000)
            b = g.map.road_point_near(a[0], a[1], 900, 2200)
            self.active = {"kind": "courier", "title": "Kurye", "stage": 0,
                           "pos": a, "drop": b, "timer": 60 * 60, "reward": 700,
                           "hint": "Paketi al, müşteriye ulaştır"}
            g.set_waypoint(a[0], a[1], "Paket")
            return f"Franklin: Kuryelik işi. Paketi al, müşteriye 90 saniyede yetiştir. Ödül $700."
        if kind == "hit":
            tx, ty = g.map.sidewalk_point(p.x, p.y)
            ped = Pedestrian(tx, ty, g.map)
            ped.target_ped = True
            ped.health = 130
            ped.shirt = (150, 40, 60)
            hx, hy = p.x + random.uniform(-60, 60), p.y + 140
            ped.x, ped.y = clamp(hx, 60, MAP_W - 60), clamp(hy, 60, MAP_H - 60)
            g.peds.append(ped)
            self.active = {"kind": "hit", "title": "Suikast", "stage": 0, "ped": ped,
                           "pos": (ped.x, ped.y), "timer": 75 * 60, "reward": 1200,
                           "hint": "Hedefi (kırmızı ok) indir"}
            g.set_waypoint(ped.x, ped.y, "Hedef")
            return "Franklin: Bir muhbir konuşuyor. Kırmızı oklu adamı hallet, $1200 senin. Polis umurumda değil."
        if kind == "boost":
            bx, by = g.map.road_point_near(p.x, p.y, 700, 1500)
            vt = random.choice(VEHICLE_TYPES)
            v = Vehicle(bx, by, vt)
            v.angle = random.uniform(0, 360)
            v.is_mission_car = True
            g.vehicles.append(v)
            drop = g.map.road_point_near(bx, by, 1200, 2600)
            self.active = {"kind": "boost", "title": "Araç Kaçırma", "stage": 0,
                           "veh": v, "pos": (bx, by), "drop": drop, "timer": 100 * 60,
                           "reward": 1500, "hint": f"{vt['name']} çal ve teslim et"}
            g.set_waypoint(bx, by, "Araç")
            return f"Franklin: {vt['name']} lazım. Sarı işaretli aracı çal, teslim noktasına götür. $1500."
        # escape
        p.add_wanted(3)
        self.active = {"kind": "escape", "title": "Kaçış", "stage": 0,
                       "timer": 60 * 60, "reward": 1000, "hint": "60 saniye polisten kaç"}
        g.set_waypoint(p.x, p.y, "Kaçış")
        return "Franklin: Polise yakalandın mı? 60 saniye dayan, sonra kaybol. $1000 hazır."

    def update(self):
        a = self.active
        if not a:
            return
        g, p = self.game, self.game.player
        a["timer"] -= 1
        if a["timer"] <= 0:
            g.toast("Görev başarısız: süre doldu", C["red"])
            self.fail()
            return

        if a["kind"] == "courier":
            if a["stage"] == 0 and dist(p.x, p.y, *a["pos"]) < 70:
                a["stage"] = 1
                g.toast("Paket alındı! Teslim noktasına git", C["green"])
                g.set_waypoint(a["drop"][0], a["drop"][1], "Teslim")
            elif a["stage"] == 1 and dist(p.x, p.y, *a["drop"]) < 80:
                self.complete()

        elif a["kind"] == "hit":
            ped = a["ped"]
            if ped.state == "dead":
                self.complete()
            else:
                a["pos"] = (ped.x, ped.y)
                g.waypoint = (ped.x, ped.y, "Hedef")
                if random.random() < 0.02:
                    ped.state = "flee"
                    ped.panic = 200
                    ped.speed = 3.2

        elif a["kind"] == "boost":
            v = a["veh"]
            if p.in_vehicle is v:
                g.toast("Araç çalındı! Teslim noktasına sür", C["green"])
                g.set_waypoint(a["drop"][0], a["drop"][1], "Teslim")
                a["stage"] = 1
            if a["stage"] == 1:
                a["pos"] = (v.x, v.y)
                if dist(v.x, v.y, *a["drop"]) < 110:
                    self.complete()

        elif a["kind"] == "escape":
            a["pos"] = (p.x, p.y)
            if p.wanted == 0:
                self.complete()

    def complete(self):
        a = self.active
        if not a:
            return
        g, p = self.game, self.game.player
        bonus = int(a["reward"] * (0.5 * a["timer"] / (90 * 60)))
        total = a["reward"] + max(0, bonus)
        p.money += total
        p.wanted = max(0, p.wanted - 1)
        self.done += 1
        g.toast(f"GÖREV TAMAM! +${total:,}".replace(",", "."), C["gold"])
        g.phone.notify("Görev", f"Tebrikler! {a['title']} tamamlandı. ${total} hesabına geçti.")
        self.active = None
        g.waypoint = None
        g.mission_marker = None

    def fail(self):
        self.active = None
        self.game.waypoint = None
        self.game.phone.notify("Görev", "İş yattı. Franklin seni arayacak (aramayacak).")

    def draw_marker(self, screen, cam):
        a = self.active
        if not a:
            return
        pos = a.get("pos")
        if not pos:
            return
        px, py = world_to_screen(pos[0], pos[1], cam)
        t = pygame.time.get_ticks() * 0.004
        for k in range(3):
            r = 22 + k * 9 + (t * 8 % 12)
            al = max(0, 140 - k * 40)
            s = pygame.Surface((int(r * 2) + 6, int(r * 2) + 6), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 210, 40, al), (int(r) + 3, int(r) + 3), int(r), 3)
            screen.blit(s, (px - r - 3, py - r - 3))
        pygame.draw.polygon(screen, C["gold"], [(px, py - 18), (px - 11, py + 4), (px + 11, py + 4)])


# ============================================================
#  HUD
# ============================================================
class HUD:
    def __init__(self):
        self.flash = 0

    def draw(self, screen, player, cam, gmap, game):
        # ---- üst bar ----
        bar = pygame.Surface((SCREEN_W, 74), pygame.SRCALPHA)
        pygame.draw.rect(bar, (12, 13, 17, 205), (0, 0, SCREEN_W, 74))
        pygame.draw.line(bar, (255, 255, 255, 26), (0, 73), (SCREEN_W, 73))
        screen.blit(bar, (0, 0))

        # can
        self._bar(screen, 20, 16, 230, 16, player.health / player.max_health, C["green"], "CAN", int(player.health))
        # zırh
        self._bar(screen, 20, 40, 230, 12, player.armor / 100, C["blue"], "", int(player.armor))

        # para
        m = f"${player.money:,}".replace(",", ".")
        text(screen, m, SCREEN_W - 24 - font(22, True).size(m)[0], 14, 22, True, C["green"])
        text(screen, "LOS SANTOS", SCREEN_W - 24 - font(11, True).size("LOS SANTOS")[0], 44, 11, True, (150, 155, 165))

        # silah
        wn = 150
        wx = SCREEN_W // 2 - wn // 2
        panel(screen, (wx, 12, wn, 50), (14, 16, 22), (80, 86, 100), 10, 200)
        text(screen, player.weapon.upper(), SCREEN_W // 2, 16, 13, True, (255, 255, 255), center=True)
        am = f"{player.mag} / {player.ammo}"
        text(screen, am, SCREEN_W // 2, 34, 15, True, C["gold"] if player.mag else C["red"], center=True)
        if player.reload_t > 0:
            pygame.draw.rect(screen, (50, 52, 60), (wx + 16, 52, wn - 32, 4), border_radius=2)
            pygame.draw.rect(screen, C["gold"], (wx + 16, 52, (wn - 32) * (1 - player.reload_t / 45), 4), border_radius=2)
        text(screen, f"[R] {gmap is None and '' or ''}şarjör", SCREEN_W // 2, 56, 9, False, (150, 155, 165), center=True)

        # wanted yıldızları
        for i in range(5):
            cx = SCREEN_W // 2 - 250 + i * 29
            cy = 22
            if i < player.wanted:
                t = pygame.time.get_ticks() * 0.006
                glow = pygame.Surface((44, 44), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 60, 40, int(45 + 35 * math.sin(t + i))), (22, 22), 16)
                screen.blit(glow, (cx - 22, cy - 22))
                pygame.draw.polygon(screen, C["gold"], star_points(cx, cy, 11, 4.6))
                pygame.draw.polygon(screen, (140, 100, 0), star_points(cx, cy, 11, 4.6), 1)
            else:
                pygame.draw.polygon(screen, (52, 54, 60), star_points(cx, cy, 9.5, 4))
                pygame.draw.polygon(screen, (78, 80, 88), star_points(cx, cy, 9.5, 4), 1)

        # ---- minimap ----
        self._minimap(screen, player, gmap, game)

        # ---- görev paneli ----
        m = game.missions.active
        if m:
            pw, ph = 330, 96
            px, py = 20, 90
            panel(screen, (px, py, pw, ph), (16, 18, 24), C["gold"], 12, 215)
            text(screen, "GÖREV: " + m["title"].upper(), px + 14, py + 10, 13, True, C["gold"])
            for i, ln in enumerate(wrap_text(m["hint"], 12, pw - 28)[:2]):
                text(screen, ln, px + 14, py + 32 + i * 16, 12, False, (226, 230, 238))
            secs = max(0, m["timer"] // 60)
            frac = clamp(m["timer"] / (90 * 60), 0, 1)
            pygame.draw.rect(screen, (44, 46, 54), (px + 14, py + 70, pw - 28, 8), border_radius=4)
            pygame.draw.rect(screen, C["red"] if secs < 15 else C["green"],
                             (px + 14, py + 70, (pw - 28) * frac, 8), border_radius=4)
            text(screen, f"{secs}s", px + pw - 14, py + 54, 12, True, (255, 255, 255))

        # ---- waypoint oku ----
        if game.waypoint and game.waypoint[0] is not None:
            self._waypoint_arrow(screen, player, cam, game.waypoint)

        # ---- etkileşim ipucu ----
        hint = game.interaction_hint()
        if hint:
            bw = font(14, True).size(hint)[0] + 46
            bx, by = SCREEN_W // 2 - bw // 2, SCREEN_H - 208
            panel(screen, (bx, by, bw, 38), (16, 18, 24), C["green"], 10, 225)
            pygame.draw.circle(screen, C["green"], (bx + 20, by + 19), 12)
            text(screen, "E", bx + 20, by + 11, 13, True, (10, 20, 10), center=True, shadow=False)
            text(screen, hint, bx + 38, by + 11, 14, True, (255, 255, 255))

        # ---- bildirimler ----
        for i, (msg, col, life, maxlife) in enumerate(game.toasts):
            a = clamp(life / 30, 0, 1)
            w = font(13, True).size(msg)[0] + 34
            y = 152 + i * 34
            s = pygame.Surface((w, 28), pygame.SRCALPHA)
            pygame.draw.rect(s, (14, 16, 22, int(230 * a)), (0, 0, w, 28), border_radius=8)
            pygame.draw.rect(s, (*col, int(255 * a)), (0, 0, w, 28), 1, border_radius=8)
            s.blit(font(13, True).render(msg, True, (*col, int(255 * a))), (16, 7))
            screen.blit(s, (SCREEN_W - w - 24, y))

        # ---- alt bilgi ----
        text(screen, "WASD  •  Mouse nişan  •  Sol tık ateş  •  E etkileşim  •  T telefon  •  R şarjör  •  F1 yardım",
             SCREEN_W // 2, SCREEN_H - 20, 11, False, (170, 176, 188), center=True)

        # ---- crosshair ----
        if not player.in_vehicle and game.state == "play":
            mx, my = pygame.mouse.get_pos()
            spread = 9 if player.is_aiming else 15
            col = C["red"] if player.is_aiming else (255, 255, 255)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pygame.draw.line(screen, col, (mx + dx * spread, my + dy * spread),
                                 (mx + dx * (spread + 8), my + dy * (spread + 8)), 2)
            pygame.draw.circle(screen, col, (mx, my), 2)
            if player.is_aiming:
                pygame.draw.circle(screen, (255, 255, 255), (mx, my), spread + 10, 1)

        # ---- vignette ----
        if player.health < 40:
            v = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            a = int(40 + 25 * math.sin(pygame.time.get_ticks() * 0.006))
            for i in range(22):
                pygame.draw.rect(v, (200, 30, 30, max(0, a - i * 2)),
                                 (i * 5, i * 4, SCREEN_W - i * 10, SCREEN_H - i * 8), 2)
            screen.blit(v, (0, 0))

    @staticmethod
    def _bar(screen, x, y, w, h, pct, col, label, val):
        pygame.draw.rect(screen, (26, 28, 34), (x, y, w, h), border_radius=h // 2)
        pct = clamp(pct, 0, 1)
        if pct > 0:
            pygame.draw.rect(screen, col, (x + 1, y + 1, max(2, (w - 2) * pct), h - 2), border_radius=(h - 2) // 2)
        pygame.draw.rect(screen, (70, 74, 84), (x, y, w, h), 1, border_radius=h // 2)
        text(screen, label, x + 8, y + (h - 11) // 2, 10, True, (255, 255, 255))
        text(screen, str(val), x + w - 8 - font(10, True).size(str(val))[0], y + (h - 11) // 2, 10, True, (255, 255, 255))

    def _minimap(self, screen, player, gmap, game):
        size = 200
        x, y = 20, SCREEN_H - size - 34
        panel(screen, (x - 6, y - 6, size + 12, size + 12), (10, 11, 14), (90, 96, 110), 12, 235)
        mini = pygame.transform.smoothscale(gmap.mini, (size, size))
        screen.blit(mini, (x, y))
        sc = size / MAP_W

        # dükkanlar
        for b in gmap.buildings:
            if b.kind == "shop":
                pygame.draw.circle(screen, SHOPS[b.shop_key]["accent"],
                                   (int(x + b.door[0] * sc), int(y + b.door[1] * sc)), 3)
        # polis
        for pol in game.police:
            pygame.draw.circle(screen, (90, 140, 255), (int(x + pol.x * sc), int(y + pol.y * sc)), 2)
        # waypoint
        if game.waypoint and game.waypoint[0] is not None:
            wx, wy = int(x + game.waypoint[0] * sc), int(y + game.waypoint[1] * sc)
            pygame.draw.circle(screen, C["gold"], (wx, wy), 5)
            pygame.draw.circle(screen, (0, 0, 0), (wx, wy), 5, 1)
        # oyuncu
        px, py = int(x + player.x * sc), int(y + player.y * sc)
        pygame.draw.circle(screen, (0, 0, 0), (px, py), 6)
        pygame.draw.circle(screen, C["green"], (px, py), 4)
        # kamera
        cr = pygame.Rect(x + int((game.camera.x - SCREEN_W / 2 / game.camera.zoom) * sc),
                         y + int((game.camera.y - SCREEN_H / 2 / game.camera.zoom) * sc),
                         int(SCREEN_W / game.camera.zoom * sc), int(SCREEN_H / game.camera.zoom * sc))
        pygame.draw.rect(screen, (255, 255, 255), cr.clip(pygame.Rect(x, y, size, size)), 1)
        pygame.draw.rect(screen, (90, 96, 110), (x, y, size, size), 1)
        text(screen, "LOS SANTOS", x + 6, y + 6, 10, True, (255, 255, 255))
        text(screen, "N", x + size - 14, y + size - 18, 11, True, (255, 255, 255))

    def _waypoint_arrow(self, screen, player, cam, wp):
        wx, wy = wp[0], wp[1]
        px, py = world_to_screen(wx, wy, cam)
        if 40 < px < SCREEN_W - 40 and 40 < py < SCREEN_H - 40:
            return
        ang = math.atan2(wy - player.y, wx - player.x)
        cx, cy = SCREEN_W / 2, SCREEN_H / 2
        rx, ry = SCREEN_W / 2 - 70, SCREEN_H / 2 - 70
        ax, ay = cx + math.cos(ang) * rx, cy + math.sin(ang) * ry
        size = 16
        pts = [(ax + math.cos(ang) * size, ay + math.sin(ang) * size),
               (ax + math.cos(ang + 2.5) * size, ay + math.sin(ang + 2.5) * size),
               (ax + math.cos(ang - 2.5) * size, ay + math.sin(ang - 2.5) * size)]
        pygame.draw.polygon(screen, C["gold"], pts)
        pygame.draw.polygon(screen, (0, 0, 0), pts, 2)
        d = int(dist(player.x, player.y, wx, wy) / 10)
        text(screen, f"{d}m", ax, ay + 20, 12, True, C["gold"], center=True)


# ============================================================
#  OYUN
# ============================================================
class Game:
    STATE_PLAY = "play"
    STATE_PHONE = "phone"
    STATE_SHOP = "shop"

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("GTA 5 Top-Down — T: Telefon • E: Etkileşim • WASD")
        self.clock = pygame.time.Clock()
        self.state = self.STATE_PLAY

        self.map = GameMap()
        self.camera = Camera()
        self.player = Player(ROAD_XS[3], ROAD_YS[3] + 120)
        self.phone = Phone(self.player)
        self.hud = HUD()
        self.missions = MissionManager(self)
        self.toasts = []
        self.waypoint = None
        self.interior = None
        self.parked_car = None
        self.show_help = False

        self.bullets = []
        self.particles = []
        self.police = []
        self.vehicles = []
        self.peds = []
        self.time_scale = 1.0

        self._populate()

    # ---------- dünya ----------
    def _populate(self):
        for _ in range(26):
            ix = random.choice(ROAD_XS)
            iy = random.choice(ROAD_YS)
            x = ix + random.uniform(-60, 60)
            y = iy + random.choice([-1, 1]) * random.uniform(120, 420)
            v = Vehicle(x, y, random.choice(VEHICLE_TYPES))
            v.angle = random.choice([90, -90, 0, 180])
            v.ai = "traffic"
            v.road_i = ROAD_XS.index(ix)
            v.road_j = ROAD_YS.index(iy)
            v.dir = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
            self.vehicles.append(v)
        for _ in range(55):
            x, y = self.map.sidewalk_point(self.player.x, self.player.y)
            self.peds.append(Pedestrian(x, y, self.map))
        # oyuncunun yanında 2 araç garanti
        for i, vt in enumerate(random.sample(VEHICLE_TYPES, 2)):
            v = Vehicle(self.player.x + 90 + i * 90, self.player.y + 60, vt)
            v.angle = 0
            self.vehicles.append(v)
        self.spawn_taxi  # noqa

    def _shop_car(self):
        v = getattr(self, "parked_car", None)
        if v is not None and v in self.vehicles:
            return v
        return None

    def toast(self, msg, col=(255, 255, 255)):
        self.toasts.insert(0, [msg, col, 200, 200])
        self.toasts = self.toasts[:4]

    def set_waypoint(self, x, y, label=""):
        if x is None or y is None:
            return
        self.waypoint = (x, y, label)

    def spawn_taxi(self):
        vt = [v for v in VEHICLE_TYPES if v.get("taxi")][0]
        self.spawn_vehicle_near(vt)

    def spawn_vehicle_near(self, vt):
        a = random.uniform(0, math.tau)
        x = clamp(self.player.x + math.cos(a) * 220, 120, MAP_W - 120)
        y = clamp(self.player.y + math.sin(a) * 220, 120, MAP_H - 120)
        v = Vehicle(x, y, vt, angle=angle_to(x, y, self.player.x, self.player.y))
        self.vehicles.append(v)
        self.spawn_particles(v.x, v.y, 12, (255, 255, 255))
        return v

    def spawn_particles(self, x, y, n, color=(255, 200, 60), spread=5):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.8, spread)
            self.particles.append(Particle(x, y, math.cos(a) * s, math.sin(a) * s,
                                           random.randint(12, 26), color, random.randint(2, 4)))

    def spawn_police(self):
        a = random.uniform(0, math.tau)
        d = random.uniform(600, 900)
        x = clamp(self.player.x + math.cos(a) * d, 80, MAP_W - 80)
        y = clamp(self.player.y + math.sin(a) * d, 80, MAP_H - 80)
        car = sum(1 for p in self.police if p.is_car)
        self.police.append(PoliceUnit(x, y, is_car=(car < 2 or random.random() < 0.7)))

    # ---------- alışveriş efektleri ----------
    def apply_effect(self, effect, value, shop_key):
        p = self.player
        if effect == "health":
            before = p.health
            p.health = min(p.max_health, p.health + value)
            return f"+{int(p.health - before)} can. Afiyet olsun!"
        if effect == "healmax":
            p.health = p.max_health
            return "Canın fullendi."
        if effect == "maxhealth":
            p.max_health += value
            p.health = min(p.max_health, p.health + value)
            return f"Maksimum canın +{value} arttı ({p.max_health})."
        if effect == "armor":
            p.armor = min(100, p.armor + value)
            return f"Zırh +{value} ({int(p.armor)}/100)."
        if effect == "ammo":
            p.ammo += value
            return f"+{value} mermi. Toplam {p.ammo}."
        if effect == "rifle":
            p.weapon = "Rifle"
            p.mag_max = 30
            p.mag = 30
            p.ammo += 60
            return "Rifle alındı! Otomatik atış, +60 mermi."
        if effect == "hair":
            p.hair = random.choice([(20, 16, 14), (92, 62, 34), (200, 190, 180), (140, 40, 30), (40, 90, 160)])
            return "Yeni saç modeli! Aynaya bak."
        if effect == "shirt":
            p.shirt = random.choice([(200, 50, 60), (40, 110, 200), (40, 150, 90), (240, 200, 60),
                                     (30, 30, 36), (150, 70, 180), (230, 230, 235)])
            return "Kombinin değişti. Şık!"
        if effect == "tattoo":
            p.tattoo = 1
            return "Dövme yapıldı. Acıdı mı?"
        if effect == "gamble":
            win = random.choice([0, 0, 150, 300, 450, 800, 1500]) if value == 0 else random.choice(
                [0, 500, 900, 1800, 3000])
            p.money += win
            if win == 0:
                return "Kaybettin... Klavye suçlu."
            return f"ESPOR turnuvası kazandın! +${win}"
        if effect == "repair":
            v = p.in_vehicle or self._shop_car()
            if v:
                v.health = 100
                return "Aracın tamir edildi."
            for vv in self.vehicles:
                if dist(vv.x, vv.y, p.x, p.y) < 400:
                    vv.health = 100
                    return "Yakındaki araç tamir edildi."
            return "Yakında araç yok, kapıda bekle."
        if effect == "nitro":
            v = p.in_vehicle or self._shop_car()
            if v:
                v.nitro = 60 * 6
                return "Nitro takıldı! Gaza bas, uçacaksın."
            for vv in self.vehicles:
                if dist(vv.x, vv.y, p.x, p.y) < 420:
                    vv.nitro = 60 * 6
                    return "Yakındaki araca nitro takıldı."
            return "Nitro için araçta olmalısın."
        if effect == "paint":
            v = p.in_vehicle or self._shop_car()
            if v:
                v.type["color"] = tuple(random.randint(30, 240) for _ in range(3))
                return "Araç boyandı!"
            for vv in self.vehicles:
                if dist(vv.x, vv.y, p.x, p.y) < 400:
                    vv.type["color"] = tuple(random.randint(30, 240) for _ in range(3))
                    return "Yakındaki araç boyandı!"
            return "Yakında araç yok."
        return "İşlem tamam."

    # ---------- etkileşim ----------
    def interaction_hint(self):
        if self.state != self.STATE_PLAY:
            return ""
        p = self.player
        shop = self.map.shop_at_door(p.x, p.y)
        if shop and (p.in_vehicle is None or p.in_vehicle.speed < 2.5):
            return SHOPS[shop.shop_key]["name"] + " — gir"
        if p.in_vehicle:
            return "İn"
        for v in self.vehicles:
            if dist(p.x, p.y, v.x, v.y) < 70:
                return v.type["name"] + " — bin"
        for (mx, my) in self.map.mission_spots:
            if dist(p.x, p.y, mx, my) < 80:
                return "Görev al"
        return ""

    def interact(self):
        p = self.player
        # dükkan kapısındaysa (duruyorsa araçla da olur) içeri gir
        shop = self.map.shop_at_door(p.x, p.y)
        if shop and (p.in_vehicle is None or p.in_vehicle.speed < 2.5):
            self.enter_shop(shop)
            return
        if p.in_vehicle:
            self.exit_vehicle()
            return
        best = None
        bd = 70
        for v in self.vehicles:
            d = dist(p.x, p.y, v.x, v.y)
            if d < bd:
                bd, best = d, v
        if best:
            self.enter_vehicle(best)
            return
        for (mx, my) in self.map.mission_spots:
            if dist(p.x, p.y, mx, my) < 80:
                msg = self.missions.start_random()
                self.phone.notify("Franklin", msg)
                self.toast("Görev alındı!", C["gold"])
                return

    def enter_vehicle(self, v):
        p = self.player
        p.in_vehicle = v
        v.occupied = True
        v.ai = None
        p.armor = max(p.armor, 0)
        if random.random() < 0.8:
            p.add_wanted(1)
            if p.wanted >= 2 and len(self.police) < 3:
                self.spawn_police()
        self.toast(f"{v.type['name']} — W gaz, S fren, A/D direksiyon", (150, 220, 255))

    def exit_vehicle(self):
        p = self.player
        v = p.in_vehicle
        a = math.radians(v.angle)
        for side in (1, -1):
            nx = v.x - math.sin(a) * 46 * side
            ny = v.y + math.cos(a) * 46 * side
            if not self.map.blocked(pygame.Rect(int(nx) - 10, int(ny) - 10, 20, 20)):
                p.x, p.y = nx, ny
                break
        else:
            p.x, p.y = v.x, v.y + 50
        v.occupied = False
        p.in_vehicle = None
        p.invul = 20

    def enter_shop(self, b):
        p = self.player
        if p.in_vehicle:
            # araçta giriyorsa aracı kapının önünde bırak
            v = p.in_vehicle
            v.occupied = False
            v.ai = None
            self.parked_car = v
            p.in_vehicle = None
        self.interior = Interior(b.shop_key, SHOPS[b.shop_key], self)
        self.state = self.STATE_SHOP

    def exit_shop(self):
        if not self.interior:
            return
        b = None
        for bb in self.map.buildings:
            if bb.kind == "shop" and bb.shop_key == self.interior.key:
                if bb.door and dist(self.player.x, self.player.y, bb.door[0], bb.door[1]) < 140:
                    b = bb
                    break
        # oyuncuyu kapının dışına koy
        best, bd = None, 1e9
        for bb in self.map.buildings:
            if bb.kind != "shop":
                continue
            d = dist(self.player.x, self.player.y, bb.door[0], bb.door[1])
            if d < bd:
                bd, best = d, bb
        if best and bd < 400:
            self.player.x, self.player.y = best.door[0], best.door[1]
        self.state = self.STATE_PLAY
        self.interior = None

    # ---------- olaylar ----------
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit()
            elif e.type == pygame.KEYDOWN:
                if self.state == self.STATE_PLAY:
                    self.key_play(e)
                elif self.state == self.STATE_PHONE:
                    self.key_phone(e)
                elif self.state == self.STATE_SHOP:
                    self.key_shop(e)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if self.state == self.STATE_PLAY and e.button == 1:
                    self.player_shoot()
                elif self.state == self.STATE_PHONE and e.button == 1:
                    if self.phone.click(e.pos):
                        self.phone.call_selected(self)

    def key_play(self, e):
        k = e.key
        if k == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
            else:
                self.quit()
        elif k in (pygame.K_t, pygame.K_p):
            self.phone.open_phone()
            self.state = self.STATE_PHONE
        elif k in (pygame.K_e, pygame.K_f):
            self.interact()
        elif k == pygame.K_r:
            self.player.reload()
        elif k == pygame.K_h and self.player.in_vehicle:
            self.player.in_vehicle.horn = 20
        elif k == pygame.K_F1:
            self.show_help = not self.show_help

    def key_phone(self, e):
        k = e.key
        if k in (pygame.K_t, pygame.K_p, pygame.K_ESCAPE):
            self.phone.close_phone()
            self.state = self.STATE_PLAY
        elif k == pygame.K_UP:
            self.phone.move_selection(-1)
        elif k == pygame.K_DOWN:
            self.phone.move_selection(1)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.phone.call_selected(self)

    def key_shop(self, e):
        k = e.key
        if k in (pygame.K_q, pygame.K_ESCAPE):
            self.exit_shop()
        elif k in (pygame.K_e, pygame.K_RETURN):
            self.interior.buy()

    def player_shoot(self):
        p = self.player
        b = p.try_shoot()
        if b:
            self.bullets.append(b)
            self.camera.shake = 1.6
            self.spawn_particles(b.x, b.y, 4, (255, 190, 60), 4)
            for ped in self.peds:
                if ped.state != "dead" and dist(ped.x, ped.y, b.x, b.y) < 240:
                    ped.state = "flee"
                    ped.panic = 220
                    ped.speed = 3.2
        elif p.mag <= 0 and p.reload_t == 0:
            self.toast("Şarjör boş — R ile doldur", C["red"])

    def quit(self):
        pygame.quit()
        sys.exit()

    # ---------- güncelleme ----------
    def update(self):
        keys = pygame.key.get_pressed()
        mouse = pygame.mouse.get_pos()

        self.phone.update()
        for t in self.toasts:
            t[2] -= 1
        self.toasts = [t for t in self.toasts if t[2] > 0]

        if self.state == self.STATE_SHOP:
            self.interior.update(keys, mouse)
            return

        p = self.player
        p.update(keys, mouse, self.camera, self.map)

        # araç sürüşü
        if p.in_vehicle:
            v = p.in_vehicle
            throttle = 0.0
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                throttle = 1.0
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
                throttle = -1.0
            steer = 0.0
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                steer += 1
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                steer -= 1
            handbrake = keys[pygame.K_SPACE]
            v.physics(self.map, throttle, steer, handbrake)
            p.x, p.y = v.x, v.y
            if v.health <= 0:
                self.toast("Araç hurdaya döndü!", C["red"])
                self.spawn_particles(v.x, v.y, 30, (255, 130, 30), 8)
                self.camera.shake = 12
                self.exit_vehicle()
                if v in self.vehicles:
                    self.vehicles.remove(v)
            # araca çarpan yayalar
            for ped in self.peds:
                if ped.state != "dead" and dist(ped.x, ped.y, v.x, v.y) < 35 and v.speed > 3:
                    ped.take_damage(120, v.vx, v.vy)
                    self.spawn_particles(ped.x, ped.y, 14, (170, 20, 20), 6)
                    v.vx *= 0.9
                    v.vy *= 0.9
                    p.add_wanted(1)
                    self.camera.shake = 5
                    if len(self.police) < 2:
                        self.spawn_police()
            self.camera.follow(v.x + v.vx * 8, v.y + v.vy * 8)
        else:
            self.camera.follow(p.x, p.y)

        # trafik + AI
        for v in self.vehicles:
            if v is p.in_vehicle:
                continue
            if v.ai == "traffic":
                v.update_traffic(self.map)
            elif v.ai is None and v.occupied:
                pass
            else:
                v.physics(self.map, 0, 0, False)
        # polis araçlarının kendi fiziği PoliceUnit içinde
        for pol in self.police:
            if pol.is_car:
                pol.update(p, self.map, self.bullets)
            else:
                pol.update(p, self.map, self.bullets)

        # araç-araç itme (polis araçları dahil)
        veh = list(self.vehicles) + [pol.vehicle for pol in self.police if pol.is_car]
        for i in range(len(veh)):
            a = veh[i]
            for j in range(i + 1, len(veh)):
                b = veh[j]
                if abs(a.x - b.x) < 80 and abs(a.y - b.y) < 90:
                    d = dist(a.x, a.y, b.x, b.y)
                    min_d = 62.0
                    if d < min_d and d > 0.1:
                        ang = angle_to(b.x, b.y, a.x, a.y)
                        push = (min_d - d) * 0.45
                        a.x += math.cos(math.radians(ang)) * push
                        a.y += math.sin(math.radians(ang)) * push
                        b.x -= math.cos(math.radians(ang)) * push
                        b.y -= math.sin(math.radians(ang)) * push
                        if a is p.in_vehicle or b is p.in_vehicle:
                            self.camera.shake = max(self.camera.shake, 3)

        # yayalar
        for ped in self.peds:
            ped.update(p, self.bullets, self.map)
            if ped.state == "dead":
                continue
            # oyuncu ezme (yaya olarak)
            if not p.in_vehicle and dist(ped.x, ped.y, p.x, p.y) < 24 and p.moving:
                ped.state = "flee"
                ped.panic = 120

        # mermiler
        for b in self.bullets[:]:
            alive = b.update(self.map)
            if not alive:
                self.bullets.remove(b)
                self.spawn_particles(b.x, b.y, 5, (140, 140, 150), 4)
                continue
            hit = False
            if b.owner == "player":
                for ped in self.peds:
                    if ped.state == "dead":
                        continue
                    if dist(b.x, b.y, ped.x, ped.y) < 18:
                        dead = ped.take_damage(b.damage, b.vx, b.vy)
                        self.spawn_particles(b.x, b.y, 10, (190, 25, 25), 5)
                        if dead:
                            p.money += random.randint(20, 60)
                            if not ped.target_ped:
                                p.add_wanted(2)
                                self.toast("Cinayet! Polis aranıyor", C["red"])
                            else:
                                self.toast("Hedef indirildi", C["gold"])
                            if random.random() < 0.7:
                                self.spawn_police()
                        hit = True
                        break
                if not hit:
                    for pol in self.police[:]:
                        tx, ty = (pol.vehicle.x, pol.vehicle.y) if pol.is_car else (pol.x, pol.y)
                        if dist(b.x, b.y, tx, ty) < 26:
                            self.spawn_particles(b.x, b.y, 8, (120, 120, 130), 5)
                            if pol.is_car:
                                pol.vehicle.health -= b.damage
                                if pol.vehicle.health <= 0:
                                    self.spawn_particles(tx, ty, 26, (255, 130, 20), 8)
                                    self.police.remove(pol)
                                    p.money += 120
                                    self.camera.shake = 8
                            else:
                                pol.health -= b.damage
                                if pol.health <= 0:
                                    self.police.remove(pol)
                                    self.spawn_particles(tx, ty, 14, (190, 25, 25), 6)
                                    p.money += 90
                            p.add_wanted(1)
                            hit = True
                            break
            elif b.owner == "police":
                if dist(b.x, b.y, p.x, p.y) < 20:
                    p.take_damage(b.damage * (0.5 if p.in_vehicle else 1.0))
                    self.camera.shake = 4
                    self.spawn_particles(b.x, b.y, 6, (255, 70, 70), 4)
                    hit = True
            if not hit:
                for v in self.vehicles:
                    if dist(b.x, b.y, v.x, v.y) < 30:
                        v.health -= b.damage * 0.5
                        self.spawn_particles(b.x, b.y, 6, (190, 190, 200), 4)
                        hit = True
                        break
            if hit and b in self.bullets:
                self.bullets.remove(b)

        # partiküller
        self.particles = [pt for pt in self.particles if pt.update()]

        # görevler
        self.missions.update()

        # polis yönetimi
        if p.wanted > 0:
            want = int(p.wanted * 1.8) + 1
            if len(self.police) < want and random.random() < 0.012 + p.wanted * 0.006:
                self.spawn_police()
            self.camera.shake = max(self.camera.shake, 0)
        else:
            if self.police and random.random() < 0.004:
                self.police.pop(0)

        # ölüm
        if p.health <= 0:
            self.respawn()

        # trafik yenile
        if len(self.vehicles) < 22 and random.random() < 0.008:
            ix = random.choice(ROAD_XS)
            iy = random.choice(ROAD_YS)
            v = Vehicle(ix + random.uniform(-60, 60), iy + random.uniform(-400, 400),
                        random.choice(VEHICLE_TYPES))
            v.ai = "traffic"
            v.road_i = ROAD_XS.index(ix)
            v.road_j = ROAD_YS.index(iy)
            v.dir = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
            self.vehicles.append(v)

    def respawn(self):
        p = self.player
        self.spawn_particles(p.x, p.y, 20, (220, 20, 20), 6)
        if p.in_vehicle:
            p.in_vehicle.occupied = False
            p.in_vehicle = None
        p.health = p.max_health
        p.armor = 0
        p.money = max(0, p.money - 350)
        p.wanted = 0
        p.x, p.y = ROAD_XS[3], ROAD_YS[3]
        self.bullets.clear()
        self.camera.follow(p.x, p.y, snap=True)
        self.phone.notify("Los Santos Hastanesi", "Tedavi edildin. $350 kesildi. Polis kayıtları temizlendi.")
        self.toast("Hastanedesin. $350 kesildi", C["red"])

    # ---------- çizim ----------
    def draw(self):
        if self.state == self.STATE_SHOP:
            self.interior.draw(self.screen)
            pygame.display.flip()
            return

        self.map.draw(self.screen, self.camera)

        # görev / dükkan işaretleri
        for (mx, my) in self.map.mission_spots:
            px, py = world_to_screen(mx, my, self.camera)
            if -60 < px < SCREEN_W + 60 and -60 < py < SCREEN_H + 60:
                t = pygame.time.get_ticks() * 0.004
                r = 16 + math.sin(t) * 3
                pygame.draw.circle(self.screen, (30, 90, 200), (int(px), int(py)), int(r))
                pygame.draw.circle(self.screen, (255, 255, 255), (int(px), int(py)), int(r), 2)
                text(self.screen, "?", px, py - 11, 18, True, (255, 255, 255), center=True, shadow=False)

        # çizilecek nesneleri derinliğe göre sırala
        items = []
        for v in self.vehicles:
            items.append((v.y, "veh", v))
        for ped in self.peds:
            items.append((ped.y, "ped", ped))
        for pol in self.police:
            items.append((pol.y, "pol", pol))
        if not self.player.in_vehicle:
            items.append((self.player.y, "player", self.player))
        items.sort(key=lambda it: it[0])

        for _, kind, obj in items:
            if kind == "veh":
                obj.draw(self.screen, self.camera, highlight=obj.is_mission_car)
            elif kind == "ped":
                obj.draw(self.screen, self.camera)
            elif kind == "pol":
                obj.draw(self.screen, self.camera)
            else:
                obj.draw(self.screen, self.camera)

        for b in self.bullets:
            b.draw(self.screen, self.camera)
        for pt in self.particles:
            pt.draw(self.screen, self.camera)

        self.missions.draw_marker(self.screen, self.camera)

        # HUD
        self.hud.draw(self.screen, self.player, self.camera, self.map, self)

        # araç göstergesi
        if self.player.in_vehicle:
            self._speedo()

        if self.show_help:
            self._draw_help()

        # telefon
        self.phone.draw(self.screen)


        pygame.display.flip()

    def _draw_help(self):
        w, h = 720, 470
        x, y = SCREEN_W // 2 - w // 2, SCREEN_H // 2 - h // 2
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        self.screen.blit(ov, (0, 0))
        panel(self.screen, (x, y, w, h), (14, 16, 22), C["neon"], 16, 246)
        text(self.screen, "KONTROLLER", x + 26, y + 18, 22, True, C["neon"])
        text(self.screen, "F1 / ESC ile kapat", x + w - 26 - font(11, True).size("F1 / ESC ile kapat")[0],
             y + 26, 11, True, (160, 166, 178))
        rows = [
            ("WASD / Yön tuşları", "yürü  •  araçta: gaz / fren / direksiyon"),
            ("Mouse", "360° nişan alma"),
            ("Sol tık", "ateş et"),
            ("Sağ tık (basılı)", "nişan modu (lazer + hassas)"),
            ("E / F", "araca bin-in  •  dükkana gir  •  görev al  •  satın al"),
            ("Q", "dükkandan çık"),
            ("T veya P", "iFruit telefon / rehber"),
            ("R", "şarjör doldur"),
            ("SPACE", "el freni (drift)"),
            ("H", "korna"),
            ("F1", "bu yardım ekranı"),
            ("ESC", "çıkış"),
        ]
        for i, (a, b) in enumerate(rows):
            ry = y + 62 + i * 27
            if i % 2 == 0:
                pygame.draw.rect(self.screen, (22, 25, 33), (x + 18, ry - 4, w - 36, 25), border_radius=6)
            text(self.screen, a, x + 32, ry, 13, True, (255, 220, 120))
            text(self.screen, b, x + 260, ry, 13, False, (226, 232, 242))
        text(self.screen, "Dükkanlar: Berber • Market • Espor Arena • Ammu-Nation • Giyim • Eczane • Spor Salonu • Customs • Dövme • Cluckin' Bell",
             x + 26, y + h - 34, 11, False, (170, 178, 192))

    def _speedo(self):
        v = self.player.in_vehicle
        kmh = int(v.speed * 18)
        w, h = 250, 74
        x, y = SCREEN_W // 2 - w // 2, SCREEN_H - 120
        panel(self.screen, (x, y, w, h), (14, 16, 22), (80, 86, 100), 12, 220)

        # kadran
        cx, cy = x + 46, y + h // 2
        pygame.draw.circle(self.screen, (30, 32, 40), (cx, cy), 32)
        pygame.draw.circle(self.screen, (70, 74, 84), (cx, cy), 32, 2)
        pct = clamp(abs(v.forward_speed()) / v.type["max_speed"], 0, 1)
        for i in range(11):
            a = math.radians(150 + i * 24)
            col = C["green"] if i / 10 <= pct else (60, 62, 72)
            pygame.draw.line(self.screen, col,
                             (cx + math.cos(a) * 24, cy + math.sin(a) * 24),
                             (cx + math.cos(a) * 30, cy + math.sin(a) * 30), 3)
        ang = math.radians(150 + pct * 240)
        pygame.draw.line(self.screen, C["red"], (cx, cy),
                         (cx + math.cos(ang) * 26, cy + math.sin(ang) * 26), 3)

        text(self.screen, f"{kmh}", x + 100, y + 10, 26, True, (255, 255, 255))
        text(self.screen, "KM/H", x + 100, y + 44, 11, True, (160, 166, 178))
        text(self.screen, v.type["name"], x + 160, y + 12, 14, True, (200, 215, 240))
        hp = int(v.health)
        col = C["green"] if hp > 55 else (C["gold"] if hp > 25 else C["red"])
        pygame.draw.rect(self.screen, (40, 42, 50), (x + 160, y + 36, 78, 8), border_radius=4)
        pygame.draw.rect(self.screen, col, (x + 160, y + 36, 78 * hp / 100, 8), border_radius=4)
        if v.nitro > 0:
            text(self.screen, "NITRO", x + 160, y + 50, 10, True, (0, 220, 255))
        text(self.screen, "[E] in  [SPACE] el freni", x + 160, y + 50 if v.nitro <= 0 else y + 60,
             9, False, (150, 156, 170))

    def run(self):
        self.errors = 0
        while True:
            self.clock.tick(FPS)
            try:
                self.handle_events()
                self.update()
                self.draw()
            except SystemExit:
                raise
            except Exception:
                # bir kare hata verirse oyun kapanmasın: konsola yaz, devam et
                import traceback
                traceback.print_exc()
                self.errors += 1
                self.toast(f"Beklenmeyen hata (x{self.errors}) — konsola bak", C["red"])
                try:
                    # güvenli duruma dön
                    self.state = self.STATE_PLAY
                    self.show_help = False
                    self.phone.close_phone()
                    self.interior = None
                    self.bullets.clear()
                    self.particles.clear()
                    self.player.health = max(1, self.player.health)
                    pygame.display.flip()
                except Exception:
                    pass


if __name__ == "__main__":
    Game().run()
