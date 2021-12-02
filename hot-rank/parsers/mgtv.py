import json
import re
from utils import download_page, purge_meta, logging, push_detail, push_res

logger = logging.getLogger(__name__)


json_str_reg = re.compile("callback_rc_ranklist_\d+\((.*)\)")


async def parse_rank(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url)
    match = json_str_reg.search(resp)
    if not match:
        logger.warning(f"not match json_reg {resp[:100]}")
    data = json.loads(match[1]).get("data", {})
    for i, video in enumerate(data):
        meta["index"] = i
        if video.get("info", "").find("热播指数:") >= 0:
            meta["popularity"] = video["info"].replace("热播指数:", "").strip()
        new_url = f"https://pcweb.api.mgtv.com/video/info?vid={video.get('videoId', '')}&cid={video.get('clipId', '')}&_support=10000000"
        push_detail({"url": new_url, "meta": meta})


async def parse(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url)
    data = json.loads(resp)
    if data.get("code", 404) != 200:
        return []
    video_info = data.get("data", {}).get("info", {})
    detail = video_info.get("detail", {})

    meta["title"] = video_info.get("title", "")
    meta["actors"] = [d.strip() for d in detail.get("leader", "").split("/")]
    meta["directors"] = [d.strip() for d in detail.get("director", "").split("/")]
    meta["area"] = detail.get("area", "")
    meta["labels"] = [k.strip() for k in detail.get("kind", "").split("/")]
    meta["prompt_text"] = detail.get("updateInfo", "")
    meta["earliest_issue_time"] = detail.get("releaseTime", "")
    meta["year"] = detail.get("releaseTime", "").strip()[:4]
    meta["cover"] = video_info.get("videoImage", "")

    meta["raw"] = detail
    push_res(meta)
