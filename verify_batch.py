#!/usr/bin/env python3
"""Verify restaurant addresses and coordinates in batches."""
import csv, json, math, sys, time, urllib.parse, urllib.request

CSV_PATH = "restaurants.csv"
USER_AGENT = "mothers-day-restaurant-verifier/1.0 (emily@liveti.me)"

BOROUGH_QUERY = {
    "Manhattan": "Manhattan, New York, NY",
    "Brooklyn": "Brooklyn, New York, NY",
    "Queens": "Queens, New York, NY",
    "Bronx": "Bronx, New York, NY",
    "Staten Island": "Staten Island, New York, NY",
    "New Jersey": "New Jersey",
}

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def geocode(query):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 3, "addressdetails": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def best_result(results, borough):
    """Pick the result that best matches the borough."""
    if not results or isinstance(results, dict):
        return None
    boro_lower = borough.lower() if borough else ""
    for r in results:
        display = r.get("display_name", "").lower()
        if boro_lower and boro_lower in display:
            return r
        if borough == "Manhattan" and "new york county" in display:
            return r
        if borough == "Brooklyn" and "kings county" in display:
            return r
        if borough == "Queens" and "queens county" in display:
            return r
        if borough == "Bronx" and "bronx county" in display:
            return r
    return results[0]

def verify(r):
    addr = r["address"]
    boro = r["borough"]
    boro_q = BOROUGH_QUERY.get(boro, boro)
    query = f"{addr}, {boro_q}"
    results = geocode(query)
    if isinstance(results, dict) and "error" in results:
        return {"status": "error", "msg": results["error"]}
    if not results:
        # Try without exact address (street-level)
        results = geocode(f"{addr}, {boro_q}".replace("&", "and"))
    if not results:
        return {"status": "not_found"}
    pick = best_result(results, boro)
    glat, glng = float(pick["lat"]), float(pick["lon"])
    slat, slng = float(r["lat"]), float(r["lng"])
    dist = haversine(slat, slng, glat, glng)
    return {
        "status": "ok",
        "dist_m": round(dist, 1),
        "geo_lat": glat,
        "geo_lng": glng,
        "matched": pick.get("display_name", ""),
    }

def main():
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    start = (batch - 1) * size
    end = start + size

    with open(CSV_PATH) as f:
        rows = list(csv.DictReader(f))
    wishlist = [r for r in rows if r["status"] == "wishlist"]
    chunk = wishlist[start:end]
    print(f"# Batch {batch}: {len(chunk)} restaurants (wishlist {start+1}-{start+len(chunk)} of {len(wishlist)})\n")
    print(f"{'id':>4} {'name':<32} {'address':<30} {'boro':<10} {'dist':>7}  flag")
    print("-" * 110)
    out = []
    for r in chunk:
        v = verify(r)
        flag = ""
        if v["status"] == "error":
            flag = f"ERR: {v['msg']}"
        elif v["status"] == "not_found":
            flag = "NOT_FOUND"
        else:
            d = v["dist_m"]
            if d > 500:
                flag = f"⚠️  FAR ({d:.0f}m) -> {v['matched'][:70]}"
            elif d > 100:
                flag = f"check ({d:.0f}m)"
        dist_s = f"{v.get('dist_m','-'):>7}" if v["status"] == "ok" else f"{'-':>7}"
        print(f"{r['id']:>4} {r['name'][:32]:<32} {r['address'][:30]:<30} {r['borough'][:10]:<10} {dist_s}  {flag}")
        out.append({**r, **v})
        time.sleep(1.05)  # Nominatim rate limit

    # Save batch results
    with open(f"batch_{batch}_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved batch_{batch}_results.json")

if __name__ == "__main__":
    main()
