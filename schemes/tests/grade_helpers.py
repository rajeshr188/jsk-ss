from datetime import time

from schemes.models import (
    MetalGrade,
    PaymentOperationsControl,
    PaymentScheduleWindow,
    SchemeAccount,
    SchemePlanOffering,
)


GRADE_DEFINITIONS = {
    MetalGrade.GOLD_22K_916: {
        "metal": MetalGrade.Metal.GOLD,
        "display_name": "22K Gold",
        "fineness": "0.916000",
        "display_order": 10,
    },
    MetalGrade.GOLD_24K_9999: {
        "metal": MetalGrade.Metal.GOLD,
        "display_name": "24K Gold",
        "fineness": "0.999900",
        "display_order": 20,
    },
    MetalGrade.SILVER_999: {
        "metal": MetalGrade.Metal.SILVER,
        "display_name": "999 Silver",
        "fineness": "0.999000",
        "display_order": 30,
    },
}


def ensure_metal_grades():
    for code, values in GRADE_DEFINITIONS.items():
        MetalGrade.objects.get_or_create(code=code, defaults=values)
    control, _created = PaymentOperationsControl.objects.get_or_create(
        pk=PaymentOperationsControl.SINGLETON_PK
    )
    for weekday in PaymentScheduleWindow.Weekday.values:
        PaymentScheduleWindow.objects.get_or_create(
            control=control,
            weekday=weekday,
            defaults={
                "enabled": True,
                "opens_at": time(9, 0),
                "closes_at": time(13 if weekday == 6 else 21, 0),
            },
        )


def metal_grade_for(metal, *, code=None):
    ensure_metal_grades()
    if code is None:
        code = (
            MetalGrade.GOLD_24K_9999
            if metal == MetalGrade.Metal.GOLD
            else MetalGrade.SILVER_999
        )
    return MetalGrade.objects.get(code=code)


def grade_for_mode(plan, mode, *, code=None):
    if mode == SchemeAccount.SavingsMode.CASH:
        return None
    if code is None:
        code = (
            MetalGrade.GOLD_24K_9999
            if mode == SchemeAccount.SavingsMode.GOLD
            else MetalGrade.SILVER_999
        )
    grade = metal_grade_for(mode, code=code)
    SchemePlanOffering.objects.update_or_create(
        plan=plan,
        metal_grade=grade,
        defaults={"active": True},
    )
    return grade


def enrolment_grade_kwargs(plan, mode, *, code=None):
    grade = grade_for_mode(plan, mode, code=code)
    if grade is None:
        return {"savings_mode": SchemeAccount.SavingsMode.CASH}
    return {"metal_grade": grade}
