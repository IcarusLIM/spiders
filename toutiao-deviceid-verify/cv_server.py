import os
from aiohttp import web
import asyncio
import uuid
import cv2

import aiohttp

TMP_DIR = "verify_tmp"

if not os.path.exists(TMP_DIR):
    os.mkdir(TMP_DIR)


async def download_pic(src, fname, session):
    async with session.get(src) as resp:
        if resp.status == 200:
            with open(fname, "wb") as f:
                f.write(await resp.read())


def match(tmp_dir):
    bg = cv2.Canny(cv2.imread(tmp_dir + "bg.png", 0), 400, 800)
    h, w = bg.shape
    slide = cv2.Canny(cv2.imread(tmp_dir + "slide.png", 0), 400, 800)
    res = cv2.matchTemplate(slide, bg, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    x, y = max_loc
    return w, h, x, y

# # bgEl: background img element in puppeteer by document.querySelector
# # slideEl: slide img element
# bgPos = bgEl.getBoundingClientRect()
# slidePos = slideEl.getBoundingClientRect()
# # request.body
# {
#     bg: {
#         src: bgEl.src,
#         pos: { x: bgPos.x, y: bgPos.y, w: bgPos.width, h: bgPos.height }
#     },
#     slide: {
#         src: slideEl.src,
#         pos: { x: slidePos.x, y: slidePos.y, w: slidePos.width, h: slidePos.height }
#     }
# }
async def handle(request):
    tmp_dir = f"{TMP_DIR}/{uuid.uuid4()}/"
    print(f"=>> Request receive, dir {tmp_dir}")
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)
    body = await request.json()
    bg = body["bg"]
    slide = body["slide"]
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            download_pic(bg["src"], tmp_dir + "bg.png", session),
            download_pic(slide["src"], tmp_dir + "slide.png", session),
        )
    w, h, x, y = match(tmp_dir)
    pixel = x / w * bg["pos"]["w"] - (slide["pos"]["x"] - bg["pos"]["x"])
    return web.json_response({"pixel": pixel, "meta": {"x": x, "y": y, "w": w, "h": h}})


app = web.Application()
app.add_routes([web.post("/", handle)])

if __name__ == "__main__":
    web.run_app(app, port=777)
