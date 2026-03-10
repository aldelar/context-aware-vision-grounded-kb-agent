# fn_convert_markitdown — MarkItDown HTML→Markdown converter
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

COPY shared/ shared/
COPY fn_convert_markitdown/ fn_convert_markitdown/
COPY host.json .
COPY fn_convert_markitdown/function_app.py .

RUN pip install --no-cache-dir ./shared ./fn_convert_markitdown
