from urllib.parse import parse_qs, urlparse


def extract_query_param(url: str, query_param_name: str) -> str | None:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_param = query_params.get(query_param_name)
    if query_param:
        return query_param[0]  # parse_qs returns a list for each key
    return None
