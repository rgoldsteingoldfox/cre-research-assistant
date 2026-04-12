"""Metro Atlanta county detection and property search URL generation."""

# Zip code ranges mapped to counties (metro Atlanta)
# Source: USPS zip code assignments
ZIP_TO_COUNTY = {}

# Fulton County zips
for z in [
    30301, 30302, 30303, 30304, 30305, 30306, 30307, 30308, 30309, 30310,
    30311, 30312, 30313, 30314, 30315, 30316, 30317, 30318, 30319, 30320,
    30321, 30322, 30324, 30325, 30326, 30327, 30328, 30329, 30330, 30331,
    30332, 30334, 30336, 30337, 30339, 30342, 30343, 30344, 30346, 30348,
    30349, 30350, 30353, 30354, 30355, 30356, 30357, 30358, 30359, 30361,
    30363, 30368, 30369, 30370, 30371, 30374, 30375, 30377, 30378, 30380,
    30384, 30385, 30388, 30392, 30394, 30396, 30398, 30399,
    30004, 30005, 30009, 30022, 30023, 30024, 30075, 30076, 30077,
    30213, 30268, 30272, 30291, 30331, 30349,
]:
    ZIP_TO_COUNTY[str(z)] = "Fulton"

# Cobb County zips
for z in [
    30006, 30007, 30008, 30060, 30061, 30062, 30063, 30064, 30065, 30066,
    30067, 30068, 30069, 30080, 30081, 30082, 30101, 30106, 30111, 30126,
    30127, 30131, 30133, 30134, 30135, 30136, 30137, 30139, 30141, 30144,
    30152, 30156, 30160, 30168, 30171, 30178, 30339,
]:
    ZIP_TO_COUNTY[str(z)] = "Cobb"

# DeKalb County zips
for z in [
    30002, 30012, 30021, 30030, 30031, 30032, 30033, 30034, 30035, 30036,
    30037, 30038, 30058, 30074, 30079, 30083, 30084, 30085, 30086, 30087,
    30088, 30316, 30317, 30319, 30322, 30324, 30329, 30340, 30341, 30345,
    30346, 30360,
]:
    ZIP_TO_COUNTY[str(z)] = "DeKalb"

# Gwinnett County zips
for z in [
    30010, 30011, 30017, 30019, 30024, 30042, 30043, 30044, 30045, 30046,
    30047, 30048, 30049, 30071, 30078, 30091, 30092, 30093, 30095, 30096,
    30097, 30098, 30099, 30340, 30360, 30501, 30515, 30517, 30518, 30519,
]:
    ZIP_TO_COUNTY[str(z)] = "Gwinnett"

# Cherokee County zips
for z in [
    30102, 30107, 30114, 30115, 30142, 30143, 30148, 30151, 30177, 30183,
    30188, 30189,
]:
    ZIP_TO_COUNTY[str(z)] = "Cherokee"

# Forsyth County zips
for z in [
    30028, 30040, 30041, 30097, 30518, 30519,
]:
    ZIP_TO_COUNTY[str(z)] = "Forsyth"

# Henry County zips
for z in [
    30228, 30236, 30248, 30252, 30253, 30281,
]:
    ZIP_TO_COUNTY[str(z)] = "Henry"

# Douglas County zips
for z in [
    30122, 30134, 30135, 30154,
]:
    ZIP_TO_COUNTY[str(z)] = "Douglas"

# Hall County zips
for z in [
    30501, 30502, 30503, 30504, 30506, 30507, 30542, 30548,
]:
    ZIP_TO_COUNTY[str(z)] = "Hall"

# Fayette County zips
for z in [
    30214, 30215, 30269, 30270, 30290,
]:
    ZIP_TO_COUNTY[str(z)] = "Fayette"

# Coweta County zips
for z in [
    30263, 30265, 30276, 30277,
]:
    ZIP_TO_COUNTY[str(z)] = "Coweta"

# Jackson County zips
for z in [
    30549, 30553, 30548,
]:
    ZIP_TO_COUNTY[str(z)] = "Jackson"

# Walton County zips
for z in [
    30655, 30656, 30025,
]:
    ZIP_TO_COUNTY[str(z)] = "Walton"

# Chatham County zips
for z in [
    31401, 31402, 31404, 31405, 31406, 31407, 31408, 31409, 31410,
    31411, 31412, 31414, 31415, 31416, 31419, 31420, 31421,
]:
    ZIP_TO_COUNTY[str(z)] = "Chatham"


# County-specific property search - use Google to find the assessor record
# Direct assessor URLs are unreliable (blocked, JS-rendered, broken deep links)
COUNTY_SEARCH_TEMPLATES = {
    "Fulton": "Fulton County GA tax assessor property",
    "Cobb": "Cobb County GA tax assessor property",
    "DeKalb": "DeKalb County GA tax assessor property",
    "Gwinnett": "Gwinnett County GA tax assessor property",
    "Cherokee": "Cherokee County GA tax assessor property",
    "Forsyth": "Forsyth County GA tax assessor property",
    "Henry": "Henry County GA tax assessor property",
    "Douglas": "Douglas County GA tax assessor property",
    "Hall": "Hall County GA tax assessor property",
    "Fayette": "Fayette County GA tax assessor property",
    "Coweta": "Coweta County GA tax assessor property",
    "Jackson": "Jackson County GA tax assessor property",
    "Walton": "Walton County GA tax assessor property",
    "Chatham": "Chatham County GA tax assessor property",
}

