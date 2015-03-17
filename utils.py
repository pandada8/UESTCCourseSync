import json


def writejson(data):
    def special_dumper(d):
        if hasattr(d, 'isoformat'):
            return d.isoformat() + "+08:00"
        else:
            return json.dumps(d)
    return json.dumps(data, default=special_dumper)
