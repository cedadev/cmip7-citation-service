from django.urls import get_resolver, URLPattern, URLResolver

def list_urls(resolver=None, namespace_prefix=""):
    if resolver is None:
        resolver = get_resolver()

    urls = []

    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLPattern):
            # Build full name including namespaces
            if pattern.name:
                full_name = f"{namespace_prefix}{pattern.name}"
                urls.append((full_name, pattern.pattern.describe()))
        elif isinstance(pattern, URLResolver):
            # Build namespace prefix
            new_prefix = namespace_prefix
            if pattern.namespace:
                new_prefix += pattern.namespace + ":"
            urls.extend(list_urls(pattern, new_prefix))

    return urls

# Run it
for name, path in list_urls():
    print(f"{name} → {path}")
