import json
import re
import numpy
import textwrap
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from functools import partial

# Reference https://blog.csdn.net/jerrism/article/details/105755042
class FontDecrypter:
    def __init__(self, f, ucmap):
        self.font0 = TTFont(f)
        self.ucmap = ucmap
        glyph_list0 = list(self.font0.getBestCmap().values())
        self.glyph_coords_map0 = {g: self._get_glyph_coords(self.font0["glyf"][g]) for g in glyph_list0}

    @staticmethod
    def get_cosine_sim(_v1, _v2):
        l = min(len(_v1), len(_v2))
        v1 = numpy.array(_v1[:l])
        v2 = numpy.array(_v2[:l])
        product = numpy.linalg.norm(v1) * numpy.linalg.norm(v2)
        return numpy.dot(v1, v2) / product

    def sub_all(self, font_file, s, p="&#x(.+?);", raw=False):
        if raw:
            p = "(.)"
        font = TTFont(font_file)
        glyph_list = list(font.getBestCmap().values())
        glyph_coords_map = {k: None for k in glyph_list}
        cache = {}
        return re.sub(p, partial(self._sub_one, font, glyph_coords_map, raw, cache), s)

    def _sub_one(self, font, glyph_coords_map, raw, cache, s_match):
        s = s_match[1]
        if s in cache:
            return cache[s]
        code = ord(s) if raw else int(s, 16)
        glyph_name = font.getBestCmap().get(code)
        if not glyph_name or glyph_name not in glyph_coords_map:
            return s_match[0]
        if glyph_coords_map[glyph_name] is None:
            glyph_coords_map[glyph_name] = self._get_glyph_coords(font["glyf"][glyph_name])
        glyph_coords = glyph_coords_map[glyph_name]

        best_sim = -1
        best = None
        for glyph_name0, glyph_coords0 in self.glyph_coords_map0.items():
            sim = 0
            if len(glyph_coords0) != len(glyph_coords):
                continue
            for _v1, _v2 in zip(glyph_coords0, glyph_coords):
                sim += self.get_cosine_sim(_v1, _v2)
            if sim > best_sim:
                best_sim = sim
                best = glyph_name0

        if best in self.ucmap:
            cache[s] = self.ucmap[best]
            return cache[s]
        else:
            return s_match[0]

    @classmethod
    def _get_glyph_coords(cls, glyph):
        # 获取字符路径，并按endpoint分段
        coords = glyph.coordinates.array
        end_pts = glyph.endPtsOfContours
        end_pts = [0] + end_pts
        return [coords[end_pts[i] : end_pts[i + 1] * 2] for i in range(len(end_pts) - 1)]

    # 打印字体文件maoyan.woff的glyphs列表，渲染glyphs到font.png
    # 用于手动编辑maoyan.json映射关系
    @staticmethod
    def show_glyphs(f):
        font = TTFont(f)
        codes = []
        unis = []
        for code, uni in font.getBestCmap().items():
            codes.append(code)
            unis.append(uni)
        print(unis)
        text = " ".join([chr(code) for code in codes])
        img = Image.new("RGB", (1280, 360), "#fff")
        draw = ImageDraw.Draw(img)
        f.seek(0)
        draw.text((10, 0), textwrap.fill(text, width=100), font=ImageFont.truetype(f, 40), fill="#000", spacing=20)
        img.save("font.png")


if __name__ == "__main__":
    # with open("maoyan.woff", "rb") as f0:
    #     FontDecrypter.show_glyphs(f0)
    with open("maoyan.woff", "rb") as f0, open("maoyan.json", "r") as f0_ucmap, open(
        "0e639b50c64de717b142088fe01561392276.woff", "rb"
    ) as f:
        dd = FontDecrypter(f0, json.load(f0_ucmap))
        print(dd.sub_all(f, "&#xf84c;&#xf84c;.&#xf518;"))  # 11.25
        print(dd.sub_all(f, "&#xe4cc;.&#xf655;&#xf5e7;"))  # 2.08
