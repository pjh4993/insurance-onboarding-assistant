"""The 8 seed products from wiki/catalog-seed.md (KR + US x four product types).

Amounts are integer minor units (KRW won, USD cents). Values are seed data, not bolttech rates."""

from __future__ import annotations

from typing import Any

KR_RESIDENT = {
    "subject": "NEEDS_ASSESSMENT",
    "attribute": "residence_country",
    "operator": "IN",
    "value": ["KR"],
    "failure_reason_code": "NOT_KR_RESIDENT",
    "description": "한국 거주자만 가입할 수 있습니다",
}
US_RESIDENT = {
    "subject": "NEEDS_ASSESSMENT",
    "attribute": "residence_country",
    "operator": "IN",
    "value": ["US"],
    "failure_reason_code": "NOT_US_RESIDENT",
    "description": "Only US residents can enrol",
}


def _rule(subject: str, attribute: str, operator: str, value: Any, code: str, description: str) -> dict:
    return {
        "subject": subject,
        "attribute": attribute,
        "operator": operator,
        "value": value,
        "failure_reason_code": code,
        "description": description,
    }


def _obj(attr: str, operator: str, value: Any, code: str, description: str) -> dict:
    return _rule("INSURABLE_OBJECT", f"attributes.{attr}", operator, value, code, description)


def _tm(attribute: str, values: list, weight: float, rationale: str) -> dict:
    return {"attribute": attribute, "values": values, "weight": weight, "rationale": rationale}


