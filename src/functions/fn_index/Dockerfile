# fn_index — Search index builder
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

COPY shared/ shared/
COPY fn_index/ fn_index/
COPY host.json .
COPY fn_index/function_app.py .

RUN pip install --no-cache-dir ./shared ./fn_index
