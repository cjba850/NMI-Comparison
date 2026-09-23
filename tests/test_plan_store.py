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


def test_plan_store_accepts_dollar_supply_subscription_and_controlled_load(tmp_path):
    from app.plan_store import PlanStore
    plan = {"id":"fees-plan","provider":"Test","name":"Fees","effective_from":"2026-01-01","effective_to":None,"daily_supply_dollars":1.25,"monthly_subscription_dollars":9.95,"controlled_load":{"cl1_cents_per_kwh":15,"cl2_cents_per_kwh":10},"usage":{"type":"flat","cents_per_kwh":30}}
    store = PlanStore(tmp_path/'plans.json')
    store.save(plan)
    assert store.get('fees-plan')['daily_supply_dollars'] == 1.25


def test_validate_tou_months():
    p=flat_plan('seasonal')
    p['usage']={'type':'tou','periods':[{'name':'summer peak','months':[12,1,2],'days':[0,1,2,3,4],'start':'14:00','end':'20:00','cents_per_kwh':45}]}
    validate_plan(p)

def test_reject_invalid_tou_month():
    p=flat_plan('bad-season')
    p['usage']={'type':'tou','periods':[{'name':'bad','months':[0,13],'days':[0,1,2,3,4],'start':'14:00','end':'20:00','cents_per_kwh':45}]}
    with pytest.raises(ValueError): validate_plan(p)


def test_validate_tou_months():
    p=flat_plan('seasonal')
    p['usage']={'type':'tou','periods':[{'name':'summer peak','months':[12,1,2],'days':[0,1,2,3,4],'start':'14:00','end':'20:00','cents_per_kwh':45}]}
    validate_plan(p)

def test_reject_invalid_tou_month():
    p=flat_plan('bad-season')
    p['usage']={'type':'tou','periods':[{'name':'bad','months':[0,13],'days':[0,1,2,3,4],'start':'14:00','end':'20:00','cents_per_kwh':45}]}
    with pytest.raises(ValueError): validate_plan(p)


def test_validate_demand_surcharge():
    p=flat_plan('demand')
    p['demand']={'enabled':True,'rate_dollars_per_kw':12.50}
    validate_plan(p)


def test_reject_negative_demand_rate():
    p=flat_plan('bad-demand')
    p['demand']={'enabled':True,'rate_dollars_per_kw':-1}
    with pytest.raises(ValueError): validate_plan(p)
