// ---------------------------------------------------------------------------
// main.bicep — Context Aware & Vision Grounded KB Agent
// ---------------------------------------------------------------------------
// Provisions all Azure resources for the context-aware, vision-grounded KB agent:
//   - Monitoring (Log Analytics + Application Insights)
//   - Storage (Staging + Serving accounts)
//   - Azure AI Services (Content Understanding + Embeddings + Agent model)
//   - Azure AI Search (Basic tier, vector + full-text)
//   - Azure Functions (Python, Container App with custom Docker container)
//
// All inter-service auth uses managed identity (no keys/secrets).
// ---------------------------------------------------------------------------

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@minLength(2)
@maxLength(8)
@description('Short project identifier used in all resource names (e.g. "myproj"). Alphanumeric and hyphens only. Max 8 chars to fit Azure Storage 24-char limit.')
param projectName string

@minLength(2)
@maxLength(7)
@description('Name of the environment (e.g., dev, staging, prod). Use "prod" for production.')
param environmentName string

@description('Primary Azure region for all resources')
param location string = 'eastus2'

@description('Tags to apply to all resources')
param tags object = {}

@description('Azure AI Search SKU')
@allowed(['free', 'basic', 'standard'])
param searchSkuName string = 'basic'

@description('Principal ID of the deployer (human user). AZD populates this via AZURE_PRINCIPAL_ID.')
param principalId string = ''

@description('Entra App Registration client ID for web app Easy Auth')
param entraClientId string = ''

@description('Entra App Registration client secret for web app Easy Auth')
@secure()
param entraClientSecret string = ''

@description('Chainlit auth secret used by the web app for JWT session signing')
@secure()
param chainlitAuthSecret string = ''

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

// Base name for resources: kebab-case, e.g. '{project}-dev'
var baseName = '${projectName}-${environmentName}'

// Storage account names: lowercase alphanumeric, max 24 chars
// Worst case: st(2) + projectName(8) + staging(7) + env(7) = 24
var stagingStorageName = replace('st${projectName}staging${environmentName}', '-', '')
var servingStorageName = replace('st${projectName}serving${environmentName}', '-', '')
var functionsStorageName = replace('st${projectName}func${environmentName}', '-', '')

// Merge default tags
var defaultTags = union(tags, {
  'azd-env-name': environmentName
  project: 'kb-ingestion'
})

// ---------------------------------------------------------------------------
// Module: Monitoring
// ---------------------------------------------------------------------------
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    deployerPrincipalId: principalId
    aiServicesPrincipalId: aiServices.outputs.aiServicesPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Module: Staging Storage Account
// ---------------------------------------------------------------------------
module stagingStorage 'modules/storage.bicep' = {
  name: 'staging-storage'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
  }
}

// ---------------------------------------------------------------------------
// Module: Serving Storage Account
// ---------------------------------------------------------------------------
module servingStorage 'modules/storage.bicep' = {
  name: 'serving-storage'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
  }
}

// ---------------------------------------------------------------------------
// Module: Azure AI Services (Content Understanding + Models)
// ---------------------------------------------------------------------------
module aiServices 'modules/ai-services.bicep' = {
  name: 'ai-services'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: Azure AI Search
// ---------------------------------------------------------------------------
module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
  }
}

// ---------------------------------------------------------------------------
// Module: Functions Runtime Storage Account (shared by all function Container Apps)
// ---------------------------------------------------------------------------
module functionsStorage 'modules/storage.bicep' = {
  name: 'functions-storage'
  params: {
    location: location
    storageAccountName: functionsStorageName
    tags: defaultTags
    containerNames: ['deployments']
  }
}

// ---------------------------------------------------------------------------
// Module: Function Apps (one per function)
// ---------------------------------------------------------------------------

// fn_convert_cu — Content Understanding HTML→Markdown converter
module funcConvertCu 'modules/function-app.bicep' = {
  name: 'func-convert-cu'
  params: {
    location: location
    baseName: baseName
    functionName: 'cvt-cu'
    azdServiceName: 'func-convert-cu'
    tags: defaultTags
    functionsStorageAccountName: functionsStorageName
    envVars: [
      { name: 'AzureWebJobsStorage__accountName', value: functionsStorageName }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.appInsightsConnectionString }
      { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
      { name: 'STAGING_BLOB_ENDPOINT', value: stagingStorage.outputs.blobEndpoint }
      { name: 'SERVING_BLOB_ENDPOINT', value: servingStorage.outputs.blobEndpoint }
      { name: 'AI_SERVICES_ENDPOINT', value: aiServices.outputs.aiServicesEndpoint }
    ]
    deployerPrincipalId: principalId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    containerAppsEnvId: containerAppsEnv.outputs.containerAppsEnvId
  }
  dependsOn: [functionsStorage]
}

