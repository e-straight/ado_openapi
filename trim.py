import json
import copy

# Allowed endpoints and methods
ALLOWED_ENDPOINTS = {
    "/{organization}/{project}/_apis/wit/workitems": ["get"],
    # "/{organization}/{project}/_apis/wit/workitems/${type}": ["post", "get"],
    # "/{organization}/{project}/_apis/wit/workitems/{id}": ["delete", "patch", "get"],
    # "/{organization}/{project}/_apis/wit/workitemsbatch": ["post"],
    # "/{organization}/{project}/_apis/wit/workitemsdelete": ["post"],
    # "/{organization}/{project}/{team}/_apis/wit/wiql": ["post"],
    # "/{organization}/{project}/{team}/_apis/wit/wiql/{id}": ["get", "head"]
}

# Allowed tags for operations (case-insensitive)
ALLOWED_TAGS = {"work items", "wiql"}

def clean_data(obj):
    """
    Recursively remove extraneous keys from a dict or list.
    Unwanted keys include: x-ms-paths, examples, and example.
    Also filters tags to only keep allowed ones (case-insensitive).
    """
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k in {"x-ms-paths", "examples", "example"}:
                continue
            if k == "tags" and isinstance(v, list):
                # Filter tags using a case-insensitive check and ensure each tag is a string
                filtered_tags = [tag for tag in v if isinstance(tag, str) and tag.lower() in ALLOWED_TAGS]
                if filtered_tags:
                    new_obj[k] = filtered_tags
            else:
                new_obj[k] = clean_data(v)
        return new_obj
    elif isinstance(obj, list):
        return [clean_data(item) for item in obj]
    else:
        return obj

def extract_refs(obj, refs_set):
    """
    Recursively find $ref values that point to components/schemas.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                if v.startswith("#/components/schemas/"):
                    schema_name = v.split("/")[-1]
                    refs_set.add(schema_name)
            else:
                extract_refs(v, refs_set)
    elif isinstance(obj, list):
        for item in obj:
            extract_refs(item, refs_set)

def collect_schema_refs(spec, initial_refs):
    """
    Starting with an initial set of schema names, recursively collect any subreferences.
    """
    collected = set(initial_refs)
    new_refs = set(initial_refs)
    while new_refs:
        current_refs = new_refs
        new_refs = set()
        for schema_name in current_refs:
            schema = spec.get("components", {}).get("schemas", {}).get(schema_name)
            if schema:
                refs_in_schema = set()
                extract_refs(schema, refs_in_schema)
                for ref in refs_in_schema:
                    if ref not in collected:
                        collected.add(ref)
                        new_refs.add(ref)
    return collected

def main():
    # Read the input OpenAPI spec from file
    with open("wit_openapi.json", "r", encoding="utf-8") as f:
        spec = json.load(f)

    new_spec = copy.deepcopy(spec)
    new_spec["paths"] = {}

    # Filter paths and methods based on allowed endpoints
    for path, path_item in spec.get("paths", {}).items():
        if path in ALLOWED_ENDPOINTS:
            allowed_methods = {method.lower() for method in ALLOWED_ENDPOINTS[path]}
            new_path_item = {}
            for method, operation in path_item.items():
                if method.lower() in allowed_methods:
                    # Clean operation by removing unwanted fields and filtering tags
                    new_path_item[method] = clean_data(operation)
            if new_path_item:
                new_spec["paths"][path] = new_path_item

    # Clean extraneous data from the whole spec
    new_spec = clean_data(new_spec)

    # Initialize the set of referenced schemas from the paths...
    referenced_schemas = set()
    extract_refs(new_spec.get("paths", {}), referenced_schemas)
    
    # ...and also from other components (e.g., requestBodies, responses)
    if "components" in new_spec:
        for comp_key, comp_val in new_spec["components"].items():
            if comp_key != "schemas":  # Process non-schema components to catch any $ref in them
                extract_refs(comp_val, referenced_schemas)

    # Recursively collect all subreferenced schemas from the original spec
    collected_schemas = collect_schema_refs(spec, referenced_schemas)

    # Filter the components/schemas to only include the collected schemas
    if "components" in spec and "schemas" in spec["components"]:
        new_components = copy.deepcopy(spec["components"])
        new_components["schemas"] = {
            k: v for k, v in spec["components"]["schemas"].items() if k in collected_schemas
        }
        new_spec["components"] = new_components

    # Write the trimmed spec to a new file
    with open("wit_openapi_trimmed.json", "w", encoding="utf-8") as f:
        json.dump(new_spec, f, indent=2)

if __name__ == "__main__":
    main()