# County-specific qPublic property search (free, no login required)
COUNTY_QPUBLIC_URLS = {
    "Fulton": "https://qpublic.schneidercorp.com/Application.aspx?App=FultonCountyGA&Layer=Parcels&PageType=Search",
    "Cobb": "https://qpublic.schneidercorp.com/Application.aspx?App=CobbCountyGA&Layer=Parcels&PageType=Search",
    "DeKalb": "https://qpublic.schneidercorp.com/Application.aspx?App=DeKalbCountyGA&Layer=Parcels&PageType=Search",
    "Gwinnett": "https://qpublic.schneidercorp.com/Application.aspx?App=GwinnettCountyGA&Layer=Parcels&PageType=Search",
    "Cherokee": "https://qpublic.schneidercorp.com/Application.aspx?App=CherokeeCountyGA&Layer=Parcels&PageType=Search",
    "Forsyth": "https://qpublic.schneidercorp.com/Application.aspx?App=ForsythCountyGA&Layer=Parcels&PageType=Search",
    "Henry": "https://qpublic.schneidercorp.com/Application.aspx?App=HenryCountyGA&Layer=Parcels&PageType=Search",
    "Douglas": "https://qpublic.schneidercorp.com/Application.aspx?App=DouglasCountyGA&Layer=Parcels&PageType=Search",
    "Hall": "https://qpublic.schneidercorp.com/Application.aspx?App=HallCountyGA&Layer=Parcels&PageType=Search",
    "Fayette": "https://qpublic.schneidercorp.com/Application.aspx?App=FayetteCountyGA&Layer=Parcels&PageType=Search",
    "Coweta": "https://qpublic.schneidercorp.com/Application.aspx?App=CowetaCountyGA&Layer=Parcels&PageType=Search",
    "Jackson": "https://qpublic.schneidercorp.com/Application.aspx?App=JacksonCountyGA&Layer=Parcels&PageType=Search",
    "Walton": "https://qpublic.schneidercorp.com/Application.aspx?App=WaltonCountyGA&Layer=Parcels&PageType=Search",
    "Chatham": "https://qpublic.schneidercorp.com/Application.aspx?App=ChathamCountyGA&Layer=Parcels&PageType=Search",
}

# City-to-Municode slug mapping (for municipal code / zoning ordinance lookups)
CITY_MUNICODE_SLUGS = {
    "Atlanta": "atlanta",
    "Alpharetta": "alpharetta",
    "Roswell": "roswell",
    "Milton": "milton",
    "Johns Creek": "johns_creek",
    "Sandy Springs": "sandy_springs",
    "Dunwoody": "dunwoody",
    "Brookhaven": "brookhaven",
    "Marietta": "marietta",
    "Smyrna": "smyrna",
    "Kennesaw": "kennesaw",
    "Acworth": "acworth",
    "Woodstock": "woodstock",
    "Canton": "canton",
    "Cumming": "cumming",
    "Duluth": "duluth",
    "Lawrenceville": "lawrenceville",
    "Suwanee": "suwanee",
    "Norcross": "norcross",
    "Peachtree Corners": "peachtree_corners",
    "Decatur": "decatur",
    "Tucker": "tucker",
    "Stonecrest": "stonecrest",
    "East Point": "east_point",
    "College Park": "college_park",
    "Union City": "union_city",
    "Fairburn": "fairburn",
    "Palmetto": "palmetto",
    "Hapeville": "hapeville",
    "Chamblee": "chamblee",
    "Doraville": "doraville",
    "Clarkston": "clarkston",
    "Avondale Estates": "avondale_estates",
    "Pine Lake": "pine_lake",
    "Lithonia": "lithonia",
    "Powder Springs": "powder_springs",
    "Austell": "austell",
    "Mableton": "mableton",
    "Holly Springs": "holly_springs",
    "Ball Ground": "ball_ground",
    "Waleska": "waleska",
    "Mountain Park": "mountain_park",
}

# GA Secretary of State business search (for LLC/entity lookups)
GA_SOS_BUSINESS_SEARCH = "https://ecorp.sos.ga.gov/BusinessSearch"

# GSCCCA deed search (for property deed/grantor-grantee history)
GSCCCA_DEED_SEARCH = "https://search.gsccca.org/RealEstate/"


def detect_county(address):
    """Extract zip code from address and map to county."""
    import re
    match = re.search(r'\b(\d{5})(?:-\d{4})?\b', address)
    if match:
        zipcode = match.group(1)
        return ZIP_TO_COUNTY.get(zipcode, "Unknown")
    return "Unknown"


def get_property_search_url(address):
    """Get a Google search URL that finds the county assessor record for this address."""
    from urllib.parse import quote_plus
    county = detect_county(address)
    street = address.split(",")[0].strip()

    if county in COUNTY_SEARCH_TEMPLATES:
        query = f'{COUNTY_SEARCH_TEMPLATES[county]} "{street}"'
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        return county, url
    return county, None


def get_qpublic_url(address):
    """Get the qPublic property search URL for this address's county."""
    county = detect_county(address)
    return COUNTY_QPUBLIC_URLS.get(county, "")


def get_municode_url(city):
    """Get the Municode library URL for a city's municipal code / zoning ordinances."""
    city_clean = city.strip().title()
    slug = CITY_MUNICODE_SLUGS.get(city_clean, "")
    if slug:
        return f"https://library.municode.com/ga/{slug}"
    return ""


def get_ga_sos_url():
    """Get the GA Secretary of State business search URL."""
    return GA_SOS_BUSINESS_SEARCH


def get_gsccca_url():
    """Get the GSCCCA deed search URL."""
    return GSCCCA_DEED_SEARCH
