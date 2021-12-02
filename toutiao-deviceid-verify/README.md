# 破解滑动验证码

利用 puppeteer 和 opencv，自动处理滑块验证码

## 使用方式

> deviceid 可随机生成，或使用 https://github.com/coder-fly/douyin_device_register#docker ，或使用安卓模拟器生成

deviceid 生成后，需触发一次滑动验证才能长期使用，本例在浏览器中访问搜索接口触发验证码完成验证

1. 使用工具或随机生成 deviceid
2. 将未验证的 deviceid 存储到 redis 中
3. 启动 cv_server.py 和 puppeteer/verify.js，verify.js 将轮询 redis 中的无效 deviceid 并验证

redis 数据格式

| 键            | 类型 |                                                                      |
| ------------- | ---- | -------------------------------------------------------------------- |
| tokens:all    | hash | kv 对，key 为 deviceid，value 为完整 device 信息                     |
| tokens:expire | set  | 已过期的 deviceid，初始状态把 tokens:all 中所有 deviceid 加入 set 中 |

eg:

```bash
# redis-cli
127.0.0.1:6379> HSET tokens:all 4495250849804686 '{"device_id": "4495250849804686", "install_id": "3105468165931352", "mac_address": "9a:13:a5:12:48:3a", "openudid": "2ji2lnkfjkdj8n63", "udid": "751397510104898"}'
SADD tokens:expire 4495250849804686
```