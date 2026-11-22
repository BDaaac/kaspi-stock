import orders_sync as o
for x in o.kaspi_window(["NEW", "SIGN_REQUIRED", "PICKUP", "DELIVERY", "KASPI_DELIVERY", "ARCHIVE"], 42):
    a = x.get("attributes") or {}
    kd = a.get("kaspiDelivery") or {}
    if a.get("status") not in ("COMPLETED", "ACCEPTED_BY_MERCHANT", "APPROVED_BY_BANK") or kd.get("returnedToWarehouse"):
        dms = o.ms_order_demands(f"kaspi-{a.get('code')}", str(a.get("code")))
        print("K|", a.get("code"), x.get("_state") or a.get("state"), a.get("status"), "| передан курьеру:", bool(kd.get("courierTransmissionDate")),
              "| returnedToWarehouse:", kd.get("returnedToWarehouse"), "| отгрузок МС:", len(dms),
              "| возврат в МС:", any(o.ms_has_return(d) for d in dms), "|", a.get("cancellationReason"))
