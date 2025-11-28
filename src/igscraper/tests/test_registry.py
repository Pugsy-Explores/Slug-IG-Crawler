import re
import json
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, TypeAdapter
from igscraper.models.common import BaseFlexibleSafeModel, XdtViewer,MODEL_REGISTRY
from igscraper.models import RootResponse
from igscraper.models.registry_parser import GraphQLModelRegistry
import logging
from igscraper.logger import get_logger
from igscraper.utils import pretty_print_flattened,pretty_print_any,schema_lint
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = get_logger(__name__)

import json
from pathlib import Path
from typing import Dict, Any, List

def load_json_sample(file_path: str) -> List[Dict[str, Any]]:
    """
    Load JSON data from a file as sample data.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        List of dictionaries containing the JSON data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data        
        # If it's a single dictionary, wrap it in a list for consistency
        # if isinstance(data, dict):
        #     return [data]
        # elif isinstance(data, list):
        #     return data
        # else:
        #     raise ValueError(f"Unexpected JSON structure: {type(data)}")
            
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in file {file_path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Error loading JSON from {file_path}: {e}")

# ----------------------------
# Test harness
# ----------------------------
# if __name__ == "__main__":
    # Load schema.yaml
    # schema_path = "src/igscraper/flatten_schema.yaml"
    # registry = GraphQLModelRegistry(registry=MODEL_REGISTRY, schema_path=schema_path)
    # test apply nested schema
    # print(f"schema - {registry.flatten_schema}")
    # print(f"base schema(working) - {schema}")
    # print(f"flattened schem inside registry - {registry.flatten_schema}")
    # rows, diag = registry.apply_nested_schema(sample_response_dict, registry.flatten_schema, debug=True)
    # registry.save_parsed_results(rows,"src/igscraper/tests/parsed_results.json")
    # registry.save_parsed_results([diag],"src/igscraper/tests/diag.json")
    # print(rows)
    # print(diag)
    # Run parser
    # results = registry.parse_responses(
    #     [{"requestId": "req1", "url": "fakeurl", "response": json.dumps(sample_json)}]
    # )
    # data = []
    # logger.info('yeah')
    # for entry in results:
    #     safe_entry = registry._to_serializable(entry)
    #     data.append(json.dumps(safe_entry, indent=2, ensure_ascii=False))  # Add indent for pretty printing

    # print("\n=== Final Results ===")
    # for json_str in data:
    #     logger.info(json_str)
    #     logger.info("-" * 50)  # Separator between entries

import json
from typing import Any, Dict, List, Tuple, Union
if __name__ == "__main__":
    # Sample schema from user
    schema_path = "src/igscraper/flatten_schema.yaml"
    registry = GraphQLModelRegistry(registry=MODEL_REGISTRY, schema_path=schema_path)
    schema = {
        "data": {
            "xdt_api__v1__feed__timeline__connection": {
                "__strict__": False,
                "edges": {
                    "unwrap": "node",
                    "fields": ["id", "pk", "code", "taken_at", "comment_count", "like_count"],
                    "image_versions2": {
                        "unwrap": "candidates",
                        "fields": ["url", "height", "width"]
                    },
                    "user": {
                        "fields": ["id", "username"]
                    }
                }
            }
        }
    }

    # Sample JSON payload
    sample_json = {
        "data": {
            "xdt_api__v1__feed__timeline__connection": {
                "edges": [
                    {
                        "node": {
                            "id": "1",
                            "pk": "pk1",
                            "code": "abc123",
                            "taken_at": 1670000000,
                            "comment_count": 10,
                            "like_count": 20,
                            "image_versions2": {
                                "candidates": [
                                    {"url": "http://img1", "height": 640, "width": 480},
                                    {"url": "http://img2", "height": 1280, "width": 720},
                                ]
                            },
                            "user": {"id": "u1", "username": "testuser"},
                        },
                        "cursor": "cursor1",
                    }
                ]
            }
        },
        "status": "ok",
    }
    sample_path = 'src/igscraper/tests/sample_graphql_timeline_response.json'
    sample_path_2 = 'src/igscraper/tests/new_sample_client_profile_page_gql.json'
    sample_response_dict = load_json_sample(sample_path)
    sample_response_dict_hcode = {
        "data": {
            "xdt_api__v1__feed__user_timeline_graphql_connection": {
                "edges": [
                    {
                        "node": {
                            "id": "1", "pk": "pk1", "code": "abc123", 
                            "taken_at": 111, "comment_count": 10, "like_count": 20,
                            "image_versions2": {
                                "candidates": [
                                    {"url": "http://img1", "height": 640, "width": 480}
                                ]
                            },
                            "user": {"id": "u1", "username": "testuser"}
                        }
                    }
                ]
            },
            "xdt_api__v1__media__media_id__comments__connection": {
                "edges": [
                    {
                        "node": {
                            "pk": "comment_pk1", "child_comment_count": 0, 
                            "text": "Nice post!", "created_at": 1758421138,
                            "comment_like_count": 5,
                            "user": {"id": "user2", "username": "commenter"}
                        }
                    }
                ]
            }
        },
        "extensions": {
            "all_video_dash_prefetch_representations": [
                {
                    "video_id": "vid1",
                    "representations": [
                        {
                            "base_url": "http://video.com/1", 
                            "width": 1280, "height": 720,
                            "mime_type": "video/mp4", "representation_id": "rep1",
                            "segments": [{"start": 0, "end": 10}]
                        }
                    ]
                }
            ]
        }
    }
    from typing import Any, Dict, List, Tuple, Union
    import re

    def apply_nested_schema_with_separate_flag_v2(
        obj: Any,
        schema: Dict[str, Any],
        sep: str = "__",
        debug: bool = False
    ) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
        """
        Final apply_nested_schema:
        - Use __separate__: True to force children into separate output rows (no merging).
        - Child-level __strict__ overrides parent for regex vs exact matching.
        - Regexes precompiled and cached; invalid regex falls back to exact match.
        - 'unwrap' explodes lists; absence of 'unwrap' keeps lists intact but processes each item
        (so carousel_media remains a list of processed dicts).
        - sep controls the separator used in flattened column names (default '__').
        """
        if isinstance(obj, BaseFlexibleSafeModel):
            obj = obj.model_dump()

        matched_rules = set()
        unmatched_rules = set()
        regex_cache: Dict[str, Union[re.Pattern, None]] = {}

        def join_path(path: str, child: str) -> str:
            return f"{path}{sep}{child}" if path else child

        def _nested_children_keys(scfg: Dict[str, Any]) -> List[str]:
            return [k for k in scfg.keys() if k not in ("fields", "__strict__", "unwrap", "__separate__")]

        def _compile_or_none(pattern: str):
            if pattern in regex_cache:
                return regex_cache[pattern]
            try:
                compiled = re.compile(pattern)
                regex_cache[pattern] = compiled
                return compiled
            except re.error:
                regex_cache[pattern] = None
                return None

        def process_item_with_schema(item: Dict[str, Any], scfg: Dict[str, Any]):
            """
            Process a single list-item dict according to scfg:
            - include scfg['fields'] for the item
            - process nested children per-item (keeps lists unless nested child says 'unwrap')
            """
            result = {}
            if not isinstance(item, dict):
                return item
            # attach fields at this level
            if "fields" in scfg:
                for f in scfg["fields"]:
                    if f in item:
                        result[f] = item[f]
            # handle nested children
            for child_key, child_cfg in scfg.items():
                if child_key in ("fields", "__strict__", "unwrap", "__separate__"):
                    continue
                if child_key not in item:
                    continue
                val = item[child_key]
                # list
                if isinstance(val, list):
                    if isinstance(child_cfg, dict) and "unwrap" in child_cfg:
                        unwrap_key = child_cfg["unwrap"]
                        processed_list = []
                        for it in val:
                            if isinstance(it, dict) and unwrap_key in it:
                                payload = it[unwrap_key]
                            else:
                                payload = it
                            if isinstance(payload, dict):
                                processed_list.append(process_item_with_schema(payload, child_cfg))
                            else:
                                processed_list.append(payload)
                        result[child_key] = processed_list
                    else:
                        processed_list = []
                        for it in val:
                            if isinstance(it, dict):
                                processed_list.append(process_item_with_schema(it, child_cfg))
                            else:
                                processed_list.append(it)
                        result[child_key] = processed_list
                # dict
                elif isinstance(val, dict):
                    result[child_key] = process_item_with_schema(val, child_cfg)
                # scalar
                else:
                    # only include scalar if declared in child_cfg['fields']
                    if "fields" in child_cfg and child_key in child_cfg["fields"]:
                        result[child_key] = val
            return result

        def walk(o: Any, schema_node: Dict[str, Any], path: str) -> List[Dict[str, Any]]:
            """
            Pure recursion: returns list[dict] where each dict is a flattened row.
            """
            if isinstance(o, BaseFlexibleSafeModel):
                o = o.model_dump()

            # unwrap-from-dict shortcut
            if isinstance(o, dict) and "unwrap" in schema_node:
                unwrap_key = schema_node["unwrap"]
                if unwrap_key in o and isinstance(o[unwrap_key], list):
                    return walk(o[unwrap_key], schema_node, join_path(path, unwrap_key))

            # If node explicitly asks for separation, process children independently
            child_keys = [k for k in schema_node.keys() if k not in ("fields", "__strict__", "unwrap", "__separate__")]
            if schema_node.get("__separate__", False) and child_keys:
                result_rows: List[Dict[str, Any]] = []
                if isinstance(o, dict):
                    parent_strict = schema_node.get("__strict__", True)
                    for sk in child_keys:
                        scfg = schema_node[sk]
                        child_strict = (scfg.get("__strict__", parent_strict) if isinstance(scfg, dict) else parent_strict)

                        matches: List[Tuple[str, str]] = []
                        if child_strict:
                            if sk in o:
                                matches.append((sk, sk))
                        else:
                            compiled = _compile_or_none(sk)
                            if compiled is None:
                                if sk in o:
                                    matches.append((sk, sk))
                            else:
                                for actual_key in o.keys():
                                    if compiled.fullmatch(actual_key):
                                        matches.append((sk, actual_key))

                        if not matches:
                            unmatched_rules.add(join_path(path, sk))
                            continue

                        for _, actual_key in matches:
                            current_path = join_path(path, actual_key)
                            matched_rules.add(current_path)
                            value = o[actual_key]
                            child_rows = walk(value, scfg if isinstance(scfg, dict) else {}, current_path)
                            if child_rows:
                                result_rows.extend(child_rows)
                    return result_rows
                else:
                    return []

            # Single-pattern processing (fields at this level, children merged)
            if isinstance(o, dict):
                base_rows: List[Dict[str, Any]] = [{}]

                # attach fields at this level
                if "fields" in schema_node:
                    for f in schema_node["fields"]:
                        if f in o:
                            for br in base_rows:
                                br[join_path(path, f)] = o[f]
                            matched_rules.add(join_path(path, f))
                        else:
                            unmatched_rules.add(join_path(path, f))

                for sk, scfg in schema_node.items():
                    if sk in ("fields", "__strict__", "unwrap", "__separate__"):
                        continue

                    parent_strict = schema_node.get("__strict__", True)
                    child_strict = (scfg.get("__strict__", parent_strict) if isinstance(scfg, dict) else parent_strict)

                    matches: List[Tuple[str, str]] = []
                    if child_strict:
                        if sk in o:
                            matches.append((sk, sk))
                    else:
                        compiled = _compile_or_none(sk)
                        if compiled is None:
                            if sk in o:
                                matches.append((sk, sk))
                        else:
                            for actual_key in o.keys():
                                if compiled.fullmatch(actual_key):
                                    matches.append((sk, actual_key))

                    if not matches:
                        unmatched_rules.add(join_path(path, sk))
                        continue

                    new_base_rows: List[Dict[str, Any]] = []
                    for _, actual_key in matches:
                        current_path = join_path(path, actual_key)
                        matched_rules.add(current_path)
                        v = o[actual_key]

                        # LIST
                        if isinstance(v, list):
                            if isinstance(scfg, dict) and "unwrap" in scfg:
                                unwrap_key = scfg["unwrap"]
                                for br in base_rows:
                                    for item in v:
                                        if isinstance(item, dict) and unwrap_key in item:
                                            item_payload = item[unwrap_key]
                                        else:
                                            item_payload = item

                                        if isinstance(item_payload, dict):
                                            parent_for_child = {}
                                            fields = scfg.get("fields")
                                            if fields:
                                                for f in fields:
                                                    if f in item_payload:
                                                        parent_for_child[join_path(current_path, f)] = item_payload[f]
                                            child_rows = walk(item_payload, scfg, current_path)
                                            if child_rows:
                                                for cr in child_rows:
                                                    new_base_rows.append({**br, **parent_for_child, **cr})
                                            else:
                                                new_base_rows.append({**br, **parent_for_child})
                                        else:
                                            new_base_rows.append({**br, current_path: item_payload})
                            else:
                                # keep list intact; but if scfg has fields or nested children,
                                # process each list-item and store processed list
                                fields = scfg.get("fields") if isinstance(scfg, dict) else None
                                nested_children = _nested_children_keys(scfg if isinstance(scfg, dict) else {})
                                if (fields or nested_children) and all(isinstance(it, dict) for it in v):
                                    processed_list = [process_item_with_schema(it, scfg) for it in v]
                                    for br in base_rows:
                                        new = dict(br)
                                        new[current_path] = processed_list
                                        new_base_rows.append(new)
                                else:
                                    for br in base_rows:
                                        new = dict(br)
                                        new[current_path] = v
                                        new_base_rows.append(new)

                        # DICT
                        elif isinstance(v, dict):
                            fields = scfg.get("fields") if isinstance(scfg, dict) else None
                            nested_children = _nested_children_keys(scfg if isinstance(scfg, dict) else {})
                            if fields:
                                for br in base_rows:
                                    new = dict(br)
                                    for f in fields:
                                        if f in v:
                                            new[join_path(current_path, f)] = v[f]
                                    if nested_children:
                                        child_rows = walk(v, scfg if isinstance(scfg, dict) else {}, current_path)
                                        if child_rows:
                                            for cr in child_rows:
                                                new_base_rows.append({**new, **cr})
                                        else:
                                            new_base_rows.append(new)
                                    else:
                                        new_base_rows.append(new)
                            else:
                                child_rows = walk(v, scfg if isinstance(scfg, dict) else {}, current_path)
                                if child_rows:
                                    for br in base_rows:
                                        for cr in child_rows:
                                            new_base_rows.append({**br, **cr})
                                else:
                                    for br in base_rows:
                                        new_base_rows.append(dict(br))

                        # SCALAR
                        else:
                            if "fields" in schema_node and actual_key in schema_node["fields"]:
                                for br in base_rows:
                                    new_row = dict(br)
                                    new_row[current_path] = v
                                    new_base_rows.append(new_row)
                            else:
                                for br in base_rows:
                                    new_base_rows.append(dict(br))

                    base_rows = new_base_rows if new_base_rows else base_rows

                return base_rows

            # LIST at node level (not exploded)
            elif isinstance(o, list):
                if "unwrap" in schema_node:
                    unwrap_key = schema_node["unwrap"]
                    result_rows: List[Dict[str, Any]] = []
                    for item in o:
                        if isinstance(item, dict) and unwrap_key in item:
                            item_payload = item[unwrap_key]
                        else:
                            item_payload = item

                        if isinstance(item_payload, dict):
                            parent_for_child = {}
                            fields = schema_node.get("fields")
                            if fields:
                                for f in fields:
                                    if f in item_payload:
                                        parent_for_child[join_path(path, f)] = item_payload[f]
                            child_rows = walk(item_payload, schema_node, path)
                            if child_rows:
                                for cr in child_rows:
                                    result_rows.append({**parent_for_child, **cr})
                            else:
                                result_rows.append(parent_for_child)
                        else:
                            result_rows.append({path or "value": item_payload})
                    return result_rows
                else:
                    # keep list intact, but process per-item if schema_node defines fields/nested children
                    fields = schema_node.get("fields")
                    nested_children = _nested_children_keys(schema_node)
                    if (fields or nested_children) and all(isinstance(it, dict) for it in o):
                        processed_list = [process_item_with_schema(it, schema_node) for it in o]
                        return [{path or "value": processed_list}]
                    else:
                        return [{path or "value": o}]

            # fallback
            return []

        rows = walk(obj, schema, "")

        if not rows and (obj or debug):
            rows = [{}]

        if debug:
            diag = {
                "matched_rules": sorted(matched_rules),
                "unmatched_schema_paths": sorted(unmatched_rules),
                "rows_count": len(rows),
                "rows_sample": rows[:5],
            }
            return rows, diag

        return rows, {}

    schema_lint(registry.flatten_schema)
    USE_GQL = True
    # Process data and extensions separately        
    data_schema = {"data": registry.flatten_schema["data"]}
    extensions_schema = {"extensions": registry.flatten_schema["extensions"]}


    logger.info(f"USE_GQL - {USE_GQL}")
    # Process data
    pretty_print_any(f'data schema - {data_schema}')    
    if USE_GQL:
        data_rows, data_diag = registry.apply_nested_schema(sample_response_dict, data_schema, debug=True, sep='$$')
    else:
        data_rows, data_diag = apply_nested_schema_with_separate_flag_v2(
            sample_response_dict, data_schema, debug=True, sep='$$'
        )

    # Process extensions (only if extensions exist in sample)
    if USE_GQL:
        extensions_rows, extensions_diag = registry.apply_nested_schema(
            sample_response_dict, extensions_schema, sep='$$', debug=True
        )
    else:
        extensions_rows, extensions_diag = apply_nested_schema_with_separate_flag_v2(
            sample_response_dict, extensions_schema, debug=True, sep='$$'
        )
    
    # Combine results if needed
    all_rows = data_rows + extensions_rows
    
    pretty_print_any(all_rows[:])  # Show first 3 data rows
    if extensions_rows:
        print("--- Extensions Rows ---")
        pretty_print_any(extensions_rows[:3])
    print(f"Data rows: {len(data_rows)}")
    print(f"Extensions rows: {len(extensions_rows)}")
    print(f"Total rows: {len(all_rows)}")