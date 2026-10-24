"""Probe YouTube: InnerTube (no key) search + comments, and googleapis reachability."""
import json
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
WEB_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
CTX = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20241001.00.00",
                              "hl": "en", "gl": "PK"}}}


def post(url: str, payload: dict):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Accept-Language": "en-US,en;q=0.9", "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        return f"ERR: {e}"


def dig(obj, *keys):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def walk(node, key):
    """Yield all values of dict key anywhere in nested structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(node, list):
        for it in node:
            yield from walk(it, key)


# 1) search
res = post(f"https://www.youtube.com/youtubei/v1/search?key={WEB_KEY}&prettyPrint=false",
           {**CTX, "query": "cricket bat review"})
if isinstance(res, str):
    print("SEARCH:", res)
else:
    vids = [(vr.get("videoId"), dig(vr, "title", "runs", 0, "text"),
             dig(vr, "ownerText", "runs", 0, "text"))
            for vr in walk(res, "videoRenderer")]
    print(f"SEARCH OK: {len(vids)} videos")
    for v in vids[:5]:
        print("  ", v)

    # 2) comments page for first video
    vid = vids[0][0] if vids else None
    if vid:
        nxt = post(f"https://www.youtube.com/youtubei/v1/next?key={WEB_KEY}&prettyPrint=false",
                   {**CTX, "videoId": vid})
        if isinstance(nxt, str):
            print("NEXT:", nxt)
        else:
            cont = None
            for c in walk(nxt, "continuationCommand"):
                tok = c.get("token")
                if tok and len(tok) > 100:
                    cont = tok
                    break
            print("NEXT OK | continuation found:", bool(cont))

            if cont:
                cmt = post(f"https://www.youtube.com/youtubei/v1/next?key={WEB_KEY}&prettyPrint=false",
                           {**CTX, "continuation": cont})
                if isinstance(cmt, str):
                    print("COMMENTS:", cmt)
                else:
                    ents = list(walk(cmt, "commentEntityPayload"))
                    print(f"COMMENTS OK: {len(ents)} commentEntityPayloads")
                    for e in ents[:6]:
                        author = dig(e, "author", "displayName") or "?"
                        txt = (dig(e, "properties", "content", "content") or "")[:110]
                        likes = dig(e, "toolbar", "likeCountNotliked") or dig(e, "toolbar", "likeCountLiked")
                        when = dig(e, "properties", "publishedTime")
                        print(f"   [{author} | {when} | likes={likes}] {txt}")

# 3) official Data API domain reachability (needs user key later)
try:
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&type=video&maxResults=1&key=INVALID",
        headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        print("GOOGLEAPIS:", r.status)
except urllib.error.HTTPError as e:
    print("GOOGLEAPIS reachable, HTTP", e.code, "(400 expected for INVALID key)")
except Exception as e:  # noqa: BLE001
    print("GOOGLEAPIS ERR:", e)
