# BACKEND/automations/google/google_pages.py

COMMON_SITES = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "google": "https://www.google.com",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://twitter.com",
}


def open_website(driver, name: str):
    name = name.lower().strip()

    if name in COMMON_SITES:
        driver.get(COMMON_SITES[name])
    elif name.startswith("http"):
        driver.get(name)
    else:
        if "." in name:
            driver.get(f"https://{name}")
        else:
            driver.get(f"https://{name}.com")
