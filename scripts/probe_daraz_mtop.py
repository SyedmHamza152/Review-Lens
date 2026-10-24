"""Probe Daraz mtop h5 gateway for review text + verify remaining platform endpoints."""
import hashlib
import json
import re
import time
from urllib.parse import quote

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
APP_KEY = "12574478"  # Daraz/Lazada web appKey used by daraz.pk storefront
ITEM_ID = "1957775263"  # iPhone 17 Pro Max from catalog
PRODUCT_URL = f"https://www.daraz.pk/products/apple-iphone-17-pro-max-512gb-i{ITEM_ID}.html"


def get_h5tk(sess: requests.Session) -> str:
    """Hit the mtop gateway once so it sets the _m_h5_tk cookie, return token."""
    t = str(int(time.time() * 1000))
    url = (
        f"https://api.daraz.pk/h5/mtop.daraz.product.review.getreviewlist/1.0/"
        f"?jsv=2.7.2&appKey={APP_KEY}&t={t}&sign=0&type=originaljson&dataType=json"
        f"&timeout=20000&api=mtop.daraz.product.review.getreviewlist&v=1.0"
        f"&data={quote(json.dumps({'itemId': ITEM_ID, 'pageSize': 5, 'pageNo': 1}))}"
    )
    r = sess.get(url, timeout=20)
    print("[h5tk bootstrap] HTTP", r.status_code, "body:", r.text[:200])
    tk = sess.cookies.get("_m_h5_tk", domain=".daraz.pk") or sess.cookies.get("_m_h5_tk")
    print("[h5tk cookie]:", tk)
    return (tk or "").split("_")[0]


def mtop_call(sess: requests.Session, token: str, api: str, data: dict, v: str = "1.0") -> dict:
    t = str(int(time.time() * 1000))
    data_str = json.dumps(data, separators=(",", ":"))
    sign = hashlib.md5(f"{token}&{t}&{APP_KEY}&{data_str}".encode()).hexdigest()
    url = (
        f"https://api.daraz.pk/h5/{api}/{v}/?jsv=2.7.2&appKey={APP_KEY}&t={t}&sign={sign}"
        f"&type=originaljson&dataType=json&timeout=20000&api={api}&v={v}"
        f"&data={quote(data_str)}"
    )
    r = sess.get(url, timeout=20)
    print(f"[{api}] HTTP {r.status_code} len={len(r.text)}")
    try:
        return r.json()
    except Exception:
        print("[{api}] non-JSON:", r.text[:300])
        return {}


def main() -> None:
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Referer": PRODUCT_URL, "Accept": "application/json, text/plain, */*"})

    # 1. Load product page (sets EGG_SESS / hng cookies)
    r = sess.get(PRODUCT_URL, timeout=25)
    print("[product page] HTTP", r.status_code, "bytes:", len(r.text))
    m = re.search(r'"itemId"\s*:\s*"?(\d{8,15})', r.text)
    print("[page itemId]:", m.group(1) if m else "not found")

    # 2. Bootstrap mtop token
    token = get_h5tk(sess)
    time.sleep(1)

    # 3. Signed review-list call
    for payload in (
        {"itemId": ITEM_ID, "pageSize": 20, "pageNo": 1, "filter": "", "sort": "0"},
        {"itemId": ITEM_ID, "pageSize": 20, "pageNo": 1},
        {"itemId": int(ITEM_ID), "pageSize": 20, "pageNo": 1},
    ):
        resp = mtop_call(sess, token, "mtop.daraz.product.review.getreviewlist", payload)
        if resp:
            print(json.dumps(resp, ensure_ascii=False)[:800])
            if resp.get("data") and not isinstance(resp["data"], dict):
                break
            if resp.get("data") and (resp["data"].get("reviewList") or resp["data"].get("list")):
                break
        time.sleep(1)


if __name__ == "__main__":
    main()