// fn_convert_mistral — Mistral Document AI HTML→Markdown converter
module funcConvertMistral 'modules/function-app.bicep' = {
  name: 'func-convert-mistral'
  params: {
    location: location
    baseName: baseName
    functionName: 'cvt-mis'
    azdServiceName: 'func-convert-mistral'
    tags: defaultTags
    functionsStorageAccountName: functionsStorageName
    envVars: [
      { name: 'AzureWebJobsStorage__accountName', value: functionsStorageName }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.appInsightsConnectionString }
      { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
      { name: 'STAGING_BLOB_ENDPOINT', value: stagingStorage.outputs.blobEndpoint }
      { name: 'SERVING_BLOB_ENDPOINT', value: servingStorage.outputs.blobEndpoint }
      { name: 'AI_SERVICES_ENDPOINT', value: aiServices.outputs.aiServicesEndpoint }
      { name: 'MISTRAL_DEPLOYMENT_NAME', value: aiServices.outputs.mistralDeploymentName }
    ]
    deployerPrincipalId: principalId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    containerAppsEnvId: containerAppsEnv.outputs.containerAppsEnvId
  }
  dependsOn: [functionsStorage]
}

// fn_convert_markitdown — MarkItDown HTML→Markdown converter
module funcConvertMarkitdown 'modules/function-app.bicep' = {
  name: 'func-convert-markitdown'
  params: {
    location: location
    baseName: baseName
    functionName: 'cvt-mit'
    azdServiceName: 'func-convert-markitdown'
    tags: defaultTags
    functionsStorageAccountName: functionsStorageName
    envVars: [
      { name: 'AzureWebJobsStorage__accountName', value: functionsStorageName }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.appInsightsConnectionString }
      { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
      { name: 'STAGING_BLOB_ENDPOINT', value: stagingStorage.outputs.blobEndpoint }
      { name: 'SERVING_BLOB_ENDPOINT', value: servingStorage.outputs.blobEndpoint }
      { name: 'AI_SERVICES_ENDPOINT', value: aiServices.outputs.aiServicesEndpoint }
    ]
    deployerPrincipalId: principalId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    containerAppsEnvId: containerAppsEnv.outputs.containerAppsEnvId
  }
  dependsOn: [functionsStorage]
}

// fn_index — Search index builder
module funcIndex 'modules/function-app.bicep' = {
  name: 'func-index'
  params: {
    location: location
    baseName: baseName
    functionName: 'idx'
    azdServiceName: 'func-index'
    tags: defaultTags
    functionsStorageAccountName: functionsStorageName
    envVars: [
      { name: 'AzureWebJobsStorage__accountName', value: functionsStorageName }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.appInsightsConnectionString }
      { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
      { name: 'SERVING_BLOB_ENDPOINT', value: servingStorage.outputs.blobEndpoint }
      { name: 'AI_SERVICES_ENDPOINT', value: aiServices.outputs.aiServicesEndpoint }
      { name: 'EMBEDDING_DEPLOYMENT_NAME', value: aiServices.outputs.embeddingDeploymentName }
      { name: 'SEARCH_ENDPOINT', value: search.outputs.searchEndpoint }
      { name: 'SEARCH_INDEX_NAME', value: 'kb-articles' }
    ]
    deployerPrincipalId: principalId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    containerAppsEnvId: containerAppsEnv.outputs.containerAppsEnvId
  }
  dependsOn: [functionsStorage]
}

// ---------------------------------------------------------------------------
// Module: Container Registry
// ---------------------------------------------------------------------------
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: Container Apps Environment (shared by web app, agent, and functions)
// ---------------------------------------------------------------------------
module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'container-apps-env'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
  }
}

// Agent endpoint via APIM gateway root. The APIM KB Agent API is published
// at the gateway root, so the web app should call {gateway}/responses.
var agentApimEndpoint = apim.outputs.apimGatewayUrl

