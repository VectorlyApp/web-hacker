import json
from web_hacker.data_models.production_routine import (
    Routine, 
    RoutineFetchOperation, 
    Endpoint, 
    HTTPMethod, 
    Parameter, 
    ParameterType, 
    RoutineOperationTypes
)

routine = Routine(
    name="USA Spending Award Search",
    description="Search spending by award on usaspending.gov. Mimicks a specific curl request.",
    parameters=[
        Parameter(
            name="key_words",
            type=ParameterType.STRING,
            description="Keywords to search for, as a stringified list of quoted strings (e.g. '\"keyword1\", \"keyword2\"').",
            default='"ukaine", "drone"',
            examples=['"ukaine", "drone"'],
            pattern=r'^"[^"]+"(?:,\s*"[^"]+")*$'
        ),
        Parameter(
            name="start_date",
            type=ParameterType.DATE,
            description="Start date for the time period filter",
            default="2007-10-01",
            format="YYYY-MM-DD"
        ),
        Parameter(
            name="end_date",
            type=ParameterType.DATE,
            description="End date for the time period filter",
            default="2026-09-30",
            format="YYYY-MM-DD"
        )
    ],
    operations=[
        RoutineFetchOperation(
            type=RoutineOperationTypes.FETCH,
            session_storage_key="spending_results",
            endpoint=Endpoint(
                url="https://api.usaspending.gov/api/v2/search/spending_by_award/",
                method=HTTPMethod.POST,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body={
                    "filters": {
                        "keywords": ["{{key_words}}"],
                        "time_period": [{
                            "start_date": "{{start_date}}",
                            "end_date": "{{end_date}}"
                        }],
                        "award_type_codes": ["A", "B", "C", "D"]
                    },
                    "page": 1,
                    "limit": 100,
                    "sort": "Award Amount",
                    "order": "desc",
                    "auditTrail": "Results Table - Spending by award search",
                    "fields": [
                        "Award ID",
                        "Recipient Name",
                        "Award Amount",
                        "Total Outlays",
                        "Description",
                        "Contract Award Type",
                        "Recipient UEI",
                        "Recipient Location",
                        "Primary Place of Performance",
                        "def_codes",
                        "COVID-19 Obligations",
                        "COVID-19 Outlays",
                        "Infrastructure Obligations",
                        "Infrastructure Outlays",
                        "Awarding Agency",
                        "Awarding Sub Agency",
                        "Start Date",
                        "End Date",
                        "NAICS",
                        "PSC",
                        "recipient_id",
                        "prime_award_recipient_id"
                    ],
                    "spending_level": "awards"
                }
            )
        )
    ]
)

# Fix placeholders to ensure correct quoting for interpolated values
routine.fix_placeholders()

# Output the routine JSON
print(routine.model_dump_json(indent=2))

# save to file
with open("routine.json", "w") as f:
    f.write(routine.model_dump_json(indent=2))

# save to file
with open("routine.json", "w") as f:
    f.write(routine.model_dump_json(indent=2))

