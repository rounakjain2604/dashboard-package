def make_source_url(cik: str, accession: str | None) -> str:
    """Generate a direct SEC.gov Archives URL for a fact, or a companyfacts API fallback."""
    if accession:
        accession_no_dashes = accession.replace("-", "")
        try:
            cik_clean = str(int(cik))
        except (ValueError, TypeError):
            cik_clean = cik
        return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_no_dashes}/"
    else:
        cik_padded = str(cik).zfill(10)
        return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
