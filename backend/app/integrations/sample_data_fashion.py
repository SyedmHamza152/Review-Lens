"""SAMPLE corpus - sneakers archetype (DEMONSTRATION DATA ONLY)."""

# (platform, text, rating, days_ago, variant)
SNEAKERS_ITEMS: list[tuple[str, str, float | None, int, str | None]] = [
    # --- Daraz ---
    ("daraz", "Size thora chota le raha hai, ek size bara order karo. Quality achi hai.", 4, 14, "EU 42"),
    ("daraz", "جوتے اصل ہیں اور آرام دہ ہیں، قیمتیں بھی مناسب ہیں۔", 5, 26, None),
    ("daraz", "Color thora dull tha picture se, lekin fitting perfect hai.", 3, 38, "EU 43"),
    ("daraz", "Sole 2 hafte mein hi khul gaya, ghatiya maal.", 1, 10, None),
    ("daraz", "Original product mila, packing bhi achi thi. Shukriya!", 5, 58, "EU 42"),
    # --- Amazon ---
    ("amazon", "Comfortable for running, true to size, breathable material.", 5, 44, "EU 43"),
    ("amazon", "Laces frayed within two weeks, disappointed with the durability.", 2, 24, None),
    ("amazon", "Great design, gets compliments everywhere. Worth the price.", 5, 75, "EU 42"),
    ("amazon", "These are first copy, not original. Strong plastic smell also.", 1, 16, None),
    ("amazon", "Good grip and cushioning, using them for gym daily.", 4, 95, None),
    # --- AliExpress ---
    ("aliexpress", "Quality unexpected achi thi, delivery 2 hafte mein mili.", 4, 50, None),
    ("aliexpress", "Sole came off after light use, bekar product.", 1, 30, None),
    ("aliexpress", "آرام دہ جوتے ہیں، سائز بھی ٹھیک آیا۔", 4, 68, None),
    # --- Temu ---
    ("temu", "Surprisingly comfy for the price point.", 4, 20, None),
    ("temu", "Design sundar hai lekin material sasta lagta hai.", 2, 40, None),
    # --- SHEIN ---
    ("shein", "Colorway is fire! Quality feels premium for the price.", 5, 32, "EU 43"),
    ("shein", "Late delivery thi but shoes are cute and comfortable.", 3, 55, None),
    # --- Reddit ---
    ("reddit", "Daily walk ke liye perfect, 6 months chal gaye abhi tak.", None, 80, None),
    ("reddit", "Arch support nahi hai, lambe walk pe paon dukh jate hain.", None, 35, None),
    ("reddit", "Grip wet floor par kamzor hai, otherwise solid shoes.", None, 22, None),
    # --- YouTube ---
    ("youtube", "On-feet review: comfort 8/10, durability 6/10, style 9/10.", None, 60, None),
    ("youtube", "In shoes mein running ke liye cushioning achi hai.", None, 41, None),
    # --- X ---
    ("x", "In shoes ka comfort level next level hai yar.", None, 15, None),
    ("x", "Second week mein hi sole squeak karne laga, poor quality.", None, 28, None),
    # --- Facebook ---
    ("facebook", "Kya ye original hain ya copy? Koi bata de please.", None, 19, None),
    ("facebook", "Fitting achi hai, per delivery late thi 10 din.", None, 46, None),
    # --- Instagram ---
    ("instagram", "Photos se zyada acha lag raha hai real mein!", None, 27, None),
    # --- TikTok ---
    ("tiktok", "Unboxing: box perfect condition, shoes gorgeous.", None, 21, None),
    ("tiktok", "1 week later update: abhi tak solid, koi issue nahi.", None, 39, None),
]

# Cross-platform promotional spam examples (demonstrate spam filtering)
SPAM_ITEMS: list[tuple[str, str, float | None, int, str | None]] = [
    ("tiktok", "BIG SALE BIG SALE buy now click link in bio free coupon discount offer!", None, 3, None),
    ("facebook", "Order now whatsapp 0300-1234567 best price guarantee full stock available!", None, 6, None),
    ("x", "Check my page for discount codes and cashback offers, dm me now for deals!", None, 4, None),
    ("aliexpress", "Visit www.cheapdeals24.com for coupon codes on all products today!", None, 9, None),
]