// ---------------------------------------------------------------------------
// Module: Container App (Context Aware & Vision Grounded KB Agent)
// ---------------------------------------------------------------------------
module containerApp 'modules/container-app.bicep' = {
  name: 'container-app'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    containerAppsEnvId: containerAppsEnv.outputs.containerAppsEnvId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    aiServicesEndpoint: aiServices.outputs.aiServicesEndpoint
    embeddingDeploymentName: aiServices.outputs.embeddingDeploymentName
    searchEndpoint: search.outputs.searchEndpoint
    servingBlobEndpoint: servingStorage.outputs.blobEndpoint
    entraClientId: entraClientId
    entraClientSecret: entraClientSecret
    agentEndpoint: agentApimEndpoint
    cosmosEndpoint: cosmosDb.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmosDb.outputs.cosmosDatabaseName
    chainlitAuthSecret: chainlitAuthSecret
  }
}

// ---------------------------------------------------------------------------
// Module: Foundry Project (child of AI Services)
// ---------------------------------------------------------------------------
module foundryProject 'modules/foundry-project.bicep' = {
  name: 'foundry-project'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    deployerPrincipalId: principalId
    appInsightsResourceId: monitoring.outputs.appInsightsId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    webAppPrincipalId: containerApp.outputs.containerAppPrincipalId
    apimResourceId: apim.outputs.apimResourceId
  }
}

// ---------------------------------------------------------------------------
// Module: Agent Container App (KB Agent — external HTTPS + JWT auth)
// ---------------------------------------------------------------------------
module agentContainerApp 'modules/agent-container-app.bicep' = {
  name: 'agent-container-app'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    containerAppsEnvId: containerAppsEnv.outputs.containerAppsEnvId
    containerAppsEnvDefaultDomain: containerAppsEnv.outputs.containerAppsEnvDefaultDomain
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    aiServicesEndpoint: aiServices.outputs.aiServicesEndpoint
    searchEndpoint: search.outputs.searchEndpoint
    servingBlobEndpoint: servingStorage.outputs.blobEndpoint
    projectEndpoint: foundryProject.outputs.projectEndpoint
    agentModelDeploymentName: aiServices.outputs.agentDeploymentName
    embeddingDeploymentName: aiServices.outputs.embeddingDeploymentName
    applicationInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    cosmosEndpoint: cosmosDb.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmosDb.outputs.cosmosDatabaseName
  }
}

// ---------------------------------------------------------------------------
// Module: API Management — AI Gateway
// ---------------------------------------------------------------------------
module apim 'modules/apim.bicep' = {
  name: 'apim'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: APIM Agent API definition + backend
// ---------------------------------------------------------------------------
module apimAgentApi 'modules/apim-agent-api.bicep' = {
  name: 'apim-agent-api'
  params: {
    apimName: apim.outputs.apimName
    agentExternalUrl: agentContainerApp.outputs.agentExternalUrl
  }
}

// ---------------------------------------------------------------------------
// Module: Cosmos DB (conversation history)
// ---------------------------------------------------------------------------
module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant per-function managed identity access to services
// ---------------------------------------------------------------------------

// --- Staging storage: Blob Data Contributor (3 convert functions) ---
module stagingStorageRoleCvtCu 'modules/storage.bicep' = {
  name: 'staging-role-cvt-cu'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
    contributorPrincipalId: funcConvertCu.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

module stagingStorageRoleCvtMis 'modules/storage.bicep' = {
  name: 'staging-role-cvt-mis'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
    contributorPrincipalId: funcConvertMistral.outputs.functionAppPrincipalId
  }
}

module stagingStorageRoleCvtMit 'modules/storage.bicep' = {
  name: 'staging-role-cvt-mit'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
    contributorPrincipalId: funcConvertMarkitdown.outputs.functionAppPrincipalId
  }
}

// --- Serving storage: Blob Data Contributor (3 converts) + Reader (fn_index) ---
module servingStorageRoleCvtCu 'modules/storage.bicep' = {
  name: 'serving-role-cvt-cu'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    contributorPrincipalId: funcConvertCu.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

module servingStorageRoleCvtMis 'modules/storage.bicep' = {
  name: 'serving-role-cvt-mis'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    contributorPrincipalId: funcConvertMistral.outputs.functionAppPrincipalId
  }
}

module servingStorageRoleCvtMit 'modules/storage.bicep' = {
  name: 'serving-role-cvt-mit'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    contributorPrincipalId: funcConvertMarkitdown.outputs.functionAppPrincipalId
  }
}

