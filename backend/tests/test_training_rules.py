from datetime import date
from app.api.trainings import RULES, add_years
def test_training_rules():
    assert RULES["Az Tehlikeli"]==(8,3)
    assert RULES["Tehlikeli"]==(12,2)
    assert RULES["Çok Tehlikeli"]==(16,1)
def test_add_years_leap_day():
    assert add_years(date(2024,2,29),1)==date(2025,2,28)
