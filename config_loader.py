"""Configuration loading utilities."""

import json
import os
import re
from pathlib import Path


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from config.json."""
    if config_path is None:
        config_path = Path(__file__).parent / "config.json"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    # Load seed companies
    config["target_companies"] = _load_seed_file(config["seeds"]["include"])
    config["excluded_companies"] = _load_seed_file(config["seeds"]["exclude"])

    return config


def _load_seed_file(path: str) -> list[dict]:
    """Load a seed file (target or excluded companies)."""
    seed_path = Path(__file__).parent / path

    if not seed_path.exists():
        return []

    with open(seed_path) as f:
        data = json.load(f)

    return data.get("companies", [])


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it with: export ANTHROPIC_API_KEY=your-key"
        )
    return key


def get_locations(config: dict) -> list[str]:
    """Get list of configured locations from config.

    Returns locations in "City, State" format (e.g., "Palo Alto, CA").
    """
    return config.get("preferences", {}).get("locations", [])


def is_remote_enabled(config: dict) -> bool:
    """Check if remote/distributed roles are enabled in config."""
    return config.get("preferences", {}).get("include_remote", False)


def get_location_slug(location: str) -> str:
    """Convert a location string to a filesystem-safe slug.

    Examples:
        "Palo Alto, CA" -> "palo-alto-ca"
        "Boca Raton, FL" -> "boca-raton-fl"
        "remote" -> "remote"
    """
    if location.lower() == "remote":
        return "remote"

    # Lowercase and replace non-alphanumeric with hyphens
    slug = location.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def get_location_description(location: str) -> str:
    """Generate a metro area description for a location.

    The description expands the city to include the surrounding metropolitan area
    to ensure comprehensive job searches.

    Examples:
        "Palo Alto, CA" -> "Palo Alto, California and the surrounding San Francisco Bay Area / Silicon Valley metropolitan region"
        "Boca Raton, FL" -> "Boca Raton, Florida and the surrounding South Florida metropolitan region (Miami, Fort Lauderdale, Palm Beach area)"
    """
    if location.lower() == "remote":
        return "remote-friendly companies that allow fully remote or distributed work"

    # Parse city and state
    parts = location.split(",")
    if len(parts) != 2:
        return f"{location} and the surrounding metropolitan area"

    city = parts[0].strip()
    state_abbrev = parts[1].strip().upper()

    # Map state abbreviations to full names
    state_names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
    }

    state_full = state_names.get(state_abbrev, state_abbrev)

    # Known metro area expansions
    metro_expansions = {
        ("palo alto", "CA"): "San Francisco Bay Area / Silicon Valley (San Francisco, San Jose, Mountain View, Sunnyvale, Menlo Park, Redwood City)",
        ("san francisco", "CA"): "San Francisco Bay Area / Silicon Valley (San Jose, Palo Alto, Mountain View, Oakland, Berkeley)",
        ("san jose", "CA"): "San Francisco Bay Area / Silicon Valley (San Francisco, Palo Alto, Mountain View, Sunnyvale, Santa Clara)",
        ("boca raton", "FL"): "South Florida (Miami, Fort Lauderdale, Palm Beach, West Palm Beach, Delray Beach)",
        ("miami", "FL"): "South Florida (Fort Lauderdale, Boca Raton, Palm Beach, Coral Gables, Hollywood)",
        ("fort lauderdale", "FL"): "South Florida (Miami, Boca Raton, Palm Beach, Hollywood, Pompano Beach)",
        ("new york", "NY"): "New York metropolitan area (Manhattan, Brooklyn, Queens, Jersey City, Newark, Hoboken)",
        ("seattle", "WA"): "Seattle metropolitan area (Bellevue, Redmond, Kirkland, Tacoma)",
        ("austin", "TX"): "Austin metropolitan area (Round Rock, Cedar Park, Georgetown, San Marcos)",
        ("boston", "MA"): "Boston metropolitan area (Cambridge, Somerville, Newton, Brookline, Quincy)",
        ("los angeles", "CA"): "Los Angeles metropolitan area (Santa Monica, Culver City, Pasadena, Burbank, Long Beach)",
        ("denver", "CO"): "Denver metropolitan area (Boulder, Aurora, Lakewood, Westminster)",
        ("chicago", "IL"): "Chicago metropolitan area (Evanston, Oak Park, Naperville, Schaumburg)",
        ("atlanta", "GA"): "Atlanta metropolitan area (Alpharetta, Marietta, Decatur, Sandy Springs)",
        ("washington", "DC"): "Washington D.C. metropolitan area (Arlington, Bethesda, Alexandria, Tysons)",
        ("portland", "OR"): "Portland metropolitan area (Beaverton, Hillsboro, Lake Oswego, Vancouver WA)",
        ("phoenix", "AZ"): "Phoenix metropolitan area (Scottsdale, Tempe, Mesa, Chandler)",
        ("san diego", "CA"): "San Diego metropolitan area (La Jolla, Carlsbad, Chula Vista)",
        ("raleigh", "NC"): "Raleigh-Durham Research Triangle (Durham, Chapel Hill, Cary, Morrisville)",
        ("salt lake city", "UT"): "Salt Lake City metropolitan area (Provo, Lehi, Draper, Park City)",
    }

    key = (city.lower(), state_abbrev)
    if key in metro_expansions:
        metro_desc = metro_expansions[key]
        return f"{city}, {state_full} and the surrounding {metro_desc}"

    # Default expansion
    return f"{city}, {state_full} and the surrounding metropolitan area"


def get_all_location_slugs(config: dict) -> list[str]:
    """Get all location slugs including remote if enabled.

    Returns a list of slugs for use with job files (e.g., jobs-palo-alto-ca.json).
    """
    slugs = [get_location_slug(loc) for loc in get_locations(config)]
    if is_remote_enabled(config):
        slugs.append("remote")
    return slugs


def classify_job_location(job_location: str, config: dict) -> str:
    """Classify a job's location string to the best matching configured location slug.

    Args:
        job_location: The location string from a job posting (e.g., "Mountain View, CA")
        config: The loaded configuration

    Returns:
        The slug of the best matching location, or "remote" if no match found.
    """
    job_loc_lower = job_location.lower()

    # Check for remote indicators first
    remote_indicators = ["remote", "distributed", "work from home", "wfh", "anywhere", "virtual"]
    if any(indicator in job_loc_lower for indicator in remote_indicators):
        if is_remote_enabled(config):
            return "remote"

    # Check each configured location
    for location in get_locations(config):
        location_lower = location.lower()
        parts = location.split(",")
        if len(parts) == 2:
            city = parts[0].strip().lower()
            state = parts[1].strip().lower()

            # Direct city match
            if city in job_loc_lower:
                return get_location_slug(location)

            # State match (for broader metro area matching)
            if state in job_loc_lower or _get_state_full(state).lower() in job_loc_lower:
                # Check if it's in the same metro area
                if _is_same_metro_area(job_loc_lower, city, state):
                    return get_location_slug(location)

    # Default to remote if enabled, otherwise first location
    if is_remote_enabled(config):
        return "remote"

    locations = get_locations(config)
    return get_location_slug(locations[0]) if locations else "unknown"


def _get_state_full(state_abbrev: str) -> str:
    """Get full state name from abbreviation."""
    state_names = {
        "ca": "california", "fl": "florida", "ny": "new york", "tx": "texas",
        "wa": "washington", "ma": "massachusetts", "co": "colorado", "il": "illinois",
        "ga": "georgia", "nc": "north carolina", "az": "arizona", "or": "oregon",
        "ut": "utah", "dc": "district of columbia", "pa": "pennsylvania",
        "nj": "new jersey", "md": "maryland", "va": "virginia", "oh": "ohio",
        "mi": "michigan", "mn": "minnesota", "wi": "wisconsin", "mo": "missouri",
    }
    return state_names.get(state_abbrev.lower(), state_abbrev)


def _is_same_metro_area(job_location: str, city: str, state: str) -> bool:
    """Check if a job location is in the same metro area as the configured city."""
    # Define metro area cities for known locations
    metro_areas = {
        ("palo alto", "ca"): ["san francisco", "san jose", "mountain view", "sunnyvale",
                              "menlo park", "redwood city", "cupertino", "santa clara",
                              "fremont", "oakland", "berkeley", "bay area", "silicon valley"],
        ("san francisco", "ca"): ["palo alto", "san jose", "mountain view", "sunnyvale",
                                   "menlo park", "redwood city", "oakland", "berkeley",
                                   "bay area", "silicon valley"],
        ("boca raton", "fl"): ["miami", "fort lauderdale", "palm beach", "west palm beach",
                               "delray beach", "pompano beach", "hollywood", "south florida",
                               "deerfield beach", "coral springs"],
        ("miami", "fl"): ["fort lauderdale", "boca raton", "palm beach", "hollywood",
                          "coral gables", "south florida", "dade"],
        ("seattle", "wa"): ["bellevue", "redmond", "kirkland", "tacoma", "everett"],
        ("austin", "tx"): ["round rock", "cedar park", "georgetown", "san marcos"],
        ("boston", "ma"): ["cambridge", "somerville", "newton", "brookline", "quincy"],
        ("new york", "ny"): ["manhattan", "brooklyn", "queens", "bronx", "jersey city",
                             "newark", "hoboken", "nyc"],
        ("los angeles", "ca"): ["santa monica", "culver city", "pasadena", "burbank",
                                 "long beach", "beverly hills", "glendale"],
        ("denver", "co"): ["boulder", "aurora", "lakewood", "westminster", "broomfield"],
        ("chicago", "il"): ["evanston", "oak park", "naperville", "schaumburg", "skokie"],
        ("atlanta", "ga"): ["alpharetta", "marietta", "decatur", "sandy springs", "buckhead"],
        ("washington", "dc"): ["arlington", "bethesda", "alexandria", "tysons", "mclean", "reston"],
    }

    key = (city.lower(), state.lower())
    if key in metro_areas:
        for metro_city in metro_areas[key]:
            if metro_city in job_location:
                return True

    return False