module servingStorageRoleIdx 'modules/storage.bicep' = {
  name: 'serving-role-idx'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    readerPrincipalId: funcIndex.outputs.functionAppPrincipalId
  }
}

// --- AI Services: per-function roles ---
// CU converter: full Cognitive Services User + OpenAI User (+ deployer)
module aiServicesRoleCvtCu 'modules/ai-services-role.bicep' = {
  name: 'ai-role-cvt-cu'
  params: {
    baseName: baseName
    cognitiveServicesUserPrincipalId: funcConvertCu.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

// Mistral converter: full Cognitive Services User + OpenAI User
module aiServicesRoleCvtMis 'modules/ai-services-role.bicep' = {
  name: 'ai-role-cvt-mis'
  params: {
    baseName: baseName
    cognitiveServicesUserPrincipalId: funcConvertMistral.outputs.functionAppPrincipalId
  }
}

// MarkItDown converter: OpenAI User only
module aiServicesRoleCvtMit 'modules/ai-services-role.bicep' = {
  name: 'ai-role-cvt-mit'
  params: {
    baseName: baseName
    openAIOnlyUserPrincipalId: funcConvertMarkitdown.outputs.functionAppPrincipalId
  }
}

// Index function: OpenAI User only
module aiServicesRoleIdx 'modules/ai-services-role.bicep' = {
  name: 'ai-role-idx'
  params: {
    baseName: baseName
    openAIOnlyUserPrincipalId: funcIndex.outputs.functionAppPrincipalId
  }
}

// --- AI Search: Index Data Contributor + Service Contributor (fn_index only) ---
module searchRoleIdx 'modules/search.bicep' = {
  name: 'search-role-idx'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexContributorPrincipalId: funcIndex.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant Container App managed identity access to services
// ---------------------------------------------------------------------------

// ACR: AcrPull role for webapp is now inside container-app.bicep module to avoid
// race condition during initial provisioning (revision needs ACR access immediately).

// Serving storage: Blob Data Reader (Container App MI — read-only for image proxy)
module servingStorageReaderRole 'modules/storage.bicep' = {
  name: 'serving-storage-reader-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    readerPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// AI Services: Cognitive Services OpenAI User (Container App MI — OpenAI only, no CU)
module aiServicesWebAppRole 'modules/ai-services-role.bicep' = {
  name: 'ai-services-webapp-role'
  params: {
    baseName: baseName
    openAIOnlyUserPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// AI Search: Search Index Data Reader (Container App MI — read-only for querying)
module searchWebAppRole 'modules/search.bicep' = {
  name: 'search-webapp-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexReaderPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// Cosmos DB: Data Contributor (Container App MI — read/write conversations)
// Uses a dedicated role module to avoid re-deploying the full cosmos-db module.
module cosmosDbWebAppRole 'modules/cosmos-db-role.bicep' = {
  name: 'cosmos-db-webapp-role'
  params: {
    baseName: baseName
    principalId: containerApp.outputs.containerAppPrincipalId
  }
}

// Cosmos DB: Data Contributor (Agent CA MI — read/write sessions)
module cosmosDbAgentRole 'modules/cosmos-db-role.bicep' = {
  name: 'cosmos-db-agent-role'
  params: {
    baseName: baseName
    principalId: agentContainerApp.outputs.agentPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant Agent Container App managed identity access to services
// The agent runs as a Container App and needs RBAC on AI Services, Search,
// and serving storage for agentic retrieval and model calls.
// ---------------------------------------------------------------------------

// AI Services: Cognitive Services User + OpenAI User (agent CA MI)
module aiServicesAgentContainerAppRole 'modules/ai-services-role.bicep' = {
  name: 'ai-services-agent-ca-role'
  params: {
    baseName: baseName
    cognitiveServicesUserPrincipalId: agentContainerApp.outputs.agentPrincipalId
  }
}

// AI Search: Index Data Reader + Service Contributor (agent CA MI — for agentic retrieval)
module searchAgentContainerAppRole 'modules/search.bicep' = {
  name: 'search-agent-ca-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexReaderPrincipalId: agentContainerApp.outputs.agentPrincipalId
    serviceContributorOnlyPrincipalId: agentContainerApp.outputs.agentPrincipalId
  }
}

// Serving storage: Blob Data Reader (agent CA MI — for image proxy)
module servingStorageAgentContainerAppRole 'modules/storage.bicep' = {
  name: 'serving-storage-agent-ca-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    readerPrincipalId: agentContainerApp.outputs.agentPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Outputs — consumed by AZD and application code
// ---------------------------------------------------------------------------
output AZURE_LOCATION string = location
output RESOURCE_GROUP string = resourceGroup().name

// Storage
output STAGING_STORAGE_ACCOUNT string = stagingStorage.outputs.storageAccountName
output STAGING_BLOB_ENDPOINT string = stagingStorage.outputs.blobEndpoint
output SERVING_STORAGE_ACCOUNT string = servingStorage.outputs.storageAccountName
output SERVING_BLOB_ENDPOINT string = servingStorage.outputs.blobEndpoint

// AI Services
output AI_SERVICES_NAME string = aiServices.outputs.aiServicesName
output AI_SERVICES_ENDPOINT string = aiServices.outputs.aiServicesEndpoint
output EMBEDDING_DEPLOYMENT_NAME string = aiServices.outputs.embeddingDeploymentName
output AGENT_DEPLOYMENT_NAME string = aiServices.outputs.agentDeploymentName
output CU_COMPLETION_DEPLOYMENT_NAME string = aiServices.outputs.cuCompletionDeploymentName
output MISTRAL_DEPLOYMENT_NAME string = aiServices.outputs.mistralDeploymentName

// Search
output SEARCH_SERVICE_NAME string = search.outputs.searchName
output SEARCH_ENDPOINT string = search.outputs.searchEndpoint

// Functions (Container Apps — one per function)
output FUNC_CONVERT_CU_NAME string = funcConvertCu.outputs.functionAppName
output FUNC_CONVERT_CU_URL string = funcConvertCu.outputs.functionAppUrl
output FUNC_CONVERT_MISTRAL_NAME string = funcConvertMistral.outputs.functionAppName
output FUNC_CONVERT_MISTRAL_URL string = funcConvertMistral.outputs.functionAppUrl
output FUNC_CONVERT_MARKITDOWN_NAME string = funcConvertMarkitdown.outputs.functionAppName
output FUNC_CONVERT_MARKITDOWN_URL string = funcConvertMarkitdown.outputs.functionAppUrl
output FUNC_INDEX_NAME string = funcIndex.outputs.functionAppName
output FUNC_INDEX_URL string = funcIndex.outputs.functionAppUrl
output FUNCTIONS_STORAGE_ACCOUNT string = functionsStorageName

// Monitoring
output APPINSIGHTS_NAME string = monitoring.outputs.appInsightsName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString

// Container Registry
output CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.containerRegistryName
output CONTAINER_REGISTRY_LOGIN_SERVER string = containerRegistry.outputs.containerRegistryLoginServer
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.containerRegistryLoginServer

// Web App (Container App)
output WEBAPP_NAME string = containerApp.outputs.containerAppName
output WEBAPP_URL string = containerApp.outputs.containerAppUrl

// Foundry Project (AZURE_AI_* outputs required by AZD agent extension)
output AZURE_AI_PROJECT_ID string = foundryProject.outputs.projectId
output AZURE_AI_PROJECT_ENDPOINT string = foundryProject.outputs.projectEndpoint
output AZURE_AI_PROJECT_NAME string = foundryProject.outputs.projectName
output AZURE_AI_ACCOUNT_NAME string = aiServices.outputs.aiServicesName
output AZURE_OPENAI_ENDPOINT string = replace(aiServices.outputs.aiServicesEndpoint, '.cognitiveservices.azure.com/', '.openai.azure.com/')
output FOUNDRY_PROJECT_NAME string = foundryProject.outputs.projectName
output FOUNDRY_PROJECT_ENDPOINT string = foundryProject.outputs.projectEndpoint

// Agent Container App
output AGENT_APP_NAME string = agentContainerApp.outputs.agentAppName
output AGENT_ENDPOINT string = agentContainerApp.outputs.agentEndpoint
output AGENT_EXTERNAL_URL string = agentContainerApp.outputs.agentExternalUrl

// API Management (AI Gateway)
output APIM_NAME string = apim.outputs.apimName
output APIM_GATEWAY_URL string = apim.outputs.apimGatewayUrl

// Cosmos DB
output COSMOS_ENDPOINT string = cosmosDb.outputs.cosmosEndpoint
output COSMOS_DATABASE_NAME string = cosmosDb.outputs.cosmosDatabaseName
