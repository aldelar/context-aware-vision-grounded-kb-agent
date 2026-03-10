# fn_convert_cu — Content Understanding HTML→Markdown converter
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

# Copy shared package, function package, host.json, and function entry point
COPY shared/ shared/
COPY fn_convert_cu/ fn_convert_cu/
COPY host.json .
COPY fn_convert_cu/function_app.py .

# Install dependencies
RUN pip install --no-cache-dir ./shared ./fn_convert_cu
