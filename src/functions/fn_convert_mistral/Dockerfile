# fn_convert_mistral — Mistral Document AI HTML→Markdown converter
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

COPY shared/ shared/
COPY fn_convert_mistral/ fn_convert_mistral/
COPY host.json .
COPY fn_convert_mistral/function_app.py .

RUN pip install --no-cache-dir ./shared ./fn_convert_mistral

# Playwright Chromium — required for HTML→PDF rendering
RUN playwright install --with-deps chromium
