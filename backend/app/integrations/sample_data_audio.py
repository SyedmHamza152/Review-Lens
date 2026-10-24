"""SAMPLE corpus - wireless earbuds archetype (DEMONSTRATION DATA ONLY)."""

# (platform, text, rating, days_ago, variant)
EARBUDS_ITEMS: list[tuple[str, str, float | None, int, str | None]] = [
    # --- Daraz ---
    ("daraz", "Sound quality kamaal ki hai is price par, bass zabardast.", 5, 10, "Black"),
    ("daraz", "Ek side kaam nahi kar rahi after 2 weeks, bekar product.", 1, 9, "White"),
    ("daraz", "قیمت کم اور کوالٹی اچھی، ڈیلیوری جلدی ہوئی۔", 4, 22, None),
    ("daraz", "Call quality thori weak hai but music mast hai.", 3, 30, "Black"),
    ("daraz", "Original hain, box sealed tha. Paisay wasool!", 5, 48, None),
    ("daraz", "Charging case ka hinge toot gaya 1 hafte mein, ghatiya material.", 2, 15, "White"),
    # --- Amazon ---
    ("amazon", "Sound is crisp and bass is deep. Best budget earbuds I have used!", 5, 35, "Black"),
    ("amazon", "Left earbud stopped pairing after a month. Poor quality control.", 2, 20, "White"),
    ("amazon", "Battery lasts 5 hours per charge as advertised. Genuine product.", 5, 70, None),
    ("amazon", "They are okay for calls but the case feels flimsy.", 3, 52, None),
    ("amazon", "Comfortable fit, stayed in ears during workout. Worth the price.", 4, 90, "Black"),
    ("amazon", "Mic quality is terrible, other person cannot hear clearly.", 1, 26, None),
    # --- AliExpress ---
    ("aliexpress", "Shipping slow thi lekin product original aur packing sealed thi.", 4, 40, None),
    ("aliexpress", "Sound quality theek hai but mic quality ghatiya hai calls ke liye.", 2, 33, None),
    ("aliexpress", "بہت اچھی کوالٹی ہے اور قیمت بھی مناسب ہے۔", 5, 60, None),
    ("aliexpress", "Touch controls are responsive and pairing is fast. Good buy.", 4, 85, "Black"),
    # --- Alibaba ---
    ("alibaba", "Bulk order for office, all units working fine so far.", 4, 100, None),
    ("alibaba", "Supplier sent wrong color variant, replacement took another month.", 2, 65, None),
    # --- Temu ---
    ("temu", "Good sound for the price but touch controls are annoying sometimes.", 3, 18, None),
    ("temu", "Case arrived scratched, earbuds are fine though.", 3, 44, None),
    # --- SHEIN ---
    ("shein", "Aesthetic case design, sound quality was better than expected.", 4, 28, "White"),
    # --- Reddit ---
    ("reddit", "ANC is surprisingly decent, but battery drops fast with ANC on.", None, 42, None),
    ("reddit", "Ye buds 3k mein best hain, sound zabardast aur fit bhi acha.", None, 25, None),
    ("reddit", "Case hinge toota after 1 month, durability weak hai in ki.", None, 36, None),
    ("reddit", "Anyone facing connection drops with the left bud? Mine disconnects randomly.", None, 12, None),
    # --- YouTube ---
    ("youtube", "Detailed review: bass heavy, mids thora kam, overall value for money.", None, 55, None),
    ("youtube", "Mic test: calls mein awaz saaf nahi aati, traffic noise aa jati hai.", None, 30, None),
    ("youtube", "In earbuds ka sound signature warm hai, music lovers ke liye sahi hai.", None, 78, None),
    # --- X ---
    ("x", "Naye buds ka bass level dekho, kamaal!", None, 8, None),
    ("x", "Charging case kharab ho gaya 2 hafton mein, bakwas quality.", None, 24, None),
    # --- Facebook ---
    ("facebook", "Kisi ne ye buds use kiye hain? Opinions chahiye before ordering.", None, 16, None),
    ("facebook", "Bhai sound bohat achi hai in ki, paisay wasool.", None, 50, None),
    # --- Instagram ---
    ("instagram", "Aesthetic aur sound dono on point!", None, 20, None),
    ("instagram", "Case ka finish premium hai, impressed.", None, 62, None),
    # --- TikTok ---
    ("tiktok", "Bass test video: sound zabardast hai is price mein.", None, 13, None),
    ("tiktok", "Ek hafta use kiya, ab tak koi masla nahi.", None, 34, None),
]
