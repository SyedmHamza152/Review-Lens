"""SAMPLE corpus - smartphone archetype.

DEMONSTRATION DATA ONLY: these comments are curated synthetic examples
written to exercise the analysis pipeline (English / Urdu script / Roman
Urdu / mixed, sarcasm, spam, seller-vs-product complaints). They are always
labelled `data_source="sample"` in the database and shown with a prominent
SAMPLE badge in the UI. They are NEVER presented as real collected reviews.
"""

# (platform, text, rating, days_ago, variant)
PHONE_ITEMS: list[tuple[str, str, float | None, int, str | None]] = [
    # --- Daraz ---
    ("daraz", "Bohat acha phone hai is price mein, camera or battery dono zabardast. Delivery bhi 2 din mein mil gayi.", 5, 12, "8GB+256GB Black"),
    ("daraz", "Battery backup kamaal ka hai, sara din chalta hai heavy use par bhi.", 5, 25, "8GB+256GB Black"),
    ("daraz", "Packing sealed thi lekin charger missing tha, seller se contact kiya koi response nahi aya.", 2, 8, "12GB+512GB Titanium"),
    ("daraz", "Display bohat achi hai, colors crisp hain. Value for money!", 4, 40, "12GB+512GB Titanium"),
    ("daraz", "Ye product bohat acha hai, paisay wasool hain.", 5, 55, None),
    ("daraz", "Phone original hai, PTA approved, sab theek. Shukriya seller.", 5, 90, "8GB+256GB Black"),
    ("daraz", "قیمت کے لحاظ سے بہترین فون ہے، کیمرہ بہت اچھا ہے لیکن بیٹری اوسط ہے۔", 4, 15, None),
    ("daraz", "Seller ne jaali product bheja hai, box seal nahi tha. Paisay barbaad.", 1, 5, None),
    ("daraz", "Quality achi hai but delivery bohat late thi, 12 din lag gaye.", 3, 20, None),
    ("daraz", "Design sundar hai lekin performance thori slow hai.", 3, 48, "8GB+256GB Black"),
    # --- Amazon ---
    ("amazon", "The camera is amazing, but the battery is terrible. Drains within 3 hours.", 3, 30, "256GB"),
    ("amazon", "Excellent build quality, feels premium in hand. Display is stunning.", 5, 45, "512GB Titanium Gray"),
    ("amazon", "Stopped working after 10 days. Total waste of money, requesting refund.", 1, 7, "256GB"),
    ("amazon", "Fast shipping, well packaged, genuine product with proper warranty card.", 5, 60, None),
    ("amazon", "Performance is smooth, no lag even with heavy gaming. Highly recommended.", 5, 100, "512GB Titanium Gray"),
    ("amazon", "Overpriced for what it offers. Previous model was better value for money.", 2, 75, None),
    ("amazon", "Good phone overall but charging speed is slow, takes almost 2 hours.", 3, 35, "256GB"),
    ("amazon", "This product is excellent, and the quality is worth the price.", 5, 120, None),
    # --- AliExpress ---
    ("aliexpress", "Shipping took 3 weeks but product is genuine and works perfectly.", 4, 50, None),
    ("aliexpress", "Camera zabardast hai lekin delivery bohat late thi.", 3, 18, None),
    ("aliexpress", "یہ پروڈکٹ بہت اچھی ہے اور قیمت کے لحاظ سے بہترین ہے۔", 5, 28, None),
    ("aliexpress", "Packaging was damaged on arrival but phone is fine. Seller responded quickly.", 4, 42, None),
    ("aliexpress", "Not original as described, screen protector was already applied and scratched.", 2, 14, None),
    ("aliexpress", "Display quality bohat achi hai is range mein, gaming smooth chalta hai.", 4, 65, None),
    # --- Alibaba ---
    ("alibaba", "Bulk order received, all units genuine with proper invoice. Good supplier.", 4, 80, None),
    ("alibaba", "Supplier communication was poor, shipment delayed by two weeks.", 2, 55, None),
    ("alibaba", "قیمت مناسب ہے اور کوالٹی عمدہ ہے۔", 4, 110, None),
    # --- Temu ---
    ("temu", "Surprisingly good for the price, camera quality decent in daylight.", 4, 22, None),
    ("temu", "Battery drains fast and the phone heats up while charging.", 2, 30, None),
    # --- SHEIN ---
    ("shein", "Cute color options, phone case quality was better than expected.", 4, 26, None),
    ("shein", "Took forever to arrive, packaging was torn.", 2, 38, None),
    # --- Reddit ---
    ("reddit", "Been using this phone for 3 months now. Build quality is solid, no issues. Camera is brilliant in low light.", None, 85, None),
    ("reddit", "Battery life is disappointing, barely 4 hours screen on time. My old phone lasted way longer.", None, 40, None),
    ("reddit", "Ye phone lena chahiye ya nahi? Reviews mixed hain, kuch keh rahe hain battery weak hai.", None, 15, None),
    ("reddit", "Wah kya product hai, 2 din mein hang hone laga hai. Great going.", None, 9, None),
    ("reddit", "PTA approved version lena warna signal issues hoti hain. Original le to best hai is range mein.", None, 60, None),
    ("reddit", "Performance wise no complaints, but customer support is useless. No response to warranty claim.", None, 50, None),
    ("reddit", "صرف نمبر کا فون ہے، بیٹری بالکل نہیں چلتی۔", None, 33, None),
    ("reddit", "Camera zabardast hai lekin battery bilkul achi nahi.", None, 20, None),
    # --- YouTube ---
    ("youtube", "Full review: display 10/10, camera 9/10, battery 6/10 thori weak hai is price par.", None, 70, None),
    ("youtube", "Mere pass 6 months se hai, koi issue nahi aya. Zabardast phone!", None, 95, None),
    ("youtube", "Overpriced flagship honestly. Previous generation was better value.", None, 45, None),
    ("youtube", "Gaming performance is impressive, PUBG runs smooth on high settings.", None, 25, None),
    ("youtube", "اس فون کا کیمرہ شاندار ہے لیکن قیمت زیادہ ہے۔", None, 55, None),
    ("youtube", "Heating issue while charging, otherwise decent phone for daily use.", None, 12, None),
    # --- X ---
    ("x", "New phone day 1: camera amazing, battery terrible by evening. Mixed feelings.", None, 6, None),
    ("x", "Paisay wasool product hai yar, sab kuch smooth chalta hai.", None, 30, None),
    ("x", "Daraz pe is phone ki delivery bohat late thi but product original nikla.", None, 22, None),
    ("x", "Worst customer service ever, no response from the brand for 2 weeks.", None, 40, None),
    ("x", "قیمت کے لحاظ سے بہترین، کمال کا فون ہے۔", None, 65, None),
    # --- Facebook ---
    ("facebook", "Bhai ye phone original hai ya first copy? Koi experience share kare.", None, 18, None),
    ("facebook", "Zabardast phone hai, main ne bhi order kiya tha, waqt par mila.", None, 44, None),
    ("facebook", "Battery backup kamzor hai lekin camera is range mein best hai.", None, 58, None),
    ("facebook", "Seller ne galti se galat variant bheja, phir jaldi replace kar diya. Good service.", None, 72, None),
    # --- Instagram ---
    ("instagram", "Unboxing done! Packaging premium thi, phone looks stunning.", None, 14, None),
    ("instagram", "Camera samples dekho, quality achi hai but video stabilization weak hai.", None, 36, None),
    ("instagram", "Is price mein is se acha phone nahi milta, guaranteed.", None, 88, None),
    ("instagram", "Battery life ka pata nahi kabhi kabhi din khatam hone se pehle hi band ho jata hai.", None, 28, None),
    # --- TikTok ---
    ("tiktok", "POV: naya phone liya aur battery 3 ghante mein khatam. Bekar!", None, 11, None),
    ("tiktok", "Ye phone bohat acha hai guys, link bio mein hai!", None, 5, None),
    ("tiktok", "Camera test kar liya, quality zabardast hai.", None, 26, None),
    ("tiktok", "عام استعمال کے لیے ٹھیک ہے، گیمنگ کے لیے نہیں۔", None, 48, None),
]
