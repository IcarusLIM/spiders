const createClient = require("redis").createClient
const puppeteer = require('puppeteer')
const axios = require('axios').default;
const sleep = t => new Promise(r => setTimeout(r, t))

const RANDOM_QUERY = [
    "自产疫苗不被认可，77万人白打“高端疫苗”？前“立委”孙大千：不",
    "05年张前拍《亮剑》，开出50万请陈建斌出演李云龙，被拒绝了，又",
    "又一国产轿车火了！油耗低至5.5L，30天卖13979台，关键顶",
    "大舅的“牙疼验方”，其实就那么简单，可惜很多人还不知道！",
    "房地产税的定位和征管难点，专家：试点“一定会动存量房产”",
    "还在玩充电？五菱已经加氢了",
    "警方紧急提醒：这种二维码千万别扫！",
    "王者荣耀隐藏分为何要隐藏呢？答案让人意外，原因竟是保护玩家！",
    "“辽宁营口坠龙”事件，到底是怎么回事？专家：龙或许真的存在",
    "edg挺进四强"
]

const DEVICE_MAP = "tokens:all"
const EXPIRE_SET = "tokens:expire"
const cvServer = "http://10.143.15.226:777"

let _moveTrace = function* (dis) {
    let trace = []
    let t0 = 0.2
    let curr = 0
    let step = 0
    let a = 0.8

    while (curr < dis) {
        let t = t0 * (++step)
        curr = parseFloat((1 / 2 * a * t * t).toFixed(2))
        trace.push(curr)
    }

    for (let i = 0; i < trace.length; ++i) {
        yield trace[i]
    }
}

async function main() {
    const browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-gpu'], headless: true })
    const redisClient = createClient({ url: "redis://:waibiwaibiwaibibabo@10.143.15.226:6379" })
    await redisClient.connect()

    async function get_expires() {
        const expiresDevice = await redisClient.sMembers(EXPIRE_SET)
        const devices = []
        for (const d of expiresDevice) {
            const device = await redisClient.hGet(DEVICE_MAP, d)
            if (device) {
                devices.push(JSON.parse(device))
            } else {
                await redisClient.sRem(EXPIRE_SET, d)
            }
        }
        return devices
    }

    async function mark_ok(deviceId) {
        console.log("Enable, ", Date.now(), deviceId)
        await redisClient.sRem(EXPIRE_SET, deviceId)
    }

    async function tryActive(device) {
        const query = RANDOM_QUERY[Math.floor(Math.random() * RANDOM_QUERY.length)]
        const url = `https://is.snssdk.com/search/?source=search_bar_inner&keyword_type=inbox&search_position=search_list` +
            `&cur_tab_title=search_tab&from=search_tab&is_ttwebview=0&keyword=${encodeURIComponent(query)}&manifest_version_code=8470` +
            `&channel=tt_wtt_qrcod&isTTWebView=0&device_type=Android8.0&language=zh&host_abi=armeabi-v7a&resolution=768*1184` +
            `&openudid=${device["openudid"]}&update_version_code=84707&os_api=26&mac_address=${encodeURIComponent(device["mac_address"])}&dpi=320` +
            `&ac=wifi&os=android&device_id=${device["device_id"]}&os_version=8.0.0&version_code=847&app_name=news_article&version_name=8.4.7&` +
            `device_brand=Android&device_platform=android&aid=13&rom_version=26`
        const ctx = await browser.createIncognitoBrowserContext()
        const page = await ctx.newPage()
        await page.evaluateOnNewDocument(async () => {
            const newProto = navigator.__proto__;
            delete newProto.webdriver;
            navigator.__proto__ = newProto;
        });

        const waitVerify = page.waitForResponse(resp => {
            return resp.url().startsWith("https://verify.snssdk.com/captcha/get")
        }, { timeout: 3000 })
        try {
            await page.goto(url)
            let neeVerify = true
            await waitVerify.catch(_ => { neeVerify = false })
            if (!neeVerify) {
                return true
            }
            await page.waitForSelector(".captcha_verify_container img[draggable='false']", { timeout: 2000 }).catch(e => { console.log("fail to wait verify img", e.message) })
            await page.waitForSelector(".captcha_verify_container img.captcha_verify_img_slide", { timeout: 2000 }).catch(e => { console.log("fail to wait verify img slide", e.message) })
            const verifyPics = await page.evaluate(() => {
                if (document.querySelector("div.captcha_verify_container")) {
                    // need verify
                    const bgEl = document.querySelector(".captcha_verify_container img[draggable='false']")
                    const bgPos = bgEl.getBoundingClientRect()
                    const slideEl = document.querySelector(".captcha_verify_container img.captcha_verify_img_slide")
                    const slidePos = slideEl.getBoundingClientRect()
                    return {
                        bg: {
                            src: bgEl.src,
                            pos: { x: bgPos.x, y: bgPos.y, w: bgPos.width, h: bgPos.height }
                        },
                        slide: {
                            src: slideEl.src,
                            pos: { x: slidePos.x, y: slidePos.y, w: slidePos.width, h: slidePos.height }
                        }
                    }
                }
            })
            // try slide
            const cvRes = (await axios.post(cvServer, verifyPics)).data
            const slideBtnPos = await page.evaluate(() => {
                const btn = document.querySelector(".captcha_verify_container .secsdk-captcha-drag-icon")
                const rect = btn.getBoundingClientRect()
                return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
            })
            await page.mouse.move(slideBtnPos.x, slideBtnPos.y)
            await page.mouse.down()
            const traces = _moveTrace(cvRes.pixel)
            for (const t of traces) {
                await page.mouse.move(slideBtnPos.x + t, slideBtnPos.y)
            }
            await page.mouse.up()
            await page.waitForSelector(".result-content a.cs-view", { timeout: 2000 }).catch(e => { console.log("waitForSelector result-content", e.message) })
        } catch (e) {
            console.log(e.message)
            return false
        } finally {
            await page.close()
            await ctx.close()
        }
    }

    while (true) {
        const devices = await get_expires()
        if (devices.length === 0) {
            await sleep(1000)
            continue
        }
        for (const device of devices) {
            const isSucceed = await tryActive(device)
            if (isSucceed) {
                mark_ok(String(device["device_id"]))
            }
            break
        }
    }

}

main()