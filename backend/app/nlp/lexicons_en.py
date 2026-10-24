"""English sentiment lexicon (compact VADER-style with weights).

Score range: about -2..+2. Phrases are matched before unigrams.
"""

EN_POSITIVE: dict[str, float] = {
    "amazing": 2.0, "excellent": 2.0, "outstanding": 2.0, "perfect": 2.0,
    "flawless": 1.9, "superb": 1.8, "best": 1.8, "fantastic": 1.8,
    "love": 1.8, "loved": 1.8, "loving": 1.5, "brilliant": 1.6,
    "awesome": 1.6, "great": 1.5, "recommend": 1.5, "recommended": 1.5,
    "impressed": 1.5, "impressive": 1.5, "gem": 1.4, "beautiful": 1.3,
    "satisfied": 1.3, "happy": 1.2, "good": 1.2, "worth": 1.2,
    "reliable": 1.3, "durable": 1.2, "sturdy": 1.1, "premium": 1.0,
    "solid": 1.0, "responsive": 1.0, "smooth": 1.0, "crisp": 0.9,
    "fast": 0.8, "snappy": 1.0, "genuine": 1.0, "original": 0.8,
    "decent": 0.7, "nice": 1.0, "helpful": 1.0, "comfortable": 1.0,
    "value": 0.9, "works": 0.7, "working": 0.7, "fine": 0.6,
    "okay": 0.3, "ok": 0.3, "alright": 0.4, "satisfactory": 0.6,
    "thankyou": 0.6, "thanks": 0.5, "bargain": 1.0, "affordable": 0.9,
    "stunning": 1.6, "powerful": 1.2, "sharp": 0.8, "clear": 0.7,
    "accurate": 1.0, "fresh": 0.6, "soft": 0.6, "lightweight": 0.6,
    "longlasting": 1.0, "immaculate": 1.6, "5star": 1.6, "musthave": 1.4,
}

EN_NEGATIVE: dict[str, float] = {
    "terrible": -2.0, "awful": -2.0, "horrible": -2.0, "worst": -2.0,
    "garbage": -2.0, "scam": -2.0, "counterfeit": -2.0, "fraud": -2.0,
    "waste": -1.8, "useless": -1.8, "defective": -1.8, "fake": -1.8,
    "trash": -1.8, "hate": -1.8, "disaster": -1.7, "broken": -1.5,
    "damaged": -1.5, "cracked": -1.5, "disappointed": -1.5,
    "disappointing": -1.5, "poor": -1.3, "bad": -1.2, "flimsy": -1.3,
    "laggy": -1.1, "overheats": -1.3, "overheating": -1.3, "dead": -1.4,
    "uselessless": -1.8, "refund": -0.7, "return": -0.6, "returned": -0.6,
    "late": -0.9, "delayed": -1.0, "delay": -0.9, "missing": -1.0,
    "overpriced": -1.3, "pricey": -0.8, "costly": -1.0, "expensive": -0.9,
    "annoying": -1.1, "uncomfortable": -1.1, "cheap": -0.7,
    "slow": -0.8, "buggy": -1.2, "glitchy": -1.2, "faulty": -1.5,
    "smell": -0.7, "stinky": -1.0, "ripped": -1.3, "faded": -0.9,
    "unusable": -1.7, "regret": -1.5, "avoid": -1.2, "rubbish": -1.8,
    "weak": -1.1, "pathetic": -1.8, "cheapquality": -1.5, "unreliable": -1.4,
    "stopped": -0.9, "stoppedworking": -1.8, "unresponsive": -1.3,
    "hanging": -1.0, "hangs": -1.0, "blown": -1.3, "peeling": -1.1,
    "itchy": -0.9, "tight": -0.5, "loose": -0.5, "flawed": -1.2,
    "mediocre": -0.8, "subpar": -1.2, "notgood": -1.4,
}

# Multi-word phrases checked on the normalized token stream first.
EN_PHRASES: dict[str, float] = {
    "value for money": 1.6, "worth every penny": 1.9, "worth the price": 1.5,
    "money well spent": 1.6, "highly recommended": 1.8, "must buy": 1.6,
    "go for it": 1.3, "works fine": 1.0, "works perfectly": 1.7,
    "works great": 1.6, "as advertised": 1.1, "as described": 1.0,
    "five stars": 1.6, "top notch": 1.7, "well built": 1.4,
    "build quality is good": 1.4, "build quality is great": 1.6,
    "battery life is good": 1.3, "battery backup is good": 1.3,
    "not recommended": -1.6, "waste of money": -1.9, "waste of time": -1.6,
    "total waste": -1.7, "stopped working": -1.8, "never buy": -1.8,
    "dont buy": -1.7, "do not buy": -1.7, "don t buy": -1.7,
    "money wasted": -1.7, "total scam": -2.0, "fake product": -1.9,
    "first copy": -1.4, "not original": -1.6, "poor quality": -1.6,
    "bad quality": -1.4, "cheap quality": -1.5, "low quality": -1.4,
    "worst experience": -1.8, "worst product": -1.8, "battery drains": -1.4,
    "battery life is bad": -1.4, "not worth": -1.5, "camera is good": 1.3,
    "sound quality is good": 1.3, "sound quality is great": 1.5,
    "delivery was fast": 1.1, "delivery was quick": 1.1,
    "delivery was late": -1.2, "arrived late": -1.1, "arrived damaged": -1.5,
    "box was damaged": -1.2, "customer service is bad": -1.5,
    "customer support is bad": -1.5, "no response": -1.1,
    "thanks a lot": 0.4,  # can be sarcastic; sarcasm heuristics handle it
}

EN_NEGATORS = {
    "not", "no", "never", "none", "nobody", "nothing", "neither", "nor",
    "isnt", "wasnt", "arent", "werent", "dont", "doesnt", "didnt", "cant",
    "wont", "cannot", "couldnt", "shouldnt", "wouldnt", "without", "hardly",
    "barely", "lack", "lacks", "lacking", "zero",
}

EN_INTENSIFIERS = {
    "very": 1.4, "really": 1.35, "extremely": 1.6, "absolutely": 1.5,
    "totally": 1.45, "super": 1.4, "incredibly": 1.55, "truly": 1.35,
    "highly": 1.4, "so": 1.2, "such": 1.2, "damn": 1.3, "insanely": 1.5,
    "completely": 1.45, "utterly": 1.5, "v": 1.3, "fully": 1.3,
}

EN_DIMINISHERS = {
    "slightly": 0.6, "somewhat": 0.7, "bit": 0.65, "little": 0.7,
    "kinda": 0.7, "kind": 0.75, "almost": 0.7, "mostly": 0.75,
    "partially": 0.7, "mildly": 0.65,
}

EN_ADVERSATIVES = {"but", "however", "although", "though", "yet", "except", "nevertheless", "whereas"}

EN_MARKERS = {
    # common function words that mark English
    "the", "a", "an", "is", "are", "was", "were", "this", "that", "with",
    "for", "have", "has", "had", "you", "your", "it", "its", "of", "to",
    "in", "on", "my", "me", "i", "im", "ive", "very", "really", "product",
    "quality", "battery", "camera", "price", "value", "buy", "using",
    "used", "after", "week", "month", "day", "good", "great", "not",
    "and", "but", "or", "if", "when", "then", "there", "their", "from",
    "they", "them", "we", "our", "will", "would", "can", "could", "should",
    "get", "got", "one", "all", "about", "just", "been", "be",
}
