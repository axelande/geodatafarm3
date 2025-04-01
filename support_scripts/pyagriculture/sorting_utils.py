from collections import defaultdict


def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v
                     for k, v in dd.items()}}
    if t.attrib:
        d[t.tag]['attr'] = (list(t.attrib.keys()))
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d


def find_by_key(data_dict: dict, key_name: str, 
                key_value: str) -> tuple[bool, str, int]:
    """Returns a dict key where "key_name" equals the key_value, if the dict is nested in a list,
    also returns the index of the list where the key is found."""
    for key in data_dict.keys():
        if isinstance(data_dict[key], list):
            for i, item in enumerate(data_dict[key]):
                if item[key_name] == key_value:
                    return True, key, i
        else:
            if data_dict[key][key_name] == key_value:
                return True, key, -1
    return False, key_value, -1
