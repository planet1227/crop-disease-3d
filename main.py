import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import requests
import base64
from PIL import Image
import io
import json
import re
import time
import math
import datetime

app = FastAPI()

# 本地字体目录（标题字体，录视频时不依赖外网）
app.mount("/fonts", StaticFiles(directory="fonts"), name="fonts")
# 本地化的第三方脚本，手机不依赖 CDN
app.mount("/lib", StaticFiles(directory="lib"), name="lib")
app.mount("/models", StaticFiles(directory="models"), name="models")

# ========= 密钥：从环境变量读，本地开发写在同目录 .env（不进仓库）=========
def _load_dotenv():
    """读同目录 .env（每行 KEY=VALUE），已存在的环境变量优先，不覆盖。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    try:
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception as e:
        print("【.env 读取失败】", repr(e))

_load_dotenv()
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not DEEPSEEK_API_KEY or not DASHSCOPE_API_KEY:
    print("【提示】没读到 DEEPSEEK_API_KEY / DASHSCOPE_API_KEY，请在同目录建 .env（参照 .env.example）")
# ================================================================

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ===== 识病：输出一张结构化的「病情诊断单」，而不是一段散文 =====
VISION_PROMPT = """你是大田作物病害诊断员，为本报撰写「病情诊断单」。
只输出一个 JSON 对象。第一个字符必须是 {，最后一个字符必须是 }。
不要写解释、不要写前言、不要用 ``` 代码块。

字段定义：
{
  "crop": "作物名；认不出写 未辨识",
  "verdict": "确诊" 或 "疑似" 或 "不敢断",
  "disease": "病害全名，必须写成「作物名＋病名」，如 小麦条锈病 / 玉米大斑病 / 黄瓜霜霉病 / 稻瘟病；不敢断时填 暂不能确定",
  "confidence": 0 到 100 的整数,
  "evidence": "图上真实看到的依据：颜色、形状、大小、分布位置，30字以内；大小只写「约为叶宽的几分之几」这类相对说法，不报厘米",
  "severity": "轻" 或 "中" 或 "重",
  "stage": "初期" 或 "盛期" 或 "末期",
  "window": "防治窗口，例如 三日内 / 立冬后七日内 / 暂不需处理",
  "prescription": "具体处置：药剂名+剂型+亩用量或稀释倍数；不必打药就写田间管理措施",
  "fieldnote": "田间提醒，如湿度、通风、邻田传染风险，20字以内",
  "candidates": [{"name": "候选病名，同样写成作物＋病名", "confidence": 0 到 100}]
}

看图顺序（先在脑子里走完这五步，再写 JSON）：
第一步 认清作物：看叶形、叶脉、茎秆、果实、穗型，判断是小麦、玉米、水稻、番茄、黄瓜，还是别的
第二步 看部位：病斑在叶片、茎秆叶鞘、果实，还是穗子上
第三步 看颜色：鲜黄 / 橙褐 / 深褐红 / 肉桂色 / 灰白 / 白色粉状 / 粉红霉层 / 墨绿
第四步 看排列：沿叶脉成行（虚线状）/ 散生随机 / 成片霉层 / 环绕茎基 / 被叶脉框成多角形
第五步 看形状与凸起：长梭形 / 小椭圆 / 圆形同心轮纹 / 多角形 / 梭形眼斑 / 隆起疱堆 / 穿孔
第六步 量比例、数个数：把病斑的长短去比叶片的横宽（垂直于叶脉那个方向），再数一片叶上有几个斑。图上没有尺子，一律用「约叶宽的几分之几」说话。这一步是区分玉米大斑和小斑的硬指标，比颜色可靠。

常见病害鉴别点（按作物分）：

【小麦】
- 条锈病：叶片，鲜黄色、小、沿叶脉排成一行行虚线状长条，不破裂
- 叶锈病：叶片，橙褐色、近圆形、大小不一、散生不成行，边缘常带黄晕
- 秆锈病：茎秆、叶鞘，穗部也上。病部是隆起的疱堆，个头最大，深褐红至砖红色，疱堆能把表皮撑破、散出锈色粉末；摸着是硬的、凸起的
- 白粉病：叶片，白色粉状霉层平铺成片，擦之有粉，后期转灰
- 赤霉病：麦穗。小穗基部生粉红色霉层，霉层柔软、成团，不隆起不成疱；受害小穗发白枯死，穗子局部或整穗干枯
- 纹枯病：茎基部叶鞘，椭圆形褐色病斑，一圈套一圈呈同心环云纹状

【玉米】
- 大斑病：叶片。病斑长梭形（纺锤形），两头尖，长宽比常在 3:1 以上；单个斑的长度往往超过叶片横宽的一半，长的能到叶宽的两倍，顺着叶脉伸展，后期几个斑连成大块；一片叶上通常只有几个到十几个。中央灰褐或浅灰，边缘深褐。中央发白也照样可能是大斑，颜色不是区分点
- 小斑病：叶片。病斑椭圆形、接近圆形，单个斑的长度不到叶片横宽的三分之一，长宽比多在 2:1 以内；一片叶上密密麻麻几十个，常常铺满叶面。中央灰白、边缘一圈褐色
- 锈病：叶片。肉桂色到红褐色的圆形疱堆，隆起，成熟破皮散黄褐粉末，沿叶脉成行或散生；斑极小，直径不到叶宽的五分之一

【番茄】
- 早疫病：叶片为主。圆形褐色病斑，带清晰同心轮纹（靶心状），轮廓分明，外圈一圈浅黄晕；不生长绒毛状霉
- 晚疫病：叶片为主，也上果实和茎。从叶缘叶尖起的暗绿色水渍状不规则大斑，边界模糊、没有清晰轮廓，也没有同心轮纹，叶背尤其明显；潮湿时表面生白色霜状薄霉
- 灰霉病：主要在果实、花器和残花上，叶片上少见。霉层灰褐色、绒毛状、成团堆积，病部软化塌陷

【黄瓜】
- 霜霉病：叶片，受叶脉限制的多角形黄褐色斑，边角分明，叶背对应处生灰黑色霉层
- 白粉病：叶片，白色粉状霉层呈不规则斑片，中心浓白边缘稀薄，后期叶黄卷边
- 细菌性角斑病：叶片，受叶脉限制的多角形水渍状褐斑，后期中央干裂穿孔

【水稻】
- 稻瘟病：叶片也看穗颈，梭形（眼形）病斑，中央灰白、边缘褐色，穗颈受害则整穗发白
- 稻曲病：稻穗，谷粒被墨绿色至黑绿色绒状球粒取代，病粒明显大于正常谷粒
- 白叶枯病：叶片，从叶尖叶缘起的波纹状黄白色条斑，向叶基延伸并逐渐枯褐

铁律：
1. 看不清病斑、图像模糊、主体不是作物时，verdict 必须写「不敢断」，disease 写「暂不能确定」
2. 只有特征完全对得上才写「确诊」；两种以上分不清时写「疑似」
3. confidence 必须保守：特征典型最高 92；有相似病害干扰时不超过 72；不敢断时不超过 40
4. candidates 给 2 到 3 个，按把握从高到低，把最容易混淆的那个放进去
5. 不许编造药剂和用量；拿不准就写「请咨询当地农技站」
6. evidence 只写图上看得见的东西，不许写「可能是」「怀疑」；也不许报厘米数，大小一律写成「约为叶宽的几分之几」
7. 全部用简体中文
8. disease 字段必须是「作物名＋病名」的完整写法，这是本报立起立体模型的依据；写成「锈病」「白粉病」这种短名会让模型认错
9. 农户若指定了作物，一律以指定为准，不要改成你猜的；没指定就自己从叶形、叶脉、茎秆判断，把结论写进 crop
10. 玉米叶片上出现斑点，先算「斑长 ÷ 叶宽」再数个数：一个斑的长度明显超过叶片横宽的一半，就按大斑病走；斑小到只有叶宽三分之一以下、且一片叶上几十个，才是小斑病。只凭「中央灰白」判小斑不算数，大斑的中央也常发白
11. 番茄先看部位再定病：在叶片上、斑里有同心轮纹 → 早疫；在叶片上、斑是边界模糊的水渍大斑、带白色霜霉 → 晚疫；在果实或残花上、长灰褐绒毛霉并软化塌陷 → 灰霉。只凭「有霉层」判灰霉不算数，晚疫也长白霉
12. 图上只有叶片、看不到果实和残花时，番茄的候选里一律不要出现灰霉病。灰霉的标志部位是果实和残花，叶片上极少单独发生"""

OBSERVE_PROMPT = """你只做观察记录，不做诊断，不许提任何病名，也不许猜。
看这张作物叶片的照片，把真正看得见的东西记下来，只输出一个 JSON：

{
 "crop": "什么作物：玉米叶宽大、中脉粗白；小麦叶细长窄；水稻叶细长、中脉明显、叶缘略糙；番茄是羽状复叶、小叶带齿；黄瓜叶掌状有裂角",
 "part": "只能选：叶片 / 茎秆叶鞘 / 果实 / 穗子",
 "shape": "只能选：长梭形(两头尖) / 椭圆形 / 圆形 / 多角形 / 不规则大片 / 条带状(沿叶缘或叶脉拉成长条)",
 "ratio": "一个病斑的长度大约是叶片横宽的几分之几，写成 1/5、1/3、1/2、2/3 这样",
 "count": "这一片叶上大约几个病斑，写数字或「几十个」",
 "center_color": "病斑中央颜色",
 "edge_color": "病斑边缘颜色",
 "surface": "只能选或组合：隆起疱堆 / 白色霜霉(叶背灰白霉层) / 白色粉状霉层(叶面白粉，像撒了面粉) / 灰褐绒毛霉 / 同心轮纹 / 穿孔 / 平滑无霉",
 "arrangement": "病斑怎么分布的：成行沿叶脉 / 散生随机 / 连片铺满 / 沿叶缘延伸",
 "extent": "病斑占这张画面的多少：少量 / 局部 / 大半"
}
只输出 JSON，不要解释，不要提病名。"""

DIAG_BRIDGE = """

【本次是文字研判】
照片不在你眼前，观察员已经把客观特征记下来了：
%s

请完全依据这份记录判断，对照上面的鉴别点写诊断单，并遵守这几条换算：
- shape 是「长梭形」、ratio 到 1/2 以上、count 是个位数 → 玉米大斑病，此时不许判小斑
- shape 是「椭圆形」、ratio 在 1/4 以下、count 是几十个 → 玉米小斑病
- shape 是「不规则大片」、surface 含「白色霜霉」、part 是叶片 → 番茄晚疫病
- surface 含「同心轮纹」：番茄叶片 → 早疫病；小麦且 part 是茎秆叶鞘 → 纹枯病
- 小麦 part 是「叶片」时不要判纹枯病（纹枯长在茎基叶鞘上）；叶片上散生橙褐或橙黄小圆斑 → 叶锈病
- surface 含「白色粉状霉层」（叶面像撒面粉）、且 part 是叶片 → 白粉病，小麦判小麦白粉病、黄瓜判黄瓜白粉病；part 是穗子时不要判白粉，白色或粉红霉层长在小穗上就是赤霉病
- surface 含「白色霜霉」且是叶背灰白霉 → 霜霉病一类，别和白粉病混
- 水稻叶片：shape 含「条带状」或 arrangement 含「沿叶缘延伸」→ 白叶枯病
- 水稻叶片但病斑是一个个散生独立的小斑，中央灰白、边缘深褐、形状梭形或眼形 → 稻瘟病，不要判白叶枯
- surface 含「隆起疱堆」：颜色鲜黄或黄色 → 小麦条锈病；橙褐色且散生圆斑 → 小麦叶锈病；在茎秆叶鞘或穗子上、红褐色 → 秆锈病
- part 是穗子：表面柔软粉红霉层 → 赤霉病；平滑无霉的长梭形红褐疱 → 秆锈病
- part 是果实、表面灰褐绒毛霉且软化塌陷 → 番茄灰霉病；只有叶片就不要判灰霉
- 记录里没写的特征一律不许编；evidence 直接引用记录里的形状、比例、个数、表面特征
"""


CHAT_PROMPT = """你是村里种了一辈子地的老把式，跟农户说话要亲切、质朴、接地气。
用大白话回答种植问题：
1. 用"咱"、"老乡"、"地里"、"庄稼"这种词，别用书面语
2. 像邻居大叔教你种地一样，语气亲热，不端着
3. 优先给田间管理建议，不编造知识
4. 输出Markdown格式，简短实在，别啰嗦
"""


def parse_diag(text):
    """从模型回复里挖出 JSON，兼容代码块和前后夹带文字的情况。"""
    if not text:
        return None
    t = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            return json.loads(t[i:j + 1])
        except Exception:
            return None
    return None


def clean_diag(d):
    """字段清洗：拦掉越界值，避免前端渲染出畸形表格。"""
    if not isinstance(d, dict):
        return None

    def s(k, limit=120):
        v = d.get(k, "")
        if v is None:
            return ""
        if not isinstance(v, str):
            v = str(v)
        return v.strip()[:limit]

    verdict = s("verdict", 12) or "疑似"
    if verdict not in ("确诊", "疑似", "不敢断"):
        verdict = "疑似"

    try:
        conf = int(float(d.get("confidence", 0)))
    except Exception:
        conf = 0
    conf = max(0, min(100, conf))

    severity = s("severity", 4)
    if severity not in ("轻", "中", "重"):
        severity = severity or "中"

    stage = s("stage", 8)

    cands = []
    raw_c = d.get("candidates")
    if isinstance(raw_c, list):
        for c in raw_c[:3]:
            if isinstance(c, dict) and c.get("name"):
                try:
                    p = int(float(c.get("confidence", 0)))
                except Exception:
                    p = 0
                cands.append({"name": str(c["name"])[:40], "confidence": max(0, min(100, p))})

    return {
        "crop": s("crop", 20) or "未辨识",
        "verdict": verdict,
        "disease": s("disease", 40) or "暂不能确定",
        "confidence": conf,
        "evidence": s("evidence", 80),
        "severity": severity,
        "stage": stage,
        "window": s("window", 60),
        "prescription": s("prescription", 300),
        "fieldnote": s("fieldnote", 80),
        "candidates": cands,
    }


@app.get("/")
async def index():
    return FileResponse("index.html")


# ===== 天气：先用国内源（校园网/热点常连不上境外接口）=====
ITBOY_URL = "http://t.weather.itboy.net/api/weather/city/101090201"  # 保定

TYPE2CODE = {
    "雷阵雨": 95, "雨夹雪": 68, "冻雨": 66,
    "暴雨": 65, "大雨": 65, "阵雨": 80, "中雨": 63, "小雨": 61,
    "大雪": 75, "中雪": 73, "小雪": 71,
    "阴": 3, "雾": 45, "霾": 45, "浮尘": 45, "多云": 1, "少云": 1, "晴": 0,
}


def _num(v):
    """从 '高温 15℃' / '76%' / 12 里抠出数字。"""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group()) if m else None


def _code_of(text):
    for k, v in TYPE2CODE.items():
        if k in (text or ""):
            return v
    return 3


def _rain_of(text):
    t = text or ""
    if "雨" in t:
        return 75 if ("大" in t or "暴" in t) else 55
    if "雪" in t:
        return 60
    if "阴" in t:
        return 20
    if "云" in t:
        return 10
    return 0


def _hourly_series(hi, lo, hum, wind, code, rain, base):
    """接口只给日高温低温，用一条正弦曲线折算成逐时温度（峰 14 时，谷 2 时）。"""
    out = {
        "time": [], "temperature_2m": [], "relative_humidity_2m": [],
        "precipitation_probability": [], "weather_code": [], "wind_speed_10m": [],
    }
    peak = 14
    for i in range(48):
        t = base + datetime.timedelta(hours=i)
        phase = (t.hour - peak) % 24
        ratio = 0.5 + 0.5 * math.cos(2 * math.pi * phase / 24)
        temp = round(lo + (hi - lo) * ratio, 1)
        h = max(30, min(99, round(hum + 8 * (1 - ratio))))
        out["time"].append(t.strftime("%Y-%m-%dT%H:%M"))
        out["temperature_2m"].append(temp)
        out["relative_humidity_2m"].append(h)
        out["precipitation_probability"].append(rain)
        out["weather_code"].append(code)
        out["wind_speed_10m"].append(round(wind, 1))
    return out


def _convert_itboy(d):
    data = d.get("data") or {}
    fc = (data.get("forecast") or [{}])[0]
    t_now = _num(data.get("wendu")) or 0
    hi = _num(fc.get("high")) or t_now + 3
    lo = _num(fc.get("low")) or t_now - 6
    hum = _num(data.get("shidu")) or 55
    lv = _num(fc.get("fl")) or 2
    wind = {0: 0.5, 1: 3, 2: 9, 3: 16, 4: 24, 5: 34, 6: 44, 7: 56}.get(int(lv), 9)
    typ = (fc.get("type") or "晴").strip()
    code = _code_of(typ)
    rain = _rain_of(typ)
    base = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    return {
        "source": "itboy",
        "city": (d.get("cityInfo") or {}).get("city", "保定"),
        "current": {
            "time": base.strftime("%Y-%m-%dT%H:%M"),
            "temperature_2m": t_now,
            "relative_humidity_2m": hum,
            "precipitation": 0,
            "precipitation_probability": rain,
            "weather_code": code,
            "wind_speed_10m": wind,
        },
        "hourly": _hourly_series(hi, lo, hum, wind, code, rain, base),
    }


_weather_cache = {"ts": 0.0, "data": None}


@app.get("/weather")
def weather():
    now = time.time()
    if _weather_cache["data"] and (now - _weather_cache["ts"] < 300):
        return _weather_cache["data"]
    try:
        r = requests.get(ITBOY_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        d = r.json()
        if d.get("status") == 200 and d.get("data"):
            payload = _convert_itboy(d)
            _weather_cache["ts"] = time.time()
            _weather_cache["data"] = payload
            print("【天气】来源 itboy，", payload["current"]["temperature_2m"], "℃")
            return payload
        print("【天气异常】返回状态", d.get("status"), d.get("message"))
    except Exception as e:
        print("【天气异常】", repr(e))
    if _weather_cache["data"]:
        return _weather_cache["data"]
    return JSONResponse({"error": "weather unavailable"}, status_code=503)


def _trim_white(im, pad_ratio=0.07):
    """白底标本照把四周空白裁掉，让叶片占满画面。
    模型要量「病斑长度 ÷ 叶片横宽」，画面里叶片越大，比例越算得准。
    田间实拍的背景不白，裁不动就原样返回，不会误伤。"""
    try:
        g = im.convert("L")
        mask = g.point(lambda v: 0 if v > 244 else 255)
        bbox = mask.getbbox()
        if not bbox:
            return im
        w, h = im.size
        x0, y0, x1, y1 = bbox
        pad = int(max(w, h) * pad_ratio)
        nx0 = max(0, x0 - pad); ny0 = max(0, y0 - pad)
        nx1 = min(w, x1 + pad); ny1 = min(h, y1 + pad)
        if (nx1 - nx0) * (ny1 - ny0) < w * h * 0.35:
            return im
        if (nx1 - nx0) < w * 0.25 or (ny1 - ny0) < h * 0.25:
            return im
        return im.crop((nx0, ny0, nx1, ny1))
    except Exception:
        return im


# ===== 病害诊断（千问识图 → 结构化诊断单）=====
@app.post("/vision")
async def vision(image: UploadFile = File(...), crop: str = Form("")):
    try:
        img_bytes = await image.read()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img = _trim_white(img)
        if max(img.size) > 1600:
            img.thumbnail((1600, 1600))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=92)
        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        img_data_url = f"data:image/jpeg;base64,{img_b64}"

        crop = (crop or "").strip()[:20]
        if crop:
            crop_hint = "农户已指定这次拍的是「%s」，以它为准，不要改成别的作物。" % crop
        else:
            crop_hint = "农户没指定作物，请先看清叶片和茎秆判断是哪种作物，写进 crop 字段。"

        headers = {"Authorization": f"Bearer {DASHSCOPE_API_KEY}"}
        url = f"{DASHSCOPE_BASE_URL}/chat/completions"

        # 第一步：只让它观察。病名一掺进去，模型就会先押一个答案再凑理由，
        #         大斑小斑这种靠比例区分的，押错的概率很高。
        obs_payload = {
            "model": "qwen3-vl-plus",
            "messages": [
                {"role": "system", "content": OBSERVE_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": crop_hint + "把这张照片里的病斑特征如实记下来。"},
                    {"type": "image_url", "image_url": {"url": img_data_url}}
                ]}
            ],
            "temperature": 0
        }
        try:
            ro = requests.post(url, json=obs_payload, headers=headers, timeout=60)
            print("【观察状态】", ro.status_code)
            obs_text = ""
            if ro.status_code == 200 and "choices" in ro.json():
                obs_text = ro.json()["choices"][0]["message"]["content"].strip()
            print("【观察记录】", obs_text[:300])
        except Exception as eo:
            print("【观察失败】", repr(eo))
            obs_text = ""

        # 第二步：拿着观察记录做判断。有记录就纯文字研判，没记录就退回带图一步问。
        if obs_text:
            messages = [
                {"role": "system", "content": VISION_PROMPT + (DIAG_BRIDGE % obs_text)},
                {"role": "user", "content": crop_hint + "按格式输出诊断单 JSON。"}
            ]
        else:
            messages = [
                {"role": "system", "content": VISION_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": crop_hint + "按格式输出这张叶片的诊断单 JSON。"},
                    {"type": "image_url", "image_url": {"url": img_data_url}}
                ]}
            ]
        payload = {"model": "qwen3-vl-plus", "messages": messages, "temperature": 0}
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        print("【千问状态】", r.status_code)
        res = r.json()

        if "choices" not in res:
            print("【千问错误】", res.get("error", {}).get("message", "未知"))
            return {"ok": False, "error": "识图服务没有应答，稍后再试一次。"}

        raw = res["choices"][0]["message"]["content"]
        print("【千问原文】", raw[:400])

        diag = parse_diag(raw)
        cleaned = clean_diag(diag) if diag else None
        if not cleaned:
            return {"ok": False, "error": "本报读不懂这次的诊断，请重拍一张更清晰的叶片照片。"}

        return {"ok": True, "diag": cleaned, "obs": obs_text[:600]}

    except Exception as e:
        print("【异常】", repr(e))
        return {"ok": False, "error": "识病先生这会儿没应声，稍等片刻再传一次。"}


# ===== 农事问答（DeepSeek）=====
@app.post("/chat")
async def chat(data: dict):
    try:
        msg = data.get("msg", "")
        if not msg:
            return {"content": "你想问点啥？说清楚些。"}
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": CHAT_PROMPT},
                    {"role": "user", "content": msg}
                ],
                "temperature": 0.3,
                "max_tokens": 400
            },
            timeout=60
        )
        res = resp.json()
        print("【问答状态】", resp.status_code)
        if "choices" in res:
            return {"content": res["choices"][0]["message"]["content"]}
        return {"content": "回答出错了，请稍后再试"}
    except Exception as e:
        print("【问答异常】", repr(e))
        return {"content": "老把式这会儿不在，换句话再问问。"}


if __name__ == "__main__":
    import os
    import uvicorn

    # 绑 0.0.0.0 才能让同一 WiFi 下的手机访问；电脑本机仍用 127.0.0.1 打开
    port = int(os.environ.get("PORT", 80))   # 默认 80，手机只输 IP 就能开
    uvicorn.run("main:app", host="0.0.0.0", port=port)
