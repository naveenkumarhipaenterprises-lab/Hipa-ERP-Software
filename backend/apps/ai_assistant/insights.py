"""
Insight payloads for the module pages. Insights are written by `manage.py run_analytics`
from real records; until it has produced any, every block is empty.
"""
from .models import Insight


def latest(module, limit=5):
    return list(Insight.objects.filter(module=module)[:limit])


def texts(module):
    """insights: string[]"""
    return [i.text for i in latest(module)]


def block(module):
    """insights: { text?, actions? }"""
    items = latest(module)
    if not items:
        return {}
    return {"text": items[0].text, "actions": [i.action for i in items if i.action]}


def items_block(module):
    """insights: { items?, actions? }"""
    items = latest(module)
    if not items:
        return {}
    return {"items": [i.text for i in items], "actions": [i.action for i in items if i.action]}
