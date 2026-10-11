# Container-image Lambda for the particle run (numpy + Pillow). Built by `sam build` in M4.
FROM public.ecr.aws/lambda/python:3.12
RUN pip install --no-cache-dir "numpy>=2.0" "pillow>=10" "requests>=2.32" "jinja2>=3.1"
COPY common/ ${LAMBDA_TASK_ROOT}/common/
COPY ingest_firms/ ${LAMBDA_TASK_ROOT}/ingest_firms/
COPY ingest_weather/ ${LAMBDA_TASK_ROOT}/ingest_weather/
COPY forecast/ ${LAMBDA_TASK_ROOT}/forecast/
COPY render/ ${LAMBDA_TASK_ROOT}/render/
COPY sample/ ${LAMBDA_TASK_ROOT}/sample/
# sample/{schools,entities}.py import these at module level, and forecast/steps.py
# imports zones lazily for the burning/NDVI summaries. Omitting any of them fails the
# `sample` step with ModuleNotFoundError after prepare/advect/render have already run.
COPY protocol/ ${LAMBDA_TASK_ROOT}/protocol/
COPY records/ ${LAMBDA_TASK_ROOT}/records/
COPY notify/ ${LAMBDA_TASK_ROOT}/notify/
COPY zones/ ${LAMBDA_TASK_ROOT}/zones/
CMD ["forecast.handler.handler"]