PRODUCTS: list[dict[str, Any]] = [
    # ------------------------------------------------------------------------------------------ KR
    {
        "product_code": "KR-MOB-SWAP",
        "product_type": "MOBILE_INSURANCE",
        "marketing_name": "폰교체 패스",
        "insurable_object_type": "DEVICE",
        "billing_period": "MONTHLY",
        "currency": "KRW",
        "jurisdictions": ["KR"],
        "rating": {
            "method": "TIERED",
            "basis": "MSRP",
            "tiers": [
                {"up_to_minor": 500000, "premium_minor": 5990},
                {"up_to_minor": 1000000, "premium_minor": 7990},
                {"up_to_minor": 1500000, "premium_minor": 9990},
                {"up_to_minor": 2000000, "premium_minor": 12990},
                {"up_to_minor": 2500000, "premium_minor": 13990},
                {"up_to_minor": None, "premium_minor": 15990},
            ],
        },
        "term_rule": {"length": 36, "unit": "MONTH", "starts": "PURCHASE_DATE"},
        "coverages": [
            {"code": "SWAP_RETURN", "name": "파손·고장 교체(반납)", "limit_minor": 2500000, "deductible_minor": 50000},
            {"code": "SWAP_NO_RETURN", "name": "교체(미반납)", "limit_minor": 2500000, "deductible_minor": 100000},
            {"code": "REPAIR", "name": "공식센터 수리", "limit_minor": 2500000, "deductible_minor": 50000},
        ],
        "rules": [
            _obj("device_category", "IN", ["SMARTPHONE"], "DEVICE_NOT_SMARTPHONE", "스마트폰만 가입할 수 있습니다"),
            _obj(
                "manufacturer",
                "IN",
                ["Samsung", "Apple"],
                "MANUFACTURER_NOT_COVERED",
                "삼성·애플 기기만 가입할 수 있습니다",
            ),
            _obj("has_existing_damage", "EQ", False, "EXISTING_DAMAGE", "이미 파손된 기기는 가입할 수 없습니다"),
            _obj("activation_date", "WITHIN_DAYS", 30, "ACTIVATION_TOO_OLD", "개통 30일 이내에만 가입할 수 있습니다"),
            KR_RESIDENT,
        ],
        "required_application_fields": ["imei", "device_model", "msrp", "activation_date"],
        "target_markets": [
            _tm("objectives", ["PROTECT_DEVICE"], 0.8, "새 스마트폰의 파손·고장 시 기기를 교체해 줍니다"),
            _tm("age_range", ["AGE_19_29", "AGE_30_39"], 0.1, "스마트폰을 자주 바꾸는 연령대에 많이 선택됩니다"),
        ],
    },
    {
        "product_code": "KR-DEV-LAPTOP",
        "product_type": "DEVICE_PROTECTION",
        "marketing_name": "노트북·태블릿 파손 보장",
        "insurable_object_type": "DEVICE",
        "billing_period": "MONTHLY",
        "currency": "KRW",
        "jurisdictions": ["KR"],
        "rating": {
            "method": "TIERED",
            "basis": "MSRP",
            "tiers": [
                {"up_to_minor": 1500000, "premium_minor": 7200},
                {"up_to_minor": None, "premium_minor": 8400},
            ],
        },
        "term_rule": {"length": 36, "unit": "MONTH", "starts": "PURCHASE_DATE"},
        "coverages": [
            {"code": "ACCIDENTAL_DAMAGE", "name": "파손 수리", "limit_minor": 2000000, "deductible_minor": 30000},
        ],
        "rules": [
            _obj(
                "device_category",
                "IN",
                ["NOTEBOOK", "TABLET"],
                "DEVICE_NOT_LAPTOP_TABLET",
                "노트북·태블릿만 가입할 수 있습니다",
            ),
            _obj("purchase_date", "WITHIN_DAYS", 60, "PURCHASE_TOO_OLD", "구매 60일 이내에만 가입할 수 있습니다"),
            _obj("condition", "EQ", "NEW", "DEVICE_NOT_NEW", "새 제품만 가입할 수 있습니다"),
            KR_RESIDENT,
        ],
        "required_application_fields": ["serial_number", "device_model", "purchase_date", "purchase_price"],
        "target_markets": [
            _tm("objectives", ["PROTECT_DEVICE"], 0.8, "노트북·태블릿의 낙하·파손 수리비를 보장합니다"),
            _tm("objectives", ["REDUCE_PREMIUM"], 0.1, "월 7천원대의 낮은 보험료로 시작할 수 있습니다"),
        ],
    },
    {
        "product_code": "KR-EW-HOME",
        "product_type": "EXTENDED_WARRANTY",
        "marketing_name": "가전 연장 보증",
        "insurable_object_type": "DEVICE",
        "billing_period": "ONE_TIME",
        "currency": "KRW",
        "jurisdictions": ["KR"],
        "rating": {
            "method": "TIERED",
            "basis": "PURCHASE_PRICE",
            "tiers": [
                {"up_to_minor": 150000, "premium_minor": 4000},
                {"up_to_minor": 300000, "premium_minor": 6000},
                {"up_to_minor": 500000, "premium_minor": 7000},
                {"up_to_minor": 750000, "premium_minor": 10500},
                {"up_to_minor": 1000000, "premium_minor": 14000},
                {"up_to_minor": 1500000, "premium_minor": 21000},
                {"up_to_minor": 2000000, "premium_minor": 28000},
                {"up_to_minor": 3000000, "premium_minor": 42000},
                {"up_to_minor": 5000000, "premium_minor": 70000},
            ],
        },
        "term_rule": {"length": 4, "unit": "YEAR", "starts": "WARRANTY_END"},
        "coverages": [
            {"code": "BREAKDOWN", "name": "제조사 보증 뒤 고장 수리", "limit_minor": 5000000, "deductible_minor": 0},
        ],
        "rules": [
            _obj("purchase_date", "WITHIN_DAYS", 0, "NOT_PURCHASED_TODAY", "제품 구매 당일에만 가입할 수 있습니다"),
            _obj(
                "device_category",
                "IN",
                ["TV", "APPLIANCE", "NOTEBOOK", "TABLET"],
                "DEVICE_NOT_APPLIANCE",
                "TV·가전·노트북·태블릿만 가입할 수 있습니다",
            ),
            _rule("PARTY", "party_type", "EQ", "PERSON", "NOT_PERSON", "개인 고객만 가입할 수 있습니다"),
            _obj(
                "purchase_price_minor",
                "LTE",
                5000000,
                "PRICE_TOO_HIGH",
                "구매가 500만원 이하 제품만 가입할 수 있습니다",
            ),
        ],
        "required_application_fields": ["serial_number", "purchase_date"],
        "target_markets": [
            _tm("objectives", ["EXTEND_WARRANTY"], 0.8, "제조사 보증이 끝난 뒤 4년 동안 고장 수리비를 보장합니다"),
            _tm("objectives", ["REDUCE_PREMIUM"], 0.1, "한 번만 내면 추가 보험료가 없습니다"),
        ],
    },
    {
        "product_code": "KR-TRV-OVERSEAS",
        "product_type": "TRAVEL_PROTECTION",
        "marketing_name": "해외여행 보험",
        "insurable_object_type": "TRIP",
        "billing_period": "PER_TRIP",
        "currency": "KRW",
        "jurisdictions": ["KR"],
        "rating": {"method": "PER_TRIP_DAY", "rate": 1350, "min_premium_minor": 1850},
        "term_rule": {"length": None, "unit": "DAY", "starts": "TRIP_DEPARTURE"},
        "coverages": [
            {
                "code": "OVERSEAS_INJURY_MEDICAL",
                "name": "해외 상해의료비",
                "limit_minor": 30000000,
                "deductible_minor": 0,
            },
            {
                "code": "OVERSEAS_ILLNESS_MEDICAL",
                "name": "해외 질병의료비",
                "limit_minor": 30000000,
                "deductible_minor": 0,
            },
            {"code": "BELONGINGS", "name": "휴대품 손해", "limit_minor": 400000, "deductible_minor": 10000},
            {"code": "FLIGHT_DELAY", "name": "항공기 지연", "limit_minor": 300000, "deductible_minor": 0},
        ],
        "rules": [
            _rule("DERIVED", "trip_length_days", "LTE", 89, "TRIP_TOO_LONG", "89일 이하 여행만 가입할 수 있습니다"),
            _obj("departure_country", "EQ", "KR", "NOT_DEPARTING_KR", "한국에서 출발하는 여행만 가입할 수 있습니다"),
            _rule("DERIVED", "applicant_age", "GTE", 19, "APPLICANT_UNDER_19", "만 19세 이상만 가입할 수 있습니다"),
            _rule(
                "DERIVED", "days_until_departure", "GTE", 0, "TRIP_ALREADY_STARTED", "출발 전에만 가입할 수 있습니다"
            ),
            KR_RESIDENT,
        ],
        "required_application_fields": [
            "departure_date",
            "return_date",
            "destination",
            "traveler_name",
            "traveler_date_of_birth",
            "traveler_gender",
        ],
        "target_markets": [
            _tm("objectives", ["TRAVEL_COVER"], 0.8, "해외여행 중 상해·질병 의료비와 휴대품 손해를 보장합니다"),
            _tm("objectives", ["REDUCE_PREMIUM"], 0.1, "여행 일수만큼만 하루 1,350원을 냅니다"),
        ],
    },
    # ------------------------------------------------------------------------------------------ US
    {
        "product_code": "US-MOB-BOLT",
        "product_type": "MOBILE_INSURANCE",
        "marketing_name": "bolt Mobile Handset Protection",
        "insurable_object_type": "DEVICE",
        "billing_period": "MONTHLY",
        "currency": "USD",
        "jurisdictions": ["US"],
        "rating": {
            "method": "TIERED",
            "basis": "MSRP",
            "tiers": [
                {"up_to_minor": 49999, "premium_minor": 799},
                {"up_to_minor": 99999, "premium_minor": 1199},
                {"up_to_minor": None, "premium_minor": 1399},
            ],
        },
        "term_rule": {"length": 1, "unit": "MONTH", "starts": "PURCHASE_DATE", "auto_renew": True},
        "coverages": [
            {"code": "REPAIR", "name": "Repair", "limit_minor": 100000, "deductible_minor": 9900},
            {"code": "REPLACEMENT", "name": "Replacement", "limit_minor": 100000, "deductible_minor": 19900},
        ],
        "rules": [
            _obj("device_category", "IN", ["SMARTPHONE"], "DEVICE_NOT_SMARTPHONE", "Smartphones only"),
            _obj("purchase_date", "WITHIN_DAYS", 60, "PURCHASE_TOO_OLD", "Must enrol within 60 days of purchase"),
            _obj("condition", "EQ", "NEW", "DEVICE_NOT_NEW", "New devices only"),
            US_RESIDENT,
        ],
        "required_application_fields": ["imei", "device_model", "purchase_date", "proof_of_purchase"],
        "target_markets": [
            _tm("objectives", ["PROTECT_DEVICE"], 0.8, "Covers repair or replacement of a damaged or broken phone"),
            _tm("objectives", ["REDUCE_PREMIUM"], 0.1, "Month-to-month; cancel any time"),
        ],
    },
    {
        "product_code": "US-DEV-LAPTOP-2Y",
        "product_type": "DEVICE_PROTECTION",
        "marketing_name": "2-Year Laptop Protection with Accidents",
        "insurable_object_type": "DEVICE",
        "billing_period": "ONE_TIME",
        "currency": "USD",
        "jurisdictions": ["US"],
        "rating": {
            "method": "TIERED",
            "basis": "PURCHASE_PRICE",
            "tiers": [
                {"up_to_minor": 9999, "premium_minor": 2000},
                {"up_to_minor": 49999, "premium_minor": 5000},
                {"up_to_minor": 99999, "premium_minor": 9000},
                {"up_to_minor": 149999, "premium_minor": 13000},
                {"up_to_minor": None, "premium_minor": 18000},
            ],
        },
        "term_rule": {"length": 24, "unit": "MONTH", "starts": "PURCHASE_DATE"},
        "coverages": [
            {
                "code": "ACCIDENTAL_DAMAGE",
                "name": "Drops, spills and cracked screens",
                "limit_minor": 250000,
                "deductible_minor": 0,
            },
            {
                "code": "BREAKDOWN",
                "name": "Mechanical and electrical failure",
                "limit_minor": 250000,
                "deductible_minor": 0,
            },
        ],
        "rules": [
            _obj("device_category", "IN", ["NOTEBOOK"], "DEVICE_NOT_LAPTOP", "Laptops only"),
            _obj("purchase_date", "WITHIN_DAYS", 30, "PURCHASE_TOO_OLD", "Must enrol within 30 days of purchase"),
            _obj(
                "condition",
                "IN",
                ["NEW", "MFR_REFURBISHED"],
                "DEVICE_NOT_NEW",
                "New or manufacturer-refurbished laptops only",
            ),
            US_RESIDENT,
        ],
        "required_application_fields": ["purchase_price", "purchase_date", "serial_number", "order_number"],
        "target_markets": [
            _tm("objectives", ["PROTECT_DEVICE"], 0.8, "Covers accidental damage to a new laptop for two years"),
            _tm("objectives", ["EXTEND_WARRANTY"], 0.3, "Also covers mechanical failure after the maker's warranty"),
        ],
    },
    {
        "product_code": "US-EW-TV-3Y",
        "product_type": "EXTENDED_WARRANTY",
        "marketing_name": "3-Year TV Protection",
        "insurable_object_type": "DEVICE",
        "billing_period": "ONE_TIME",
        "currency": "USD",
        "jurisdictions": ["US"],
        "rating": {
            "method": "TIERED",
            "basis": "PURCHASE_PRICE",
            "tiers": [
                {"up_to_minor": 49999, "premium_minor": 5000},
                {"up_to_minor": 59999, "premium_minor": 7500},
                {"up_to_minor": 124999, "premium_minor": 10000},
                {"up_to_minor": None, "premium_minor": 15000},
            ],
        },
        "term_rule": {"length": 3, "unit": "YEAR", "starts": "PURCHASE_DATE"},
        "coverages": [
            {
                "code": "BREAKDOWN",
                "name": "Mechanical and electrical failure, wear and tear",
                "limit_minor": 250000,
                "deductible_minor": 0,
            },
        ],
        "rules": [
            _obj("device_category", "IN", ["TV"], "DEVICE_NOT_TV", "TVs only"),
            _obj("purchase_date", "WITHIN_DAYS", 30, "PURCHASE_TOO_OLD", "Must enrol within 30 days of purchase"),
            _rule("PARTY", "party_type", "EQ", "PERSON", "NOT_PERSON", "Personal (non-commercial) use only"),
            US_RESIDENT,
        ],
        "required_application_fields": ["purchase_price", "purchase_date", "serial_number", "order_number"],
        "target_markets": [
            _tm("objectives", ["EXTEND_WARRANTY"], 0.8, "Covers TV breakdowns for three years from purchase"),
        ],
    },
    {
        "product_code": "US-TRV-SINGLE",
        "product_type": "TRAVEL_PROTECTION",
        "marketing_name": "Single Trip Protection",
        "insurable_object_type": "TRIP",
        "billing_period": "PER_TRIP",
        "currency": "USD",
        "jurisdictions": ["US"],
        "rating": {"method": "PERCENT", "basis": "TRIP_COST", "rate": 0.06, "min_premium_minor": 5000},
        "term_rule": {"length": None, "unit": "DAY", "starts": "TRIP_DEPARTURE"},
        "coverages": [
            {"code": "TRIP_CANCELLATION", "name": "Trip cancellation", "limit_minor": 10000000, "deductible_minor": 0},
            {"code": "TRIP_INTERRUPTION", "name": "Trip interruption", "limit_minor": 15000000, "deductible_minor": 0},
            {"code": "EMERGENCY_MEDICAL", "name": "Emergency medical", "limit_minor": 5000000, "deductible_minor": 0},
            {
                "code": "EMERGENCY_TRANSPORT",
                "name": "Emergency transportation",
                "limit_minor": 50000000,
                "deductible_minor": 0,
            },
            {"code": "BAGGAGE", "name": "Baggage loss/damage", "limit_minor": 100000, "deductible_minor": 0},
            {"code": "BAGGAGE_DELAY", "name": "Baggage delay", "limit_minor": 30000, "deductible_minor": 0},
            {"code": "TRAVEL_DELAY", "name": "Travel delay", "limit_minor": 80000, "deductible_minor": 0},
        ],
        "rules": [
            US_RESIDENT,
            _rule("DERIVED", "trip_length_days", "LTE", 180, "TRIP_TOO_LONG", "Trips of 180 days or fewer"),
            _rule("DERIVED", "days_until_departure", "GTE", 0, "TRIP_ALREADY_STARTED", "Must enrol before departure"),
        ],
        "required_application_fields": ["destination", "departure_date", "return_date", "traveler_age", "trip_cost"],
        "target_markets": [
            _tm("objectives", ["TRAVEL_COVER"], 0.8, "Protects trip costs and covers emergency medical care abroad"),
        ],
    },
]
