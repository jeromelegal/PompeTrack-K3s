import pandas as pd

    
# def shaping_metrics(list_metrics):
#     categories, parameters, dates, performers, values, units, devices = [], [], [], [], [], [], []
    
#     for metric in list_metrics:
#         categories.append(metric.get("category")[0].get("coding")[0].get("display"))
#         parameters.append(metric.get("code").get("coding")[0].get("display"))
#         date = None
#         try:
#             date = metric.get("effectiveDateTime") or metric["effectivePeriod"]["start"]
#         except Exception:
#             date = None
#         dates.append(date)
#         performer = None
#         try: 
#             performer = metric.get("performer")[0].get("display")
#         except Exception:
#             performer = None
#         performers.append(performer)
#         value = None
#         try:
#             value = metric.get("valueQuantity").get("value")
#         except Exception:
#             value = None
#         values.append(value)
#         unit=None
#         try:
#             unit = metric.get("valueQuantity").get("unit")
#         except Exception:
#             unit = None
#         units.append(unit)
#         device = None
#         try:
#             device = metric.get("device").get("display")
#         except Exception:
#             device = None
#         devices.append(device)
#     metrics = {
#         "category": categories,
#         "parameter": parameters,
#         "timestamp": dates,
#         "performer": performers,
#         "value": values,
#         "unit": units,
#         "device": devices
#         }
#     df = pd.DataFrame(metrics)
#     return df

import pandas as pd

def shaping_metrics(list_metrics):
    rows = []

    for metric in list_metrics:
        # Common field
        category = None
        if metric.get("category"):
            coding = metric["category"][0].get("coding")
            if coding:
                category = coding[0].get("display")
        timestamp = (
            metric.get("effectiveDateTime")
            or metric.get("effectivePeriod", {}).get("start")
        )
        performer = None
        if metric.get("performer"):
            performer = metric["performer"][0].get("display")
        device = None
        if metric.get("device"):
            device = metric["device"].get("display")

        # Observation with 'component'
        if "component" in metric and metric["component"]:
            for comp in metric["component"]:
                parameter = None
                coding = comp.get("code", {}).get("coding")
                if coding:
                    parameter = coding[0].get("display")
                value = None
                unit = None
                if comp.get("valueQuantity"):
                    value = comp["valueQuantity"].get("value")
                    unit = comp["valueQuantity"].get("unit")
                rows.append({
                    "category": category,
                    "parameter": parameter,
                    "timestamp": timestamp,
                    "performer": performer,
                    "value": value,
                    "unit": unit,
                    "device": device
                })

        # Simple observation
        else:
            parameter = None
            coding = metric.get("code", {}).get("coding")
            if coding:
                parameter = coding[0].get("display")

            value = None
            unit = None
            if metric.get("valueQuantity"):
                value = metric["valueQuantity"].get("value")
                unit = metric["valueQuantity"].get("unit")

            rows.append({
                "category": category,
                "parameter": parameter,
                "timestamp": timestamp,
                "performer": performer,
                "value": value,
                "unit": unit,
                "device": device
            })

    return pd.DataFrame(rows)

full_metric = {'category': [{'coding': [{'display': 'Vitals'}]}], 'code': {'coding': [{'display': 'Heart rate'}]}, 'device': {'display': 'Polar H10'}, 'effectiveDateTime': '2025-01-01T10:00:00Z'}