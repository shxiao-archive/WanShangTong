from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas import BusinessDataIn, BusinessDataOut


def future_business_data_payload() -> dict:
    return {
        "business_date": date.today() + timedelta(days=1),
        "visitors": 20,
        "orders": 10,
        "revenue": 200,
        "rating": 4.8,
        "dine_in_orders": 6,
        "delivery_orders": 2,
        "group_buy_orders": 1,
        "other_orders": 1,
        "peak_hour": 12,
    }


def test_business_data_input_rejects_future_date():
    with pytest.raises(ValidationError, match="经营日期不能晚于今天"):
        BusinessDataIn.model_validate(future_business_data_payload())


def test_business_data_output_allows_preloaded_future_date():
    row = BusinessDataOut.model_validate(
        {
            **future_business_data_payload(),
            "id": 1,
            "merchant_id": 1,
            "updated_at": datetime.now(),
        }
    )

    assert row.business_date == date.today() + timedelta(days=1)
