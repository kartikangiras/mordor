"""Lambda entry for the sample step (DESIGN.md §11). The logic lives in sample/schools.py and is
invoked by forecast/steps.py so the state machine and the local CLI share one code path."""
from forecast.steps import sample_handler as handler  # noqa: F401
