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
    name="USA Spending Award Count",
    description="Get spending award counts from usaspending.gov. Mimicks a specific curl request.",
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
            session_storage_key="spending_counts",
            endpoint=Endpoint(
                url="https://api.usaspending.gov/api/v2/search/spending_by_award_count/",
                method=HTTPMethod.POST,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "x-requested-with": "USASpendingFrontend"
                },
                body={
                    "filters": {
                        "keywords": ["{{key_words}}"],
                        "time_period": [{
                            "start_date": "{{start_date}}",
                            "end_date": "{{end_date}}"
                        }]
                    },
                    "spending_level": "awards",
                    "auditTrail": "Results View - Tab Counts"
                }
            )
        ),
        # Return the data we fetched
        {
            "type": "return",
            "session_storage_key": "spending_counts"
        }
    ]
)

# Fix placeholders to ensure correct quoting for interpolated values
routine.fix_placeholders()

# Output the routine JSON
print(routine.model_dump_json(indent=2))

# Save to file
with open("routine_count.json", "w") as f:
    f.write(routine.model_dump_json(indent=2))


