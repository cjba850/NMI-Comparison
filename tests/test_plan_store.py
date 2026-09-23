import json
from pathlib import Path
import pytest
from app.plan_store import PlanStore, validate_plan


def flat_plan(pid='test-plan'):
    return {
        'id': pid, 'provider': 'Test Retailer', 'name': 'Test Flat',
        'effective_from': '2025-01-01', 'effective_to': '2025-12-31',
        'daily_supply_cents': 100, 'usage': {'type': 'flat', 'cents_per_kwh': 30},
        'source_document': 'test', 'source_url': 'https://example.com', 'last_verified': '2026-09-23'
    }

def test_save_update_delete(tmp_path):
    store=PlanStore(tmp_path/'plans.json')
    store.save(flat_plan())
    assert store.get('test-plan')['provider']=='Test Retailer'
    p=flat_plan(); p['name']='Updated'; store.save(p)
    assert store.get('test-plan')['name']=='Updated'
    assert store.delete('test-plan')
    assert store.get('test-plan') is None
    assert (tmp_path/'plans.json.backup').exists()

def test_validate_bad_dates():
    p=flat_plan(); p['effective_to']='2024-01-01'
    with pytest.raises(ValueError): validate_plan(p)

def test_validate_tou():
    p=flat_plan('tou'); p['usage']={'type':'tou','periods':[{'name':'peak','days':[0,1,2,3,4],'start':'14:00','end':'20:00','cents_per_kwh':45}]}
    validate_plan(p)
